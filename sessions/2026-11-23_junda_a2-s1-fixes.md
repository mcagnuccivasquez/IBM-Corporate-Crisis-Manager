# Session · 2026-11-23 · Junda · A2 S1 live-run fixes

| Field | Value |
|---|---|
| Who | Junda |
| Start → end | — → session end |
| Tool / LLM | IBM Bob |
| Working on | A2 Impact & Risk — post-S1-live-run fixes |
| Branch | junda/a2-impact-risk |
| Goal | Apply two fixes from Matteo's S1 turn-1 live run: (1) source_ids claim-ID slip → check= lambda + prompt fix; (2) economic S=3 vs S=2 → coordinate with Alibek |

## Log
- · Read STATUS.md, session template, a2_impact.py, a2_common.md, llm.py, kb.py, test_a2_integration.py — baseline confirmed
- · Fix 1a: updated `src/prompts/a2_common.md` — rewrote source-citation rule (source_ids = U-xx / KB-xx only, never C-xxx); added `incident_evidence` to basis enum in output example
- · Fix 1b: added `_check_source_ids` inner function + `check=_check_source_ids` to `call_structured` call in `src/agents/a2_impact.py`; added `from src.kb import unknown_kb_ids` import
- · Fix 1c: added `TestSourceIdsCheckLambda` (5 tests) to `tests/test_a2_integration.py` — covers C-xxx flagged, valid pass, unknown U-xx, unknown KB-xx, multiple bad IDs
- · Full test run: 145/145 passed (5 new tests all green)
- · Fix 2 (economic S=3 vs S=2): raised as method question for Matteo + Alibek — see Needs director review

## Summary
Applied Fix 1 from Matteo's S1 live-run feedback in full: tightened the prompt to ban C-xxx from `source_ids`, added a `check=` lambda to `call_structured` so any slip auto-retries, and added 5 new tests (145/145 green). Fix 2 (economic S=3 vs S=2) is a method/anchor question — not safe to change unilaterally. Raised under Needs director review for Matteo + Alibek. Checked git: Giacomo has not started A1 yet (no branch, no commits).

## Done
- Fix 1 (source_ids slip): prompt tightened, `check=` lambda added to `call_structured`, 5 new tests all green (145/145)
- Fix 2 (economic S=3 vs S=2): identified as a method/anchor question; flagged for director review

## Not done / blockers
- Economic S=3 vs S=2 unresolved — needs Matteo + Alibek to agree on whether reach belongs in Severity (current anchor wording) or Likelihood only (D-014); see Needs director review

## Next steps (for whoever picks this up)
- Once Matteo decides on economic anchor clarification: either update `src/prompts/a2_economic.md` or update Alibek's expected fixture
- After Giacomo's A1 lands: run end-to-end S1 turn 1 again to verify 0 reference errors

## Files touched
- `src/prompts/a2_common.md`
- `src/agents/a2_impact.py`
- `tests/test_a2_integration.py`
- `sessions/2026-11-23_junda_a2-s1-fixes.md`
- `STATUS.md`

## Needs director review
- **Economic severity anchor ambiguity (D-014):** A2b gave S=3 on S1 turn-1 citing "broad public attention … 1.2k reposts" and upper-bound replacement cost €330k (11,000 units). Matteo's note says reach belongs in Likelihood only. The current S=3 anchor text reads "broad public attention" which the model used for Severity. Two options:
  1. Clarify the economic lens prompt (`a2_economic.md`) to say reach/attention is Likelihood only, and cost band is the sole Severity driver for economic domain → S1 expected S=2 (€10k–100k realised cost band).
  2. Keep the anchor as-is and update Alibek's expected fixture to S=3.
  Junda's read: option 1 is cleaner (aligns with D-014 intent). Bring to Matteo before changing anything.
