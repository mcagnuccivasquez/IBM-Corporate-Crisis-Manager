# Session · 2026-11-21 · project lead · director setup

| Field | Value |
|---|---|
| Who | project lead |
| Tool / LLM | Claude Code (director chat) |
| Working on | planning / architecture |
| Goal | Review the original 5-agent plan, decide the architecture, create the project and agent specs and the collaboration protocol |

## Log
- Read the brief, the original plan (docs/IBM_PROJECT_PLANNING_original.pdf), the KB README, all 12 ACME PDFs, the CSV and 3 screenshots
- Reorganised folders: `docs/`, `knowledge_base/` (copied from the `UseCase2-…` export folder, which can be deleted)
- Decisions D-001…D-008 recorded in PROJECT.md §12
- Created PROJECT.md, AGENTS.md, CLAUDE.md, STATUS.md, README.md, .gitignore, agents/A0–A5, sessions/_TEMPLATE.md

## Summary
Original plan kept in spirit (evidence → impacts → actions → validation → report) with 5 changes: an A0 orchestrator for the versioned loop, a single A3 instead of 3a/3b/3c, a deterministic 4-level risk engine (S×L + floors), focus doesn't change scores, and A4 as critic + outlook. Build approach: Python code in Git.

## Next steps
- Create the GitHub repo, invite the team, assign owners in STATUS.md
- Start P0 foundations (contracts, llm wrapper, KB extraction, risk.py) and scenario S1

## Needs director review
- none
