# Session · 2026-11-25 · Alibek · a4-dedup-confirmed-candidates

| Field | Value |
|---|---|
| Who | Alibek |
| Start → end | 16:05 → |
| Tool / LLM | IBM Bob |
| Working on | A4 Critic & Outlook — follow-up from Matteo's PR #12 review |
| Branch | alibek/a4-critic-outlook-and-scenarios |
| Goal | Apply Matteo's three suggested fixes: cleaner prompt, dedup-by-target+item_id merge, new INT-4 test |

## Log
- 16:05 · Read STATUS.md and git log; PR #12 merged by Matteo, follow-up fixes identified
- 16:06 · `src/prompts/a4_critic.md` — replaced conflicting "do NOT repeat" + "mark blocking only if real" instruction with unified "confirm = report as your own blocking issue with same target+item_id; otherwise ignore"
- 16:07 · `src/agents/a4_critic.py` — updated merge step: pre-pass issue dropped when LLM returned one with same (target, item_id) and item_id is not None; exact problem-text dedup retained
- 16:08 · `tests/test_a4_critic.py` — added INT-4: fake LLM confirms ACT-002 pre-pass candidate → verdict REVISE, exactly 1 ACT-002 issue in output (no duplicate), that issue is blocking
- 16:09 · `py -m pytest tests/test_a4_critic.py -v` → 19/19 passed
- 16:10 · `py -m pytest -q` → 348/351 passed; 3 pre-existing A5 PDF/Playwright failures (chromium not installed, known from STATUS.md)

## Summary

Applied all three items from Matteo's post-PR-#12 review comment:
1. Prompt now gives the LLM a single unambiguous instruction: confirm a candidate → report it blocking with same target+item_id; ignore false alarms.
2. Merge step deduplicates by (target, item_id) pair when item_id is set, so a confirmed pre-pass hit appears only once in Appendix C.
3. INT-4 test covers the new behaviour end-to-end with a fake LLM.

## Done
- Prompt instruction cleaned up (no more conflicting "do NOT repeat" vs "mark blocking")
- Code merge step: dedup by (target, item_id) when item_id is not None
- Test INT-4: LLM confirms one candidate → REVISE, no duplicate issue

## Not done / blockers
- Live API test of A4 (waiting for Matteo to run S1)

## Next steps (for whoever picks this up)
- Matteo runs live S1 with A4 and reports cost/result
- If new issues surface from the live run, address in this branch or a new PR

## Files touched
- `src/prompts/a4_critic.md`
- `src/agents/a4_critic.py`
- `tests/test_a4_critic.py`

## Needs director review
- none
