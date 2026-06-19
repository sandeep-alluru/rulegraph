"""Tests for rulegraph.conflicts module."""
import pytest

from rulegraph.conflicts import RuleConflict, detect_conflicts, find_cycles
from rulegraph.rule import RuleEdge, RuleGraph, RuleNode


def _node(rule_id: str, tags: list[str] | None = None, node_type: str = "mechanic") -> RuleNode:
    return RuleNode(rule_id=rule_id, text=f"Rule text for {rule_id}.", node_type=node_type, tags=tags or [])


def test_detect_conflicts_empty_graph():
    graph = RuleGraph()
    conflicts = detect_conflicts(graph)
    assert conflicts == []


def test_detect_conflicts_no_conflicts():
    graph = RuleGraph()
    graph.add_node(_node("rule.a"))
    graph.add_node(_node("rule.b"))
    conflicts = detect_conflicts(graph)
    assert conflicts == []


def test_detect_conflicts_overlapping_scope():
    graph = RuleGraph()
    graph.add_node(_node("rule.a", tags=["combat"], node_type="mechanic"))
    graph.add_node(_node("rule.b", tags=["combat"], node_type="narrative"))
    conflicts = detect_conflicts(graph)
    assert any(c.conflict_type == "overlapping_scope" for c in conflicts)


def test_detect_conflicts_direct_contradiction():
    graph = RuleGraph()
    graph.add_node(_node("rule.a"))
    graph.add_node(_node("rule.b"))
    # A supersedes B and B supersedes A
    graph.add_edge(RuleEdge(source_id="rule.a", target_id="rule.b", relation="supersedes"))
    graph.add_edge(RuleEdge(source_id="rule.b", target_id="rule.a", relation="supersedes"))
    conflicts = detect_conflicts(graph)
    assert any(c.conflict_type == "direct_contradiction" for c in conflicts)


def test_detect_conflicts_circular_dependency():
    graph = RuleGraph()
    graph.add_node(_node("rule.a"))
    graph.add_node(_node("rule.b"))
    graph.add_node(_node("rule.c"))
    graph.add_edge(RuleEdge(source_id="rule.a", target_id="rule.b", relation="requires"))
    graph.add_edge(RuleEdge(source_id="rule.b", target_id="rule.c", relation="requires"))
    graph.add_edge(RuleEdge(source_id="rule.c", target_id="rule.a", relation="requires"))
    conflicts = detect_conflicts(graph)
    assert any(c.conflict_type == "circular_dependency" for c in conflicts)


def test_find_cycles_no_cycles():
    graph = RuleGraph()
    graph.add_node(_node("rule.a"))
    graph.add_node(_node("rule.b"))
    graph.add_edge(RuleEdge(source_id="rule.a", target_id="rule.b", relation="requires"))
    cycles = find_cycles(graph)
    assert cycles == []


def test_find_cycles_simple_cycle():
    graph = RuleGraph()
    graph.add_node(_node("rule.a"))
    graph.add_node(_node("rule.b"))
    graph.add_edge(RuleEdge(source_id="rule.a", target_id="rule.b", relation="requires"))
    graph.add_edge(RuleEdge(source_id="rule.b", target_id="rule.a", relation="requires"))
    cycles = find_cycles(graph)
    assert len(cycles) >= 1


def test_rule_conflict_to_dict():
    c = RuleConflict(
        rule_a_id="a",
        rule_b_id="b",
        conflict_type="direct_contradiction",
        description="test",
        severity="critical",
    )
    d = c.to_dict()
    assert d["rule_a_id"] == "a"
    assert d["conflict_type"] == "direct_contradiction"
    assert d["severity"] == "critical"


def test_same_tags_same_type_no_overlap():
    """Same tags, same type should not generate overlapping_scope conflict."""
    graph = RuleGraph()
    graph.add_node(_node("rule.a", tags=["combat"], node_type="mechanic"))
    graph.add_node(_node("rule.b", tags=["combat"], node_type="mechanic"))
    conflicts = [c for c in detect_conflicts(graph) if c.conflict_type == "overlapping_scope"]
    assert conflicts == []
