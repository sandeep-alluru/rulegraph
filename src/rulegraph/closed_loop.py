"""Closed-loop policy gates for rulegraph (POLICY-ARBITRATION + LOGPROB-GATE).

Who reads the output?
  Policy gates before endorse/COI-sensitive actions, CI, eagle-eyes dogfood.
  Agent runtimes that must block brittle tool args before execution (AgentUQ).

What outcome changes?
  Empty rule graphs → FAIL_LOUD. Critical conflicts → FAIL.
  Queries that need determinate policy and get unknown/indeterminate → FAIL.
  Farm COI/endorse pack compiles to a load-bearing graph (not a docs stub).
  Missing / empty token logprobs on high-risk steps → FAIL_LOUD (AgentUQ).
  Mean or min token logprob below threshold → FAIL (block / human_required).

Farm case POLICY-ARBITRATION:
  COI / endorse rules must be *compiled* into the rule graph and arbitrated
  before action - a rulebook that is never queried is ornament.

Public map:
  * AgentUQ (HN) - token-logprob runtime gate for LLM agent steps
  * AgentWard (HN) - post-deletion policy enforcement
  * MAFIA (arXiv) - policy + HITL on audit/tools
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rulegraph.conflicts import RuleConflict, detect_conflicts
from rulegraph.rule import (
    ArbitrationResult,
    RuleArbiter,
    RuleEdge,
    RuleGraph,
    RuleNode,
)

# Default thresholds for AgentUQ-class logprob gates (natural logprobs).
# Providers emit negative logprobs; less negative = more confident.
DEFAULT_MIN_MEAN_LOGPROB: float = -1.5
DEFAULT_MIN_TOKEN_LOGPROB: float = -4.0


class ClosedLoopError(ValueError):
    """Raised when policy gate refuses empty/conflicted/indeterminate graphs."""


@dataclass(frozen=True)
class GateOutcome:
    """Result of a closed-loop policy or logprob gate.

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
        confidence: Arbitration confidence or geometric mean token prob.
        provenance: Rule ids used for the answer.
        human_required: True when policy needs human arbitration.
        mean_logprob: Mean token logprob when a logprob gate ran.
        min_logprob: Minimum token logprob when a logprob gate ran.
        token_count: Number of tokens examined by a logprob gate.
        action: Action / step name gated (logprob path).
        brittle_spans: Span names that failed logprob thresholds.
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
    mean_logprob: float | None = None
    min_logprob: float | None = None
    token_count: int = 0
    action: str | None = None
    brittle_spans: tuple[str, ...] = ()

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
            "mean_logprob": self.mean_logprob,
            "min_logprob": self.min_logprob,
            "token_count": self.token_count,
            "action": self.action,
            "brittle_spans": list(self.brittle_spans),
        }


