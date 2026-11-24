# STATUS — current state of the project

_Last updated: 2026-11-25 16:10 · by: Alibek (a4-dedup-confirmed-candidates session)_

**Next deadline:** Playback 2 · **Tue 24 Nov 2026** · demo target: scenario S1 turn 1 → Report v1 PDF
**Final:** Wed 2 Dec 2026

## Team
**Matteo** (project lead / director) · **Giacomo** · **Alibek** · **Serdar** · **Junda**

## Agents / components
| Component | Spec | Owner | Status | Next step |
|---|---|---|---|---|
| Foundations (`contracts.py`, `llm.py`, `kb.py`, KB extraction) | A0 | **Matteo** | done (PR #1) | D-015 `A3Output.warnings` on branch `matteo/d015-a3-warnings` |
| A0 Orchestrator (`pipeline.py`, `app.py`, `diff.py`) + integration | A0 | **Matteo** | in progress | App runs real A0, A1, A2, risk, A3, A5 + PDF (A4 still stub). Next: first live S1 run, read cost in `trace.jsonl`; demo prep |
| A1 Evidence Analyst | A1 | **Giacomo** | done (PR #8) | Follow-up PR: attachment paths → `Source.file`; register cited KB sources with `kb_source` |
| A2a/b/c Impact assessors + `risk.py` | A2 | **Junda** | done (PR #6) | Check live S1 scores against the scenario's expected levels |
| A3 Action Planner | A3 | **Serdar** | done (PR #10) | D-015 warnings field approved (implemented by Matteo); live run |
| A4 Critic & Outlook | A4 | **Alibek** | in review (PR ready) | PR #12 merged (Matteo). Follow-up: prompt dedup fix, merge dedup by (target, item_id), INT-4 test; 19/19 tests pass; waiting for live S1 API run from Matteo |
| A5 Report Writer (template + PDF) | A5 | **Serdar** | done (PR #2) | Follow-up PR: v1 badge "— → HIGH" (before the demo), number check, full names |
| Test scenarios S1–S3 + fixture states (QA lead) | A4 | **Alibek** | done (PR #7) | Fix S1 action IDs (see A4 row) |

_Assignment proposed by the director on 2026-11-21. Swap freely, but update this table._
Status values: not started · in progress · in review (PR open) · done · blocked

### Working notes
- Models (D-012): Sonnet 5.5 for A1–A4, Haiku 5.5 for A0/A5 (incl. `A5-factcheck`). Never Opus. Real costs per turn: `cases/<id>/trace.jsonl`.
- `ACME_STUB_AGENTS` in your own `.env` forces chosen agents to their stub (e.g. `a4` while it doesn't exist; free runs: the app's "Stub agents" switch).
- PDF rendering needs `python -m playwright install chromium` on every machine that runs the app.

### Live coordination (not tracked in this file)
- **Who is working right now:** post one line in the group chat when you start and finish ("Starting A1 extraction, until ~20:00").
- **Who owns what:** one GitHub Issue per component, assigned to its owner. Comment on the issue before touching someone else's files.

## Milestone checklist
- [x] Plan reviewed, architecture decided (PROJECT.md D-001…D-008)
- [x] GitHub repo created, all teammates invited
- [x] Owners assigned in the table above (proposal; confirm with the team)
- [x] P0 foundations merged
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
- 2026-11-25 · Alibek · A4 dedup confirmed candidates: prompt unified instruction, merge dedup by (target, item_id), INT-4 test, 19/19 pass → `sessions/2026-11-25_Alibek_a4-dedup-confirmed-candidates.md`
- 2026-11-24 · Alibek · A4 pre-pass non-blocking: pre-pass hits→non-blocking, false-alarm prompt, docstring fix, basis_source_ids fix, dedup instruction, ACT-001 scenario rename → `sessions/2026-11-24_Alibek_a4-prepass-nonblocking.md`
- 2026-11-23 · Alibek · A4 checks integration: `a4_critic.py`, prompt, 18 tests, Appendix C pass condition in all 7 expected.md files → `sessions/2026-11-23_Alibek_a4-checks-integration.md`
- 2026-11-23 · Matteo · reviews + D-015: merged PR #8 (A1), #2 (A5), #10 (A3); `A3Output.warnings` → non-blocking QA notes; app runs all real agents except A4; 332 tests → `sessions/2026-11-23_matteo_reviews-d015.md`
- 2026-11-23 · Serdar · A3 Action Planner: plan → code-built records, hard/soft checks, shared banned phrases (KB-04/S2), requirements audit of A3 + A5; 5 items for Matteo → `sessions/2026-11-23_serdar_a3-actions.md`
- 2026-11-22 · Giacomo · A1 director-review fixes: prompt renamed `a1_evidence.md`, `_build_context_block`, `check=` KB-id lambda, 33 tests pass; PR pending → `sessions/2026-11-22_giacomo_a1-evidence.md`
- 2026-11-22 · Matteo · integration: merged PR #6 (A2 + risk) and #7 (fixture + scenarios); `ACME_STUB_AGENTS` per-agent stub switch; A1 needs contract fixes (PR pending) → `sessions/2026-11-22_matteo_integration.md`
- 2026-11-22 · Alibek · A4 fixture contract fixes: case_id, outlook.reasons, ACT-001 owner → `sessions/2026-11-22_Alibek_a4-critic-outlook.md`
- 2026-11-22 · Junda · A2 pre-merge director review: verified 3 fixes (no _STUB_MODE, F4 names justification, Legal/regulatory), 140 tests pass, PR open → `sessions/2026-11-22_junda_a2-pre-merge-review.md`
- 2026-11-22 · Junda · A2 LLM wiring & contract migration: merged P0 foundations, migrated schema, wired call_structured, 120 tests → `sessions/2026-11-22_junda_a2-llm-wiring.md`
- 2026-11-21 · Serdar · A5 session 2: PR #2 fitted to the pipeline (Matteo's 4 changes), weaknesses fixed, AI fact-check + safety net, event-loop fix, A5 spec updated; 6 items for Matteo → `sessions/2026-11-21_serdar_a5-pipeline-and-fixes.md`
- 2026-11-21 · Alibek · A4 QA lead: fixture state_v1_S1.json + all S1–S3 scenario files → `sessions/2026-11-21_Alibek_a4-critic-outlook-and-scenarios.md`
- 2026-11-21 · Matteo · Streamlit chat UI (`app.py`): cases, versions + PDF downloads, risk badge, attachments, live agent progress; localhost-only config → `sessions/2026-11-21_matteo_app-ui.md`
