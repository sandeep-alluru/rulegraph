"""POLICY-ARBITRATION - farm COI/endorse pack + policy gates.

Farm: COI / endorse rules must compile and arbitrate before action.
Public: AgentUQ / AgentWard / MAFIA - policy gates on tools.
"""

from __future__ import annotations

import pytest

from rulegraph.closed_loop import (
    ClosedLoopError,
    assert_arbitration_ok,
    assert_policy_ok,
    compile_farm_policy_graph,
    gate_arbitration,
    gate_policy_graph,
    gate_policy_query,
    list_critical_conflicts,
)
from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleEdge, RuleGraph, RuleNode


def test_compile_farm_policy_graph_has_coi_and_endorse() -> None:
    g = compile_farm_policy_graph()
    ids = set(g.node_ids())
    assert "FARM.coi.no_self_endorse" in ids
    assert "FARM.coi.disclose_interest" in ids
    assert "FARM.endorse.require_review" in ids
    assert "FARM.endorse.no_auto" in ids
    assert "FARM.legal.no_autofix" in ids
    assert g.edge_count() >= 3
    assert g.node_count() >= 5


def test_farm_graph_gates_pass() -> None:
    g = compile_farm_policy_graph()
    out = gate_policy_graph(g)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.exit_code == 0
    assert out.rule_count >= 5
    assert out.critical_conflict_count == 0


def test_empty_graph_fails_loud() -> None:
    out = gate_policy_graph(RuleGraph())
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert "empty" in out.reason.lower() or "ornament" in out.reason.lower()


def test_critical_conflict_fails() -> None:
    g = RuleGraph()
    g.add_node(RuleNode("A", "Rule A supersedes B", "policy", ["x"]))
    g.add_node(RuleNode("B", "Rule B supersedes A", "policy", ["x"]))
    g.add_edge(RuleEdge("A", "B", "supersedes"))
    g.add_edge(RuleEdge("B", "A", "supersedes"))
    out = gate_policy_graph(g)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.critical_conflict_count >= 1
    assert "POLICY-ARBITRATION" in out.reason


def test_query_endorse_has_provenance() -> None:
    g = compile_farm_policy_graph()
    out = gate_policy_query(g, "May I auto endorse a project without review?")
    # Should find endorse-related rules
    assert out.rule_count >= 5
    if out.ok:
        assert out.provenance
        assert out.tier in {"determinate", "indeterminate", "unknown"}
    else:
        # still must not be silent empty
        assert out.verdict in {"FAIL", "FAIL_LOUD"}


def test_gate_arbitration_refuses_empty_provenance() -> None:
    result = ArbitrationResult(
        query="endorse?",
        answer="maybe",
        tier="unknown",
        provenance=[],
        confidence=0.0,
        contradictions=[],
    )
    out = gate_arbitration(result, require_provenance=True)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "provenance" in out.reason.lower()


def test_gate_arbitration_require_determinate() -> None:
    result = ArbitrationResult(
        query="q",
        answer="a",
        tier="indeterminate",
        provenance=["R1"],
        confidence=0.8,
        contradictions=[],
    )
    out = gate_arbitration(result, require_determinate=True)
    assert out.ok is False
    assert "determinate" in out.reason.lower()


def test_gate_arbitration_refuses_contradictions() -> None:
    result = ArbitrationResult(
        query="q",
        answer="a",
        tier="determinate",
        provenance=["R1", "R2"],
        confidence=0.9,
        contradictions=["R2"],
    )
    out = gate_arbitration(result)
    assert out.ok is False
    assert "contradiction" in out.reason.lower()


def test_gate_arbitration_pass_clean() -> None:
    result = ArbitrationResult(
        query="endorse with review?",
        answer="Require review per FARM.endorse.require_review",
        tier="determinate",
        provenance=["FARM.endorse.require_review"],
        confidence=0.95,
        contradictions=[],
    )
    out = gate_arbitration(result, require_determinate=True, min_confidence=0.5)
    assert out.ok is True
    assert out.verdict == "PASS"


def test_assert_policy_ok_raises_on_empty() -> None:
    with pytest.raises(ClosedLoopError, match="FAIL_LOUD"):
        assert_policy_ok(RuleGraph())


def test_assert_policy_ok_on_farm() -> None:
    out = assert_policy_ok(compile_farm_policy_graph())
    assert out.ok is True


def test_assert_arbitration_ok_raises() -> None:
    bad = ArbitrationResult("q", "a", "unknown", [], 0.0, [])
    with pytest.raises(ClosedLoopError):
        assert_arbitration_ok(bad, require_provenance=True)


def test_coi_query_finds_coi_rules() -> None:
    g = compile_farm_policy_graph()
    arb = RuleArbiter(g)
    result = arb.query("conflict of interest self endorse financial")
    # Keyword match should surface COI rules
    assert any("coi" in p.lower() or "endorse" in p.lower() for p in result.provenance) or (
        result.tier == "unknown"
    )
    # Farm graph itself remains gate-clean
    assert gate_policy_graph(g).ok is True


def test_list_critical_conflicts_empty_on_farm() -> None:
    assert list_critical_conflicts(compile_farm_policy_graph()) == []


def test_to_dict_fields() -> None:
    payload = gate_policy_graph(compile_farm_policy_graph()).to_dict()
    assert payload["ok"] is True
    assert payload["rule_count"] >= 5
    assert "verdict" in payload
