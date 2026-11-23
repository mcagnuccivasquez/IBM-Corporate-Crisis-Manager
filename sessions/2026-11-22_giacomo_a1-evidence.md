# Session · 2026-11-22 · Giacomo · a1-evidence

| Field | Value |
|---|---|
| Who | Giacomo Castelmare |
| Start → end | 16:59 → ongoing |
| Tool / LLM | IBM Bob |
| Working on | A1 Evidence Analyst |
| Branch | giacomo/a1-evidence |
| Goal | Implement A1 Evidence Analyst: rewrite a1_evidence.py using contracts.py + llm.py, write the agent prompt, write tests |

## Log
- 16:59 · session started; pulled main (already up to date)
- 17:00 · read STATUS.md, A1_evidence_analyst.md, contracts.py, llm.py, pipeline.py – interface check done (see below)
- 17:00 · created branch giacomo/a1-evidence
- 17:01 · rewrote src/agents/a1_evidence.py using contracts.py A1Output + llm.call_structured
- 17:02 · wrote src/prompts/a1.md (cached agent prompt, per spec §6 + PROJECT §5 definitions)
- 17:03 · wrote tests/test_a1_evidence.py (unit + integration-level tests)
- 17:04 · updated STATUS.md
- 20:59 · director review applied: prompt renamed a1.md → a1_evidence.md; _build_context_block refactor; check= lambda for KB IDs
- 21:03 · updated tests/test_a1_evidence.py: 33 tests all pass

## Summary
Addressed all 4 issues raised in director review: (1) already using shared contract; (2) already using call_structured; (3) renamed prompt file to a1_evidence.md so load_prompt works without fallback; (4) added unknown_kb_ids check= lambda. Refactored _build_user_content → _build_context_block returning str. Tests updated: 33 pass.

## Done
- src/agents/a1_evidence.py: _build_context_block, run() with check= lambda, load_prompt("a1_evidence")
- src/prompts/a1_evidence.md: renamed from a1.md (content unchanged — already complete)
- tests/test_a1_evidence.py: updated + 7 new tests; 33 total, all pass

## Not done / blockers
- pymupdf not installed in dev env → 9 test_pipeline.py tests fail (pre-existing, unrelated to A1)

## Next steps (for whoever picks this up)
- Merge foundations branch (matteo/p0-foundations) so pipeline.py picks up real A1
- Remove a1 from ACME_STUB_AGENTS in .env to run with real A1 in app
- Run `python -m src.pipeline --text "Customers report hot PCX-100 chargers"` for first real end-to-end test

## Files touched
- src/agents/a1_evidence.py (updated)
- src/prompts/a1.md → src/prompts/a1_evidence.md (renamed)
- tests/test_a1_evidence.py (updated)
- STATUS.md (updated)

## Needs director review
- Interface check results: see below

### Interface check — A1 vs spec/contract
Checked `agents/A1_evidence_analyst.md` §3 (Output) against `src/contracts.py` A1Output:

| Spec §3 field | contracts.py A1Output | Match? |
|---|---|---|
| `new_sources: [Source]` | `sources: list[Source]` | ⚠ **name mismatch** – spec says `new_sources`, contracts.py uses `sources` |
| `new_claims: [Claim]` | `claims: list[Claim]` | ⚠ **name mismatch** – spec says `new_claims`, contracts.py uses `claims` |
| `claim_updates: [ClaimUpdate]` | not present | ⚠ **missing** – contracts.py has no `claim_updates`; updates are expressed by returning the full updated Claim with an appended `change_history` entry |
| `evidence_gaps: [EvidenceGap]` | `open_questions: list[OpenQuestion]` | ⚠ **name + model mismatch** – spec uses `evidence_gaps`, contracts.py uses `open_questions` with `OpenQuestion(question, owner, raised_in_version, closed_in_version)` |
| `trend_notes: [str]` | not present | ⚠ **missing** – contracts.py A1Output has no `trend_notes` field |

**Resolution (applied):** `contracts.py` is the binding contract (per AGENTS.md). The spec §3 output block is an earlier draft. The real implementation follows `A1Output` from contracts.py exactly:
- `sources` + `claims` (new or updated; A0 merges by ID)
- `open_questions` (using `OpenQuestion`)
- no `trend_notes` or `claim_updates` fields in the structured output (trends can be mentioned in claim `reliability_note` or open question text)

This discrepancy should be **flagged to the director** so the spec can be updated to match the contract.
