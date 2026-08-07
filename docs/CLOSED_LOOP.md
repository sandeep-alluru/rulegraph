# Closed loop — `rulegraph`

**Status:** reader wired (eagle-eyes / 2026-08-06) — **POLICY-ARBITRATION**  
**Owner loop:** L7

## Load-bearing job

Typed rule graph + arbitration for policies/rules

## Who reads the output?

- `gate_policy_graph` / `gate_arbitration` / `gate_policy_query`
- Farm pack: `compile_farm_policy_graph()` (COI + endorse + legal)

## What outcome changes?

Empty graph → FAIL_LOUD. Critical conflicts → FAIL. Missing provenance /
indeterminate when required → FAIL. Determinate allow/deny with provenance → PASS.

## When NOT to use (anti-ornament)

Not a substitute for SEAL content gates without wiring

## Non-Ornament checklist

- [x] Reader implemented (`closed_loop` gates + farm pack)
- [x] Empty/wrong output fails loudly
- [x] Not free MCP without gate
- [ ] Linked gap IDs in mem0 when improving

## Related failures (farm memory)

- 2026-07-22 MCP buffet trim: write-only tools removed from Foundry framework
- D-FOGHORN: misuse of append-only fact log as current state
- Dual-path mem0: never rely on MCP-only for critical memory

## Daily rotation note

This file exists so pillar **C (closed loop)** can rise with real wiring over time. Prefer small daily commits that move a checkbox toward done.

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-07
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-07
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-07
- pytest_rc: 0
- node: clawer-samurai-2
