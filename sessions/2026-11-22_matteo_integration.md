# Session · 2026-11-22 · Matteo · integration

| Field | Value |
|---|---|
| Who | Matteo (director) |
| Start → end | 21:20 → 22:10 |
| Tool / LLM | Claude Code (Opus 5.5) |
| Working on | A0 integration: merge teammates' PRs, per-agent stub switch |
| Branch | matteo/stub-agents-switch |
| Goal | Get the reviewed agents into main and keep the app usable while other agents are still being fixed |

## Log
- 21:20 · Re-checked Junda's PR #6 after round-2 fixes: `_STUB_MODE` removed (A2 always calls `llm.call_structured`, verified with an intercepted call), F4 names the justification, "Legal/regulatory"; Alibek's PR #7: fixture valid (CASE-001, ACT-001 owner Maya Chen, domain_projection folded into outlook.reasons). main + #6 + #7: 140 tests pass
- 21:30 · Matteo merged PR #6 and PR #7 (STATUS.md conflict resolved with "Accept both"); local main updated, 140 tests pass; app restarted
- 21:35 · Found: Giacomo's `src/agents/a1_evidence.py` was pushed straight to main on 2026-11-21 (commit 6c16442, message "."), no PR/review. It defines its own models, calls the SDK directly on `claude-opus-4-5`, its prompt file is missing, and its output fails the contract `A1Output` (5 errors) → with the stub switch off, every report turn fails at A1 after a paid Opus call. Only hardcoded model in `src/` (grep)
- 21:40 · Matteo: do option A (per-agent stub switch) + draft message to Giacomo; recommended branch protection on main (Matteo to enable)
- 21:50 · Option A: `pipeline.py` `ACME_STUB_AGENTS` (comma list of slots forced to their stub, not even imported; unknown names ignored with a warning; "Agents in use" shows `stub (ACME_STUB_AGENTS)`), `.env.example` documented, `tests/conftest.py` blanks the variable so tests never depend on a personal `.env`, 3 new tests · pytest 143 passed. Matteo's `.env`: `ACME_STUB_AGENTS=a1`; app restarted: A1 stub, A2 + risk real
- 21:55 · Message to Giacomo drafted (contract A1Output, `call_structured` instead of direct SDK/Opus 4.5, commit prompt file, `kb_source`, branch + PR); added explicit "Sonnet 5.5 / Haiku 5.5, never Opus" paragraph
- 22:05 · Giacomo's assistant asked for `kb.py` to inject the KB into his prompt: not needed (`llm.py` already puts rules + KB first in every system prompt, cached and shared); his latest commit `d83b8e8` on `giacomo/a1-evidence` already removed the placeholder and uses `call_structured`. No PR yet → Matteo asks him to open one
- 22:10 · Committed + pushed branch `matteo/stub-agents-switch`

## Summary
Merged Junda's A2 + risk engine (PR #6) and Alibek's fixture + scenarios (PR #7) after re-checking them. Found Giacomo's unreviewed A1 in main, which broke real runs; added a per-agent stub switch (`ACME_STUB_AGENTS`) so the app runs Junda's real agents while A1 is fixed, and asked Giacomo for a contract-compliant A1 via a PR.

## Done
- PR #6 and #7 re-checked and merged; local main updated; app restarted
- `ACME_STUB_AGENTS` per-agent stub switch + tests (143 pass); Matteo's `.env` uses `a1`
- Messages to Giacomo drafted

## Not done / blockers
- Giacomo: open the PR for `giacomo/a1-evidence`; then review and remove `a1` from `ACME_STUB_AGENTS`
- Serdar: PR #2 fixes still pending
- Branch protection on `main` (Matteo to enable in GitHub settings)

## Next steps
- Merge this branch; review Giacomo's PR when it opens
- First real S1 turn with A1 + A2 + risk live; read `trace.jsonl` for real cost per turn

## Files touched
- `src/pipeline.py`, `.env.example`, `tests/conftest.py` (new), `tests/test_pipeline.py`, `STATUS.md`, this file

## Needs director review
- none
