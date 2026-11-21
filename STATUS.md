# STATUS — current state of the project

_Last updated: 2026-11-21 18:05 · by: Matteo (p0-foundations session)_

**Next deadline:** Playback 2 · **Tue 24 Nov 2026** · demo target: scenario S1 turn 1 → Report v1 PDF
**Final:** Wed 2 Dec 2026

## Agents / components
## Team
**Matteo** (project lead / director) · **Giacomo** · **Alibek** · **Serdar** · **Junda**

| Component | Spec | Owner | Status | Next step |
|---|---|---|---|---|
| Foundations (`contracts.py`, `llm.py`, `kb.py`, KB extraction) | A0 | **Matteo** | in review (branch `matteo/p0-foundations`) | Open PR → main and merge; live API verified (cache hit, $0.03) |
| A0 Orchestrator (`pipeline.py`, `app.py`, `diff.py`) + integration | A0 | **Matteo** | in review (branch `matteo/app-ui`) | `pipeline.py`, `diff.py`, stubs, `app.py` done (UI runs end to end on stubs: `.\.venv\Scripts\python.exe -m streamlit run src/app.py`); next: integrate teammates' agents, first live S1 run |
| A1 Evidence Analyst | A1 | **Giacomo** | not started | Prompt + output model (needed for Playback 2) |
| A2a/b/c Impact assessors + `risk.py` | A2 | **Junda** | not started | `risk.py` + tests first (pure Python, no dependencies) |
| A5 Report Writer (template + PDF) | A5 | **Serdar** | in progress | Renderer + narrative + checks done (61 tests, branch `serdar/a5-report`). Next: run with a real API key, fix known weaknesses, switch to `contracts.py`/`llm.py` and Alibek's S1 fixture |
| A3 Action Planner | A3 | **Serdar** | not started | After Playback 2 (25–28 Nov) |
| A4 Critic & Outlook | A4 | **Alibek** | not started | After Playback 2 (25–28 Nov) |
| Test scenarios S1–S3 + fixture states (QA lead) | A4 | **Alibek** | not started | **Write S1 + a v1 fixture state now**, needed by Serdar, Giacomo and the demo |

_Assignment proposed by the director on 2026-11-21. Swap freely, but update this table._
Status values: not started · in progress · in review (PR open) · done · blocked

### Until foundations land (unblocking plan)
- Foundations are on branch `matteo/p0-foundations` (PR pending). Once merged: use `src/contracts.py` (incl. agent output models), `src/llm.py` (`call_structured`), `src/kb.py`; your agent module is picked up by `src/pipeline.py` automatically. Interface list: `sessions/2026-11-21_matteo_p0-foundations.md` → "Changes for teammates". **Each owner: check the interface against your spec.**
- Models (D-012): Sonnet 5.5 for A1–A4, Haiku 5.5 for A0/A5. A full report turn ≈ $0.35 (estimate; real costs in `cases/<id>/trace.jsonl`).
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
- 2026-11-21 · Matteo · Streamlit chat UI (`app.py`): cases, versions + PDF downloads, risk badge, attachments, live agent progress; localhost-only config → `sessions/2026-11-21_matteo_app-ui.md`
- 2026-11-21 · Matteo · reviews of Junda's + Alibek's branches; D-014 severity anchors (S=3, reach → Likelihood) → `sessions/2026-11-21_matteo_branch-reviews.md`
- 2026-11-21 · Matteo · director review of PR #2 (A5): 10 items decided, D-013 contract additions; PR #2 needs interface fix → `sessions/2026-11-21_matteo_a5-review.md`
- 2026-11-21 · Matteo · P0 foundations: contracts, KB extraction, llm.py (live-tested), pipeline + stubs, hybrid models (D-009…D-012) → `sessions/2026-11-21_matteo_p0-foundations.md`
- 2026-11-21 · Serdar · A5 report: renderer, template, narrative + checks, readability redesign; 10 items need director review → `sessions/2026-11-21_serdar_a5-report.md`
- 2026-11-21 · Matteo · director setup: plan review, architecture, all specs → `sessions/2026-11-21_lead_director-setup.md`
