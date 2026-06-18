"""Rule data models — the content-addressed primitives of rulegraph."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _sha16(text: str) -> str:
    """Return the first 16 hex chars of SHA-256(text)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class RuleNode:
    """A single rule extracted from a rulebook, content-addressed by rule_id.

    Two RuleNode objects with the same rule_id always share the same id,
    regardless of when they were created.

    Attributes:
        rule_id: Human-readable identifier (e.g. "PHB.5e.attack_roll").
        text: The full rule text.
        node_type: Semantic category (e.g. "mechanic", "definition", "narrative").
        tags: Free-form labels for filtering (e.g. ["combat", "attack"]).
        source: Source book or document (e.g. "D&D SRD 5.1").
        confidence: Certainty that this is a deterministic rule, in [0.0, 1.0].
        id: SHA-256[:16] of rule_id, set automatically in __post_init__.
    """

    rule_id: str
    text: str
    node_type: str
    tags: list[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 1.0
    id: str = field(init=False)

    def __post_init__(self) -> None:
        self.id = _sha16(self.rule_id)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "text": self.text,
            "node_type": self.node_type,
            "tags": self.tags,
            "source": self.source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RuleNode:
        """Deserialize from a dict produced by to_dict()."""
        node = cls(
            rule_id=d["rule_id"],
            text=d["text"],
            node_type=d["node_type"],
            tags=d.get("tags", []),
            source=d.get("source", ""),
            confidence=d.get("confidence", 1.0),
        )
        return node

    def __repr__(self) -> str:
        return f"RuleNode({self.id!r}: {self.rule_id!r} [{self.node_type}])"


@dataclass
class RuleEdge:
    """A directed relationship between two rules.

    Edges represent how rules interact: one rule may modify, supersede,
    require, or be an exception to another.

    Attributes:
        source_id: rule_id of the source RuleNode.
        target_id: rule_id of the target RuleNode.
        relation: Type of relationship (e.g. "modifies", "supersedes",
            "requires", "exception-to").
        condition: Optional condition under which the edge applies.
        confidence: Certainty that this edge is correct, in [0.0, 1.0].
        id: SHA-256[:16] of "{source_id}|{target_id}|{relation}", auto-set.
    """

    source_id: str
    target_id: str
    relation: str  # "modifies", "supersedes", "requires", "exception-to"
    condition: str = ""
    confidence: float = 1.0
    id: str = field(init=False)

    def __post_init__(self) -> None:
        self.id = _sha16(f"{self.source_id}|{self.target_id}|{self.relation}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "condition": self.condition,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RuleEdge:
        """Deserialize from a dict produced by to_dict()."""
        return cls(
            source_id=d["source_id"],
            target_id=d["target_id"],
            relation=d["relation"],
            condition=d.get("condition", ""),
            confidence=d.get("confidence", 1.0),
        )

    def __repr__(self) -> str:
        return f"RuleEdge({self.source_id!r} --[{self.relation}]--> {self.target_id!r})"


@dataclass
class ArbitrationResult:
    """The structured answer to a query against the rule graph.

    Attributes:
        query: The original question posed.
        answer: The synthesized answer.
        tier: Classification — "determinate" | "indeterminate" | "unknown".
        provenance: List of rule_ids that were used to produce the answer.
        confidence: Aggregate confidence in [0.0, 1.0].
        contradictions: rule_ids of rules that conflict with the answer.
    """

    query: str
    answer: str
    tier: str  # "determinate" | "indeterminate" | "unknown"
    provenance: list[str]
    confidence: float
    contradictions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "query": self.query,
            "answer": self.answer,
            "tier": self.tier,
            "provenance": self.provenance,
            "confidence": self.confidence,
            "contradictions": self.contradictions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ArbitrationResult:
        """Deserialize from a dict produced by to_dict()."""
        return cls(
            query=d["query"],
            answer=d["answer"],
            tier=d["tier"],
            provenance=d.get("provenance", []),
            confidence=d.get("confidence", 0.0),
            contradictions=d.get("contradictions", []),
        )

    def __repr__(self) -> str:
        return (
            f"ArbitrationResult(tier={self.tier!r}, "
            f"confidence={self.confidence:.2f}, "
            f"provenance={len(self.provenance)} rules)"
        )


class RuleGraph:
    """An in-memory directed graph of RuleNode objects connected by RuleEdge objects.

    The graph supports efficient lookup by rule_id, tag, node_type, and
    keyword search in the text field.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, RuleNode] = {}  # keyed by rule_id
        self._edges: list[RuleEdge] = []

    def add_node(self, node: RuleNode) -> None:
        """Add a RuleNode to the graph (idempotent by rule_id)."""
        self._nodes[node.rule_id] = node

    def add_edge(self, edge: RuleEdge) -> None:
        """Add a RuleEdge to the graph.

        Duplicate edges (same source_id, target_id, relation) are silently
        ignored to keep the graph idempotent.
        """
        for existing in self._edges:
            if existing.id == edge.id:
                return
        self._edges.append(edge)

    def get_node(self, rule_id: str) -> RuleNode | None:
        """Return the RuleNode with the given rule_id, or None."""
        return self._nodes.get(rule_id)

    def get_edges(
        self,
        source_id: str | None = None,
        relation: str | None = None,
    ) -> list[RuleEdge]:
        """Return edges, optionally filtered by source_id and/or relation."""
        result = self._edges
        if source_id is not None:
            result = [e for e in result if e.source_id == source_id]
        if relation is not None:
            result = [e for e in result if e.relation == relation]
        return list(result)

    def find_rules(
        self,
        tag: str | None = None,
        node_type: str | None = None,
        text_contains: str | None = None,
    ) -> list[RuleNode]:
        """Search for rules matching any combination of filters.

        Args:
            tag: If given, only nodes whose tags list contains this string.
            node_type: If given, only nodes of this type.
            text_contains: If given, only nodes whose text contains this
                substring (case-insensitive).

        Returns:
            List of matching RuleNode objects in insertion order.
        """
        result = list(self._nodes.values())
        if tag is not None:
            result = [n for n in result if tag in n.tags]
        if node_type is not None:
            result = [n for n in result if n.node_type == node_type]
        if text_contains is not None:
            lower = text_contains.lower()
            result = [n for n in result if lower in n.text.lower()]
        return result

    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self._nodes)

    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self._edges)


class RuleStore:
    """SQLite-backed persistence layer for RuleNode, RuleEdge, and ArbitrationResult objects.

    Attributes:
        path: Path to the SQLite database file.
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS nodes (
        id TEXT NOT NULL,
        rule_id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        node_type TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '[]',
        source TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 1.0
    );
    CREATE TABLE IF NOT EXISTS edges (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        relation TEXT NOT NULL,
        condition TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 1.0
    );
    CREATE TABLE IF NOT EXISTS results (
        query TEXT NOT NULL,
        answer TEXT NOT NULL,
        tier TEXT NOT NULL,
        provenance TEXT NOT NULL DEFAULT '[]',
        confidence REAL NOT NULL DEFAULT 0.0,
        contradictions TEXT NOT NULL DEFAULT '[]',
        recorded_at REAL NOT NULL
    );
    """

    def __init__(self, path: str | Path) -> None:
        import time

        self._time = time
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def save_node(self, node: RuleNode) -> None:
        """Persist a RuleNode (upsert by rule_id)."""
        self._conn.execute(
            """INSERT OR REPLACE INTO nodes
               (id, rule_id, text, node_type, tags, source, confidence)
               VALUES (?,?,?,?,?,?,?)""",
            (
                node.id,
                node.rule_id,
                node.text,
                node.node_type,
                json.dumps(node.tags),
                node.source,
                node.confidence,
            ),
        )
        self._conn.commit()

    def save_edge(self, edge: RuleEdge) -> None:
        """Persist a RuleEdge (upsert by id)."""
        self._conn.execute(
            """INSERT OR REPLACE INTO edges
               (id, source_id, target_id, relation, condition, confidence)
               VALUES (?,?,?,?,?,?)""",
            (
                edge.id,
                edge.source_id,
                edge.target_id,
                edge.relation,
                edge.condition,
                edge.confidence,
            ),
        )
        self._conn.commit()

    def load_graph(self) -> RuleGraph:
        """Load all persisted nodes and edges into a new RuleGraph."""
        graph = RuleGraph()
        for row in self._conn.execute("SELECT * FROM nodes").fetchall():
            d = dict(row)
            d["tags"] = json.loads(d["tags"])
            graph.add_node(RuleNode.from_dict(d))
        for row in self._conn.execute("SELECT * FROM edges").fetchall():
            graph.add_edge(RuleEdge.from_dict(dict(row)))
        return graph

    def save_result(self, result: ArbitrationResult) -> None:
        """Persist an ArbitrationResult."""
        import time as _time

        self._conn.execute(
            """INSERT INTO results
               (query, answer, tier, provenance, confidence, contradictions, recorded_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                result.query,
                result.answer,
                result.tier,
                json.dumps(result.provenance),
                result.confidence,
                json.dumps(result.contradictions),
                _time.time(),
            ),
        )
        self._conn.commit()

    def list_results(self) -> list[ArbitrationResult]:
        """Return all stored ArbitrationResult objects, oldest first."""
        rows = self._conn.execute("SELECT * FROM results ORDER BY recorded_at").fetchall()
        out: list[ArbitrationResult] = []
        for row in rows:
            d = dict(row)
            d["provenance"] = json.loads(d["provenance"])
            d["contradictions"] = json.loads(d["contradictions"])
            out.append(ArbitrationResult.from_dict(d))
        return out

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()


class RuleArbiter:
    """Query engine that arbitrates questions against a RuleGraph.

    Given a natural-language question, the arbiter:
    1. Finds relevant rules by matching keywords against rule text, tags, and rule_id.
    2. Detects contradictions among the found rules.
    3. Classifies the query as determinate or indeterminate based on rule types.
    4. Returns a structured ArbitrationResult with full provenance.

    Attributes:
        graph: The RuleGraph to search.
    """

    # Node types that signal deterministic / computable rules
    _DETERMINATE_TYPES: typing.ClassVar[set[str]] = {
        "mechanic",
        "formula",
        "table",
        "numeric",
        "roll",
    }
    # Node types that signal interpretation-required rules
    _INDETERMINATE_TYPES: typing.ClassVar[set[str]] = {
        "narrative",
        "flavour",
        "flavor",
        "interpretation",
        "optional",
    }

    def __init__(self, graph: RuleGraph) -> None:
        self.graph = graph

    def query(self, question: str) -> ArbitrationResult:
        """Arbitrate a natural-language question against the rule graph.

        Finds relevant rules by keyword matching, detects contradictions,
        classifies as determinate/indeterminate, and returns a structured
        result with provenance.

        Args:
            question: A natural-language question about the rules.

        Returns:
            An ArbitrationResult with the answer, tier, provenance, and
            any detected contradictions.
        """
        keywords = self._extract_keywords(question)
        relevant = self._find_relevant(keywords)

        if not relevant:
            return ArbitrationResult(
                query=question,
                answer="No matching rules found for this query.",
                tier="unknown",
                provenance=[],
                confidence=0.0,
                contradictions=[],
            )

        contradictions = self._detect_contradictions(relevant)
        tier = self._classify(relevant)
        confidence = self._aggregate_confidence(relevant, contradictions)
        answer = self._synthesize_answer(question, relevant, contradictions, tier)

        return ArbitrationResult(
            query=question,
            answer=answer,
            tier=tier,
            provenance=[n.rule_id for n in relevant],
            confidence=confidence,
            contradictions=[n.rule_id for n in contradictions],
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_keywords(self, question: str) -> list[str]:
        """Extract meaningful tokens from the question."""
        # Strip punctuation, lowercase, filter short stop words
        stop = {
            "a",
            "an",
            "the",
            "is",
            "are",
            "of",
            "in",
            "to",
            "do",
            "does",
            "how",
            "what",
            "when",
            "where",
            "why",
            "i",
            "my",
            "can",
            "for",
            "with",
            "and",
            "or",
        }
        import re

        tokens = re.findall(r"[a-z0-9]+", question.lower())
        return [t for t in tokens if t not in stop and len(t) > 1]

    def _find_relevant(self, keywords: list[str]) -> list[RuleNode]:
        """Score and return rules relevant to the given keywords."""
        scored: dict[str, tuple[int, RuleNode]] = {}
        for node in self.graph.find_rules():
            score = 0
            text_lower = node.text.lower()
            rid_lower = node.rule_id.lower()
            tags_lower = [t.lower() for t in node.tags]
            for kw in keywords:
                if kw in text_lower:
                    score += 2
                if kw in rid_lower:
                    score += 3
                if any(kw in tag for tag in tags_lower):
                    score += 2
            if score > 0:
                scored[node.rule_id] = (score, node)
        # Sort by score descending, return nodes
        return [node for _, node in sorted(scored.values(), key=lambda x: -x[0])]

    def _detect_contradictions(self, nodes: list[RuleNode]) -> list[RuleNode]:
        """Identify nodes that contradict each other via supersedes edges."""
        superseded: set[str] = set()
        # Check graph edges for supersedes / exception-to relationships
        for node in nodes:
            for edge in self.graph.get_edges(source_id=node.rule_id, relation="supersedes"):
                superseded.add(edge.target_id)
            for edge in self.graph.get_edges(source_id=node.rule_id, relation="exception-to"):
                superseded.add(edge.target_id)
        return [n for n in nodes if n.rule_id in superseded]

    def _classify(self, nodes: list[RuleNode]) -> str:
        """Classify the query as determinate, indeterminate, or unknown."""
        types = {n.node_type.lower() for n in nodes}
        if types & self._DETERMINATE_TYPES:
            return "determinate"
        if types & self._INDETERMINATE_TYPES:
            return "indeterminate"
        # Confidence-based fallback: if most rules have confidence == 1.0,
        # treat as determinate.
        avg = sum(n.confidence for n in nodes) / len(nodes)
        if avg >= 0.9:
            return "determinate"
        return "indeterminate"

    def _aggregate_confidence(self, nodes: list[RuleNode], contradictions: list[RuleNode]) -> float:
        """Compute an aggregate confidence score."""
        if not nodes:
            return 0.0
        base = sum(n.confidence for n in nodes) / len(nodes)
        # Penalise for contradictions
        penalty = 0.15 * len(contradictions)
        return max(0.0, round(base - penalty, 4))

    def _synthesize_answer(
        self,
        question: str,
        relevant: list[RuleNode],
        contradictions: list[RuleNode],
        tier: str,
    ) -> str:
        """Build a human-readable answer string from the matched rules."""
        lines: list[str] = []

        if tier == "determinate":
            lines.append(f"Determinate ruling based on {len(relevant)} rule(s):")
        elif tier == "indeterminate":
            n = len(relevant)
            lines.append(f"Indeterminate ruling — requires GM interpretation ({n} rule(s) found):")
        else:
            lines.append(f"Ruling ({len(relevant)} rule(s) found):")

        for node in relevant[:3]:  # cap at 3 for readability
            snippet = node.text[:120] + ("…" if len(node.text) > 120 else "")
            lines.append(f"  [{node.rule_id}] {snippet}")

        if len(relevant) > 3:
            lines.append(f"  … and {len(relevant) - 3} more rule(s).")

        if contradictions:
            lines.append(
                f"WARNING: {len(contradictions)} contradiction(s) detected: "
                + ", ".join(n.rule_id for n in contradictions)
            )

        return "\n".join(lines)
