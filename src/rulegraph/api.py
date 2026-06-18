"""FastAPI REST wrapper for rulegraph.

Start:   uvicorn rulegraph.api:app --reload
Install: pip install "rulegraph[api]"
Docs:    http://localhost:8000/docs
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field
except ImportError as exc:
    raise ImportError("API server requires: pip install 'rulegraph[api]'") from exc

from rulegraph import __version__
from rulegraph.rule import RuleArbiter, RuleEdge, RuleNode, RuleStore

app = FastAPI(
    title="rulegraph API",
    description="Natural-language rulebook compiler for game arbitration.",
    version=__version__,
    license_info={
        "name": "MIT",
        "url": "https://github.com/sandeep-alluru/rulegraph/blob/main/LICENSE",
    },
)


class RuleRequest(BaseModel):
    """Request body for POST /rule."""

    rule_id: str = Field(..., description="Unique identifier for this rule.")
    text: str = Field(..., description="Full rule text.")
    node_type: str = Field("mechanic", description="Node type (mechanic, narrative, etc.).")
    tags: list[str] = Field(default_factory=list, description="Free-form tags.")
    source: str = Field("", description="Source book or document.")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    db: str = Field(".rulegraph/rules.db")


class EdgeRequest(BaseModel):
    """Request body for POST /edge."""

    source_id: str = Field(..., description="rule_id of the source node.")
    target_id: str = Field(..., description="rule_id of the target node.")
    relation: str = Field(..., description="Relation type (modifies, supersedes, etc.).")
    condition: str = Field("", description="Condition under which this edge applies.")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    db: str = Field(".rulegraph/rules.db")


class QueryRequest(BaseModel):
    """Request body for POST /query."""

    question: str = Field(..., description="Natural-language question to arbitrate.")
    save: bool = Field(True, description="Whether to persist the result.")
    db: str = Field(".rulegraph/rules.db")


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    version: str


@app.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.post("/rule")
async def add_rule(request: RuleRequest) -> Any:
    """Add a rule node to the graph."""
    store = RuleStore(request.db)
    try:
        node = RuleNode(
            rule_id=request.rule_id,
            text=request.text,
            node_type=request.node_type,
            tags=request.tags,
            source=request.source,
            confidence=request.confidence,
        )
        store.save_node(node)
        return node.to_dict()
    finally:
        store.close()


@app.post("/edge")
async def add_edge(request: EdgeRequest) -> Any:
    """Add an edge between two rule nodes."""
    store = RuleStore(request.db)
    try:
        edge = RuleEdge(
            source_id=request.source_id,
            target_id=request.target_id,
            relation=request.relation,
            condition=request.condition,
            confidence=request.confidence,
        )
        store.save_edge(edge)
        return edge.to_dict()
    finally:
        store.close()


@app.post("/query")
async def query_rules(request: QueryRequest) -> Any:
    """Arbitrate a natural-language question against the stored rules."""
    store = RuleStore(request.db)
    try:
        graph = store.load_graph()
        arbiter = RuleArbiter(graph)
        result = arbiter.query(request.question)
        if request.save:
            store.save_result(result)
        return result.to_dict()
    finally:
        store.close()


@app.get("/rules")
async def list_rules(
    db: str = ".rulegraph/rules.db",
    tag: str | None = None,
    node_type: str | None = None,
) -> Any:
    """Return stored rules, optionally filtered by tag or node_type."""
    store = RuleStore(db)
    try:
        graph = store.load_graph()
        rules = graph.find_rules(tag=tag, node_type=node_type)
        return {
            "rule_count": len(rules),
            "rules": [r.to_dict() for r in rules],
        }
    finally:
        store.close()


@app.get("/results")
async def list_results(db: str = ".rulegraph/rules.db") -> Any:
    """Return all stored arbitration results."""
    store = RuleStore(db)
    try:
        results = store.list_results()
        return {
            "result_count": len(results),
            "results": [r.to_dict() for r in results],
        }
    finally:
        store.close()
