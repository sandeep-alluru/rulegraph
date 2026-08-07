# Real-world cases driving rulegraph

Mined from farm queue (eagle-eyes) and public policy/tool-gate incidents.

## Case POLICY-ARBITRATION (farm) — CRITICAL

**Source:** eagle-eyes `REAL_WORK_QUEUE` P2 — *COI / endorse rules*; CLOSED_LOOP
expects a policy gate with determinate allow/deny + provenance.

**What failed:**

1. COI and endorsement policies lived as prose / memory, not a **compiled**
   rule graph that arbitration can query.
2. Agents could endorse or speak under conflict of interest without a
   load-bearing gate (no provenance, no conflict check).
3. Empty or cyclic rulebooks still looked “configured” while never refusing.

**Public twins:**

| Case | Mapping |
|------|---------|
| AgentUQ (HN) | Runtime gate for LLM decisions |
| AgentWard (HN) | Post-deletion policy enforcement |
| MAFIA (arXiv 2608.03844) | Policy + HITL on audit/tools |
| LEGAL-NO-AUTOFIX (worldoracle twin) | Legal gates never auto-fix |

**Product fix in this repo:**

| Control | API |
|---------|-----|
| Farm pack | `compile_farm_policy_graph()` — COI + endorse + legal |
| Graph gate | `gate_policy_graph` — empty FAIL_LOUD; critical conflicts FAIL |
| Result gate | `gate_arbitration` — provenance / determinate / contradictions |
| E2E | `gate_policy_query(graph, query)` |
| Raise forms | `assert_policy_ok`, `assert_arbitration_ok` |

**Tests:** `tests/test_policy_arbitration.py`

**Non-Ornament:** Call `gate_policy_query` (or graph + arbitration gates)
**before** endorse/COI-sensitive side effects. Compiling farm rules once is
not enough without the gate reader.

---

## Case LOGPROB-GATE — AgentUQ token-logprob runtime reliability

**Source:** Track B public research (`20260807T001222Z`):

| Incident / project | Note |
|--------------------|------|
| AgentUQ (HN Show HN) | https://github.com/antoinenguyen27/agentUQ — logprob gate for agent steps |
| AgentWard (HN) | post-deletion runtime enforcer (pairs with groundcrew DB-WIPE) |
| Tool-use brittle SQL/shell | free-form tool args executed without confidence signal |

**What fails:**

1. Agents execute tool calls (SQL, shell, selectors, JSON leaves) with **no**
   provider logprobs captured — confidence is phantom.
2. Generations with low mean or catastrophic min token logprob still run
   high-risk tools.
3. Risk is not localized to the brittle span (tool args vs narrative).

**Product in this repo:**

| Control | API |
|---------|-----|
| Summarize | `summarize_logprobs(logprobs)` → mean/min/confidence |
| Runtime gate | `gate_logprob(...)` — empty FAIL_LOUD; low score FAIL |
| Span localize | `spans={"sql_clause": [...], "tool_args": [...]}` |
| Raise form | `assert_logprob_ok(...)` |
| Defaults | `DEFAULT_MIN_MEAN_LOGPROB`, `DEFAULT_MIN_TOKEN_LOGPROB` |

**Rules (load-bearing):**

- Missing/empty logprobs when required or `high_risk` → **FAIL_LOUD**
- mean < threshold or min token < threshold → **FAIL** (`human_required` if high_risk)
- brittle named spans recorded in `GateOutcome.brittle_spans`
- Confident tokens → **PASS** with `confidence = exp(mean_logprob)`

**Tests:** `tests/test_logprob_gate.py`

**Non-Ornament:** Integrators must request provider logprobs and call
`gate_logprob` **before** executing high-risk tools. Pair with
`gate_policy_query` for COI/endorse and `groundcrew.gate_destructive` for
DROP/rm inventory. Without the pre-exec call, this library cannot stop a
brittle generation.

## Related queue IDs

- **POLICY-ARBITRATION** — this case (P2)
- **LOGPROB-GATE** — AgentUQ class (this section)
- **NORM-ENFORCE** (normsync) — unattended action without norm
- **APPROVAL-GATE** (humanproof) — owner token
- **LEGAL-NO-AUTOFIX** (worldoracle) — human_required legal
- **DB-WIPE** (groundcrew) — destructive tool inventory + approval
