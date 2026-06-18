"""Tests for RuleStore save/load operations."""

from __future__ import annotations

from rulegraph.rule import ArbitrationResult, RuleEdge, RuleGraph, RuleNode, RuleStore


def test_store_save_and_load_node(store: RuleStore) -> None:
    node = RuleNode("PHB.attack", "Roll d20", "mechanic", ["combat"])
    store.save_node(node)
    graph = store.load_graph()
    loaded = graph.get_node("PHB.attack")
    assert loaded is not None
    assert loaded.rule_id == "PHB.attack"


def test_store_save_node_upsert(store: RuleStore) -> None:
    n1 = RuleNode("PHB.attack", "Roll d20", "mechanic")
    n2 = RuleNode("PHB.attack", "Roll d20 + modifier", "mechanic")
    store.save_node(n1)
    store.save_node(n2)
    graph = store.load_graph()
    assert graph.node_count() == 1
    assert graph.get_node("PHB.attack").text == "Roll d20 + modifier"  # type: ignore[union-attr]


def test_store_save_and_load_edge(store: RuleStore) -> None:
    n1 = RuleNode("A", "Text A", "mechanic")
    n2 = RuleNode("B", "Text B", "mechanic")
    e = RuleEdge("A", "B", "modifies")
    store.save_node(n1)
    store.save_node(n2)
    store.save_edge(e)
    graph = store.load_graph()
    edges = graph.get_edges(source_id="A")
    assert len(edges) == 1
    assert edges[0].relation == "modifies"


def test_store_load_graph_empty(store: RuleStore) -> None:
    graph = store.load_graph()
    assert graph.node_count() == 0
    assert graph.edge_count() == 0


def test_store_load_graph_returns_rulegraph(store: RuleStore) -> None:
    graph = store.load_graph()
    assert isinstance(graph, RuleGraph)


def test_store_node_preserves_tags(store: RuleStore) -> None:
    node = RuleNode("r", "text", "mechanic", ["a", "b", "c"])
    store.save_node(node)
    graph = store.load_graph()
    loaded = graph.get_node("r")
    assert loaded is not None
    assert loaded.tags == ["a", "b", "c"]


def test_store_node_preserves_source_and_confidence(store: RuleStore) -> None:
    node = RuleNode("r", "text", "mechanic", source="SRD", confidence=0.75)
    store.save_node(node)
    graph = store.load_graph()
    loaded = graph.get_node("r")
    assert loaded is not None
    assert loaded.source == "SRD"
    assert loaded.confidence == 0.75


def test_store_save_and_list_results(store: RuleStore) -> None:
    result = ArbitrationResult(
        query="How to attack?",
        answer="Roll d20",
        tier="determinate",
        provenance=["PHB.attack"],
        confidence=0.9,
        contradictions=[],
    )
    store.save_result(result)
    results = store.list_results()
    assert len(results) == 1
    assert results[0].query == "How to attack?"


def test_store_list_results_multiple(store: RuleStore) -> None:
    for i in range(3):
        store.save_result(ArbitrationResult(f"query {i}", f"answer {i}", "unknown", [], 0.5, []))
    results = store.list_results()
    assert len(results) == 3


def test_store_result_preserves_all_fields(store: RuleStore) -> None:
    result = ArbitrationResult(
        query="q",
        answer="a",
        tier="indeterminate",
        provenance=["r1", "r2"],
        confidence=0.6,
        contradictions=["r1"],
    )
    store.save_result(result)
    loaded = store.list_results()[0]
    assert loaded.tier == "indeterminate"
    assert loaded.provenance == ["r1", "r2"]
    assert loaded.contradictions == ["r1"]
    assert loaded.confidence == 0.6


def test_store_multiple_nodes(store: RuleStore) -> None:
    for i in range(5):
        store.save_node(RuleNode(f"rule.{i}", f"text {i}", "mechanic"))
    graph = store.load_graph()
    assert graph.node_count() == 5


def test_store_close_does_not_raise(store_path: str) -> None:
    s = RuleStore(store_path)
    s.close()  # should not raise


def test_store_path_attribute(store: RuleStore, store_path: str) -> None:
    from pathlib import Path

    assert store.path == Path(store_path)


def test_store_creates_parent_directory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    nested = str(tmp_path / "deep" / "nested" / "rules.db")
    s = RuleStore(nested)
    s.close()
    import os

    assert os.path.exists(nested)
