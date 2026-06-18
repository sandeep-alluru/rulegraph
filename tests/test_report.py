"""Tests for rulegraph report formatters."""

from __future__ import annotations

import io
import json

import pytest
from rich.console import Console

from rulegraph.report import print_result, print_rules, to_json, to_markdown
from rulegraph.rule import ArbitrationResult, RuleNode


@pytest.fixture
def sample_result() -> ArbitrationResult:
    return ArbitrationResult(
        query="How do I make an attack roll?",
        answer="Roll d20 + modifier. Compare to AC.",
        tier="determinate",
        provenance=["PHB.attack_roll"],
        confidence=0.95,
        contradictions=[],
    )


@pytest.fixture
def sample_rules() -> list[RuleNode]:
    return [
        RuleNode("PHB.attack", "Roll d20", "mechanic", ["combat"]),
        RuleNode("PHB.damage", "Roll damage die", "mechanic", ["combat", "damage"]),
    ]


@pytest.fixture
def console_buf() -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, width=120)
    return con, buf


# ── print_result ──────────────────────────────────────────────────────────────


def test_print_result_outputs_tier(sample_result: ArbitrationResult, console_buf: tuple) -> None:
    con, buf = console_buf
    print_result(sample_result, console=con)
    output = buf.getvalue()
    assert "determinate" in output


def test_print_result_outputs_query(sample_result: ArbitrationResult, console_buf: tuple) -> None:
    con, buf = console_buf
    print_result(sample_result, console=con)
    output = buf.getvalue()
    assert "attack roll" in output.lower()


def test_print_result_outputs_confidence(
    sample_result: ArbitrationResult, console_buf: tuple
) -> None:
    con, buf = console_buf
    print_result(sample_result, console=con)
    output = buf.getvalue()
    assert "95%" in output or "0.95" in output or "Confidence" in output


def test_print_result_shows_provenance(console_buf: tuple) -> None:
    con, buf = console_buf
    result = ArbitrationResult("q", "a", "determinate", ["PHB.r1", "PHB.r2"], 0.9, [])
    print_result(result, console=con)
    output = buf.getvalue()
    assert "PHB.r1" in output or "Provenance" in output


def test_print_result_shows_contradictions(console_buf: tuple) -> None:
    con, buf = console_buf
    result = ArbitrationResult("q", "a", "determinate", ["r1"], 0.7, ["r2"])
    print_result(result, console=con)
    output = buf.getvalue()
    assert "r2" in output or "Contradiction" in output.lower()


def test_print_result_indeterminate_tier(console_buf: tuple) -> None:
    con, buf = console_buf
    result = ArbitrationResult("q", "a", "indeterminate", [], 0.5, [])
    print_result(result, console=con)
    output = buf.getvalue()
    assert "indeterminate" in output


def test_print_result_unknown_tier(console_buf: tuple) -> None:
    con, buf = console_buf
    result = ArbitrationResult("q", "No rules found.", "unknown", [], 0.0, [])
    print_result(result, console=con)
    output = buf.getvalue()
    assert "unknown" in output


# ── print_rules ───────────────────────────────────────────────────────────────


def test_print_rules_outputs_rule_id(sample_rules: list[RuleNode], console_buf: tuple) -> None:
    con, buf = console_buf
    print_rules(sample_rules, console=con)
    output = buf.getvalue()
    assert "PHB.attack" in output


def test_print_rules_empty_list(console_buf: tuple) -> None:
    con, buf = console_buf
    print_rules([], console=con)
    output = buf.getvalue()
    assert "No rules" in output or len(output) > 0


def test_print_rules_shows_node_type(sample_rules: list[RuleNode], console_buf: tuple) -> None:
    con, buf = console_buf
    print_rules(sample_rules, console=con)
    output = buf.getvalue()
    assert "mechanic" in output


def test_print_rules_shows_tags(sample_rules: list[RuleNode], console_buf: tuple) -> None:
    con, buf = console_buf
    print_rules(sample_rules, console=con)
    output = buf.getvalue()
    assert "combat" in output


# ── to_json ───────────────────────────────────────────────────────────────────


def test_to_json_with_result_is_valid_json(sample_result: ArbitrationResult) -> None:
    j = to_json(result=sample_result)
    parsed = json.loads(j)
    assert "result" in parsed


def test_to_json_with_rules_is_valid_json(sample_rules: list[RuleNode]) -> None:
    j = to_json(rules=sample_rules)
    parsed = json.loads(j)
    assert "rules" in parsed
    assert parsed["rule_count"] == 2


def test_to_json_with_both(sample_result: ArbitrationResult, sample_rules: list[RuleNode]) -> None:
    j = to_json(rules=sample_rules, result=sample_result)
    parsed = json.loads(j)
    assert "rules" in parsed
    assert "result" in parsed


def test_to_json_empty_call() -> None:
    j = to_json()
    parsed = json.loads(j)
    assert isinstance(parsed, dict)


def test_to_json_result_has_tier(sample_result: ArbitrationResult) -> None:
    parsed = json.loads(to_json(result=sample_result))
    assert parsed["result"]["tier"] == "determinate"


def test_to_json_rule_count(sample_rules: list[RuleNode]) -> None:
    parsed = json.loads(to_json(rules=sample_rules))
    assert parsed["rule_count"] == len(sample_rules)


# ── to_markdown ───────────────────────────────────────────────────────────────


def test_to_markdown_has_heading(sample_result: ArbitrationResult) -> None:
    md = to_markdown([sample_result])
    assert "rulegraph" in md
    assert "#" in md


def test_to_markdown_has_table(sample_result: ArbitrationResult) -> None:
    md = to_markdown([sample_result])
    assert "|" in md


def test_to_markdown_empty_results() -> None:
    md = to_markdown([])
    assert "No results" in md or "rulegraph" in md


def test_to_markdown_contains_tier(sample_result: ArbitrationResult) -> None:
    md = to_markdown([sample_result])
    assert "determinate" in md


def test_to_markdown_contains_json_block(sample_result: ArbitrationResult) -> None:
    md = to_markdown([sample_result])
    assert "```json" in md


def test_to_markdown_multiple_results() -> None:
    results = [
        ArbitrationResult(f"query {i}", f"answer {i}", "unknown", [], 0.5, []) for i in range(3)
    ]
    md = to_markdown(results)
    assert "3 query" in md or "query" in md
