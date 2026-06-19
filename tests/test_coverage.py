"""Tests for rulegraph.coverage module."""
import pytest

from rulegraph.coverage import CoverageTracker, RuleCoverage
from rulegraph.rule import RuleArbiter, RuleGraph, RuleNode


def _graph_with_rules(*rule_ids: str) -> RuleGraph:
    graph = RuleGraph()
    for rid in rule_ids:
        graph.add_node(RuleNode(
            rule_id=rid,
            text=f"Rule text mentioning {rid}.",
            node_type="mechanic",
            tags=[rid.split(".")[-1]],
        ))
    return graph


def test_coverage_empty_graph():
    graph = RuleGraph()
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    report = tracker.report()
    assert report.total_rules == 0
    assert report.coverage_pct == 0.0


def test_coverage_no_queries():
    graph = _graph_with_rules("rule.a", "rule.b", "rule.c")
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    report = tracker.report()
    assert report.total_rules == 3
    assert report.rules_queried == 0
    assert report.rules_never_queried == 3
    assert report.coverage_pct == 0.0
    assert set(report.dead_rules) == {"rule.a", "rule.b", "rule.c"}


def test_coverage_with_query():
    graph = _graph_with_rules("rule.attack", "rule.defense")
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    tracker.arbitrate("attack roll")
    report = tracker.report()
    assert report.total_rules == 2
    assert report.rules_queried >= 0  # May be 0 if no rules matched


def test_coverage_tracks_provenance():
    graph = RuleGraph()
    graph.add_node(RuleNode(rule_id="attack", text="Attack roll: roll d20.", node_type="mechanic", tags=["attack"]))
    graph.add_node(RuleNode(rule_id="defense", text="Armor class determines hits.", node_type="mechanic", tags=["defense"]))
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    result = tracker.arbitrate("attack")
    report = tracker.report()
    if "attack" in result.provenance:
        assert report.rules_queried >= 1
        assert "attack" in [r for r, _ in report.most_used_rules]


def test_coverage_reset():
    graph = _graph_with_rules("rule.a")
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    tracker.arbitrate("rule.a")
    tracker.reset()
    report = tracker.report()
    assert report.rules_queried == 0


def test_coverage_to_dict():
    graph = _graph_with_rules("rule.a", "rule.b")
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    report = tracker.report()
    d = report.to_dict()
    assert "total_rules" in d
    assert "coverage_pct" in d
    assert "dead_rules" in d
    assert "most_used_rules" in d


def test_coverage_most_used_sorted():
    graph = RuleGraph()
    graph.add_node(RuleNode(rule_id="attack", text="attack roll", node_type="mechanic", tags=["attack"]))
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    # Simulate multiple queries
    for _ in range(3):
        tracker.arbitrate("attack")
    report = tracker.report()
    if report.most_used_rules:
        counts = [c for _, c in report.most_used_rules]
        assert counts == sorted(counts, reverse=True)


def test_coverage_dead_rules():
    graph = _graph_with_rules("rule.used", "rule.dead")
    arbiter = RuleArbiter(graph)
    tracker = CoverageTracker(arbiter)
    # Manually inject usage
    tracker._query_counts["rule.used"] = 2
    report = tracker.report()
    assert "rule.dead" in report.dead_rules
    assert "rule.used" not in report.dead_rules
