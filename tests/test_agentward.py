"""AGENTWARD - post-incident runtime enforcement (HN AgentWard).

After agent file/DB deletion, lockdown high-risk continue until inventory +
human clearance. Twin of groundcrew pre-action gate_destructive.
"""

from __future__ import annotations

import pytest

from rulegraph.agentward import (
    EnforcementSession,
    IncidentEvent,
    assert_post_incident_ok,
    clear_incident,
    gate_post_incident,
    is_high_risk_action,
    open_incident,
    record_inventory,
)
from rulegraph.closed_loop import ClosedLoopError


def test_is_high_risk_action() -> None:
    assert is_high_risk_action("rm") is True
    assert is_high_risk_action("DROP_TABLE") is True
    assert is_high_risk_action("read_file") is False
    assert is_high_risk_action("") is False


def test_no_session_passes() -> None:
    out = gate_post_incident(None)
    assert out.ok is True
    assert out.verdict == "PASS"


def test_incident_signaled_without_session_fails_loud() -> None:
    out = gate_post_incident(
        None,
        incident_signaled=True,
        require_session_after_incident=True,
    )
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "AGENTWARD" in out.reason


def test_lockdown_empty_inventory_fails_loud() -> None:
    sess = open_incident(
        IncidentEvent("i1", "file_delete", paths=()),
        auto_lockdown=True,
    )
    assert sess.status == "lockdown"
    assert sess.inventory == []
    out = gate_post_incident(sess, require_inventory=True)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "inventory" in out.reason.lower()


def test_lockdown_blocks_high_risk() -> None:
    sess = open_incident(
        {"incident_id": "i2", "kind": "db_drop", "paths": ["users", "orders"]},
    )
    out = gate_post_incident(sess, proposed_action="drop")
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.exit_code == 1
    assert out.human_required is True
    assert "drop" in sess.blocked_actions


def test_lockdown_allows_low_risk() -> None:
    sess = open_incident(
        IncidentEvent("i3", "file_delete", paths=["deleted/file"]),
    )
    out = gate_post_incident(sess, proposed_action="read_file")
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.human_required is True  # still need clear to fully recover


def test_clear_requires_inventory_and_token() -> None:
    sess = open_incident(IncidentEvent("i4", "wipe", paths=()))
    clear_incident(sess, clearance_token="owner-1", require_inventory=True)
    assert sess.status != "cleared"  # inventory empty
    record_inventory(sess, ["/data/lost.csv"])
    clear_incident(sess, clearance_token="", require_inventory=True)
    assert sess.status != "cleared"
    clear_incident(sess, clearance_token="owner-1", require_inventory=True)
    assert sess.status == "cleared"
    out = gate_post_incident(sess, proposed_action="drop")
    assert out.ok is True
    assert out.verdict == "PASS"


def test_cleared_without_token_fails_loud() -> None:
    sess = EnforcementSession(
        incident=IncidentEvent("i5", "rm", paths=["a"]),
        status="cleared",
        inventory=["a"],
        clearance_token=None,
    )
    out = gate_post_incident(sess)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "token" in out.reason.lower()


def test_dict_session() -> None:
    out = gate_post_incident(
        {
            "incident": {"id": "d1", "kind": "delete", "paths": ["f"]},
            "status": "lockdown",
            "inventory": ["f"],
        },
        proposed_action="shell",
    )
    assert out.ok is False
    assert out.verdict == "FAIL"


def test_assert_raises() -> None:
    with pytest.raises(ClosedLoopError):
        assert_post_incident_ok(
            open_incident(IncidentEvent("x", "rm", paths=["p"])),
            proposed_action="rm",
        )


def test_false_alarm_passes() -> None:
    sess = open_incident(IncidentEvent("fa", "rm", paths=["p"]))
    sess.status = "false_alarm"
    out = gate_post_incident(sess, proposed_action="rm")
    assert out.ok is True


def test_hn_agentward_fixture() -> None:
    """End-to-end: agent deleted files → lockdown → block further delete → clear."""
    # Pre-fix class: no enforcer after deletion → FAIL_LOUD when required
    missing = gate_post_incident(
        None,
        incident_signaled=True,
        require_session_after_incident=True,
        proposed_action="delete",
    )
    assert missing.ok is False
    assert missing.verdict == "FAIL_LOUD"

    # Incident opens with partial paths from the destructive tool receipt
    sess = open_incident(
        {
            "incident_id": "agentward-1",
            "kind": "file_delete",
            "paths": ["/app/config.yml"],
            "agent_id": "coding-agent",
            "summary": "agent deleted production config",
        }
    )
    # Further destructive work blocked
    blocked = gate_post_incident(sess, proposed_action="rm")
    assert blocked.ok is False
    assert blocked.verdict == "FAIL"

    # Inventory expanded during forensics
    record_inventory(sess, ["/app/secrets.env", "/app/config.yml"])
    assert len(sess.inventory) == 2

    # Human clears
    clear_incident(sess, clearance_token="oncall-token-9")
    assert sess.status == "cleared"
    ok = gate_post_incident(sess, proposed_action="write_production")
    assert ok.ok is True
    assert ok.verdict == "PASS"
    payload = sess.to_dict()
    assert payload["lockdown_active"] is False
    assert payload["inventory"]
