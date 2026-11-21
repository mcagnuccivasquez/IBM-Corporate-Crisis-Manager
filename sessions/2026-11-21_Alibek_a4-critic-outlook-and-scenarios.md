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
- Created tests/fixtures/state_v1_S1.json — full CaseState v1 for S1 turn 1; risk=High, F1 floor, 9 sources, 1 claim, 3 actions; validated JSON
- Created tests/scenarios/S1/turn_1.md + turn_1_expected.md — turn script + expected outputs for S1 turn 1
- Double-check audit: fixed 4 issues (domain_projection, KB-08+KB-10 in sources, session next-steps, director review note)
- Created tests/scenarios/S1/turn_2.md + turn_2_expected.md — lab confirms defect in PCX-2609-B; risk escalates to Critical (F2)
- Created tests/scenarios/S1/turn_3.md + turn_3_expected.md — hold/statement completed; F4 guard keeps risk Critical
- Created tests/scenarios/S1/turn_4.md + turn_4_expected.md — CLOSE intent; risk drops to Medium (F4 satisfied by ACT-001 verified_effective)
- Created tests/scenarios/S2/turn_1.md + turn_1_expected.md — SafeCam access; F3 floor → High
- Created tests/scenarios/S2/turn_2.md + turn_2_expected.md — 2 reused passwords resolved, 1 unexplained session remains; risk stays High
- Created tests/scenarios/S3/turn_1.md + turn_1_expected.md — misleading TravelPlug repost; risk Low/Medium, no F1, claim = misleading

## Summary
<!-- filled at session end: 3–5 lines -->

## Done
- tests/fixtures/state_v1_S1.json — complete, audited, valid JSON
- tests/scenarios/S1/ — all 4 turns (turn_1.md → turn_4.md) + 4 expected files; covers F1→F2→F4 guard→close arc
- tests/scenarios/S2/ — 2 turns covering F3, T9, partial resolution with 1 unexplained session
- tests/scenarios/S3/ — 1 turn covering misleading repost (T1, T2, no F1)

## Not done / blockers
- Waiting for Matteo's P0 foundations (contracts.py, llm.py, kb.py) — blocks A4 agent code

## Next steps (for whoever picks this up)
- After foundations land: implement src/agents/a4_critic.py + src/prompts/a4_critic.md
- Write tests/test_a4_*.py with the acceptance tests from A4 spec §8
- Confirm S=3 vs S=2 reputational severity at turn 1 with director (see Needs director review)

## Files touched
- sessions/2026-11-21_Alibek_a4-critic-outlook-and-scenarios.md (created, updated)
- tests/fixtures/state_v1_S1.json (created, audited, fixed)
- tests/scenarios/S1/turn_1.md, turn_1_expected.md (created; renamed from expected.md)
- tests/scenarios/S1/turn_2.md, turn_2_expected.md (created)
- tests/scenarios/S1/turn_3.md, turn_3_expected.md (created)
- tests/scenarios/S1/turn_4.md, turn_4_expected.md (created)
- tests/scenarios/S2/turn_1.md, turn_1_expected.md (created)
- tests/scenarios/S2/turn_2.md, turn_2_expected.md (created)
- tests/scenarios/S3/turn_1.md, turn_1_expected.md (created)

## Needs director review
- Reputational severity S=3 vs S=2 at turn 1 (single screenshot, no confirmed broad attention): S=3 anchor says "safety question on a product line in market; broad public attention" — does one viral screenshot qualify as "broad public attention"? Final risk level is High either way (F1 floor), but the domain score differs (6 vs 4). Director to confirm the preferred anchor interpretation so all agents score consistently.