@dataclass(frozen=True)
class LogprobSummary:
    """Aggregate stats over a sequence of token logprobs (AgentUQ class)."""

    token_count: int
    mean_logprob: float
    min_logprob: float
    # Geometric mean of token probabilities = exp(mean logprob).
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_count": self.token_count,
            "mean_logprob": self.mean_logprob,
            "min_logprob": self.min_logprob,
            "confidence": self.confidence,
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

    POLICY-ARBITRATION product artifact - not a README list. Rules:

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
            f"empty policy graph - {n} rules (<{min_rules}); "
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
            f"types={kinds} - refuse allow/deny until resolved",
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
            f"(tier={tier}) - refuse determinate allow/deny without rule ids",
            tier=tier,
            confidence=conf,
            provenance=prov,
        )

    if require_determinate and tier != "determinate":
        return _fail(
            f"POLICY-ARBITRATION: require_determinate but tier={tier!r} for query {result.query!r}",
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


# ---------------------------------------------------------------------------
# LOGPROB-GATE / AgentUQ - token-logprob runtime reliability gate
# ---------------------------------------------------------------------------


def summarize_logprobs(logprobs: Sequence[float]) -> LogprobSummary:
    """Compute mean/min logprob and geometric-mean confidence from token logprobs.

    Args:
        logprobs: Per-token natural log-probabilities (typically ≤ 0).

    Raises:
        ValueError: if *logprobs* is empty.
    """
    if not logprobs:
        raise ValueError("empty logprobs - cannot summarize")
    vals = [float(x) for x in logprobs]
    mean_lp = sum(vals) / len(vals)
    min_lp = min(vals)
    # Clamp exp for numerical safety on extremely negative logprobs.
    conf = math.exp(max(mean_lp, -50.0))
    return LogprobSummary(
        token_count=len(vals),
        mean_logprob=mean_lp,
        min_logprob=min_lp,
        confidence=conf,
    )


def gate_logprob(
    logprobs: Sequence[float] | None,
    *,
    min_mean_logprob: float = DEFAULT_MIN_MEAN_LOGPROB,
    min_token_logprob: float = DEFAULT_MIN_TOKEN_LOGPROB,
    require_logprobs: bool = True,
    high_risk: bool = False,
    action: str | None = None,
    spans: Mapping[str, Sequence[float]] | None = None,
) -> GateOutcome:
    """Block brittle LLM steps using token logprobs (AgentUQ / LOGPROB-GATE).

    Public case: AgentUQ (HN Show HN) - single-pass runtime reliability gate
    from provider logprobs. Does **not** claim truth; refuses execution when
    the generation looks ambiguous/brittle, especially on high-risk tools
    (SQL, shell, paths, tool JSON).

    Rules:

    * ``require_logprobs`` and empty/missing logprobs → **FAIL_LOUD**
      (cannot gate a phantom confidence signal).
    * mean logprob < ``min_mean_logprob`` → **FAIL** (``human_required`` if
      high_risk).
    * any token logprob < ``min_token_logprob`` → **FAIL**.
    * optional ``spans``: each named span (e.g. ``sql_clause``, ``tool_args``)
      is checked with the same thresholds; failing span names appear in
      ``brittle_spans``.
    * clean tokens → **PASS** with ``confidence = exp(mean_logprob)``.

    Args:
        logprobs: Full-step token logprobs (may be None if only spans given).
        min_mean_logprob: Minimum allowed mean logprob (default -1.5).
        min_token_logprob: Minimum allowed single-token logprob (default -4.0).
        require_logprobs: If True, missing/empty tokens FAIL_LOUD.
        high_risk: If True, failures set ``human_required`` (tool exec class).
        action: Optional step/tool name for the reason string.
        spans: Optional map of span_name → token logprobs for localization.
    """
    act = (action or "").strip()
    brittle: list[str] = []

    # Collect all sequences to evaluate: main sequence + named spans.
    sequences: list[tuple[str | None, Sequence[float]]] = []
    if logprobs is not None:
        sequences.append((None, logprobs))
    if spans:
        for span_key, seq in spans.items():
            sequences.append((str(span_key), seq))

    if not sequences:
        if require_logprobs or high_risk:
            return _fail_loud(
                "LOGPROB-GATE/AgentUQ: no logprobs provided "
                f"(action={act!r} high_risk={high_risk}) - "
                "cannot gate brittle tool steps without provider logprobs",
                human_required=True,
                action=act,
                token_count=0,
            )
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=f"LOGPROB-GATE: logprobs not required action={act!r}",
            exit_code=0,
            human_required=False,
            action=act,
        )

    # Empty any required sequence → FAIL_LOUD
    for seq_name, seq in sequences:
        if seq is None or len(list(seq)) == 0:
            label = seq_name or "step"
            if require_logprobs or high_risk:
                return _fail_loud(
                    f"LOGPROB-GATE/AgentUQ: empty logprobs for {label!r} "
                    f"(action={act!r}) - missing confidence signal",
                    human_required=True,
                    action=act,
                    token_count=0,
                    brittle_spans=(seq_name,) if seq_name else (),
                )

    # Evaluate main sequence (or first span if only spans).
    _primary_name, primary_seq = sequences[0]
    primary_vals = [float(x) for x in primary_seq]
    summary = summarize_logprobs(primary_vals)

    # Span checks (localize brittle tool args / SQL clauses).
    for seq_name, seq in sequences:
        if seq_name is None:
            continue
        vals = [float(x) for x in seq]
        if not vals:
            continue
        s = summarize_logprobs(vals)
        if s.mean_logprob < min_mean_logprob or s.min_logprob < min_token_logprob:
            brittle.append(seq_name)

    fail_mean = summary.mean_logprob < min_mean_logprob
    fail_min = summary.min_logprob < min_token_logprob

    if fail_mean or fail_min or brittle:
        parts: list[str] = []
        if fail_mean:
            parts.append(f"mean_logprob={summary.mean_logprob:.4f} < {min_mean_logprob}")
        if fail_min:
            parts.append(f"min_logprob={summary.min_logprob:.4f} < {min_token_logprob}")
        if brittle:
            parts.append(f"brittle_spans={brittle}")
        reason = (
            "LOGPROB-GATE/AgentUQ: brittle generation - "
            + "; ".join(parts)
            + f" action={act!r} tokens={summary.token_count}"
            + (" - refuse high-risk tool exec" if high_risk else "")
        )
        return _fail(
            reason,
            confidence=summary.confidence,
            human_required=bool(high_risk),
            mean_logprob=summary.mean_logprob,
            min_logprob=summary.min_logprob,
            token_count=summary.token_count,
            action=act,
            brittle_spans=tuple(brittle),
        )

    span_note = f" spans_ok={list(spans.keys())}" if spans else ""
    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"LOGPROB-GATE ok mean={summary.mean_logprob:.4f} "
            f"min={summary.min_logprob:.4f} conf={summary.confidence:.4f} "
            f"tokens={summary.token_count} action={act!r}{span_note}"
        ),
        exit_code=0,
        confidence=summary.confidence,
        human_required=False,
        mean_logprob=summary.mean_logprob,
        min_logprob=summary.min_logprob,
        token_count=summary.token_count,
        action=act,
        brittle_spans=(),
    )


def assert_logprob_ok(
    logprobs: Sequence[float] | None,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless :func:`gate_logprob` is ok."""
    outcome = gate_logprob(logprobs, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
