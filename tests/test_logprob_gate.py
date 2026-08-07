"""LOGPROB-GATE / AgentUQ — token-logprob runtime reliability gate.

Public case (Track B research 20260807T001222Z):
  Show HN: AgentUQ — token-logprob runtime gate for LLM agents
  https://github.com/antoinenguyen27/agentUQ

Pre-fix hole: agents execute tool calls (SQL, shell, JSON args) from
generations with no confidence signal; low-logprob brittle spans still run.
"""

from __future__ import annotations

import math

import pytest

from rulegraph.closed_loop import (
    ClosedLoopError,
    GateOutcome,
    assert_logprob_ok,
    gate_logprob,
    summarize_logprobs,
)


def test_summarize_logprobs_basic() -> None:
    s = summarize_logprobs([-0.1, -0.2, -0.3])
    assert s.token_count == 3
    assert abs(s.mean_logprob - (-0.2)) < 1e-9
    assert s.min_logprob == -0.3
    assert abs(s.confidence - math.exp(-0.2)) < 1e-9


def test_summarize_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        summarize_logprobs([])


def test_missing_logprobs_high_risk_fails_loud() -> None:
    out = gate_logprob(None, high_risk=True, action="execute_sql")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert out.human_required is True
    assert out.action == "execute_sql"
    assert "AgentUQ" in out.reason or "LOGPROB-GATE" in out.reason


def test_empty_list_fails_loud() -> None:
    out = gate_logprob([], require_logprobs=True, action="tool")
    assert out.verdict == "FAIL_LOUD"
    assert out.token_count == 0


def test_confident_tokens_pass() -> None:
    # High confidence: all near 0 logprob
    tokens = [-0.05, -0.1, -0.08, -0.12]
    out = gate_logprob(tokens, action="answer")
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.token_count == 4
    assert out.mean_logprob is not None and out.mean_logprob > -0.5
    assert out.min_logprob is not None and out.min_logprob > -0.5
    assert out.confidence is not None and out.confidence > 0.5
    payload = out.to_dict()
    assert payload["token_count"] == 4
    assert payload["brittle_spans"] == []


def test_low_mean_fails() -> None:
    # Mean well below default -1.5
    tokens = [-2.0, -2.5, -3.0, -2.2]
    out = gate_logprob(tokens, high_risk=True, action="drop_table")
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.exit_code == 1
    assert out.human_required is True
    assert "mean_logprob" in out.reason


def test_single_brittle_token_fails() -> None:
    # Mean OK but one catastrophic token
    tokens = [-0.1, -0.2, -10.0, -0.15]
    out = gate_logprob(tokens, min_token_logprob=-4.0, action="shell")
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "min_logprob" in out.reason


def test_brittle_span_localizes_tool_args() -> None:
    """AgentUQ class: localize risk to tool_args / sql_clause spans."""
    step = [-0.1, -0.1, -0.1]
    spans = {
        "narrative": [-0.05, -0.1],
        "sql_clause": [-0.2, -5.5, -0.3],  # brittle
    }
    out = gate_logprob(
        step,
        spans=spans,
        high_risk=True,
        action="execute_sql",
    )
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "sql_clause" in out.brittle_spans
    assert out.human_required is True


def test_spans_only_confident_pass() -> None:
    out = gate_logprob(
        None,
        spans={"tool_args": [-0.1, -0.2, -0.15]},
        high_risk=True,
        action="call_tool",
    )
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.token_count == 3


def test_require_false_allows_missing() -> None:
    out = gate_logprob(None, require_logprobs=False, high_risk=False)
    assert out.ok is True
    assert out.verdict == "PASS"


def test_assert_logprob_ok_raises() -> None:
    with pytest.raises(ClosedLoopError) as ei:
        assert_logprob_ok([-5.0, -5.0], high_risk=True, action="rm")
    assert "LOGPROB-GATE" in str(ei.value) or "FAIL" in str(ei.value)


def test_assert_logprob_ok_passes() -> None:
    out = assert_logprob_ok([-0.1, -0.2])
    assert isinstance(out, GateOutcome)
    assert out.ok is True


def test_custom_thresholds() -> None:
    tokens = [-1.0, -1.0, -1.0]
    # Strict threshold fails
    bad = gate_logprob(tokens, min_mean_logprob=-0.5)
    assert bad.ok is False
    # Loose threshold passes
    good = gate_logprob(tokens, min_mean_logprob=-2.0, min_token_logprob=-2.0)
    assert good.ok is True
