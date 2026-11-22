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

## Summary

## Done
-

## Not done / blockers
-

## Next steps (for whoever picks this up)
-

## Files touched
- src/agents/a1_evidence.py (rewritten)
- src/prompts/a1.md (new)
- tests/test_a1_evidence.py (new)
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
