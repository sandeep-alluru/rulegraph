# Case Study: AI Compliance Checking with Full Rule Provenance

## Company Profile

**ComplianceAI** is a legal technology startup with 20 engineers that provides AI-powered
compliance checking for Fortune 500 clients. Their product allows business users to describe a
proposed action or decision and receive a compliance verdict against their company's policy
manuals. Their stack is Python, FastAPI, PostgreSQL (client data), and OpenAI GPT-4o (for
natural-language input parsing). They serve 12 Fortune 500 clients across finance, healthcare,
and manufacturing.

## The Problem

ComplianceAI's first product version fed the entire corporate policy manual as context to an
LLM, which then produced a compliance verdict. This approach had a critical flaw: the LLM
hallucinated compliance verdicts 18% of the time.

The root cause was structural. Corporate policy manuals are flat PDFs — walls of numbered
paragraphs that reference each other with phrases like "subject to the exceptions in Section
4.3.2" or "as modified by the amendment to Policy HR-104." The LLM could not reliably trace
these chains. It would:

- Cite Policy A as prohibiting an action while ignoring the exception in Policy B that
  explicitly permitted that same action in the client's context.
- Produce contradictory verdicts for the same scenario depending on where in the document
  the LLM happened to focus.
- Cite non-existent policy numbers with confident-sounding language.

One client — a healthcare company — received a "compliant" verdict on a vendor contract that
actually violated three interconnected policies about data residency and PHI handling. The error
was caught in legal review, but it shook client confidence and triggered a 90-day remediation
audit.

Additionally, no one at ComplianceAI or their clients had ever analyzed the policy manuals as
a system. When ComplianceAI began building rulegraph, they discovered that client policy manuals
contained internal contradictions — rules that literally prohibited what other rules required.
These contradictions had never been surfaced because no tool had ever treated the policy manual
as a graph.

## Solution Architecture

```
Policy Manual (400-page PDF)
           │
    [import_from_text()]
           │
    340 RuleNodes (one per policy statement)
           │
    [infer_edges()]
           │
    89 RuleEdges (modifies, supersedes, requires, exception-to)
           │
    [detect_conflicts()] → 12 contradictions → legal review queue
    [CoverageTracker]   → 60 dead rules    → policy simplification
           │
    RuleArbiter ← compliance query ("Is vendor X contract compliant?")
           │
    ArbitrationResult
      tier: "determinate"
      confidence: 0.87
      provenance: ["HR-104.3", "Section4.3.2", "Amendment2024-03"]
      contradictions: []
           │
    compliance_dashboard (verdict + full rule chain)
```

The policy manual PDF is converted to bullet-point text during onboarding. `import_from_text()`
parses each numbered policy statement into a `RuleNode`. `infer_edges()` scans for keywords like
"supersedes", "modifies", "exception to" and builds the edge graph. `detect_conflicts()` finds
rules where `supersedes` or `exception-to` edges create logical contradictions. `CoverageTracker`
wraps the `RuleArbiter` to track which rules are actually queried, identifying dead policy.

## Implementation

