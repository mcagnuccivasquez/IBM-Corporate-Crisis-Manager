# Session · 2026-11-23 · Serdar · a3-actions

| Field | Value |
|---|---|
| Who | Serdar |
| Start → end | 17:21 → 18:00 |
| Tool / LLM | Claude Code (Opus 5.5) |
| Working on | A3 Action Planner |
| Branch | serdar/a3-actions (from serdar/a5-report, PR #2 not merged yet) |
| Goal | Build A3 (`src/agents/a3_actions.py` + prompt + tests) to the pipeline interface `run(state, turn) -> A3Output`, with code checks, tested against scenarios S1–S3 |

## Log
<!-- one line per meaningful action: HH:MM · what · files -->
- 17:21 · Session started. Main now has A2 + risk (PR #6), fixture + scenarios (PR #7), per-agent stub switch (PR #9); A1 PR #8 open; PR #2 (A5) still open, no reply from Matteo to the "ready to merge" comment
- Read A3 spec, contract (`Action`, `A3Output`, `Stakeholder`), pipeline (`merge_a3`, revise loop, CLOSE), stub `a3.json`, scenarios S1–S3 (action expectations + must-not rules)
- Interface differences vs the A3 spec (contract wins): output is `A3Output(actions, stakeholders)` with only new/changed actions as full objects (A0 merges by ID); `closure_open_actions` not needed (pipeline computes `closure.open_actions` on CLOSE); A4 issues arrive in `state.qa.issues`
- Scenario inconsistency for Alibek: S1 turn 2 says ACT-001 = "retrieve sample", turns 3–4 call ACT-001 "the batch hold"
- Decision (Serdar): branch from `serdar/a5-report` so A3 can reuse `src/report/checks.py` (banned phrases, personal data)
- Decision (Serdar): A3 code checks: strict rules → one retry, then warning (owner/approver not in KB-02; unknown source IDs; changed action without a history entry for this version; reused IDs; banned phrases / personal data in A3 texts; `focus_related` missing when a focus is set). Heuristic rules → warning only (High/Critical domain without an action; major decision with < 2 options; recall/withdrawal without CEO approver; injury/authority/personal-data action without Sophie Laurent)
- 17:30 · Branch created; merged main (STATUS.md conflict: kept main's rows for others, ours for A5/A3; sessions list merged, 10 newest kept); 248 tests pass (baseline)
- Decision (Serdar): a new action the user reports as already done is created at the reported status (approved / in_progress / completed, never verified), with the user's words as reason
- Design: LLM returns a plan (`A3Plan`: new_actions, changes, stakeholders, no_action_reasons); code builds the `Action` records (IDs continue, history entry per status change for this version, earlier entries kept) → the "IDs never reused" and "history entry" rules are guaranteed by construction
- Created `src/prompts/a3_actions.md` (spec prompt + planning rules 1–9 + plan format, focus rule, revise rule, DRAFT label rule) and `src/agents/a3_actions.py` (`run`, `plan_actions`, `assemble`, hard/soft checks; Sonnet via `call_structured("A3", …, effort="high", check=…)`)
- Smoke test on Alibek's S1 fixture (simulated turn 2) found 2 false alarms → fixed: (1) "batch B. Covers" read as a name "B. Covers" (fixed in shared `src/report/checks.py`: a single letter after batch/option/and/… is a label); (2) heuristic checks now read the action title only (descriptions contain "do not claim …" guidance)
- Tightened: result evidence must be registered evidence about this incident, not a KB file
- Kept on purpose: negation counts only within 5 words, so "ACME has not seen further reports and the authorities have been notified" is still caught (test documents the trade-off)
- Added hard check against duplicates (new action with the title of an existing one, e.g. on an A4 revise run)
- Created `tests/test_a3_actions.py` (34 tests): record building, hard/soft checks, retry via llm.py, logging, pipeline two-turn test (proposed → approved, history kept, nothing duplicated)
- Updated A3 spec: §3 output per contract + plan design, §4b checks table, §5 prompt location/model, §6 acceptance tests (5 ticked, 2 need a live run) · agents/A3_action_planner.md
- 17:45 · End-to-end demo: pipeline turn with stubs + real A3 (fake AI) + real renderer → state valid, PDF rendered (scratchpad); full suite 281 passed
- Requirements audit of A3 and A5 against the brief, PROJECT R8–R18, A3 spec rules 1–9 and scenarios S1–S3; read KB-04 and S2/S3 must-not lists; checked Giacomo's A1 (PR #8): its prompt registers typed user messages as sources (`origin: user_text`), which A3 needs as result evidence
- Decision (Serdar): apply fixes 1–3 now; fixes 4–5 and the A5 agent trace later (listed under Next steps)
- Fix 1 (shared `src/report/checks.py`, also protects A5): banned phrases "asking customers for passwords or recordings" (KB-04), "account recovery proves…" (KB-09/KB-04), "data is safe / no breach occurred / no data was accessed" (KB-04, scenario S2); negated guidance passes
- Fix 2 (A3, hard): status change in a turn where the user reported nothing (no text, no attachment)
- Fix 3 (A3): empty title / what_it_does → hard; no basis without "no precedent"/"general knowledge" label, empty expected_effect → soft
- New phrases run over all 4 case fixtures: no false alarms (one true warning: handle "@kai_b" in an action title of `contract_example_state.json`)
- 17:55 · Full suite 297 passed

## Summary
Built A3 Action Planner to the pipeline interface (`run(state, turn) -> A3Output`). The LLM (Sonnet, effort high) returns a short plan; code builds the action records, so IDs, status history and the merge rule are guaranteed. Hard checks (KB-02 owners, existing sources, incident-only result evidence, duplicates, focus, banned phrases incl. new KB-04/S2 ones, status change without a user report, empty descriptions) share the one retry; soft checks warn. Audited A3 and A5 against the requirements; fixes 1–3 applied, 4–5 planned. 297 tests pass; no live run yet (API key decision pending).

## Done
- `src/agents/a3_actions.py`, `src/prompts/a3_actions.md`, `tests/test_a3_actions.py` (A3 complete for the pipeline, fake-AI tested incl. a two-turn pipeline run)
- Shared `src/report/checks.py`: name-check false alarm fixed; new banned phrases (KB-04, KB-09, scenario S2) protect A3 and A5
- A3 spec updated (output per contract, plan design, checks table, acceptance tests)
- Requirements audit of A3 and A5 (see log)

## Not done / blockers
- Live run of A3 + A5: waits for the team's API key decision
- PR #2 (A5) still not merged; this branch builds on it. Playback 2 is Tue 24 Nov
- A3 warnings only logged until Matteo decides on `A3Output.warnings`
- A4 (Alibek) not built yet: no content critique of A3's proposals in the pipeline until then

## Next steps (for whoever picks this up)
- **A3 fix 4 (prompt):** ask for each option's probable result (spec rule 2); no hold/recall when the evidence is disproved, misleading or historical (scenario S3, R18); don't generalise SC-219 (S2, trap 9)
- **A3 fix 5 (soft checks):** communication action without "DRAFT – requires approval by"; media/availability statement without Elena Rossi as approver (rule 5); P1 whose timing isn't now/24h; empty stakeholder map on v1
- **A5 (optional):** agent trace in Appendix C from `trace.jsonl` next to the PDF (D-013)
- A3 warnings are only logged until Matteo decides on `A3Output.warnings`
- Live run of A3 (Sonnet) + A5 (Haiku) on S1 turns 1–4 once the team decides on the API key

## Files touched
- `src/agents/a3_actions.py`, `src/prompts/a3_actions.md`, `tests/test_a3_actions.py` (new)
- `src/report/checks.py`, `tests/test_a5_narrative.py` (A5-owned, changed)
- `agents/A3_action_planner.md` (A3 spec, updated)
- `STATUS.md` (merge conflict resolved; A3 row; recent sessions), this file
- No files owned by other agents were edited

## Needs director review
<!-- contract / method / interface changes proposed but NOT applied -->
- **`A3Output.warnings: list[str]`** (proposal): A3's check warnings have no place in the contract (unknown fields are rejected). Proposal: add the field; the pipeline turns each into a non-blocking `QAIssue(target="A3")`, so they appear in the report's Appendix C. Until then A3 logs them.
- **A3 spec updated** (`agents/A3_action_planner.md`): output follows the contract (`A3Output`), `closure_open_actions` removed (pipeline does it), plan-based design, checks table. Please confirm.
- **Shared check fix:** `src/report/checks.py` (A5-owned) now ignores single letters after "batch/option/and/…" in the name check; affects A5 too (all A5 tests pass).
- **For Alibek:** S1 scenario uses ACT-001 for two different actions (turn 2: retrieve sample; turns 3–4: batch hold). Also: A4 can rely on A3's guarantees (IDs, history, KB-02 owners) and focus on content (trap checks, grounding).
- **Merge order:** this branch starts from `serdar/a5-report`; please merge PR #2 first, then the A3 PR shows only A3 changes.
