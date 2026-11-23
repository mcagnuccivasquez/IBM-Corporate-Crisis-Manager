# Session · 2026-11-23 · Alibek · a4-checks-integration

| Field | Value |
|---|---|
| Who | Alibek |
| Start → end | 22:55 → 23:15 |
| Tool / LLM | IBM Bob |
| Working on | A4 Critic & Outlook — integrate `check_other_agents` as first pass, build `a4_critic.py`, prompt, tests |
| Branch | alibek/a4-critic-outlook-and-scenarios |
| Goal | Implement `src/agents/a4_critic.py`: run Serdar's `check_other_agents` as a free pre-pass, then LLM QA + Outlook; write acceptance tests from spec §8. |

## Log
- 22:55 · Session started; `git pull` → Serdar's `src/report/checks.py` already in main via merged PRs; merged `origin/main` into branch
- 22:55 · Read `agents/A4_critic_outlook.md`, `src/contracts.py`, `src/report/checks.py`, `tests/fixtures/state_v1_S1.json`, stubs, pipeline.py REAL_AGENTS table
- 22:58 · Created `src/agents/a4_critic.py` — two-step: free pre-pass via `check_other_agents`, then LLM via `call_structured`; label→agent mapping; verdict correction; `run` alias for pipeline
- 23:00 · Created `src/prompts/a4_critic.md` — full checklist (G1-G3, T1-T12, M1-M6), outlook requirements, rules
- 23:02 · Created `tests/test_a4_critic.py` — 18 tests: 8 unit (pre-pass), 10 integration (LLM faked)
- 23:05 · `py -m pytest tests/test_a4_critic.py` → 3 failures; fixed: (1) test phrases adjusted (KB-10 reliability_note contains 'all units tested' in evidence support, so it passes correctly — use 'independent tests' in tests instead); (2) verdict correction logic extended to cover LLM PASS + blocking issues contradiction; (3) run alias added for pipeline
- 23:12 · All 18/18 tests pass; full suite: 315/316 pass (1 pre-existing Playwright Chromium failure — not our code)
- 23:12 · Updated STATUS.md: A4 row → "in progress", session added to Recent sessions

## Summary
Implemented `src/agents/a4_critic.py` with a two-step design: (1) free pre-pass using Serdar's `check_other_agents` from `src/report/checks.py` — each hit becomes a `QAIssue` with correct target agent and blocking flag; (2) LLM review (Sonnet 5.5) with the pre-pass hits injected into the user message so the LLM can't silently miss them. Pre-pass hits are merged into the final output even if the LLM omits them, and the verdict is always corrected to REVISE if any blocking issue is present. Added `run` alias so the pipeline picks it up as a real agent.

## Done
- `src/agents/a4_critic.py` — full implementation, `run` alias for pipeline
- `src/prompts/a4_critic.md` — system prompt with G1-G3, T1-T12, M1-M6 checklist
- `tests/test_a4_critic.py` — 18 tests: pre-pass unit tests + all 4 spec §8 acceptance tests
- `STATUS.md` updated (A4 row, recent sessions)
- `sessions/2026-11-23_Alibek_a4-checks-integration.md` created

## Not done / blockers
- Live API test (needs Anthropic key) — blocked until key is available
- `run = a4` alias means pipeline will auto-pick-up the real agent; remove `a4` from `ACME_STUB_AGENTS` to activate

## Next steps (for whoever picks this up)
- Run a live S1 turn with the real A4: `ACME_STUB_AGENTS=a1,a2,risk,a3,a5` or use the app
- Check that Appendix C safety net comes out empty on a clean S1 run
- If any new scenario deliberately plants a T11 trap, A4 should catch it as blocking before the PDF

## Files touched
- `src/agents/a4_critic.py` (created)
- `src/prompts/a4_critic.md` (created)
- `tests/test_a4_critic.py` (created)
- `STATUS.md` (updated: A4 row + recent sessions)
- `sessions/2026-11-23_Alibek_a4-checks-integration.md` (this file)

## Needs director review
- none — no contract or spec changes; only new files in the A4 boundary
