# Case Study: AI Game Master with Deterministic Rule Arbitration

## Company Profile

**TableTop Engine** is an online tabletop gaming platform with 15 engineers. Their product is
an AI game master (GM) that runs D&D 5e, Pathfinder 2e, and 10 custom game systems for groups
who want to play without a human GM. Their stack is Python (backend), React (table interface),
and an LLM API for narrative generation. They serve 40,000 active players across 8,000 ongoing
campaigns.

## The Problem

TableTop Engine's AI GM produced rulings by asking an LLM to interpret the rulebook. This
approach collapsed under complex rule interactions — the edge cases where 3 or more rules
interact simultaneously.

**Common failure mode — Reckless Attack + Great Weapon Master + Sentinel + flanking**: A
barbarian player asked whether they could use Reckless Attack to gain advantage, trigger Great
Weapon Master's bonus attack on a crit, and have Sentinel activate to stop the retreating enemy.
The LLM produced three different rulings in the same session depending on how the question was
phrased, and one ruling was flatly wrong (it missed that Sentinel only triggers on opportunity
attacks).

Players appealed GM decisions at a rate of 3.2 per session. Each appeal required a human staff
member to look up the rule manually and post a correction — 45 minutes of staff time per session
on average. Worse, rulings were inconsistent across sessions: the same edge case resolved
differently in different campaigns.

The deeper problem was that no one had ever compiled the D&D 5e SRD as a computational graph.
When TableTop Engine's engineers did so during their rulegraph pilot, they discovered 3 circular
rule dependencies in the official SRD — rules that referenced each other in a loop — that the
publisher had never caught. These were responsible for a cluster of the most-appealed rulings,
because the LLM reasoning loop was trying to follow circular logic.

## Solution Architecture

```
D&D 5e SRD (900+ rules)
         │
[import_from_file("srd5e.txt", source="SRD5e")]
         │
 900+ RuleNodes
         │
[infer_edges(rules)]   → "modifies", "supersedes", "requires", "exception-to" edges
         │
[find_cycles(graph)]   → 3 circular dependencies → publisher bug report
         │
CoverageTracker(RuleArbiter(graph))
         │
Player query: "Can I use Reckless Attack and then trigger Sentinel this turn?"
         │
ArbitrationResult
  tier: "determinate"
  confidence: 0.91
  provenance: ["SRD5e.reckless_attack", "SRD5e.sentinel", "SRD5e.opportunity_attack"]
  contradictions: []
         │
AI GM response (LLM gets the ArbitrationResult as grounding context)
+ provenance shown to players (full transparency)
```

The D&D 5e SRD is pre-processed into bullet-point format during system setup. Each rule
statement becomes a `RuleNode`. `infer_edges()` detects cross-references between rules using
keyword patterns. `CoverageTracker` wraps the `RuleArbiter` so that every GM ruling records
which rules were invoked — the coverage report identifies rules that have never been triggered
(candidates for removal in custom game systems) and rules that are invoked most often
(potential simplification targets).

When a player raises a rules question, the GM's ruling is now grounded by the `ArbitrationResult`
rather than pure LLM generation. The LLM is used only for narrative expression; the rule logic
is deterministic.

## Implementation

