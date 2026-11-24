# Session · 2026-11-24 · Serdar · demo-fixes

| Field | Value |
|---|---|
| Who | Serdar |
| Start → end | 12:12 → |
| Tool / LLM | Claude Code (Opus 5.5) |
| Working on | A3 + A5 corrections (Matteo's review messages) |
| Branch | serdar/a3-schema-demo-fixes (from main) |
| Goal | Fix A3's schema so it runs on the live API, fix the v1 badge and the "confirmed" check before Playback 2 (today), repair checks.py; then Matteo's follow-ups |

## Log
<!-- one line per meaningful action: HH:MM · what · files -->
- 12:12 · Session started. Main: PR #2 (A5), #10 (A3), #8 (A1), #11 (D-015 `A3Output.warnings`) merged; A4 PR #12 open
- Read Matteo's 2 messages (pasted by Serdar) + `sessions/2026-11-23_matteo_reviews-d015.md`: (1) A3 rejected by the live API: "compiled grammar is too large" (A3Plan: 31 optional + 15 nullable fields); fix = every field required, no nullable fields, "" / [] / "unchanged" sentinels, plan-local stakeholder/option models + offline schema guard test. (2) v1 badge "— → HIGH". (3) "confirmed" on a non-confirmed claim → make it a hard check (live run left such a sentence in the PDF). Follow-ups: number check skips dates/IDs; full names optional
- Found: `src/report/checks.py` on main has merge leftovers: the old `_INITIAL_NAME` regex re-defined after the fixed one ("batch B. Covers" false alarm is back), the KB-09 rule duplicated (double warnings), a duplicated docstring line. 332 tests still pass (no test caught it)
- 12:13 · Branch `serdar/a3-schema-demo-fixes` from main (71808fd)
- A3 schema fix (Matteo's spec): plan models fully required, no nullable fields; `approver` "" = none; `ActionChange` uses "" / [] / "unchanged" (`new_status`, `priority`, `focus_related` "true"/"false"/"unchanged"); plan-local `PlanOption` / `PlanStakeholder` converted to the contract in code (`contract_stakeholders`); empty reason → problem; `assemble()` reads the sentinels · src/agents/a3_actions.py
- Prompt explains the "" / [] / "unchanged" convention; focus rule adjusted · src/prompts/a3_actions.md
- Tests: `full()` helper keeps test plans short but always in the strict format (also what the fake Claude returns); new: offline schema guard (all properties required, no `anyOf null`), sentinel semantics, missing field rejected, empty reason · tests/test_a3_actions.py
- Verified the guard against the old schema from main: old = 31 optional + 15 nullable (same numbers as Matteo's live finding) → guard fails; new = 0 / 0 → passes
- v1 badge: "previous → current" only when a previous level exists (header badge, section 3, section 8); test · src/report/template.html, tests/test_a5_render.py
- "Confirmed/proven" on a non-confirmed claim moved from soft to hard (A5 narrative; one retry), per Matteo's live run; test · src/report/checks.py, tests/test_a5_narrative.py
- Repaired checks.py merge leftovers (duplicate docstring line, duplicate KB-09 rule, old `_INITIAL_NAME` re-definition); regression tests ("batch B. Covers" not a name; rule labels unique, one warning per sentence)
- Specs: A5 (v1 badge; "confirmed" check hard), A3 (plan format rule + example without nulls)
- 12:17 · End-to-end pipeline turn (stubs + real A3/A5 with fake AI + real renderer): valid state, A3 warning shown as QA note (D-015), v1 badge "HIGH"; full suite 342 passed

## Summary
<!-- filled at session end: 3–5 lines -->

## Done
- 

## Not done / blockers
- 

## Next steps (for whoever picks this up)
- 

## Files touched
- 

## Needs director review
<!-- contract / method / interface changes proposed but NOT applied -->
- none
