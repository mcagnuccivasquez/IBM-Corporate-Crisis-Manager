# STATUS — current state of the project

_Last updated: 2026-11-21 · by: project lead (director session)_

**Next deadline:** Playback 2 · **Tue 24 Nov 2026** · demo target: scenario S1 turn 1 → Report v1 PDF
**Final:** Wed 2 Dec 2026

## Working now
| Who | On what | Since | Branch |
|---|---|---|---|
| — | — | — | — |

## Agents / components
| Component | Spec | Owner | Status | Next step |
|---|---|---|---|---|
| Foundations (`contracts.py`, `llm.py`, `kb.py`, KB extraction) | A0 | _unassigned_ | not started | **Blocks everyone, do first** |
| `risk.py` + tests | A2 | _unassigned_ | not started | Implement PROJECT §6 |
| A0 Orchestrator (`pipeline.py`, `app.py`, `diff.py`) | A0 | _unassigned_ | not started | Single-turn pipeline with stubs |
| A1 Evidence Analyst | A1 | _unassigned_ | not started | Prompt + output model |
| A2a/b/c Impact assessors | A2 | _unassigned_ | not started | Common prompt + 3 lenses |
| A3 Action Planner | A3 | _unassigned_ | not started | After Playback 2 |
| A4 Critic & Outlook + test scenarios | A4 | _unassigned_ | not started | **Write scenario S1 now** (needed for the demo) |
| A5 Report Writer (template + PDF) | A5 | _unassigned_ | not started | HTML template from fixture state |

Status values: not started · in progress · in review (PR open) · done · blocked

## Milestone checklist
- [x] Plan reviewed, architecture decided (PROJECT.md D-001…D-008)
- [ ] GitHub repo created, all teammates invited
- [ ] Owners assigned in the table above
- [ ] P0 foundations merged
- [ ] P1 thin slice: S1 → v1 PDF
- [ ] Playback 2 (24 Nov)
- [ ] P2 full loop (v2+, A3, A4, close)
- [ ] P3 scenarios S1–S3 pass, demo rehearsed
- [ ] Final submission (2 Dec)

## Open questions for the team
1. Do the instructors expect **IBM watsonx Orchestrate** / Bob to be used? (affects D-007)
2. LLM access: does each teammate have an Anthropic API key, or do we share one budget?
3. Who presents at Playback 2, and who owns the demo script?

## Recent sessions (newest first, keep 10)
- 2026-11-21 · project lead · director setup: plan review, architecture, all specs → `sessions/2026-11-21_lead_director-setup.md`
