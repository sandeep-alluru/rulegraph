"""Tests for rulegraph.importer module."""
from pathlib import Path

import pytest

from rulegraph.importer import import_from_file, import_from_text, infer_edges
from rulegraph.rule import RuleNode


SAMPLE_TEXT = """
- Attack rolls [combat] [attack]: When you make an attack, roll 1d20.
- Damage roll [combat]: After a hit, roll damage dice.
* Difficult terrain [movement]: Moving through difficult terrain costs extra movement.
1. Grapple [combat] [grapple]: You can attempt to grapple a creature.
"""


def test_import_from_text_returns_nodes():
    nodes = import_from_text(SAMPLE_TEXT)
    assert len(nodes) == 4


def test_import_from_text_extracts_tags():
    nodes = import_from_text(SAMPLE_TEXT)
    attack_node = next((n for n in nodes if "combat" in n.tags and "attack" in n.tags), None)
    assert attack_node is not None


def test_import_from_text_clean_text():
    nodes = import_from_text(SAMPLE_TEXT)
    for node in nodes:
        assert "[" not in node.text
        assert "]" not in node.text


def test_import_from_text_source_prefix():
    nodes = import_from_text(SAMPLE_TEXT, source="PHB")
    for node in nodes:
        assert node.rule_id.startswith("PHB.")
        assert node.source == "PHB"


def test_import_from_text_default_type():
    nodes = import_from_text(SAMPLE_TEXT, default_type="definition")
    for node in nodes:
        assert node.node_type == "definition"


def test_import_from_text_empty():
    nodes = import_from_text("")
    assert nodes == []


def test_import_from_text_no_bullets():
    nodes = import_from_text("Just a paragraph with no bullets.")
    assert nodes == []


def test_import_from_text_numbered():
    text = "1. First rule [tag1]: Do this.\n2. Second rule [tag2]: Do that."
    nodes = import_from_text(text)
    assert len(nodes) == 2


def test_import_from_file(tmp_path: Path):
    rule_file = tmp_path / "rules.txt"
    rule_file.write_text("- Attack [combat]: Roll 1d20.\n- Move [movement]: Use movement speed.")
    nodes = import_from_file(rule_file)
    assert len(nodes) == 2
    assert nodes[0].source == "rules"


def test_import_from_file_with_source(tmp_path: Path):
    rule_file = tmp_path / "rules.txt"
    rule_file.write_text("- Rule one [tag]: text.")
    nodes = import_from_file(rule_file, source="custom")
    assert nodes[0].source == "custom"


def test_infer_edges_no_keywords():
    nodes = [
        RuleNode(rule_id="rule.a", text="Do something.", node_type="mechanic"),
        RuleNode(rule_id="rule.b", text="Do something else.", node_type="mechanic"),
    ]
    edges = infer_edges(nodes)
    assert edges == []


def test_infer_edges_detects_requires():
    nodes = [
        RuleNode(rule_id="rule.a", text="This rule requires rule.b to apply.", node_type="mechanic"),
        RuleNode(rule_id="rule.b", text="Base rule.", node_type="mechanic"),
    ]
    edges = infer_edges(nodes)
    assert any(e.relation == "requires" for e in edges)


def test_infer_edges_detects_supersedes():
    nodes = [
        RuleNode(rule_id="rule.a", text="This supersedes rule.b in all cases.", node_type="mechanic"),
        RuleNode(rule_id="rule.b", text="Old rule.", node_type="mechanic"),
    ]
    edges = infer_edges(nodes)
    assert any(e.relation == "supersedes" for e in edges)
