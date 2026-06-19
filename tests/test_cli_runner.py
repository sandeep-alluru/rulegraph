"""Tests for CLI using Click's CliRunner (no subprocess)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from rulegraph.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def db_path(tmp_path) -> str:  # type: ignore[no-untyped-def]
    return str(tmp_path / "test.db")


def test_cli_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "rulegraph" in result.output.lower() or "rulebook" in result.output.lower()


def test_cli_version(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0


def test_add_rule_basic(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(
        main,
        ["--db", db_path, "add-rule", "PHB.attack", "Roll d20 and add modifier"],
    )
    assert result.exit_code == 0, result.output
    assert "PHB.attack" in result.output


def test_add_rule_with_type(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(
        main,
        ["--db", db_path, "add-rule", "PHB.attack", "Roll d20", "--type", "mechanic"],
    )
    assert result.exit_code == 0


def test_add_rule_with_tag(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(
        main,
        [
            "--db",
            db_path,
            "add-rule",
            "PHB.attack",
            "Roll d20",
            "--tag",
            "combat",
            "--tag",
            "dice",
        ],
    )
    assert result.exit_code == 0


def test_add_edge_basic(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(
        main,
        ["--db", db_path, "add-edge", "UA.variant", "PHB.attack", "supersedes"],
    )
    assert result.exit_code == 0
    assert "supersedes" in result.output


def test_add_edge_with_condition(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(
        main,
        ["--db", db_path, "add-edge", "A", "B", "modifies", "--condition", "at night"],
    )
    assert result.exit_code == 0


def test_rules_empty(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(main, ["--db", db_path, "rules"])
    assert result.exit_code == 0


def test_rules_lists_added_rule(runner: CliRunner, db_path: str) -> None:
    runner.invoke(
        main,
        ["--db", db_path, "add-rule", "PHB.attack", "Roll d20", "--tag", "combat"],
    )
    result = runner.invoke(main, ["--db", db_path, "rules"])
    assert result.exit_code == 0
    assert "PHB.attack" in result.output


def test_rules_filter_by_tag(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "r1", "text1", "--tag", "combat"])
    runner.invoke(main, ["--db", db_path, "add-rule", "r2", "text2", "--tag", "spells"])
    result = runner.invoke(main, ["--db", db_path, "rules", "--tag", "combat"])
    assert result.exit_code == 0
    assert "r1" in result.output
    assert "r2" not in result.output


def test_rules_json_format(runner: CliRunner, db_path: str) -> None:
    import json

    runner.invoke(main, ["--db", db_path, "add-rule", "r1", "text1"])
    result = runner.invoke(main, ["--db", db_path, "rules", "--format", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "rules" in parsed


def test_query_no_rules(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(main, ["--db", db_path, "query", "How do I attack?", "--no-save"])
    assert result.exit_code == 0


def test_query_finds_relevant_rule(runner: CliRunner, db_path: str) -> None:
    runner.invoke(
        main,
        ["--db", db_path, "add-rule", "PHB.attack", "Roll d20 to make an attack roll"],
    )
    result = runner.invoke(main, ["--db", db_path, "query", "attack roll", "--no-save"])
    assert result.exit_code == 0


def test_query_json_format(runner: CliRunner, db_path: str) -> None:
    import json

    runner.invoke(main, ["--db", db_path, "add-rule", "r1", "attack roll d20", "--tag", "combat"])
    result = runner.invoke(
        main, ["--db", db_path, "query", "attack roll", "--format", "json", "--no-save"]
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "result" in parsed


def test_status_command(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(main, ["--db", db_path, "status"])
    assert result.exit_code == 0
    assert "Rules" in result.output or "Database" in result.output


def test_status_shows_node_count(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "r1", "text1"])
    result = runner.invoke(main, ["--db", db_path, "status"])
    assert result.exit_code == 0
    assert "1" in result.output


def test_add_rule_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["add-rule", "--help"])
    assert result.exit_code == 0


def test_add_edge_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["add-edge", "--help"])
    assert result.exit_code == 0


def test_query_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["query", "--help"])
    assert result.exit_code == 0


def test_rules_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["rules", "--help"])
    assert result.exit_code == 0


def test_status_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["status", "--help"])
    assert result.exit_code == 0


# ── conflicts command ─────────────────────────────────────────────────────────

def test_conflicts_empty_db(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(main, ["--db", db_path, "conflicts"])
    assert result.exit_code == 0
    assert "No conflicts detected" in result.output


def test_conflicts_detects_circular(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "rule.a", "Rule A text"])
    runner.invoke(main, ["--db", db_path, "add-rule", "rule.b", "Rule B text"])
    runner.invoke(main, ["--db", db_path, "add-edge", "rule.a", "rule.b", "requires"])
    runner.invoke(main, ["--db", db_path, "add-edge", "rule.b", "rule.a", "requires"])
    result = runner.invoke(main, ["--db", db_path, "conflicts"])
    assert result.exit_code == 0
    assert "circular_dependency" in result.output


def test_conflicts_detects_contradiction(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "rule.a", "Rule A text"])
    runner.invoke(main, ["--db", db_path, "add-rule", "rule.b", "Rule B text"])
    runner.invoke(main, ["--db", db_path, "add-edge", "rule.a", "rule.b", "supersedes"])
    runner.invoke(main, ["--db", db_path, "add-edge", "rule.b", "rule.a", "supersedes"])
    result = runner.invoke(main, ["--db", db_path, "conflicts"])
    assert result.exit_code == 0
    assert "direct_contradiction" in result.output


def test_conflicts_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["conflicts", "--help"])
    assert result.exit_code == 0


# ── coverage command ──────────────────────────────────────────────────────────

def test_coverage_empty_db(runner: CliRunner, db_path: str) -> None:
    result = runner.invoke(main, ["--db", db_path, "coverage"])
    assert result.exit_code == 0
    assert "Total rules" in result.output
    assert "0" in result.output


def test_coverage_with_rules(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "attack", "Roll d20 to attack", "--tag", "combat"])
    result = runner.invoke(main, ["--db", db_path, "coverage"])
    assert result.exit_code == 0
    assert "Total rules" in result.output
    assert "1" in result.output


def test_coverage_with_query_args(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "attack", "Roll d20 to attack", "--tag", "combat"])
    result = runner.invoke(main, ["--db", db_path, "coverage", "attack roll"])
    assert result.exit_code == 0
    assert "Coverage" in result.output


def test_coverage_shows_dead_rules(runner: CliRunner, db_path: str) -> None:
    runner.invoke(main, ["--db", db_path, "add-rule", "rule.unused", "Unused rule text"])
    result = runner.invoke(main, ["--db", db_path, "coverage"])
    assert result.exit_code == 0
    assert "Dead rules" in result.output


def test_coverage_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["coverage", "--help"])
    assert result.exit_code == 0
