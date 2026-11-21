# Session · 2026-11-21 · Alibek · a4-critic-outlook-and-scenarios

| Field | Value |
|---|---|
| Who | Alibek |
| Start → end | (session start) → (session end) |
| Tool / LLM | Bob (IBM) |
| Working on | A4 Critic & Outlook · QA lead · Test scenarios S1–S3 |
| Branch | alibek/a4-critic-outlook-and-scenarios |
| Goal | Understand the full project and my responsibilities: A4 agent + test scenarios S1–S3 |

## Log
<!-- one line per meaningful action: HH:MM · what · files -->
- Session started; read AGENTS.md, STATUS.md, PROJECT.md, agents/A4_critic_outlook.md
- Created tests/fixtures/state_v1_S1.json — full CaseState v1 for S1 turn 1; risk=High, F1 floor, 7 sources, 1 claim, 3 actions; validated JSON
- Created tests/scenarios/S1/turn_1.md — turn script for S1 turn 1 (viral smoke post)
- Created tests/scenarios/S1/expected.md — expected outputs, must-have/must-not-have checks, risk calc, A4 verdict expectation
- Double-check audit against AGENTS.md + PROJECT.md: found 5 issues; fixed 4 (added domain_projection to outlook, added KB-08+KB-10 to sources, cleaned session next-steps, raised S=3 severity question to director review)

## Summary
<!-- filled at session end: 3–5 lines -->

## Done
- tests/fixtures/state_v1_S1.json — complete, valid, grounded in KB data
- tests/scenarios/S1/turn_1.md — turn 1 user message + attachment description
- tests/scenarios/S1/expected.md — expected outputs with trap checklist (T3–T8, T11, T12) and risk calc

## Not done / blockers
- Waiting for Matteo's P0 foundations (contracts.py, llm.py, kb.py) — blocks full A4 implementation
- Fixture state (tests/fixtures/state_v1_S1.json) needed ASAP by Serdar and Giacomo

## Next steps (for whoever picks this up)
- Write tests/scenarios/S1/turn_2.md + turn_3.md + turn_4.md + their expected.md files
- Write tests/scenarios/S2/ (SafeCam access) + tests/scenarios/S3/ (misleading repost)
- After foundations land: implement src/agents/a4_critic.py + src/prompts/a4_critic.md
- Write tests/test_a4_*.py with the acceptance tests from A4 spec §8

## Files touched
- sessions/2026-11-21_Alibek_a4-critic-outlook-and-scenarios.md (created, updated)
- tests/fixtures/state_v1_S1.json (created)
- tests/scenarios/S1/turn_1.md (created)
- tests/scenarios/S1/expected.md (created)

## Needs director review
- Reputational severity S=3 vs S=2 at turn 1 (single screenshot, no confirmed broad attention): S=3 anchor says "safety question on a product line in market; broad public attention" — does one viral screenshot qualify as "broad public attention"? Final risk level is High either way (F1 floor), but the domain score differs (6 vs 4). Director to confirm the preferred anchor interpretation so all agents score consistently.
