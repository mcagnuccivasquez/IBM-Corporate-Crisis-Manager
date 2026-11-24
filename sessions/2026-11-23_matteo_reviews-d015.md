# Session · 2026-11-23 · Matteo · reviews + D-015

| Field | Value |
|---|---|
| Who | Matteo (director) |
| Start → end | 17:55 → 18:30 |
| Tool / LLM | Claude Code (Opus 5.5) |
| Working on | Director reviews of PR #8 (A1), #2 (A5), #10 (A3); D-015 A3 warnings |
| Branch | matteo/d015-a3-warnings |
| Goal | Get A1, A5 and A3 into main and keep the app running on the real agents before Playback 2 |

## Log
- 17:55 · PR #8 (Giacomo, A1) reviewed: own files only, uses `call_structured` + contract `A1Output`; 176 tests on main + PR; full pipeline run High, no reference errors. Two follow-ups (attachment paths → `Source.file`; register cited KB sources with `kb_source`) sent to Giacomo. Matteo merged; `.env` `ACME_STUB_AGENTS=a1` → empty; app restarted with real A1
- 18:05 · PR #2 (Serdar, A5) re-reviewed: all 10 review items fixed (`run(state, turn, prev_state)`, `render_pdf(state, pdf_path)`, `call_structured`, no None keys); 281 tests on main + PR; pipeline run with fake Claude → 5-page PDF; Claude down → PDF still produced with "Narrative not available" + warning. Director items approved (spec, `A5-factcheck` call, safety net). Follow-ups for Serdar: v1 badge "— → HIGH", loose number check (any number anywhere in the state counts), full names not detected. Matteo merged; app restarted with real A5 + renderer
- 18:10 · Message to Alibek drafted: A5 safety net (`check_other_agents`) overlaps A4's T11; suggestion to reuse it as a free first pass in A4 and map hits to `QAIssue`s
- 18:15 · PR #10 (Serdar, A3) reviewed: real changes are A3 + `checks.py` additions (GitHub's 19-file list is inflated by an old merge base; merge result leaves A1 untouched); 330 tests; two-turn pipeline run: ACT-001 created (proposed) then completed with history kept. Found: A3 soft warnings only go to a log nobody reads → approve Serdar's `A3Output.warnings` proposal. Matteo merged
- 18:25 · D-015: `A3Output.warnings: list[str]` (contracts.py); pipeline turns each into a non-blocking `QAIssue(target="A3")`, keeping only the latest A3 run's warnings after an A4 revise; `a3_actions.run()` fills the field (Serdar's file, one line + docstring); A3 spec line updated (Serdar's file); PROJECT.md §12 D-015 row; 3 tests (2 pipeline, 1 in test_a3_actions.py) · pytest 332 passed
- 18:35 · STATUS.md cleaned up (director): repeated "Accept both" merges had left duplicate and stale rows in all owners' lines and 16 recent sessions; component table rebuilt from what is merged in main (PR numbers), working notes refreshed, milestones P0 + repo ticked, recent sessions de-duplicated to 10. Owners: please check your row

## Summary
Reviewed and merged A1 (Giacomo, PR #8), A5 (Serdar, PR #2) and A3 (Serdar, PR #10). The app now runs real A0, A1, A2, risk, A3, A5 and the PDF renderer; only A4 is still a stub. Approved D-015 so A3's check warnings reach the report's Appendix C instead of a log file.

## Done
- PR #8, #2, #10 reviewed; follow-up messages for Giacomo, Serdar and Alibek drafted
- D-015 implemented + tests (332 pass)

## Not done / blockers
- A4 (Alibek) still a stub, starts 25 Nov
- First live S1 run with real agents: check cost in `trace.jsonl`
- Branch protection on `main` (Matteo to enable)

## Next steps (for whoever picks this up)
- Merge this branch; live S1 turn before Playback 2 (24 Nov); Serdar: v1 badge fix before the demo

## Files touched
- `src/contracts.py`, `src/pipeline.py`, `src/agents/a3_actions.py` (Serdar's, D-015 one-liner), `agents/A3_action_planner.md` (Serdar's, D-015 line), `PROJECT.md` (§12 D-015), `tests/test_pipeline.py`, `tests/test_a3_actions.py` (Serdar's, one assert), `STATUS.md`, this file

## Needs director review
- none (D-015 decided by the director in this session)

## Log (continued, after PR #11)
- 18:50 · First live S1 turn 1 (`python -m src.pipeline`, stand-in screenshot): **A3 rejected by the API** (400 "compiled grammar is too large"; `A3Plan` has 31 optional + 15 nullable fields). Probed schema variants (rejected calls are free): only "every field required AND no nullable fields" is accepted. CASE-003 has no version ($0.27 spent on A1 + A2). Matteo chose: test with A3 stubbed now, Serdar fixes A3 (message drafted)
- 19:05 · S1 turn 1 rerun with `ACME_STUB_AGENTS=a3` → CASE-004 v1, 17-page PDF, $0.28 (A1 $0.075, A2 3×$0.067, A5 2×$0.003). Risk High, F1, prev null, confidence low (as expected). Findings: A2 cites claim IDs in impact `source_ids` (9 reference errors); A2 rep L=3 (stand-in screenshot shows reach counts) and economic S=3 vs expected 2; A1 writes product "PowerCharge X PCX-100" / market "Germany" (expected "PCX-100" / "DE"), `Source.file` empty (known follow-up); A5 narrative called C-005 "confirmed" (caught as soft warning, no retry); no prompt-cache reads between agents (each call writes ~12k tokens) → investigate in `llm.py` after the demo
- 2026-11-24 12:35 · PR #12 (Alibek, A4) reviewed: own files only, clean merge, 350 tests; `A4Output` schema accepted by the live API (probe). Pre-pass on the real S1 v1 state (CASE-004): 5 hits, all blocking: 3 false banned-phrase alarms (A2 quotes "all units tested"/"independent tests" as things not to say), 2 handles (@lena_m poster, @kai_b from A3 stub). Pipeline run with fake Claude: blocking pre-pass → REVISE → A3 re-run + 2nd A4 call, report still ends with a blocking issue. Asked Alibek: pre-pass hits non-blocking, LLM decides; minor: docstring, `basis_source_ids` not in Outlook, de-dup, S1 ACT-001 used twice. Open policy question for Matteo: public handles in the internal report
- 12:40 · `.env` `ACME_STUB_AGENTS=a3` (A3 schema rejected live until Serdar's fix); stale app process from the previous session (PID on :8501) stopped, app restarted
- 12:55 · Drive D: was briefly disconnected (no changes made meanwhile). D-016 decided by Matteo: a poster's public social handle may appear in the internal report, never in public-facing wording; emails, phones, customer names stay flagged. PROJECT.md §8 trap 11 note + §12 D-016 row (branch `matteo/d016-handles`). Follow-ups: Serdar (`find_personal_data` stops flagging handles; skip quoted banned phrases), Alibek (A4 flags handles only in public drafts, blocking)
