"""Closed-loop policy gates for rulegraph (POLICY-ARBITRATION / Non-Ornament L7).

Who reads the output?
  Policy gates before endorse/COI-sensitive actions, CI, eagle-eyes dogfood.

What outcome changes?
  Empty rule graphs → FAIL_LOUD. Critical conflicts → FAIL.
  Queries that need determinate policy and get unknown/indeterminate → FAIL.
  Farm COI/endorse pack compiles to a load-bearing graph (not a docs stub).

Farm case POLICY-ARBITRATION:
  COI / endorse rules must be *compiled* into the rule graph and arbitrated
  before action — a rulebook that is never queried is ornament.

Public map: AgentUQ runtime gates, AgentWard post-deletion policies, MAFIA
audit-path policy + HITL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from rulegraph.conflicts import RuleConflict, detect_conflicts
from rulegraph.rule import (
    ArbitrationResult,
    RuleArbiter,
    RuleEdge,
    RuleGraph,
    RuleNode,
)


class ClosedLoopError(ValueError):
    """Raised when policy gate refuses empty/conflicted/indeterminate graphs."""


@dataclass(frozen=True)
class GateOutcome:
    """Result of a closed-loop policy gate.

    Attributes:
        ok: True only when the pipeline may continue.
        verdict: ``PASS``, ``FAIL``, or ``FAIL_LOUD``.
        reason: Always non-empty.
        exit_code: 0 PASS, 1 FAIL, 2 FAIL_LOUD.
        rule_count: Nodes in the graph.
        edge_count: Edges in the graph.
        conflict_count: Conflicts detected.
        critical_conflict_count: Severity=critical conflicts.
        tier: Arbitration tier when a query was run.
        confidence: Arbitration confidence when a query was run.
        provenance: Rule ids used for the answer.
        human_required: True when policy needs human arbitration.
    """

    ok: bool
    verdict: str
    reason: str
    exit_code: int
    rule_count: int = 0
    edge_count: int = 0
    conflict_count: int = 0
    critical_conflict_count: int = 0
    tier: str | None = None
    confidence: float | None = None
    provenance: tuple[str, ...] = ()
    human_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "rule_count": self.rule_count,
            "edge_count": self.edge_count,
            "conflict_count": self.conflict_count,
            "critical_conflict_count": self.critical_conflict_count,
            "tier": self.tier,
            "confidence": self.confidence,
            "provenance": list(self.provenance),
            "human_required": self.human_required,
        }


def _fail_loud(reason: str, **kwargs: Any) -> GateOutcome:
    kwargs.setdefault("human_required", True)
    return GateOutcome(
        ok=False,
        verdict="FAIL_LOUD",
        reason=reason,
        exit_code=2,
        **kwargs,
    )


def _fail(reason: str, **kwargs: Any) -> GateOutcome:
    kwargs.setdefault("human_required", True)
    return GateOutcome(
        ok=False,
        verdict="FAIL",
        reason=reason,
        exit_code=1,
        **kwargs,
    )


def compile_farm_policy_graph() -> RuleGraph:
    """Compile Foundry/farm COI + endorse policy rules into a RuleGraph.

    POLICY-ARBITRATION product artifact — not a README list. Rules:

    * COI: no self-endorsement when financial interest exists
    * COI: disclose material interest before public statements
    * Endorse: require owner/review before public endorse
    * Endorse: never auto-endorse without HITL
    * Legal: never auto-fix legal gates (cross-ref worldoracle LEGAL-NO-AUTOFIX)

    Edges encode requires/modifies relationships for arbitration provenance.
    """
    g = RuleGraph()

    nodes = [
        RuleNode(
            rule_id="FARM.coi.no_self_endorse",
            text=(
                "Conflict of interest: an agent or person with a material financial "
                "interest in a project MUST NOT publicly endorse that project as if "
                "independent. Self-endorsement under COI is prohibited."
            ),
            node_type="policy",
            tags=["coi", "endorse", "conflict", "farm"],
            source="farm_memory:POLICY-ARBITRATION",
            confidence=1.0,
        ),
        RuleNode(
            rule_id="FARM.coi.disclose_interest",
            text=(
                "Conflict of interest: before any public endorsement or recommendation, "
                "material interests MUST be disclosed. Hidden interest voids endorse."
            ),
            node_type="policy",
            tags=["coi", "disclose", "endorse", "farm"],
            source="farm_memory:POLICY-ARBITRATION",
            confidence=1.0,
        ),
        RuleNode(
            rule_id="FARM.endorse.require_review",
            text=(
                "Endorsement: public endorse / recommend / testimonial requires "
                "owner or designated reviewer approval before publication."
            ),
            node_type="policy",
            tags=["endorse", "review", "hitl", "farm"],
            source="farm_memory:POLICY-ARBITRATION",
            confidence=1.0,
        ),
        RuleNode(
            rule_id="FARM.endorse.no_auto",
            text=(
                "Endorsement: NEVER auto-endorse from agent pipelines without "
                "human-in-the-loop. Unattended endorse is denied."
            ),
            node_type="policy",
            tags=["endorse", "auto", "hitl", "farm"],
            source="farm_memory:POLICY-ARBITRATION",
            confidence=1.0,
        ),
        RuleNode(
            rule_id="FARM.legal.no_autofix",
            text=(
                "Legal gates (G-CONTRA and similar) ALWAYS stop for human review. "
                "NEVER auto-fix legal contradictions."
            ),
            node_type="policy",
            tags=["legal", "coi", "human_required", "farm"],
            source="farm_memory:LEGAL-NO-AUTOFIX",
            confidence=1.0,
        ),
        RuleNode(
            rule_id="FARM.action.require_provenance",
            text=(
                "Policy arbitration answers for allow/deny MUST include provenance "
                "(rule ids). Answers without provenance are indeterminate."
            ),
            node_type="policy",
            tags=["arbitration", "provenance", "farm"],
            source="farm_memory:POLICY-ARBITRATION",
            confidence=1.0,
        ),
    ]
    for n in nodes:
        g.add_node(n)

    edges = [
        RuleEdge(
            "FARM.coi.no_self_endorse",
            "FARM.endorse.require_review",
            "requires",
            condition="when endorsing under possible COI",
        ),
        RuleEdge(
            "FARM.coi.disclose_interest",
            "FARM.endorse.require_review",
            "requires",
            condition="before public endorse",
        ),
        RuleEdge(
            "FARM.endorse.no_auto",
            "FARM.endorse.require_review",
            "modifies",
            condition="blocks unattended path",
        ),
        RuleEdge(
            "FARM.legal.no_autofix",
            "FARM.action.require_provenance",
            "requires",
            condition="legal decisions need human + provenance",
        ),
        RuleEdge(
            "FARM.endorse.require_review",
            "FARM.action.require_provenance",
            "requires",
            condition="endorse decisions need provenance",
        ),
    ]
    for e in edges:
        g.add_edge(e)

    return g


def gate_policy_graph(
    graph: RuleGraph,
    *,
    refuse_critical_conflicts: bool = True,
    min_rules: int = 1,
) -> GateOutcome:
    """Gate a rule graph for POLICY-ARBITRATION readiness.

    * Empty / below min_rules → FAIL_LOUD
    * Critical conflicts (cycles, mutual supersede) → FAIL
    * Otherwise PASS (warning-level overlaps do not fail by default)
    """
    n = graph.node_count()
    e = graph.edge_count()
    if n < min_rules:
        return _fail_loud(
            f"empty policy graph — {n} rules (<{min_rules}); "
            f"write-only rulebook is ornament (POLICY-ARBITRATION)",
            rule_count=n,
            edge_count=e,
        )

    conflicts = detect_conflicts(graph)
    critical = [c for c in conflicts if c.severity == "critical"]
    if refuse_critical_conflicts and critical:
        kinds = sorted({c.conflict_type for c in critical})
        return _fail(
            f"POLICY-ARBITRATION: {len(critical)} critical conflict(s) "
            f"types={kinds} — refuse allow/deny until resolved",
            rule_count=n,
            edge_count=e,
            conflict_count=len(conflicts),
            critical_conflict_count=len(critical),
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"policy graph ok: rules={n} edges={e} conflicts={len(conflicts)} "
            f"critical={len(critical)}"
        ),
        exit_code=0,
        rule_count=n,
        edge_count=e,
        conflict_count=len(conflicts),
        critical_conflict_count=len(critical),
        human_required=False,
    )


def gate_arbitration(
    result: ArbitrationResult,
    *,
    require_determinate: bool = False,
    require_provenance: bool = True,
    min_confidence: float = 0.0,
    refuse_contradictions: bool = True,
) -> GateOutcome:
    """Gate an :class:`ArbitrationResult` for load-bearing policy decisions.

    * ``tier=unknown`` with require_provenance or require_determinate → FAIL
    * empty provenance when required → FAIL (POLICY-ARBITRATION)
    * contradictions when refuse_contradictions → FAIL
    * confidence below min → FAIL
    """
    prov = tuple(result.provenance or [])
    conf = float(result.confidence)
    tier = result.tier

    if require_provenance and not prov:
        return _fail(
            f"POLICY-ARBITRATION: no provenance for query {result.query!r} "
            f"(tier={tier}) — refuse determinate allow/deny without rule ids",
            tier=tier,
            confidence=conf,
            provenance=prov,
        )

    if require_determinate and tier != "determinate":
        return _fail(
            f"POLICY-ARBITRATION: require_determinate but tier={tier!r} "
            f"for query {result.query!r}",
            tier=tier,
            confidence=conf,
            provenance=prov,
            human_required=True,
        )

    if refuse_contradictions and result.contradictions:
        return _fail(
            f"POLICY-ARBITRATION: contradictions in provenance "
            f"{result.contradictions} for query {result.query!r}",
            tier=tier,
            confidence=conf,
            provenance=prov,
            conflict_count=len(result.contradictions),
        )

    if conf < min_confidence:
        return _fail(
            f"POLICY-ARBITRATION: confidence {conf:.3f} < min {min_confidence}",
            tier=tier,
            confidence=conf,
            provenance=prov,
        )

    if tier == "unknown" and not prov:
        return _fail_loud(
            f"no matching policy rules for {result.query!r}",
            tier=tier,
            confidence=conf,
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"arbitration ok tier={tier} confidence={conf:.3f} provenance={list(prov)}",
        exit_code=0,
        tier=tier,
        confidence=conf,
        provenance=prov,
        rule_count=len(prov),
        human_required=False,
    )


def gate_policy_query(
    graph: RuleGraph,
    query: str,
    *,
    require_determinate: bool = False,
    require_provenance: bool = True,
    min_confidence: float = 0.0,
    refuse_critical_conflicts: bool = True,
) -> GateOutcome:
    """End-to-end: graph readiness + arbitrate *query* + gate the result.

    This is the load-bearing closed-loop entry for POLICY-ARBITRATION.
    """
    base = gate_policy_graph(
        graph,
        refuse_critical_conflicts=refuse_critical_conflicts,
    )
    if not base.ok:
        return base

    arbiter = RuleArbiter(graph)
    result = arbiter.query(query)
    out = gate_arbitration(
        result,
        require_determinate=require_determinate,
        require_provenance=require_provenance,
        min_confidence=min_confidence,
    )
    # Attach graph stats
    return GateOutcome(
        ok=out.ok,
        verdict=out.verdict,
        reason=out.reason,
        exit_code=out.exit_code,
        rule_count=base.rule_count,
        edge_count=base.edge_count,
        conflict_count=base.conflict_count,
        critical_conflict_count=base.critical_conflict_count,
        tier=out.tier,
        confidence=out.confidence,
        provenance=out.provenance,
        human_required=out.human_required,
    )


def assert_policy_ok(graph: RuleGraph, **kwargs: Any) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless the policy graph gates clean."""
    outcome = gate_policy_graph(graph, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome


def assert_arbitration_ok(result: ArbitrationResult, **kwargs: Any) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless arbitration result is ok."""
    outcome = gate_arbitration(result, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome


def list_critical_conflicts(graph: RuleGraph) -> list[RuleConflict]:
    """Return only critical conflicts (for CI reports)."""
    return [c for c in detect_conflicts(graph) if c.severity == "critical"]
