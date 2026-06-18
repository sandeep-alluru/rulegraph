"""Tests for RuleNode, RuleEdge, and ArbitrationResult from rulegraph.rule."""

from __future__ import annotations

from rulegraph.rule import ArbitrationResult, RuleEdge, RuleNode

# ── RuleNode ──────────────────────────────────────────────────────────────────


def test_rule_node_id_is_content_addressed() -> None:
    n1 = RuleNode("rule.1", "text", "mechanic")
    n2 = RuleNode("rule.1", "text", "mechanic")
    assert n1.id == n2.id


def test_rule_node_different_rule_id_has_different_id() -> None:
    n1 = RuleNode("rule.1", "text", "mechanic")
    n2 = RuleNode("rule.2", "text", "mechanic")
    assert n1.id != n2.id


def test_rule_node_id_length() -> None:
    n = RuleNode("A", "text", "mechanic")
    assert len(n.id) == 16


def test_rule_node_defaults() -> None:
    n = RuleNode("r", "t", "mechanic")
    assert n.tags == []
    assert n.source == ""
    assert n.confidence == 1.0


def test_rule_node_to_dict_has_all_keys() -> None:
    n = RuleNode("PHB.attack", "Roll d20", "mechanic", ["combat"], "SRD", 0.95)
    d = n.to_dict()
    for key in ("id", "rule_id", "text", "node_type", "tags", "source", "confidence"):
        assert key in d


def test_rule_node_to_dict_values() -> None:
    n = RuleNode("PHB.attack", "Roll d20", "mechanic", ["combat"], "SRD", 0.95)
    d = n.to_dict()
    assert d["rule_id"] == "PHB.attack"
    assert d["text"] == "Roll d20"
    assert d["node_type"] == "mechanic"
    assert d["tags"] == ["combat"]
    assert d["source"] == "SRD"
    assert d["confidence"] == 0.95


def test_rule_node_from_dict_roundtrip() -> None:
    n = RuleNode("PHB.attack", "Roll d20", "mechanic", ["combat"], "SRD", 0.95)
    d = n.to_dict()
    n2 = RuleNode.from_dict(d)
    assert n2.id == n.id
    assert n2.rule_id == n.rule_id
    assert n2.text == n.text
    assert n2.node_type == n.node_type
    assert n2.tags == n.tags
    assert n2.source == n.source
    assert n2.confidence == n.confidence


def test_rule_node_from_dict_defaults() -> None:
    n = RuleNode.from_dict({"rule_id": "x", "text": "y", "node_type": "z"})
    assert n.tags == []
    assert n.source == ""
    assert n.confidence == 1.0


def test_rule_node_repr() -> None:
    n = RuleNode("r.1", "t", "mechanic")
    assert "r.1" in repr(n)
    assert "mechanic" in repr(n)


# ── RuleEdge ──────────────────────────────────────────────────────────────────


def test_rule_edge_id_is_content_addressed() -> None:
    e1 = RuleEdge("A", "B", "modifies")
    e2 = RuleEdge("A", "B", "modifies")
    assert e1.id == e2.id


def test_rule_edge_different_relation_different_id() -> None:
    e1 = RuleEdge("A", "B", "modifies")
    e2 = RuleEdge("A", "B", "supersedes")
    assert e1.id != e2.id


def test_rule_edge_id_length() -> None:
    e = RuleEdge("A", "B", "requires")
    assert len(e.id) == 16


def test_rule_edge_defaults() -> None:
    e = RuleEdge("A", "B", "requires")
    assert e.condition == ""
    assert e.confidence == 1.0


def test_rule_edge_to_dict_has_all_keys() -> None:
    e = RuleEdge("A", "B", "modifies", "when in combat", 0.9)
    d = e.to_dict()
    for key in ("id", "source_id", "target_id", "relation", "condition", "confidence"):
        assert key in d


def test_rule_edge_to_dict_values() -> None:
    e = RuleEdge("A", "B", "modifies", "when in combat", 0.9)
    d = e.to_dict()
    assert d["source_id"] == "A"
    assert d["target_id"] == "B"
    assert d["relation"] == "modifies"
    assert d["condition"] == "when in combat"
    assert d["confidence"] == 0.9


def test_rule_edge_from_dict_roundtrip() -> None:
    e = RuleEdge("X", "Y", "supersedes", "variant rule", 0.75)
    d = e.to_dict()
    e2 = RuleEdge.from_dict(d)
    assert e2.id == e.id
    assert e2.source_id == e.source_id
    assert e2.target_id == e.target_id
    assert e2.relation == e.relation
    assert e2.condition == e.condition
    assert e2.confidence == e.confidence


def test_rule_edge_repr() -> None:
    e = RuleEdge("A", "B", "modifies")
    r = repr(e)
    assert "A" in r
    assert "modifies" in r
    assert "B" in r


# ── ArbitrationResult ─────────────────────────────────────────────────────────


def test_arbitration_result_to_dict_has_all_keys() -> None:
    ar = ArbitrationResult(
        query="What is attack roll?",
        answer="Roll d20",
        tier="determinate",
        provenance=["PHB.attack"],
        confidence=0.9,
        contradictions=[],
    )
    d = ar.to_dict()
    for key in ("query", "answer", "tier", "provenance", "confidence", "contradictions"):
        assert key in d


def test_arbitration_result_from_dict_roundtrip() -> None:
    ar = ArbitrationResult("q", "a", "determinate", ["r1"], 0.9, ["r2"])
    d = ar.to_dict()
    ar2 = ArbitrationResult.from_dict(d)
    assert ar2.query == ar.query
    assert ar2.answer == ar.answer
    assert ar2.tier == ar.tier
    assert ar2.provenance == ar.provenance
    assert ar2.confidence == ar.confidence
    assert ar2.contradictions == ar.contradictions


def test_arbitration_result_from_dict_defaults() -> None:
    ar = ArbitrationResult.from_dict({"query": "q", "answer": "a", "tier": "unknown"})
    assert ar.provenance == []
    assert ar.confidence == 0.0
    assert ar.contradictions == []


def test_arbitration_result_repr() -> None:
    ar = ArbitrationResult("q", "a", "determinate", ["r"], 0.9, [])
    r = repr(ar)
    assert "determinate" in r
    assert "0.90" in r
