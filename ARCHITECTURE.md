# rulegraph Architecture

## Overview

rulegraph is a pure-Python library for loading game rulebooks into a typed directed graph
and arbitrating natural-language questions against that graph with deterministic provenance.

## Core Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI / API / MCP                           │
│   cli.py (Click)      api.py (FastAPI)    mcp_server.py (MCP)   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                       RuleArbiter                                │
│   Keyword matching → Classification → Contradiction detection    │
│   → ArbitrationResult (tier, confidence, provenance)            │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        RuleGraph                                 │
│   RuleNode (content-addressed)   RuleEdge (typed relations)     │
│   find_rules(tag, type, text)    get_edges(source, relation)    │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                        RuleStore                                 │
│   SQLite: nodes, edges, results tables                           │
│   save_node / save_edge / load_graph / save_result               │
└─────────────────────────────────────────────────────────────────┘
```

## Data Model

### RuleNode
Content-addressed by `SHA-256[:16](rule_id)`. Carries:
- `rule_id`: human-readable identifier (e.g. `PHB.attack_roll`)
- `text`: full rule text
- `node_type`: semantic category (`mechanic`, `narrative`, `formula`, etc.)
- `tags`: free-form search labels
- `source`: originating document
- `confidence`: certainty that the rule is deterministic

### RuleEdge
Content-addressed by `SHA-256[:16](source_id|target_id|relation)`. Relations:
- `modifies` — one rule changes how another operates
- `supersedes` — one rule replaces another (errata, variant rules)
- `requires` — one rule depends on another being in effect
- `exception-to` — one rule creates a special case for another

### ArbitrationResult
Structured answer to a query:
- `tier`: `determinate` | `indeterminate` | `unknown`
- `confidence`: aggregate confidence score
- `provenance`: list of `rule_id`s that produced the answer
- `contradictions`: `rule_id`s flagged by supersedes/exception-to edges

## Arbitration Algorithm

```
query(question)
  │
  ├─ _extract_keywords(question)
  │    Strip stop words, lowercase, tokenize
  │
  ├─ _find_relevant(keywords)
  │    Score each node: +2 text match, +3 rule_id match, +2 tag match
  │    Return nodes with score > 0, sorted descending
  │
  ├─ _detect_contradictions(relevant)
  │    Find nodes whose rule_id appears as target of supersedes/exception-to
  │
  ├─ _classify(relevant)
  │    If any node_type in DETERMINATE_TYPES → "determinate"
  │    If any node_type in INDETERMINATE_TYPES → "indeterminate"
  │    Fallback: if avg(confidence) >= 0.9 → "determinate" else "indeterminate"
  │
  ├─ _aggregate_confidence(relevant, contradictions)
  │    avg(confidence) - 0.15 × contradiction_count
  │
  └─ _synthesize_answer(question, relevant, contradictions, tier)
       Build human-readable answer citing up to 3 rules
```

## Storage Schema

```sql
CREATE TABLE nodes (
    id TEXT NOT NULL,
    rule_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    node_type TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',   -- JSON array
    source TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    condition TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE results (
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    tier TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT '[]',   -- JSON array
    confidence REAL NOT NULL DEFAULT 0.0,
    contradictions TEXT NOT NULL DEFAULT '[]',
    recorded_at REAL NOT NULL
);
```

## Module Map

| Module | Role |
|--------|------|
| `rule.py` | All core data classes + RuleGraph + RuleStore + RuleArbiter |
| `report.py` | Rich terminal, JSON, and Markdown formatters |
| `cli.py` | Click command group |
| `api.py` | FastAPI app with /rule, /edge, /query, /rules, /results |
| `mcp_server.py` | MCP stdio server with add_rule, query_rules, arbitrate |

## Design Decisions

1. **Single module for data model**: All domain objects in `rule.py` keeps imports simple for library consumers.
2. **Content-addressed IDs**: Same rule always same ID — safe to load the same rulebook twice without duplicates.
3. **Keyword-based retrieval**: No external NLP dependencies. The library is pure Python + SQLite.
4. **Tier classification by node_type**: Game designers label rules as mechanics vs. flavor. This label drives the tier.
5. **SQLite persistence**: Zero-config, file-based, supports concurrent reads.
