"""Shared pytest fixtures for rulegraph tests."""

from __future__ import annotations

import pytest

from rulegraph.rule import RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore


@pytest.fixture
def sample_node() -> RuleNode:
    """Return a simple RuleNode for tests."""
    return RuleNode(
        rule_id="PHB.attack_roll",
        text="When you make an attack roll, roll a d20 and add your attack modifier.",
        node_type="mechanic",
        tags=["combat", "attack", "dice"],
        source="D&D SRD 5.1",
        confidence=1.0,
    )


@pytest.fixture
def sample_edge(sample_node: RuleNode) -> RuleEdge:
    """Return a RuleEdge for tests."""
    return RuleEdge(
        source_id="UA.revised_attack",
        target_id=sample_node.rule_id,
        relation="supersedes",
    )


@pytest.fixture
def simple_graph() -> RuleGraph:
    """A small RuleGraph with a few rules for testing."""
    graph = RuleGraph()
    graph.add_node(
        RuleNode(
            rule_id="PHB.attack_roll",
            text="When you make an attack roll, roll a d20 and add your attack modifier.",
            node_type="mechanic",
            tags=["combat", "attack"],
            confidence=1.0,
        )
    )
    graph.add_node(
        RuleNode(
            rule_id="PHB.difficult_terrain",
            text="Moving through difficult terrain costs extra movement.",
            node_type="narrative",
            tags=["movement", "terrain"],
            confidence=0.8,
        )
    )
    graph.add_node(
        RuleNode(
            rule_id="PHB.damage_roll",
            text="When your attack hits, you deal damage equal to a damage die plus your modifier.",
            node_type="mechanic",
            tags=["combat", "damage"],
            confidence=1.0,
        )
    )
    return graph


@pytest.fixture
def arbiter(simple_graph: RuleGraph) -> RuleArbiter:
    """A RuleArbiter backed by simple_graph."""
    return RuleArbiter(simple_graph)


@pytest.fixture
def store_path(tmp_path):  # type: ignore[no-untyped-def]
    """Path to a temporary SQLite DB."""
    return str(tmp_path / "test_rules.db")


@pytest.fixture
def store(store_path: str):  # type: ignore[no-untyped-def]
    """A RuleStore backed by a temp DB, closed after the test."""
    s = RuleStore(store_path)
    yield s
    s.close()
