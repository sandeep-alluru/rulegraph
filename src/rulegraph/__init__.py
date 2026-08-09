"""rulegraph - Natural-language rulebook compiler for game arbitration."""

from __future__ import annotations

from importlib.metadata import version as _version

from rulegraph.agentward import (
    DEFAULT_HIGH_RISK_ACTIONS,
    EnforcementSession,
    IncidentEvent,
    assert_post_incident_ok,
    clear_incident,
    gate_post_incident,
    is_high_risk_action,
    open_incident,
    record_inventory,
)
from rulegraph.closed_loop import (
    DEFAULT_MIN_MEAN_LOGPROB,
    DEFAULT_MIN_TOKEN_LOGPROB,
    ClosedLoopError,
    GateOutcome,
    LogprobSummary,
    assert_arbitration_ok,
    assert_logprob_ok,
    assert_policy_ok,
    compile_farm_policy_graph,
    gate_arbitration,
    gate_logprob,
    gate_policy_graph,
    gate_policy_query,
    list_critical_conflicts,
    summarize_logprobs,
)
from rulegraph.conflicts import RuleConflict, detect_conflicts, find_cycles
from rulegraph.coverage import CoverageTracker, RuleCoverage
from rulegraph.importer import import_from_file, import_from_text, infer_edges
from rulegraph.rule import (
    ArbitrationResult,
    RuleArbiter,
    RuleEdge,
    RuleGraph,
    RuleNode,
    RuleStore,
)

__version__ = _version("rulegraph")

__all__ = [
    "DEFAULT_HIGH_RISK_ACTIONS",
    "DEFAULT_MIN_MEAN_LOGPROB",
    "DEFAULT_MIN_TOKEN_LOGPROB",
    "ArbitrationResult",
    "ClosedLoopError",
    "CoverageTracker",
    "EnforcementSession",
    "GateOutcome",
    "IncidentEvent",
    "LogprobSummary",
    "RuleArbiter",
    "RuleConflict",
    "RuleCoverage",
    "RuleEdge",
    "RuleGraph",
    "RuleNode",
    "RuleStore",
    "assert_arbitration_ok",
    "assert_logprob_ok",
    "assert_policy_ok",
    "assert_post_incident_ok",
    "clear_incident",
    "compile_farm_policy_graph",
    "detect_conflicts",
    "find_cycles",
    "gate_arbitration",
    "gate_logprob",
    "gate_policy_graph",
    "gate_policy_query",
    "gate_post_incident",
    "import_from_file",
    "import_from_text",
    "infer_edges",
    "is_high_risk_action",
    "list_critical_conflicts",
    "open_incident",
    "record_inventory",
    "summarize_logprobs",
]
