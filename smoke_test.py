"""
End-to-end smoke test for rulegraph.

Simulates a user who just cloned the repo and wants to verify everything works.
No mocking, no fixtures — real behaviour, real CLI, real HTTP server.

Run from repo root:
    python smoke_test.py
    python smoke_test.py --verbose

Exit 0 = all passed. Exit 1 = at least one failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
REPO_ROOT = Path(__file__).parent
PYTHON = sys.executable

passed: list[str] = []
failed: list[tuple[str, str]] = []


def ok(name: str) -> None:
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}")


def fail(name: str, reason: str) -> None:
    failed.append((name, reason))
    print(f"  {RED}✗{RESET} {name}")
    if VERBOSE:
        print(f"    {YELLOW}{reason}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def run(name: str, fn):  # noqa: ANN001
    try:
        fn()
        ok(name)
    except Exception as exc:
        reason = str(exc) if not VERBOSE else traceback.format_exc().strip()
        fail(name, reason)


# ── 1. Package import ─────────────────────────────────────────────────────────

section("1. Package import")


def _test_import_version() -> None:
    import rulegraph
    assert rulegraph.__version__, "__version__ is empty"
    assert rulegraph.__version__ != "0.0.0"


def _test_import_public_api() -> None:
    from rulegraph import ArbitrationResult, RuleArbiter, RuleEdge, RuleGraph, RuleNode, RuleStore
    assert callable(RuleGraph)
    assert callable(RuleArbiter)
    assert callable(RuleStore)


run("rulegraph package imports", _test_import_version)
run("Public API (RuleGraph, RuleArbiter, RuleStore, RuleNode, RuleEdge, ArbitrationResult)", _test_import_public_api)


# ── 2. Core data model ────────────────────────────────────────────────────────

section("2. Core data model (RuleNode, RuleEdge, ArbitrationResult)")


def _test_rule_node_content_addressed() -> None:
    from rulegraph.rule import RuleNode
    n1 = RuleNode("PHB.attack", "Roll d20", "mechanic")
    n2 = RuleNode("PHB.attack", "Roll d20", "mechanic")
    assert n1.id == n2.id, "Same rule_id must produce same ID"
    n3 = RuleNode("PHB.damage", "Roll d20", "mechanic")
    assert n1.id != n3.id


def _test_rule_node_serialization() -> None:
    from rulegraph.rule import RuleNode
    n = RuleNode("PHB.attack", "Roll d20 + modifier", "mechanic", ["combat"], "SRD", 0.9)
    d = n.to_dict()
    assert d["rule_id"] == "PHB.attack"
    assert d["confidence"] == 0.9
    n2 = RuleNode.from_dict(d)
    assert n2.id == n.id
    assert n2.tags == ["combat"]


def _test_rule_edge_serialization() -> None:
    from rulegraph.rule import RuleEdge
    e = RuleEdge("UA.variant", "PHB.attack", "supersedes", "when UA rules apply", 0.8)
    d = e.to_dict()
    assert d["relation"] == "supersedes"
    assert d["condition"] == "when UA rules apply"
    e2 = RuleEdge.from_dict(d)
    assert e2.id == e.id


def _test_rule_graph_add_and_find() -> None:
    from rulegraph.rule import RuleEdge, RuleGraph, RuleNode
    g = RuleGraph()
    g.add_node(RuleNode("r1", "Attack rule with d20", "mechanic", ["combat", "attack"]))
    g.add_node(RuleNode("r2", "Movement in terrain", "narrative", ["movement"]))
    g.add_edge(RuleEdge("r1", "r2", "modifies"))
    assert g.node_count() == 2
    assert g.edge_count() == 1
    found = g.find_rules(tag="combat")
    assert len(found) == 1
    assert found[0].rule_id == "r1"
    node = g.get_node("r1")
    assert node is not None


run("RuleNode.id is content-addressed (same rule_id = same ID)", _test_rule_node_content_addressed)
run("RuleNode.to_dict() / from_dict() round-trip", _test_rule_node_serialization)
run("RuleEdge.to_dict() / from_dict() round-trip", _test_rule_edge_serialization)
run("RuleGraph add/find/get operations", _test_rule_graph_add_and_find)


# ── 3. RuleArbiter ────────────────────────────────────────────────────────────

section("3. RuleArbiter (query, contradiction detection, classification)")


def _test_arbiter_finds_relevant_rules() -> None:
    from rulegraph.rule import RuleArbiter, RuleGraph, RuleNode
    g = RuleGraph()
    g.add_node(RuleNode(
        "PHB.attack_roll",
        "When you make an attack roll, roll a d20 and add your attack modifier.",
        "mechanic",
        ["combat", "attack"],
    ))
    g.add_node(RuleNode(
        "PHB.difficult_terrain",
        "Difficult terrain costs extra movement.",
        "narrative",
        ["movement"],
    ))
    a = RuleArbiter(g)
    result = a.query("How do I make an attack roll?")
    assert "PHB.attack_roll" in result.provenance
    assert result.tier == "determinate"
    assert result.confidence > 0


def _test_arbiter_detects_contradictions() -> None:
    from rulegraph.rule import RuleArbiter, RuleEdge, RuleGraph, RuleNode
    g = RuleGraph()
    g.add_node(RuleNode("PHB.base", "Base attack: roll d20", "mechanic", ["attack"]))
    g.add_node(RuleNode("UA.revised", "Revised attack: roll 2d6", "mechanic", ["attack", "variant"]))
    g.add_edge(RuleEdge("UA.revised", "PHB.base", "supersedes"))
    a = RuleArbiter(g)
    result = a.query("attack roll variant revised")
    # Both rules should be in provenance since both match "attack"
    assert len(result.provenance) >= 1
    # PHB.base should be flagged as contradicted by UA.revised
    assert "PHB.base" in result.contradictions


def _test_arbiter_unknown_when_no_match() -> None:
    from rulegraph.rule import RuleArbiter, RuleGraph
    a = RuleArbiter(RuleGraph())
    result = a.query("xyzzy_notarule_12345")
    assert result.tier == "unknown"
    assert result.confidence == 0.0
    assert result.provenance == []


def _test_arbiter_result_round_trip() -> None:
    from rulegraph.rule import ArbitrationResult, RuleArbiter, RuleGraph, RuleNode
    g = RuleGraph()
    g.add_node(RuleNode("r1", "Spell attack uses spell attack bonus", "mechanic", ["spells"]))
    a = RuleArbiter(g)
    result = a.query("spell attack bonus")
    d = result.to_dict()
    result2 = ArbitrationResult.from_dict(d)
    assert result2.tier == result.tier
    assert result2.provenance == result.provenance


run("RuleArbiter finds relevant rules and returns determinate tier", _test_arbiter_finds_relevant_rules)
run("RuleArbiter detects contradictions via supersedes edges", _test_arbiter_detects_contradictions)
run("RuleArbiter returns unknown tier when no rules match", _test_arbiter_unknown_when_no_match)
run("ArbitrationResult.to_dict() / from_dict() round-trip", _test_arbiter_result_round_trip)


# ── 4. Report formatters ──────────────────────────────────────────────────────

section("4. Report formatters (to_json, to_markdown, print_result)")


def _test_to_json_with_result() -> None:
    from rulegraph.report import to_json
    from rulegraph.rule import ArbitrationResult
    result = ArbitrationResult(
        "How to attack?", "Roll d20", "determinate",
        ["PHB.attack"], 0.9, []
    )
    parsed = json.loads(to_json(result=result))
    assert "result" in parsed
    assert parsed["result"]["tier"] == "determinate"


def _test_to_json_with_rules() -> None:
    from rulegraph.report import to_json
    from rulegraph.rule import RuleNode
    rules = [RuleNode("r1", "text1", "mechanic"), RuleNode("r2", "text2", "narrative")]
    parsed = json.loads(to_json(rules=rules))
    assert parsed["rule_count"] == 2
    assert len(parsed["rules"]) == 2


def _test_to_markdown_produces_table() -> None:
    from rulegraph.report import to_markdown
    from rulegraph.rule import ArbitrationResult
    results = [ArbitrationResult("How to attack?", "Roll d20", "determinate", ["r1"], 0.9, [])]
    md = to_markdown(results)
    assert "rulegraph" in md
    assert "|" in md
    assert "determinate" in md


def _test_print_result_to_console() -> None:
    import io
    from rich.console import Console
    from rulegraph.report import print_result
    from rulegraph.rule import ArbitrationResult
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    result = ArbitrationResult("q", "a", "determinate", ["r1"], 0.9, ["r2"])
    print_result(result, console=con)
    output = buf.getvalue()
    assert "determinate" in output
    assert len(output) > 20


run("to_json() returns valid JSON with result key", _test_to_json_with_result)
run("to_json() returns valid JSON with rules key", _test_to_json_with_rules)
run("to_markdown() produces Markdown table with tier", _test_to_markdown_produces_table)
run("print_result() outputs to Rich console", _test_print_result_to_console)


# ── 5. RuleStore persistence ──────────────────────────────────────────────────

section("5. RuleStore persistence (save/load cycle)")


def _test_store_round_trip() -> None:
    from rulegraph.rule import RuleEdge, RuleNode, RuleStore
    with tempfile.TemporaryDirectory() as tmp:
        s = RuleStore(f"{tmp}/rules.db")
        n = RuleNode("PHB.attack", "Roll d20", "mechanic", ["combat"])
        e = RuleEdge("UA.variant", "PHB.attack", "supersedes")
        s.save_node(n)
        s.save_edge(e)
        graph = s.load_graph()
        s.close()
    assert graph.node_count() == 1
    assert graph.edge_count() == 1
    loaded = graph.get_node("PHB.attack")
    assert loaded is not None
    assert loaded.tags == ["combat"]


def _test_store_results() -> None:
    from rulegraph.rule import ArbitrationResult, RuleStore
    with tempfile.TemporaryDirectory() as tmp:
        s = RuleStore(f"{tmp}/rules.db")
        r = ArbitrationResult("q", "a", "determinate", ["r1"], 0.9, [])
        s.save_result(r)
        results = s.list_results()
        s.close()
    assert len(results) == 1
    assert results[0].tier == "determinate"


run("RuleStore save/load node + edge round-trip", _test_store_round_trip)
run("RuleStore save/list ArbitrationResult", _test_store_results)


# ── 6. CLI ────────────────────────────────────────────────────────────────────

section("6. CLI (rulegraph)")


def _test_cli_help() -> None:
    r = subprocess.run(
        [PYTHON, "-m", "rulegraph.cli", "--help"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert len(r.stdout) > 20, "Help output is empty"


def _test_cli_add_rule() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/rules.db"
        r = subprocess.run(
            [PYTHON, "-m", "rulegraph.cli", "--db", db, "add-rule",
             "PHB.attack", "Roll d20 to attack"],
            capture_output=True, text=True,
        )
    assert r.returncode == 0
    assert "PHB.attack" in r.stdout


def _test_cli_status() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/rules.db"
        r = subprocess.run(
            [PYTHON, "-m", "rulegraph.cli", "--db", db, "status"],
            capture_output=True, text=True,
        )
    assert r.returncode == 0


run("rulegraph --help returns 0", _test_cli_help)
run("rulegraph add-rule stores and echoes rule_id", _test_cli_add_rule)
run("rulegraph status returns 0", _test_cli_status)


# ── 7. FastAPI server ─────────────────────────────────────────────────────────

section("7. FastAPI server (rulegraph[api])")


def _test_api_import() -> None:
    from rulegraph.api import app
    assert app.title == "rulegraph API"


def _test_api_health() -> None:
    from fastapi.testclient import TestClient
    from rulegraph.api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()


def _test_api_rule_and_query() -> None:
    from fastapi.testclient import TestClient
    from rulegraph.api import app
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/rules.db"
        r_rule = client.post("/rule", json={
            "rule_id": "PHB.attack", "text": "Roll d20 for attack roll",
            "node_type": "mechanic", "db": db,
        })
        assert r_rule.status_code == 200
        assert r_rule.json()["rule_id"] == "PHB.attack"
        r_query = client.post("/query", json={"question": "attack roll", "db": db})
        assert r_query.status_code == 200
        data = r_query.json()
        assert "PHB.attack" in data["provenance"]
        assert data["tier"] == "determinate"


run("rulegraph.api imports and app.title is correct", _test_api_import)
run("GET /health returns {status: ok, version: ...}", _test_api_health)
run("POST /rule + POST /query workflow", _test_api_rule_and_query)


# ── 8. MCP server ─────────────────────────────────────────────────────────────

section("8. MCP server (rulegraph[mcp])")


def _test_mcp_server_importable() -> None:
    import rulegraph.mcp_server as m
    assert hasattr(m, "run_server")


def _test_mcp_server_loads_cleanly() -> None:
    import rulegraph.mcp_server  # noqa: F401


run("mcp_server.py imports without error", _test_mcp_server_importable)
run("mcp_server module loads cleanly (no import-time crash)", _test_mcp_server_loads_cleanly)


# ── 9. Agent config files ─────────────────────────────────────────────────────

section("9. Agent config files (what a clone gives you)")


def _check_file_nonempty(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    assert p.stat().st_size > 50, f"File too small (likely empty): {rel}"


def _check_json_valid(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    json.loads(p.read_text())


def _check_yaml_parseable(rel: str) -> None:
    try:
        import yaml  # type: ignore[import-untyped]
        p = REPO_ROOT / rel
        assert p.exists(), f"Missing: {rel}"
        yaml.safe_load(p.read_text())
    except ImportError:
        content = (REPO_ROOT / rel).read_text()
        assert len(content) > 20, f"File appears empty: {rel}"


def _test_claude_commands() -> None:
    commands = list((REPO_ROOT / ".claude/commands").glob("*.md"))
    assert len(commands) >= 4, f"Expected >=4 slash commands, found {len(commands)}"


def _test_openai_tools_valid() -> None:
    _check_json_valid("tools/openai-tools.json")
    tools = json.loads((REPO_ROOT / "tools/openai-tools.json").read_text())
    assert len(tools) >= 3
    assert all("function" in t for t in tools)


def _test_openapi_yaml_parseable() -> None:
    _check_yaml_parseable("openapi.yaml")


run("AGENTS.md exists and non-empty", lambda: _check_file_nonempty("AGENTS.md"))
run("CLAUDE.md exists and non-empty", lambda: _check_file_nonempty("CLAUDE.md"))
run("CODEX.md exists and non-empty", lambda: _check_file_nonempty("CODEX.md"))
run(".github/copilot-instructions.md exists", lambda: _check_file_nonempty(".github/copilot-instructions.md"))


def _test_cursor_rules() -> None:
    mdc_files = list((REPO_ROOT / ".cursor/rules").glob("*.mdc"))
    assert len(mdc_files) >= 1, f"Expected >=1 .mdc file in .cursor/rules/, found none"


run(".cursor/rules/ has at least one .mdc file", _test_cursor_rules)
run(".windsurfrules exists", lambda: _check_file_nonempty(".windsurfrules"))
run(".aider.conf.yml exists", lambda: _check_file_nonempty(".aider.conf.yml"))
run(".continue/config.json is valid JSON", lambda: _check_json_valid(".continue/config.json"))
run(".claude/commands/ has >=4 slash commands", _test_claude_commands)
run("tools/openai-tools.json is valid JSON with >=3 tools", _test_openai_tools_valid)
run("openapi.yaml is parseable YAML", _test_openapi_yaml_parseable)


# ── 10. Docs site ─────────────────────────────────────────────────────────────

section("10. MkDocs documentation site")


def _test_mkdocs_yml() -> None:
    _check_file_nonempty("mkdocs.yml")
    content = (REPO_ROOT / "mkdocs.yml").read_text()
    assert "site_name" in content
    assert "material" in content


def _test_docs_pages() -> None:
    docs = list((REPO_ROOT / "docs").glob("*.md"))
    assert len(docs) >= 8, f"Expected >=8 doc pages, found {len(docs)}"
    names = {p.name for p in docs}
    for required in ("index.md", "quickstart.md", "architecture.md", "api-reference.md"):
        assert required in names, f"Missing docs/{required}"


run("mkdocs.yml exists with site_name and material theme", _test_mkdocs_yml)
run("docs/ has >=8 pages including index, quickstart, architecture, api-reference", _test_docs_pages)


# ── 11. examples/demo.py ─────────────────────────────────────────────────────

section("11. examples/demo.py end-to-end")


def _test_demo_runs() -> None:
    demo = REPO_ROOT / "examples" / "demo.py"
    assert demo.exists(), "examples/demo.py not found"
    r = subprocess.run(
        [PYTHON, str(demo)],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT),
    )
    if r.returncode != 0:
        raise AssertionError(f"demo.py exited {r.returncode}:\n{r.stderr[-500:]}")


run("examples/demo.py runs end-to-end without error", _test_demo_runs)


# ── Summary ───────────────────────────────────────────────────────────────────

total = len(passed) + len(failed)
print(f"\n{'='*60}")
print(f"{BOLD}Results: {len(passed)}/{total} passed{RESET}")

if failed:
    print(f"{RED}Failed ({len(failed)}):{RESET}")
    for name, reason in failed:
        print(f"  {RED}x{RESET} {name}")
        short = reason.split("\n")[0][:120]
        print(f"    {YELLOW}-> {short}{RESET}")
    print(f"\n{YELLOW}Tip: run with --verbose for full tracebacks{RESET}")
else:
    print(f"{GREEN}All {total} checks passed -- rulegraph is ready to ship{RESET}")

print(f"{'='*60}\n")
sys.exit(0 if not failed else 1)
