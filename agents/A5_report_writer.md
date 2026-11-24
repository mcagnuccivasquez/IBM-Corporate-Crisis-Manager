# A5 — Report Writer (narrative + PDF)

> **New chat? Load in this order:** `AGENTS.md` → `STATUS.md` → `PROJECT.md` (esp. §4, §7) → this file.
> **Owns:** `src/agents/a5_report.py`, `src/prompts/a5_report.md`, `src/prompts/a5_factcheck.md`, `src/report/` (`template.html`, `style.css`, `render.py`, `checks.py`), `tests/test_a5_*.py`, `tests/fixtures/a5_sample_state_v1.json`.
> **Updated 2026-11-21 (Serdar, sessions 1–2):** pipeline interface, text checks, AI fact-check, safety net, page-1 overview, D-013. Changes are listed under *Needs director review* in `sessions/2026-11-21_serdar_a5-pipeline-and-fixes.md`.

## 1. Mission
Turn the validated CaseState vN (+ vN-1) into **Crisis Management Report vN**: the same structure every time, readable by an executive, and **one PDF per version**.
A5 adds **no new facts or judgements**. It only summarises and formats what the other agents produced, and it **checks** its own text (and, as a safety net, the other agents' texts) before the report goes out.

## 2. Pipeline interface (D-013)
| Function | Signature | Notes |
|---|---|---|
| Narrative | `src/agents/a5_report.py` → `run(state, turn, prev_state) -> A5Output` | Returns `narrative` (dict, empty keys left out), `changes_summary` (→ `changelog[-1].summary`) and `narrative_warnings` (→ `report.narrative_warnings`). Never writes files. `prev_state` is not needed: A0 always builds this version's changelog entry first. |
| PDF | `src/report/render.py` → `render_pdf(state, pdf_path) -> Path` | Writes exactly `pdf_path` (A0 decides `cases/<case_id>/report_v<N>.pdf`); never overwrites; works inside or outside an asyncio event loop (web UI). |

All Claude calls go through `src/llm.py` `call_structured` (D-011). Agents named `A5…` run on the light model (Haiku 5.5, D-012) at effort `low`. A5 needs no provider-specific code: if the team switches LLM provider, only `llm.py` changes.

## 3. Split of work (cheap and consistent)
| Part | Done by | Why |
|---|---|---|
| Tables (evidence, risk matrix, actions, stakeholders, sources, changelog lists) | **code** (Jinja2 straight from CaseState) | exact, no hallucination risk |
| Page-1 overview: P1 actions, evidence counts, open questions, ID legend | **code** | decision-first view without changing the section order |
| Narrative: Executive summary (≤80 words), Situation (≤150), "What changed and why" (≤120), close-out summary (≤120) | **LLM** call `A5` (low effort) | readability |
| Text checks (§5) | **code** (`src/report/checks.py`) | reliable, free |
| Fact-check of the narrative (§5) | **LLM** call `A5-factcheck` (low effort) | catches real numbers/statuses used for the wrong thing |
| HTML → PDF | **code** (Playwright Chromium `page.pdf()`) | identical layout every version |

LLM output schema (narrative):
```json
{ "executive_summary": "...", "situation": "...", "changes_summary": "... (omitted for v1)", "closure_summary": "... (only when closed)" }
```
Keys without text are left out (`report.narrative` values must be text, D-013). Every sentence must be traceable to CaseState fields. Cite IDs in brackets, e.g. `[C-007, U-03]`; in the PDF they become small clickable references.

## 4. Fixed report structure (PROJECT §7; keep the brief's order, D-013)
0. **Header band**: ACME · Crisis Management Report · CASE-001 · **Version 3** · timestamp · status · focus · big badge **Risk: High → High** (colour + text; on v1 just **HIGH**, no "— →", session 4) · "Evidence confidence: Medium" (separate, smaller badge). Then: **Executive summary** box · **At a glance** (P1 actions with owner, timing and status; evidence counts; open questions) · **How to read this report** legend (C-/U-/KB-/ACT- codes, F1–F4, P1–P3, risk ≠ evidence confidence)
1. Situation
2. Evidence: three tables **Confirmed** / **Unconfirmed** / **Disproved or misleading**, each with a one-line explanation (claim, strength, sources with titles, history "New in v1 / Changed in v2 / No change since v1")
3. Risk and reasons: S×L per domain with reasons, floors, how the overall level was set, link to Appendix B
4. Impacts: one table, grouped by domain, incl. "if left unaddressed" and basis (ACME data / Case evidence / ACME precedent / General knowledge)
5. Stakeholders table
6. Action plan: sorted by priority, then `focus_related` (A3, D-013); status chip; options considered inline (✔ Recommended / ○ Alternative)
7. Outlook if priority actions succeed (residual risk badge, why, assumptions, cannot estimate, pattern warnings)
8. Changes since v(N-1) (risk from→to + reason even if unchanged; new evidence; claim changes; action changes) and **Open questions** (owner)
9. *(Closed only)* Remaining risk · Open actions · Conditions for reopening
- Appendix A Sources cited (ID, title, file, date, type, historical flag, reliability note) · Appendix B Risk method (static text from PROJECT §6) · Appendix C Quality checks: narrative checks, case-data checks, **safety net on other agents' texts**, unresolved A4 QA notes, claim history. Agent trace: read `cases/<id>/trace.jsonl` (D-013), not yet shown.

v1 has no previous version: section 8 says "Initial assessment".

## 5. Checks (agreed with Serdar, sessions 1–2)
| Check | Kind | On A5's narrative | On other agents' texts (safety net) |
|---|---|---|---|
| Invented numbers (digits and number words) | hard | retry once, then warning | — (A4's job) |
| IDs the case data never mentions | hard | retry once, then warning | — (shown crossed out in the PDF) |
| Banned phrases (KB-10: authorities contacted, independent tests, all units tested; KB-03: remote/firmware fix for PCX-100; KB-09: password change proves no recording was viewed), incl. paraphrases; negated use is fine; allowed when the evidence affirms it | hard | retry once, then warning | warning |
| Personal data: emails (not @acme.example), @handles, phones, "R. Dubois" / "Ms Dubois" names (ACME staff from KB-02 allowed) | hard | retry once, then warning | warning |
| "Confirmed/proven" about a claim that is not confirmed (hard since session 4, after Matteo's live run) | hard | retry once, then warning | — |
| Risk level not in the risk data | soft | warning | — |
| Wording that may blame a customer (KB-10) | soft | warning | warning |
| Word limits | soft | warning (never cut) | — |
| AI fact-check: sentence vs case data (wrong thing, status, unsupported "done", risk/confidence) | AI, soft | warning, never rewrites | — |

- All hard problems share **one** retry (inside `call_structured`). A5 **never changes another agent's text**; the safety net only reports.
- If the narrative call fails (no key, network, refusal, invalid twice): narrative = "Narrative not available (AI step failed)", a warning explains why, and the PDF is still produced. If the fact-check fails, the report says "AI fact-check not run".
- `narrative_warnings = None` means the checks did not run; `[]` means they ran and found nothing.
- Known limits (stated, not hidden): small numbers that appear inside IDs (e.g. 12 in KB-12) always pass the number check; full names ("Rachel Dubois") are not detected; phrase checks are wording-based; the fact-check is itself an AI judgement.

## 6. Rules
- No new facts, numbers, or recommendations. If a field is empty, print "None reported" rather than inventing content.
- Wording: neutral, no blame, no personal data. Drafts (statements) are marked by A3 as **DRAFT – requires approval by …**; A5 prints them as written and flags problems in Appendix C.
- Footer on every page: "Decision-support draft generated by the ACME Crisis Manager. Does not execute recalls, notifications or public statements." + case · version · page x/y.
- File name: `cases/<case_id>/report_v<N>.pdf` (decided by A0). Never overwrite an existing version.
- Print-friendly CSS: A4, `@page` margins, table headers repeat across pages, no row split mid-row, colour + text label for risk and status (readable in black and white).

## 7. Runtime prompts
- Narrative: `src/prompts/a5_report.md` (spec prompt + field rules + the check rules: cite only existing IDs, banned phrases, precedents ≠ evidence, no personal data, no blame).
- Fact-check: `src/prompts/a5_factcheck.md` (compare each sentence with the case state only; never rewrite; empty list if all matches).
- `llm.py` adds the shared `COMMON_RULES` and the KB block before each prompt (D-011).

## 8. Acceptance tests
- [x] Same CaseState rendered twice → identical HTML (only the timestamp would differ).
- [x] Report v2 shows Risk prev→current, new sources, claim and action changes, and explains an unchanged level.
- [x] All 9 sections + appendices present. Closed case shows section 9.
- [x] A narrative containing a number not in CaseState → caught (digits and number words), retried once, then flagged.
- [x] Unknown IDs, banned phrases, personal data, overstated claims, unknown risk levels, blame wording, word limits → tested.
- [x] Pipeline: real A5 + real renderer run inside `pipeline.run_turn` (fake Claude); output validates against `contracts.py`.
- [x] PDF renders inside a running asyncio event loop (web UI case).
- [x] Renders another teammate's fixture (Alibek's S1) without errors and without false safety-net alarms.
- [ ] Live run on Haiku 5.5 with a real API key (planned Monday 23 Nov).
- [ ] PDF opens on Windows; clickable references checked by hand; long tables paginate cleanly with real agent output.