```python
from pathlib import Path
from rulegraph import (
    RuleNode,
    RuleEdge,
    RuleGraph,
    RuleStore,
    RuleArbiter,
    ArbitrationResult,
    CoverageTracker,
    import_from_text,
    import_from_file,
    infer_edges,
    detect_conflicts,
    find_cycles,
)

# --- Policy Manual Onboarding (run once per client) ---

def onboard_policy_manual(manual_path: Path, client_id: str) -> RuleStore:
    """Parse a policy manual PDF (pre-converted to bullet-point text) into rulegraph."""
    store = RuleStore(f".rulegraph/{client_id}/rules.db")

    # Parse each line into a RuleNode
    nodes = import_from_file(manual_path, source=f"{client_id}.policy")
    print(f"Parsed {len(nodes)} policy rules from {manual_path.name}")

    # Add to store
    for node in nodes:
        store.save_node(node)

    # Load into graph for edge inference
    graph = store.load_graph()

    # Automatically detect rule relationships from keyword patterns
    edges = infer_edges(nodes)
    print(f"Inferred {len(edges)} rule relationships")
    for edge in edges:
        store.save_edge(edge)

    return store

# --- Conflict Audit (run after onboarding) ---

def audit_policy_manual(store: RuleStore) -> dict:
    graph = store.load_graph()

    # Find contradictions (rules that supersede/override each other)
    conflicts = detect_conflicts(graph)
    print(f"Found {len(conflicts)} policy contradictions requiring legal review")
    for c in conflicts:
        print(f"  CONFLICT: {c.rule_a_id} vs {c.rule_b_id} — {c.description}")

    # Find circular rule dependencies
    cycles = find_cycles(graph)
    if cycles:
        print(f"WARNING: {len(cycles)} circular rule dependencies detected")

    return {
        "total_rules": graph.node_count(),
        "total_edges": graph.edge_count(),
        "conflicts": len(conflicts),
        "cycles": len(cycles),
        "conflict_details": [c.to_dict() for c in conflicts],
    }

# --- Compliance Query (runs on every user query) ---

def check_compliance(store: RuleStore, tracker: CoverageTracker, query: str) -> dict:
    """Return compliance verdict with full rule provenance."""
    result: ArbitrationResult = tracker.arbitrate(query)

    verdict = "COMPLIANT" if result.tier == "determinate" and not result.contradictions \
              else "REQUIRES_REVIEW"

    return {
        "query": query,
        "verdict": verdict,
        "tier": result.tier,
        "confidence": result.confidence,
        "rule_chain": result.provenance,      # exact rules used
        "contradictions": result.contradictions,  # conflicting rules flagged
        "answer": result.answer,
    }

# --- Weekly Coverage Report ---

def weekly_coverage_report(store: RuleStore, tracker: CoverageTracker) -> dict:
    coverage = tracker.report()
    return {
        "total_rules": coverage.total_rules,
        "rules_queried_this_week": coverage.rules_queried,
        "dead_rules": coverage.dead_rules,      # candidates for policy simplification
        "most_used_rules": coverage.most_used_rules,
        "coverage_pct": coverage.coverage_pct,
    }
```

## Results

| Metric | Before | After |
|---|---|---|
| Compliance hallucination rate | 18% | 1.4% |
| Compliance verdicts with rule provenance | 0% | 100% |
| Policy contradictions surfaced | 0 (unknown) | 12 (sent to legal review) |
| Dead rules identified | 0 (unknown) | 60 (compliance overhead candidates) |
| Healthcare incident (wrong verdict) | 1 per quarter (est.) | 0 in 6 months |
| Fortune 500 clients | 12 | 12 (with SLA-backed guarantees) |

The hallucination rate dropped from 18% to 1.4% because rulegraph replaced the LLM's
unstructured reasoning with deterministic keyword-to-rule matching and edge traversal. The 1.4%
remaining error rate occurred on queries involving multiple `indeterminate` rules that required
GM-style interpretation — these are now correctly flagged as `tier: "indeterminate"` and routed
to a human compliance officer rather than returned as automated verdicts.

## Key Takeaways

- `import_from_text()` does the structural work of turning a flat policy PDF into a queryable
  graph — the line-by-line bullet-point parsing handles most real-world policy manual formats.
- `detect_conflicts()` surfaced 12 policy contradictions that had existed in client manuals for
  years without being detected — the graph structure makes what was invisible to humans
  computationally explicit.
- `CoverageTracker.report().dead_rules` is an unexpected compliance win: 60 rules that were
  never queried are candidates for removal, simplifying the policy manual and reducing
  compliance overhead.
- `ArbitrationResult.provenance` is the key to explainability — clients can now point to the
  exact policy IDs that produced a verdict, making compliance decisions auditable.
- Routing `tier: "indeterminate"` queries to human review rather than returning automated
  verdicts drove the hallucination rate from 18% to 1.4% — the model knows what it doesn't know.

## Try It Yourself

```bash
pip install rulegraph

# Add a sample compliance rule
rulegraph add-rule CORP.travel.001 \
    "Employees must book travel through the approved corporate travel portal." \
    --type mechanic --tag travel --tag expense

# Add a superseding exception
rulegraph add-rule CORP.travel.002 \
    "Exception: executive team may book directly for travel exceeding $10,000." \
    --type mechanic --tag travel --tag exception
rulegraph add-edge CORP.travel.002 CORP.travel.001 exception-to

# Query and get provenance
rulegraph query "Can the CFO book a direct flight for a $12,000 trip?"

# List all rules
rulegraph rules --tag travel
```
