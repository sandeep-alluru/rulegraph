# Quick Start

## Install

```bash
pip install rulegraph
# or with API server extras:
pip install "rulegraph[api]"
```

> **Note:** PyPI publication pending. Install directly from source:
> ```bash
> pip install git+https://github.com/sandeep-alluru/rulegraph.git
> ```

> **Debian/Ubuntu users:** If you see `No module named venv`, install the Python venv package first:
> ```bash
> sudo apt-get install python3-venv
> python3 -m venv .venv && source .venv/bin/activate
> ```

---

## Step 1: Create a RuleGraph and Add RuleNodes

A `RuleGraph` is an in-memory graph of rules. Each rule is represented as a `RuleNode` — a
single named rule with a `rule_id`, free-text description, a node type (`mechanic`, `narrative`,
`definition`, or `numeric`), optional tags, a source citation, and a confidence score.

```python
from rulegraph import RuleNode, RuleEdge, RuleGraph, RuleStore, RuleArbiter

graph = RuleGraph()

# Add a determinate (always-same-answer) rule
graph.add_node(RuleNode(
    rule_id="PHB.attack_roll",
    text="When you make an attack roll, roll d20 + modifier. If result >= AC, attack hits.",
    node_type="mechanic",
    tags=["combat", "attack", "core"],
    source="PHB Chapter 9",
    confidence=1.0,
))

# Add a narrative (interpretation-required) rule
graph.add_node(RuleNode(
    rule_id="PHB.difficult_terrain",
    text="Moving through difficult terrain costs 1 extra foot of movement per foot.",
    node_type="narrative",
    tags=["movement", "terrain"],
    source="PHB Chapter 9",
    confidence=0.9,
))

print(f"Graph has {graph.node_count()} rules")
# => Graph has 2 rules
```

---

## Step 2: Add RuleEdges

`RuleEdge` objects describe typed relationships between rules. The four built-in relation types
are:

| Relation | Meaning |
|---|---|
| `modifies` | Source rule changes how the target rule applies |
| `supersedes` | Source rule overrides the target rule entirely |
| `requires` | Source rule depends on target rule being satisfied first |
| `exception-to` | Source rule is a special case that carves out from target |

```python
# A flanking variant rule modifies the core attack roll
graph.add_edge(RuleEdge(
    source_id="PHB.flanking",
    target_id="PHB.attack_roll",
    relation="modifies",
    condition="when flanking: attacker gains advantage on melee attacks",
    confidence=0.85,
))

# Dodge action is an exception to Reckless Attack's advantage grant
graph.add_edge(RuleEdge(
    source_id="PHB.dodge_action",
    target_id="PHB.reckless_attack",
    relation="exception-to",
    condition="Dodge imposes disadvantage, canceling Reckless Attack advantage",
    confidence=1.0,
))
```

---

## Step 3: Persist with RuleStore

`RuleStore` is a SQLite-backed store. Save nodes and edges so they survive process restarts.

```python
from pathlib import Path

store = RuleStore(Path(".rulegraph/rules.db"))

for node in graph.find_rules():
    store.save_node(node)

for edge in graph.get_edges():
    store.save_edge(edge)

# Reload graph from disk
loaded_graph = store.load_graph()
```

---

## Step 4: Query with RuleArbiter

`RuleArbiter.query()` is the arbitration engine. Pass a natural-language question. It performs
keyword matching against rules, classifies the result as `determinate`, `indeterminate`, or
`unknown`, detects contradictions via `supersedes` / `exception-to` edges, and returns a
structured `ArbitrationResult`.

```python
arbiter = RuleArbiter(loaded_graph)

result = arbiter.query("How do I make an attack roll when flanking?")
```

---

## Step 5: Interpret ArbitrationResult

`ArbitrationResult` has four key fields:

| Field | Type | Description |
|---|---|---|
| `tier` | `str` | `"determinate"` — answer is rule-mechanical; `"indeterminate"` — GM/human judgment required; `"unknown"` — no matching rule found |
| `confidence` | `float` | 0.0–1.0. Degrades when indeterminate or low-confidence rules are in the chain |
| `provenance` | `list[str]` | Ordered list of `rule_id`s used to produce the answer |
| `contradictions` | `list[str]` | `rule_id`s that were overridden by `supersedes` / `exception-to` edges |
| `answer` | `str` | Human-readable ruling summary citing the matched rules |

```python
print(f"Tier:          {result.tier}")
print(f"Confidence:    {result.confidence:.2f}")
print(f"Rule chain:    {' -> '.join(result.provenance)}")
print(f"Contradictions:{result.contradictions}")
print(f"Answer:        {result.answer[:120]}...")

# Example output:
# Tier:          determinate
# Confidence:    0.85
# Rule chain:    PHB.attack_roll -> PHB.flanking
# Contradictions:[]
# Answer:        Determinate ruling based on 2 rule(s): [PHB.attack_roll] When you make...
```

A `tier: "determinate"` result means the rulebook gives a clear mechanical answer — no
interpretation needed. A `tier: "indeterminate"` result means the engine found relevant rules
but they require human judgment (the GM must decide). The `confidence` score lets you threshold
on certainty: a result below 0.6 may warrant escalation to a human.

---

## RuleArbiter.query() vs CoverageTracker

**`RuleArbiter.query(question)`** is the core arbitration call. Use it when you want a single
answer to a single question, or when you are building a one-off rule lookup tool.

**`CoverageTracker`** wraps a `RuleArbiter` and records which rules are invoked across many
queries. It answers the meta-question: "Over this session (or test suite), which rules were
*never* exercised?" Rules in `coverage.dead_rules` are candidates for removal or simplification.

```python
from rulegraph import CoverageTracker

tracker = CoverageTracker(arbiter)

# Use tracker.arbitrate() instead of arbiter.query()
result1 = tracker.arbitrate("How do I make an attack roll?")
result2 = tracker.arbitrate("What is difficult terrain?")

coverage = tracker.report()
print(f"Coverage: {coverage.coverage_pct:.1f}% of rules exercised")
print(f"Never triggered: {coverage.dead_rules}")
```

Use `RuleArbiter.query()` for production arbitration. Use `CoverageTracker` during testing or
after a game session to audit which rules in your graph are actually being reached.

---

## Full Working Example: D&D 5e Game Master

A complete example using D&D 5e combat rules with 12 `RuleNode`s, 10 `RuleEdge`s, three
combat scenarios, and a session summary is available at
[examples/dnd_game_master.py](../examples/dnd_game_master.py).

```bash
python examples/dnd_game_master.py
```

A corporate policy compliance example (12 policies, 4 proposed actions, APPROVED / BLOCKED /
PENDING verdicts) is at
[examples/policy_compliance_agent.py](../examples/policy_compliance_agent.py).

```bash
python examples/policy_compliance_agent.py
```

---

## CLI Quick Reference

```bash
# Add rules
rulegraph add-rule PHB.attack "Roll d20 + modifier >= AC to hit." --type mechanic --tag combat

# Add an edge
rulegraph add-edge PHB.flanking PHB.attack modifies --condition "when flanking"

# Arbitrate a question
rulegraph query "How do I make an attack roll?"

# List all rules (optionally filter by tag)
rulegraph rules
rulegraph rules --tag combat

# Show database statistics
rulegraph status
```

See [cli-reference.md](cli-reference.md) for full flag documentation.
