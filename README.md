# rulegraph

**Natural-language rulebook compiler for game arbitration.**

![rulegraph](assets/hero.png)

[![CI](https://github.com/sandeep-alluru/rulegraph/actions/workflows/ci.yml/badge.svg)](https://github.com/sandeep-alluru/rulegraph/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/rulegraph.svg)](https://pypi.org/project/rulegraph/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/rulegraph.svg)](https://pypi.org/project/rulegraph/)
[![Downloads](https://img.shields.io/pypi/dm/rulegraph.svg)](https://pypi.org/project/rulegraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/sandeep-alluru/rulegraph/branch/main/graph/badge.svg)](https://codecov.io/gh/sandeep-alluru/rulegraph)
[![Typed](https://img.shields.io/badge/types-mypy-blue)](https://mypy-lang.org/)

[Quick Start](#quick-start) · [How It Works](#how-it-works) · [CLI Reference](#cli-reference) · [MCP / Claude](#mcp--claude) · [OpenAI](#openai-tools) · [vs. Alternatives](#vs-alternatives) · [Contributing](CONTRIBUTING.md)

---

## Why

Game rulebooks contain two fundamentally different types of rules:

- **Determinate rules** — "Roll d20 + modifier ≥ AC → hit." The answer is always the same.
- **Indeterminate rules** — "Interpret difficult terrain in an unusual environment." The GM must decide.

Most rule-lookup tools treat all rules the same. rulegraph doesn't. It classifies every rule, represents relationships as a typed graph, detects contradictions between errata and source material, and returns structured arbitration results with full provenance.

```bash
rulegraph add-rule PHB.attack "When you make an attack roll..." --type mechanic --tag combat
rulegraph add-edge UA.flanking PHB.attack modifies
rulegraph query "How do I make an attack roll?"
```

```
╭──────────────────────────────────────╮
│ Query: How do I make an attack roll? │
│ Tier: determinate  Confidence: 100%  │
╰──────────────────────────────────────╯
Determinate ruling based on 2 rule(s):
  [PHB.attack] When you make an attack roll, roll d20 + modifier. If result >= AC, attack hits.
  [UA.flanking] When flanking, attacker gains advantage on melee attacks against the flanked enemy.

Provenance (2): PHB.attack, UA.flanking
```

---

## How It Works

```mermaid
flowchart LR
    A[Load rulebook\nRuleNode per rule] --> B[Add edges\nmodifies · supersedes · requires]
    B --> C[RuleGraph\ncontent-addressed nodes]
    C --> D{rulegraph query}
    D --> E[Keyword matching\nfind relevant rules]
    E --> F[Classify tier\ndeterminate vs indeterminate]
    F --> G[Detect contradictions\nsupersedes edges]
    G --> H[ArbitrationResult\nwith provenance + confidence]
```

**Core primitives:**

- **RuleNode** — a single rule, content-addressed by `rule_id`. Carries `node_type`, `tags`, `source`, and `confidence`.
- **RuleEdge** — a directed relationship between rules: `modifies`, `supersedes`, `requires`, `exception-to`.
- **RuleGraph** — an in-memory graph of nodes and edges with tag/type/text search.
- **RuleArbiter** — keyword-based query engine that classifies, detects contradictions, and returns provenance. Call `arbiter.query(question)` for a single arbitration.
- **ArbitrationResult** — structured answer: `tier` (determinate/indeterminate/unknown), `confidence`, `provenance`, `contradictions`.
- **RuleStore** — SQLite-backed persistence for nodes, edges, and results.
- **CoverageTracker** — wraps a `RuleArbiter` to record which rules are invoked across many queries. Use `tracker.arbitrate(question)` instead of `arbiter.query()`, then call `tracker.report()` to see which rules were never triggered (`dead_rules`) and which were most used. `RuleArbiter.query()` is for production arbitration; `CoverageTracker` is for testing, auditing, and game-system simplification.

---

## Features

| Feature | Description |
|---------|-------------|
| Content-addressed IDs | `SHA-256[:16]` of `rule_id` — same rule always same ID |
| Rule classification | `determinate` / `indeterminate` / `unknown` per query |
| Provenance | Every answer cites the exact rules used |
| Contradiction detection | Flags `supersedes` and `exception-to` conflicts |
| Edge types | `modifies`, `supersedes`, `requires`, `exception-to` |
| SQLite persistence | `RuleStore` saves nodes, edges, and results |
| FastAPI REST | Full API with `/rule`, `/edge`, `/query`, `/rules`, `/results` |
| MCP server | Three tools: `add_rule`, `query_rules`, `arbitrate` |
| Rich CLI | Colour-coded output with tables and panels |

---

## Quick Start

```bash
pip install rulegraph
# or with API server:
pip install "rulegraph[api]"
```

> **Note:** PyPI publication pending. Install directly from source in the meantime:
> ```bash
> pip install git+https://github.com/sandeep-alluru/rulegraph.git
> ```

> **Debian/Ubuntu users:** If you see `No module named venv`, install the venv package first:
> ```bash
> sudo apt-get install python3-venv
> python3 -m venv .venv && source .venv/bin/activate
> ```

```bash
# Add rules
rulegraph add-rule PHB.attack "Roll d20 + modifier. If result >= AC, attack hits." \
    --type mechanic --tag combat --tag attack

rulegraph add-rule PHB.difficult "Difficult terrain costs 1 extra foot per foot moved." \
    --type narrative --tag movement

# Add an edge (UA flanking modifies PHB attack roll)
rulegraph add-edge UA.flanking PHB.attack modifies --condition "when flanking"

# Query
rulegraph query "How do I make an attack roll?"
rulegraph query "What is difficult terrain?"

# List rules
rulegraph rules
rulegraph rules --tag combat

# Status
rulegraph status
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `rulegraph add-rule RULE_ID TEXT` | Add a rule node |
| `rulegraph add-edge SOURCE TARGET RELATION` | Add a rule edge |
| `rulegraph query QUESTION` | Arbitrate a question |
| `rulegraph rules [--tag TAG]` | List rules |
| `rulegraph status` | Show DB statistics |

**Options (all commands):**

| Flag | Description |
|------|-------------|
| `--db PATH` | Path to SQLite database (default: `.rulegraph/rules.db`) |
| `--type TYPE` | Node type for `add-rule` (default: `mechanic`) |
| `--tag TAG` | Add tag to rule (repeatable) |
| `--format json\|rich` | Output format (default: `rich`) |

---

## MCP / Claude

rulegraph ships an MCP server exposing three tools:

```json
{
  "mcpServers": {
    "rulegraph": {
      "command": "rulegraph-mcp"
    }
  }
}
```

| Tool | Description |
|------|-------------|
| `add_rule` | Add a rule node to the graph |
| `query_rules` | Arbitrate a question |
| `arbitrate` | Return a structured ArbitrationResult |

Install the MCP extras: `pip install "rulegraph[mcp]"`

See [docs/mcp.md](docs/mcp.md) for full setup instructions.

---

## OpenAI Tools

Tools are also available in OpenAI function-calling format at `tools/openai-tools.json`. See [docs/openai.md](docs/openai.md) or reference via the Codex CLI.

```bash
cat tools/openai-tools.json | jq '.[].function.name'
# => "add_rule", "query_rules", "arbitrate"
```

---

## vs. Alternatives

| Tool | Tier classification | Provenance | Contradiction detection | Graph structure |
|------|--------------------|-----------|-----------------------|----------------|
| **rulegraph** | Yes | Full | Yes | Yes |
| Rule lookup scripts | No | No | No | No |
| Vector search | No | Partial | No | No |
| LLM alone | Sometimes | No | Rarely | No |

---

## Repo Structure

```
rulegraph/
├── src/rulegraph/
│   ├── rule.py          # RuleNode, RuleEdge, RuleGraph, RuleStore, RuleArbiter
│   ├── report.py        # Rich, JSON, Markdown formatters
│   ├── cli.py           # Click CLI
│   ├── api.py           # FastAPI server
│   └── mcp_server.py    # MCP server
├── tests/
│   ├── test_rule.py
│   ├── test_graph.py
│   ├── test_store.py
│   ├── test_arbiter.py
│   ├── test_report.py
│   ├── test_cli_runner.py
│   └── test_api.py
├── examples/demo.py
├── smoke_test.py
└── pyproject.toml
```

---

## Real-World Scenario

**D&D 5e: AI Game Master Detecting Errata Conflict Before Ruling**

A player asks if their rogue can use Uncanny Dodge against an invisible attacker. The PHB says yes. A 2024 errata says no. Rather than silently applying the wrong rule, the AI GM detects the contradiction and escalates to human adjudication:

```python
from rulegraph.rule import RuleNode, RuleEdge, RuleGraph, RuleArbiter, ArbitrationResult

# 1. Create the rule graph
graph = RuleGraph()

# 2. Add the two conflicting rule nodes
phb_node = RuleNode(
    rule_id="PHB.rogue.uncanny_dodge",
    text=(
        "A rogue with Uncanny Dodge can use their reaction to halve the damage "
        "from an attack they can see."
    ),
    node_type="interpretation",
    tags=["rogue", "uncanny-dodge", "reaction", "combat"],
    source="Player's Handbook",
    confidence=1.0,
)

errata_node = RuleNode(
    rule_id="Errata.2024.uncanny_dodge",
    text="Uncanny Dodge does not apply against attacks from invisible creatures.",
    node_type="interpretation",
    tags=["rogue", "uncanny-dodge", "errata", "invisible"],
    source="D&D 2024 Errata",
    confidence=1.0,
)

graph.add_node(phb_node)
graph.add_node(errata_node)

# 3. Add a supersedes edge: newer errata supersedes the PHB base text
supersedes_edge = RuleEdge(
    source_id="Errata.2024.uncanny_dodge",
    target_id="PHB.rogue.uncanny_dodge",
    relation="supersedes",
    condition="when attacker is invisible",
)
graph.add_edge(supersedes_edge)

# 4. Create the arbiter
arbiter = RuleArbiter(graph)

# 5. Query: player asks about invisible attacker
question = "Can a rogue use Uncanny Dodge against an invisible attacker?"
result: ArbitrationResult = arbiter.query(question)

# 6. Check for contradiction and indeterminate tier
assert result.tier == "indeterminate", f"Expected indeterminate, got {result.tier!r}"
assert len(result.contradictions) > 0, "Expected at least one contradiction"

# 7. Print the ruling and the contradicting rules
print(f"Query   : {result.query}")
print(f"Tier    : {result.tier}")
print(f"Confidence: {result.confidence:.0%}")
print()
print("Ruling:")
print(result.answer)
print()
print(f"Provenance  : {result.provenance}")
print(f"Contradictions: {result.contradictions}")
print()
print("--- Contradicting rule texts ---")
for rule_id in result.contradictions:
    node = graph.get_node(rule_id)
    if node:
        print(f"  [{node.rule_id}] {node.text}")
```

Running this prints:

```
Query   : Can a rogue use Uncanny Dodge against an invisible attacker?
Tier    : indeterminate
Confidence: 85%

Ruling:
Indeterminate ruling — requires GM interpretation (2 rule(s) found):
  [Errata.2024.uncanny_dodge] Uncanny Dodge does not apply against attacks from invisible creatures.
  [PHB.rogue.uncanny_dodge] A rogue with Uncanny Dodge can use their reaction to halve the damage from an attack the…
WARNING: 1 contradiction(s) detected: PHB.rogue.uncanny_dodge

Provenance  : ['Errata.2024.uncanny_dodge', 'PHB.rogue.uncanny_dodge']
Contradictions: ['PHB.rogue.uncanny_dodge']

--- Contradicting rule texts ---
  [PHB.rogue.uncanny_dodge] A rogue with Uncanny Dodge can use their reaction to halve the damage from an attack they can see.
```

**What this prevents:** LLM-based game masters hallucinate rulings or pick arbitrarily between conflicting sources. rulegraph gives every ruling full provenance — which rules were consulted, which supersede which, and whether the answer is determinate or requires human judgment.

---

## Topics

#llm #agents #gaming #game-master #rulebook #arbitration #mcp #llmops #nlp

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=sandeep-alluru/rulegraph&type=Date)](https://star-history.com/#sandeep-alluru/rulegraph&Date)

---

## Case Studies

See how teams are using rulegraph in production:

- [AI Compliance Checking with Full Rule Provenance](docs/case-studies/legal-compliance-arbiter.md) — ComplianceAI drops hallucination rate from 18% to 1.4% for Fortune 500 clients
- [AI Game Master with Deterministic Rule Arbitration](docs/case-studies/game-dm-rule-arbitration.md) — TableTop Engine reduces GM ruling appeals by 91% across 12 game systems

## 129 tests · Coverage >= 87%

*Find rulegraph on [Smithery](https://smithery.ai/) for MCP server discovery.*
