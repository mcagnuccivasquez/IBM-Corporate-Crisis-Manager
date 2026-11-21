# STATUS — current state of the project

_Last updated: 2026-11-21 · by: project lead (director session)_

**Next deadline:** Playback 2 · **Tue 24 Nov 2026** · demo target: scenario S1 turn 1 → Report v1 PDF
**Final:** Wed 2 Dec 2026

## Agents / components
## Team
**Matteo** (project lead / director) · **Giacomo** · **Alibek** · **Serdar** · **Junda**

| Component | Spec | Owner | Status | Next step |
|---|---|---|---|---|
| Foundations (`contracts.py`, `llm.py`, `kb.py`, KB extraction) | A0 | **Matteo** | not started | **Blocks everyone, do first** (target: Sun 22 Nov) |
| A0 Orchestrator (`pipeline.py`, `app.py`, `diff.py`) + integration | A0 | **Matteo** | not started | Single-turn pipeline with stubs |
| A1 Evidence Analyst | A1 | **Giacomo** | not started | Prompt + output model (needed for Playback 2) |
| A2a/b/c Impact assessors + `risk.py` | A2 | **Junda** | in progress | `risk.py` ✅ · `a2_impact.py` ✅ · prompts ✅ · 52 tests passing; needs LLM wiring when `llm.py` lands |
| A5 Report Writer (template + PDF) | A5 | **Serdar** | not started | HTML template + PDF from a fixture state (needed for Playback 2) |
| A3 Action Planner | A3 | **Serdar** | not started | After Playback 2 (25–28 Nov) |
| A4 Critic & Outlook | A4 | **Alibek** | not started | After Playback 2 (25–28 Nov) |
| Test scenarios S1–S3 + fixture states (QA lead) | A4 | **Alibek** | not started | **Write S1 + a v1 fixture state now**, needed by Serdar, Giacomo and the demo |

_Assignment proposed by the director on 2026-11-21. Swap freely, but update this table._
Status values: not started · in progress · in review (PR open) · done · blocked

### Until foundations land (unblocking plan)
- Everyone codes against the schema in PROJECT.md §4. Matteo publishes `contracts.py` first, then everyone switches to it.
- Alibek's fixture state (`tests/fixtures/state_v1_S1.json`) lets Serdar build the PDF and Junda test `risk.py` without waiting for A1/A2.

### Live coordination (not tracked in this file)
- **Who is working right now:** post one line in the group chat when you start and finish ("Starting A1 extraction, until ~20:00").
- **Who owns what:** one GitHub Issue per component, assigned to its owner. Comment on the issue before touching someone else's files.

## Milestone checklist
- [x] Plan reviewed, architecture decided (PROJECT.md D-001…D-008)
- [ ] GitHub repo created, all teammates invited
- [x] Owners assigned in the table above (proposal; confirm with the team)
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
- 2026-11-21 · Junda · A2 impact & risk: risk.py, a2_impact.py, prompts, contracts stub, 52 tests → `sessions/2026-11-21_junda_a2-impact-risk.md`
- 2026-11-21 · Matteo · director setup: plan review, architecture, all specs → `sessions/2026-11-21_lead_director-setup.md`
