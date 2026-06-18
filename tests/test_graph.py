"""Tests for RuleGraph find/filter operations."""

from __future__ import annotations

import pytest

from rulegraph.rule import RuleEdge, RuleGraph, RuleNode


@pytest.fixture
def graph() -> RuleGraph:
    g = RuleGraph()
    g.add_node(RuleNode("PHB.attack", "Roll d20 + modifier", "mechanic", ["combat", "attack"]))
    g.add_node(RuleNode("PHB.damage", "Roll damage die", "mechanic", ["combat", "damage"]))
    g.add_node(
        RuleNode(
            "PHB.difficult", "Difficult terrain costs double movement", "narrative", ["movement"]
        )
    )
    g.add_node(
        RuleNode(
            "PHB.spell_attack",
            "Spell attack uses spell attack bonus",
            "mechanic",
            ["combat", "spells"],
        )
    )
    g.add_edge(RuleEdge("PHB.spell_attack", "PHB.attack", "modifies"))
    g.add_edge(RuleEdge("UA.revised", "PHB.attack", "supersedes"))
    return g


def test_node_count(graph: RuleGraph) -> None:
    assert graph.node_count() == 4


def test_edge_count(graph: RuleGraph) -> None:
    assert graph.edge_count() == 2


def test_add_node_idempotent() -> None:
    g = RuleGraph()
    n = RuleNode("r", "text", "mechanic")
    g.add_node(n)
    g.add_node(n)  # second add should be a no-op
    assert g.node_count() == 1


def test_add_edge_idempotent() -> None:
    g = RuleGraph()
    e = RuleEdge("A", "B", "modifies")
    g.add_edge(e)
    g.add_edge(e)
    assert g.edge_count() == 1


def test_get_node_returns_node(graph: RuleGraph) -> None:
    n = graph.get_node("PHB.attack")
    assert n is not None
    assert n.rule_id == "PHB.attack"


def test_get_node_returns_none_for_missing(graph: RuleGraph) -> None:
    assert graph.get_node("nonexistent") is None


def test_get_edges_all(graph: RuleGraph) -> None:
    edges = graph.get_edges()
    assert len(edges) == 2


def test_get_edges_by_source(graph: RuleGraph) -> None:
    edges = graph.get_edges(source_id="PHB.spell_attack")
    assert len(edges) == 1
    assert edges[0].source_id == "PHB.spell_attack"


def test_get_edges_by_relation(graph: RuleGraph) -> None:
    edges = graph.get_edges(relation="supersedes")
    assert len(edges) == 1
    assert edges[0].relation == "supersedes"


def test_get_edges_by_source_and_relation(graph: RuleGraph) -> None:
    edges = graph.get_edges(source_id="PHB.spell_attack", relation="modifies")
    assert len(edges) == 1


def test_get_edges_no_match(graph: RuleGraph) -> None:
    edges = graph.get_edges(source_id="PHB.attack", relation="supersedes")
    assert edges == []


def test_find_rules_all(graph: RuleGraph) -> None:
    rules = graph.find_rules()
    assert len(rules) == 4


def test_find_rules_by_tag(graph: RuleGraph) -> None:
    rules = graph.find_rules(tag="combat")
    assert len(rules) == 3
    rule_ids = {r.rule_id for r in rules}
    assert "PHB.attack" in rule_ids
    assert "PHB.damage" in rule_ids


def test_find_rules_by_node_type(graph: RuleGraph) -> None:
    rules = graph.find_rules(node_type="narrative")
    assert len(rules) == 1
    assert rules[0].rule_id == "PHB.difficult"


def test_find_rules_by_text_contains(graph: RuleGraph) -> None:
    rules = graph.find_rules(text_contains="d20")
    assert len(rules) == 1
    assert rules[0].rule_id == "PHB.attack"


def test_find_rules_text_contains_case_insensitive(graph: RuleGraph) -> None:
    rules = graph.find_rules(text_contains="D20")
    assert len(rules) == 1


def test_find_rules_combined_filters(graph: RuleGraph) -> None:
    rules = graph.find_rules(tag="combat", node_type="mechanic")
    assert all(r.node_type == "mechanic" for r in rules)
    assert all("combat" in r.tags for r in rules)


def test_find_rules_no_match(graph: RuleGraph) -> None:
    rules = graph.find_rules(tag="doesnotexist")
    assert rules == []


def test_find_rules_multiple_tags(graph: RuleGraph) -> None:
    rules = graph.find_rules(tag="spells")
    assert len(rules) == 1
    assert rules[0].rule_id == "PHB.spell_attack"
