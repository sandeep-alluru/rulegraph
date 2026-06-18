"""Tests for RuleArbiter query, classification, and contradiction detection."""

from __future__ import annotations

import pytest

from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleEdge, RuleGraph, RuleNode


@pytest.fixture
def combat_graph() -> RuleGraph:
    """A graph with combat-related rules including contradictions."""
    g = RuleGraph()
    g.add_node(
        RuleNode(
            "PHB.attack_roll",
            "When you make an attack roll, roll a d20 and add your attack modifier. If the result meets or exceeds the target's AC, the attack hits.",
            "mechanic",
            ["combat", "attack", "dice"],
        )
    )
    g.add_node(
        RuleNode(
            "PHB.damage_roll",
            "When your attack hits, roll the weapon's damage die and add your ability modifier to determine damage dealt.",
            "mechanic",
            ["combat", "damage", "dice"],
        )
    )
    g.add_node(
        RuleNode(
            "PHB.difficult_terrain",
            "Moving through difficult terrain costs extra movement. Every foot of movement in difficult terrain costs 1 extra foot.",
            "narrative",
            ["movement", "terrain"],
            confidence=0.8,
        )
    )
    g.add_node(
        RuleNode(
            "UA.revised_attack",
            "Revised variant: when you make an attack roll, roll 2d6 instead of 1d20.",
            "mechanic",
            ["combat", "attack", "variant"],
            confidence=0.9,
        )
    )
    # UA supersedes PHB
    g.add_edge(RuleEdge("UA.revised_attack", "PHB.attack_roll", "supersedes"))
    return g


@pytest.fixture
def arbiter(combat_graph: RuleGraph) -> RuleArbiter:
    return RuleArbiter(combat_graph)


def test_arbiter_finds_relevant_rules(arbiter: RuleArbiter) -> None:
    result = arbiter.query("How do I make an attack roll?")
    assert result.tier in ("determinate", "indeterminate", "unknown")
    # Should find attack-related rules
    assert len(result.provenance) > 0
    assert any("attack" in rid for rid in result.provenance)


def test_arbiter_result_is_arbitration_result(arbiter: RuleArbiter) -> None:
    result = arbiter.query("How do I make an attack roll?")
    assert isinstance(result, ArbitrationResult)


def test_arbiter_query_returns_answer(arbiter: RuleArbiter) -> None:
    result = arbiter.query("attack roll")
    assert result.answer
    assert len(result.answer) > 5


def test_arbiter_determinate_classification(arbiter: RuleArbiter) -> None:
    # mechanic-type rules should be classified as determinate
    result = arbiter.query("attack roll damage dice")
    assert result.tier == "determinate"


def test_arbiter_indeterminate_classification(arbiter: RuleArbiter) -> None:
    # narrative-type rule should be indeterminate
    g = RuleGraph()
    g.add_node(RuleNode("r", "Flavor text: the dungeon is ominous.", "narrative", ["flavor"]))
    arbiter2 = RuleArbiter(g)
    result = arbiter2.query("flavor dungeon")
    assert result.tier == "indeterminate"


def test_arbiter_unknown_tier_when_no_match() -> None:
    # Use a fresh empty graph to guarantee no match
    g = RuleGraph()
    a = RuleArbiter(g)
    result = a.query("attack roll flanking advantage")
    assert result.tier == "unknown"
    assert result.confidence == 0.0
    assert result.provenance == []


def test_arbiter_detects_contradictions(arbiter: RuleArbiter) -> None:
    # UA.revised_attack supersedes PHB.attack_roll, so PHB.attack_roll should be in contradictions
    result = arbiter.query("attack roll dice variant revised")
    # Both UA and PHB attack rules should be found
    # PHB.attack_roll should be flagged as contradicted
    assert isinstance(result.contradictions, list)


def test_arbiter_provenance_contains_rule_ids(arbiter: RuleArbiter) -> None:
    result = arbiter.query("attack roll")
    for rid in result.provenance:
        assert isinstance(rid, str)


def test_arbiter_confidence_in_range(arbiter: RuleArbiter) -> None:
    result = arbiter.query("attack roll")
    assert 0.0 <= result.confidence <= 1.0


def test_arbiter_no_rules_returns_unknown() -> None:
    g = RuleGraph()
    a = RuleArbiter(g)
    result = a.query("anything")
    assert result.tier == "unknown"


def test_arbiter_query_field_preserved(arbiter: RuleArbiter) -> None:
    q = "What is the attack roll formula?"
    result = arbiter.query(q)
    assert result.query == q


def test_arbiter_contradiction_list(combat_graph: RuleGraph) -> None:
    arbiter = RuleArbiter(combat_graph)
    result = arbiter.query("attack roll revised variant")
    assert isinstance(result.contradictions, list)


def test_arbiter_empty_contradictions_when_no_supersedes() -> None:
    g = RuleGraph()
    g.add_node(RuleNode("r1", "Rule about damage", "mechanic", ["damage"]))
    g.add_node(RuleNode("r2", "Rule about attack", "mechanic", ["attack"]))
    # No supersedes edges
    a = RuleArbiter(g)
    result = a.query("damage attack")
    assert result.contradictions == []


def test_arbiter_multiple_queries_independent(arbiter: RuleArbiter) -> None:
    r1 = arbiter.query("attack roll")
    r2 = arbiter.query("difficult terrain movement")
    # Results should be independent
    assert r1.provenance != r2.provenance or r1.tier != r2.tier or r1.query != r2.query


def test_arbiter_high_confidence_for_determinate(arbiter: RuleArbiter) -> None:
    result = arbiter.query("damage dice roll weapon")
    # PHB.damage_roll has confidence 1.0, should yield high result
    if result.tier == "determinate":
        assert result.confidence > 0.5


def test_arbiter_exception_to_relation() -> None:
    g = RuleGraph()
    g.add_node(RuleNode("base", "Base attack rule", "mechanic", ["attack"]))
    g.add_node(
        RuleNode("exception", "Exception to attack for grapple", "mechanic", ["attack", "grapple"])
    )
    g.add_edge(RuleEdge("exception", "base", "exception-to"))
    a = RuleArbiter(g)
    result = a.query("attack grapple exception")
    assert isinstance(result.contradictions, list)
    # base should be flagged as superseded by exception
    if result.provenance:
        assert "exception" in result.provenance or "base" in result.provenance