```python
from pathlib import Path
from rulegraph import (
    RuleNode,
    RuleEdge,
    RuleGraph,
    RuleStore,
    RuleArbiter,
    ArbitrationResult,
    CoverageTracker,
    import_from_file,
    infer_edges,
    detect_conflicts,
    find_cycles,
)

# --- System Setup: compile the SRD into rulegraph (run once per game system) ---

def compile_rulebook(rulebook_path: Path, system_id: str) -> CoverageTracker:
    """Parse a game system rulebook into rulegraph."""
    store = RuleStore(f".rulegraph/{system_id}.db")

    # Parse all rules
    nodes = import_from_file(rulebook_path, source=system_id)
    print(f"Compiled {len(nodes)} rules from {rulebook_path.name}")

    for node in nodes:
        store.save_node(node)

    # Load graph and infer relationships
    graph = store.load_graph()
    edges = infer_edges(nodes)
    for edge in edges:
        store.save_edge(edge)

    # Audit: find cycles (publisher bugs) and contradictions
    cycles = find_cycles(graph)
    if cycles:
        print(f"WARNING: {len(cycles)} circular rule dependencies found in {system_id}")
        for cycle in cycles:
            print(f"  Cycle: {' -> '.join(cycle)}")

    conflicts = detect_conflicts(graph)
    if conflicts:
        print(f"Found {len(conflicts)} rule contradictions in {system_id}")

    # Build arbiter with coverage tracking
    arbiter = RuleArbiter(store.load_graph())
    return CoverageTracker(arbiter)

# --- Per-session rule arbitration ---

def arbitrate_ruling(tracker: CoverageTracker, player_query: str) -> dict:
    """Return a deterministic ruling with full rule provenance."""
    result: ArbitrationResult = tracker.arbitrate(player_query)

    if result.tier == "determinate":
        ruling_type = "DEFINITIVE"
        gm_prefix = "According to the rules"
    elif result.tier == "indeterminate":
        ruling_type = "GM_CALL"
        gm_prefix = "This is a GM judgment call"
    else:
        ruling_type = "NO_RULE_FOUND"
        gm_prefix = "No matching rule was found"

    return {
        "query": player_query,
        "ruling_type": ruling_type,
        "confidence": result.confidence,
        "rule_chain": result.provenance,      # shown to players for transparency
        "contradictions": result.contradictions,
        "gm_context": f"{gm_prefix}: {result.answer}",
        "requires_human_review": result.tier == "indeterminate",
    }

# --- Campaign session: track all rulings ---

def run_session(tracker: CoverageTracker, player_queries: list[str]) -> dict:
    """Run a full session, tracking rule coverage."""
    rulings = []
    appeals = 0

    for query in player_queries:
        ruling = arbitrate_ruling(tracker, query)
        rulings.append(ruling)
        # Indeterminate rulings still require human GM call — count as potential appeal
        if ruling["requires_human_review"]:
            appeals += 1

    # Post-session coverage report
    coverage = tracker.report()

    return {
        "session_rulings": len(rulings),
        "definitive_rulings": sum(1 for r in rulings if r["ruling_type"] == "DEFINITIVE"),
        "gm_call_rulings": sum(1 for r in rulings if r["ruling_type"] == "GM_CALL"),
        "potential_appeals": appeals,
        "rule_coverage_pct": coverage.coverage_pct,
        "never_triggered_rules": len(coverage.dead_rules),
        "most_used_rules": coverage.most_used_rules[:5],
    }
```

## Results

| Metric | Before | After |
|---|---|---|
| GM ruling appeals per session | 3.2 | 0.29 (91% reduction) |
| Staff time per session (appeals) | 45 min | 4 min |
| Rule chain visible to players | No | Yes (full provenance) |
| Consistent rulings across campaigns | No | Yes (deterministic) |
| Circular dependencies in D&D SRD found | 0 known | 3 documented and published |
| Game systems supported | 12 | 12 (all compiled into rulegraph) |

The 91% reduction in appeals came primarily from the `provenance` field in `ArbitrationResult`:
players could see exactly which rules the ruling was based on. When they disagreed, they had a
specific rule ID to point to, making disputes resolvable in seconds rather than requiring a
staff member to look things up. The 9% of remaining appeals were all `tier: "indeterminate"`
rulings — cases where the rules genuinely require interpretation, which rulegraph correctly
flags rather than fabricating a determinate answer.

## Key Takeaways

- `find_cycles()` is the most surprising capability for game designers — circular rule
  dependencies are invisible to the human eye in a 900-rule SRD but computationally trivial to
  detect. TableTop Engine's findings were shared with the publisher.
- The `tier: "determinate"` vs `tier: "indeterminate"` classification is the product-defining
  distinction: players accept "the rules require GM interpretation" far better than a wrong
  definitive ruling.
- `ArbitrationResult.provenance` shown to players reduces appeals by creating shared ground
  truth — disputes become "I read rule PHB.reckless_attack differently" not "the GM is wrong."
- `CoverageTracker.report().dead_rules` is valuable for custom game systems: rules that are
  never triggered are candidates for removal, making the game system simpler.
- The LLM's role shifts from "rule interpreter" to "narrative expressionist" — it wraps the
  deterministic `ArbitrationResult` in prose, producing a ruling that is both accurate and
  engaging.

## Try It Yourself

```bash
pip install rulegraph

# Add rules representing a complex interaction
rulegraph add-rule SRD5e.reckless_attack \
    "You can attack recklessly. Attackers gain advantage on all melee attacks this turn." \
    --type mechanic --tag combat --tag advantage

rulegraph add-rule SRD5e.sentinel \
    "When you hit a creature with an opportunity attack, its speed becomes 0." \
    --type mechanic --tag combat --tag opportunity

rulegraph add-edge SRD5e.sentinel SRD5e.reckless_attack requires \
    --condition "when making opportunity attack"

# Query
rulegraph query "Can I use Reckless Attack and trigger Sentinel in the same turn?"

# Check for cycles
rulegraph status
```
