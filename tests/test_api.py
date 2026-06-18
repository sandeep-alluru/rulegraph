"""Tests for rulegraph FastAPI REST endpoints."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from rulegraph.api import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_has_version() -> None:
    r = client.get("/health")
    assert "version" in r.json()
    assert r.json()["version"]


def test_app_title() -> None:
    assert app.title == "rulegraph API"


def test_add_rule_returns_node(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.post(
        "/rule",
        json={
            "rule_id": "PHB.attack",
            "text": "Roll d20 and add attack modifier.",
            "node_type": "mechanic",
            "tags": ["combat"],
            "db": db,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["rule_id"] == "PHB.attack"
    assert "id" in data


def test_add_rule_id_is_16_chars(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.post(
        "/rule",
        json={"rule_id": "r.test", "text": "text", "db": db},
    )
    assert len(r.json()["id"]) == 16


def test_add_edge_returns_edge(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.post(
        "/edge",
        json={
            "source_id": "UA.variant",
            "target_id": "PHB.attack",
            "relation": "supersedes",
            "db": db,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["relation"] == "supersedes"
    assert "id" in data


def test_query_no_rules_returns_unknown(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.post("/query", json={"question": "How do I attack?", "db": db})
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == "unknown"


def test_query_finds_relevant_rule(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    # Add a rule
    client.post(
        "/rule",
        json={
            "rule_id": "PHB.attack",
            "text": "Roll d20 for attack roll",
            "node_type": "mechanic",
            "db": db,
        },
    )
    r = client.post("/query", json={"question": "attack roll dice", "db": db})
    assert r.status_code == 200
    data = r.json()
    assert data["tier"] == "determinate"
    assert "PHB.attack" in data["provenance"]


def test_query_returns_full_result_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.post("/query", json={"question": "anything", "db": db})
    data = r.json()
    for key in ("query", "answer", "tier", "provenance", "confidence", "contradictions"):
        assert key in data


def test_list_rules_empty(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.get("/rules", params={"db": db})
    assert r.status_code == 200
    assert r.json()["rule_count"] == 0


def test_list_rules_returns_added_rules(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    client.post("/rule", json={"rule_id": "r1", "text": "text 1", "db": db})
    client.post("/rule", json={"rule_id": "r2", "text": "text 2", "db": db})
    r = client.get("/rules", params={"db": db})
    assert r.status_code == 200
    assert r.json()["rule_count"] == 2


def test_list_rules_filter_by_tag(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    client.post("/rule", json={"rule_id": "r1", "text": "t1", "tags": ["combat"], "db": db})
    client.post("/rule", json={"rule_id": "r2", "text": "t2", "tags": ["spells"], "db": db})
    r = client.get("/rules", params={"db": db, "tag": "combat"})
    assert r.json()["rule_count"] == 1


def test_list_results_empty(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    r = client.get("/results", params={"db": db})
    assert r.status_code == 200
    assert r.json()["result_count"] == 0


def test_list_results_after_query(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    client.post("/rule", json={"rule_id": "r1", "text": "attack roll", "db": db})
    client.post("/query", json={"question": "attack", "save": True, "db": db})
    r = client.get("/results", params={"db": db})
    assert r.json()["result_count"] == 1


def test_query_no_save_does_not_persist(tmp_path) -> None:  # type: ignore[no-untyped-def]
    db = str(tmp_path / "test.db")
    client.post("/query", json={"question": "anything", "save": False, "db": db})
    r = client.get("/results", params={"db": db})
    assert r.json()["result_count"] == 0
