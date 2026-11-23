# PROJECT — ACME Corporate Crisis Manager (IBM Use Case 2)

> The single source of truth for **what** we are building and **how** the pieces fit.
> Every agent chat reads this file once. If you change anything in §4–§8, log it in §12 (Decision log) first.

---

## 1. Goal and deadlines

We are building a **multi-agent system** that helps ACME (a fictional consumer-electronics company) assess and respond to an emerging crisis. It works through one ongoing chat. The user supplies incident evidence (text, PDFs, screenshots), and the system produces a **versioned Crisis Management Report (v1, v2, v3…)**, one PDF per version, until the user closes the case.

| Milestone | Date | What must work |
|---|---|---|
| Playback 1 | Tue 10 Nov 2026 | done |
| **Playback 2** | **Tue 24 Nov 2026** | Thin end-to-end slice: evidence in, then **Report v1 PDF** out (A0+A1+A2+risk engine+basic A5) |
| **Final due** | **Wed 2 Dec 2026** | Full cycle v1→vN, actions, critic, close-out, 3 test scenarios passing |

Original brief: [docs/brief/UseCase2_definition.md](docs/brief/UseCase2_definition.md). Original team plan: [docs/IBM_PROJECT_PLANNING_original.pdf](docs/IBM_PROJECT_PLANNING_original.pdf).

---

## 2. Requirements → which agent owns them

| # | Requirement (brief + team plan) | Owner |
|---|---|---|
| R1 | Accept text, PDFs, and images in one ongoing chat | A0 |
| R2 | Use and **cite** company docs and incident sources | A1 (registry), all agents (cite `source_id`) |
| R3 | Distinguish **current evidence vs historical examples vs informal notes** | A1 |
| R4 | Separate **confirmed / unconfirmed / disproved-or-misleading** claims (a screenshot alone proves nothing) | A1 |
| R5 | Shift assumptions when new data arrives; earlier facts stay valid unless disproved | A1 + A0 (merge rules) |
| R6 | Assess **reputational, economic, legal/regulatory** impacts, and what happens if left unfixed | A2a/b/c |
| R7 | Overall risk **Low / Medium / High / Critical**, with a consistent method and reasons, **separate from evidence strength** | A2 + `risk.py` (§6) |
| R8 | Identify stakeholders | A2 (affected), A3 (stakeholder map) |
| R9 | Priority actions with **owners and timing**, ≥2 options for major decisions, grounded in past cases and company policy | A3 |
| R10 | Explain what each action step does | A3 |
| R11 | Track action status: proposed → approved → completed → **verified effective / ineffective** | A3 (state), A4 (checks) |
| R12 | Residual/future risk after actions, with no guessing beyond the data | A4 |
| R13 | Every update shows **previous vs current risk, new evidence, action changes, and reasons** (even if the level is unchanged) | A0 (diff) + A5 |
| R14 | Versioned report: situation; evidence; risk and reasons; impacts; stakeholders; action plan; changes and open questions | A5 |
| R15 | **One PDF per version** | A5 |
| R16 | On close: remaining risk, open actions, reopen conditions | A3 + A4 + A5 |
| R17 | ≥ 5 agents (team requirement; the brief requires ≥2) | 6 agents + 3 sub-agents |
| R18 | System drafts and recommends only. It **never** performs real recalls, regulator notifications, or public posts | All (guardrail) |

---

## 3. Architecture

### 3.1 Why we changed the original plan (summary; details in Decision log D-001…D-006)
1. **Added A0 Case Orchestrator.** The brief is a *loop* (v1→v2→vN in the same chat), not a one-shot pipeline. Something must own the case state, the version diff, and closing the case.
2. **Kept 2a/2b/2c** (domain impact lenses run in parallel). **Merged 3a/3b/3c into one A3.** Crisis actions are cross-functional (a batch hold is economic, legal, and reputational at once). Three planners would produce conflicting or duplicate actions with no single owner.
3. **The risk level is calculated by code** (`risk.py`) from the A2 domain scores, using a fixed rubric (§6). That guarantees "applied consistently". The LLM gives scores and reasons; code gives the level.
4. **Four levels, not three.** The brief requires Low/Medium/High/Critical. The 0–10 bar is replaced by Severity × Likelihood (1–16), which maps onto the 4 levels.
5. **"Focus issue" changes priority and depth, never the score.** Inflating severity because the user cares would break consistency.
6. **A4 = Critic + Outlook.** It checks A1–A3 against grounding rules and the known traps in the KB, projects residual risk after actions, and detects "repeating-pattern traps" (the team's extra idea).
7. **A5 report follows the brief's section list**, not a per-agent layout. The per-agent trace goes in an appendix.

### 3.2 Flow per user turn

```
User message + attachments (chat UI)
        │
        ▼
A0 Case Orchestrator ── classifies intent: NEW_INFO | ACTION_UPDATE | QUESTION | SET_FOCUS | CLOSE
        │  (QUESTION → answers from the latest CaseState, no new version)
        ▼
A1 Evidence Analyst ── registers sources, extracts and verifies claims, re-evaluates old claims
        │
        ├──► A2a Reputational ─┐
        ├──► A2b Economic     ─┼─ parallel; each returns domain impacts + Severity/Likelihood
        └──► A2c Legal/Reg.   ─┘
                    │
                    ▼
            risk.py (deterministic) ── overall level + floors + reasons
                    │
                    ▼
A3 Action Planner ── updates the action register (options, owners, timing, status)
        │
        ▼
A4 Critic & Outlook ── PASS → continue | REVISE → A0 re-runs the target agent ONCE, then continues
        │                 (unresolved issues are printed in the report as "QA notes")
        ▼
A5 Report Writer ── narrative + diff vs previous version → HTML → PDF  (cases/<id>/report_vN.pdf)
        │
        ▼
A0 saves state_vN.json, replies in chat with the summary + PDF link
```

### 3.3 Agent roster

| ID | Agent | LLM? | Reads | Writes (CaseState fields) | Spec |
|---|---|---|---|---|---|
| A0 | Case Orchestrator | small LLM call (intent) + code | everything | `version`, `status`, `focus`, `changelog`, `closure` (assembly) | [agents/A0_orchestrator.md](agents/A0_orchestrator.md) |
| A1 | Evidence Analyst | yes (vision) | user inputs, KB, prev. `sources`/`claims` | `sources`, `claims`, `open_questions` (evidence gaps) | [agents/A1_evidence_analyst.md](agents/A1_evidence_analyst.md) |
| A2a/b/c | Impact & Risk Assessors | yes ×3 parallel | `claims`, `sources`, KB, prev. `impacts` | `impacts.<domain>`, domain scores | [agents/A2_impact_risk.md](agents/A2_impact_risk.md) |
| — | risk engine (`risk.py`) | **no** | domain scores, claims, actions | `risk` | in A2 spec §Risk engine |
| A3 | Action Planner | yes | `claims`, `impacts`, `risk`, prev. `actions`, KB | `actions`, `stakeholders`, `closure.open_actions` | [agents/A3_action_planner.md](agents/A3_action_planner.md) |
| A4 | Critic & Outlook | yes | full draft CaseState, KB | `qa`, `outlook`, `closure.reopen_conditions` | [agents/A4_critic_outlook.md](agents/A4_critic_outlook.md) |
| A5 | Report Writer | yes (narrative only) + code (render) | full CaseState + previous version | `report` (narrative), PDF file | [agents/A5_report_writer.md](agents/A5_report_writer.md) |

---

## 4. Shared data model — `CaseState` (THE contract)

All agents read and write **one JSON object** per version. It will be implemented as Pydantic models in `src/contracts.py` (owned by A0; changes only via the Decision log). Field names below are binding.

```jsonc
{
  "case_id": "CASE-001",
  "version": 2,                       // incremented by A0 on every NEW_INFO / ACTION_UPDATE / CLOSE turn
  "created_at": "...", "updated_at": "...",
  "status": "open",                   // open | closed
  "focus": "PCX-100 overheating",     // optional, set by user; affects ordering only
  "turn_input": { "intent": "NEW_INFO", "user_text": "...", "attachments": ["U-03"] },

  "sources": [{                       // A1. Never deleted.
    "source_id": "U-03",              // KB-01..KB-13 fixed (§8); user evidence U-01, U-02, ...
    "title": "Screenshot of TownSquare post by @x", "file": "cases/CASE-001/inputs/post.png",
    "origin": "user_upload",          // kb | user_upload | user_text
    "date": "2026-11-20",             // date of the content, not of the upload
    "category": "incident_evidence",  // incident_evidence | company_record | historical_case | informal_note | planning_assumption | reference
    "time_relevance": "current",      // current | historical
    "duplicate_of": null,             // source_id if this is a copy/repost of another source
    "reliability_note": "Screenshot; original link not provided",
    "added_in_version": 2
  }],

  "claims": [{                        // A1. Never deleted; status changes need a reason + source.
    "claim_id": "C-007",
    "text": "A PCX-100 unit emitted smoke while charging a laptop",
    "status": "unconfirmed",          // confirmed | unconfirmed | disproved | misleading
    "evidence_strength": "weak",      // strong | moderate | weak   (≠ risk!)
    "source_ids": ["U-03"],
    "contradicted_by": [],            // source_ids
    "domains": ["reputational", "legal_regulatory"],
    "product": "PCX-100", "batch": null, "market": "DE",
    "first_seen_version": 2, "last_changed_version": 2,
    "change_history": [{ "version": 2, "from": null, "to": "unconfirmed", "reason": "...", "source_ids": ["U-03"] }]
  }],

  "impacts": {                        // A2a/b/c, one block per domain
    "reputational":     { "severity": 3, "likelihood": 2, "score": 6, "severity_reason": "...", "likelihood_reason": "...",
                          "impacts": [{ "description": "...", "if_unaddressed": "...", "timeframe": "24h|7d|30d", "stakeholders": ["customers DE"], "source_ids": ["..."], "basis": "company_data|incident_evidence|precedent|general_knowledge" }],
                          "floor_triggers": ["F1"], "evidence_confidence": "low" },
    "economic":         { "...": "same shape" },
    "legal_regulatory": { "...": "same shape" }
  },

  "risk": {                           // risk.py (code), never written by an LLM
    "level": "High", "previous_level": "Medium",
    "max_domain_score": 6, "floors_applied": ["F1"],
    "reasons": ["Reputational 3×2=6 → Medium", "F1: unconfirmed smoke report on product in market → floor High"],
    "evidence_confidence": "low"      // shown next to the level, never mixed into it
  },

  "stakeholders": [{ "name": "Customers in DE/IT/FR", "type": "external", "interest": "...", "impact": "...", "acme_contact": "Tom Weber (Customer Care)" }],

  "actions": [{                       // A3. Never deleted (use status "dropped").
    "action_id": "ACT-004",
    "title": "Warehouse hold on batch PCX-2609-B (3,000 units, Frankfurt)",
    "what_it_does": "Stops new shipments of the suspect batch while Quality tests samples",
    "owner": "Luca Ferri (Supply Chain)", "approver": "Elena Rossi (COO)",
    "timing": "within 24h", "priority": "P1",          // P1 now | P2 this week | P3 later
    "focus_related": null,            // A3 sets true/false when a focus is set (ordering only, D-013)
    "domains": ["economic", "legal_regulatory"],
    "status": "proposed",             // proposed | approved | in_progress | completed | verified_effective | verified_ineffective | dropped
    "options_considered": [{ "option": "Hold both batches", "pros": "...", "cons": "...", "chosen": false }],
    "basis_source_ids": ["KB-12", "KB-13"],   // precedent or policy that justifies it
    "expected_effect": "...", "result_evidence_source_ids": [],
    "status_history": [{ "version": 2, "from": null, "to": "proposed", "reason": "..." }]
  }],

  "outlook": {                        // A4
    "residual_risk_if_p1_effective": "Medium", "reasons": ["..."],
    "assumptions": ["..."], "cannot_estimate": ["..."], "pattern_warnings": ["..."]
  },
  "qa": { "verdict": "PASS", "issues": [{ "target": "A3", "item_id": "ACT-004", "problem": "...", "fix_hint": "...", "blocking": true, "resolved": false }] },

  "open_questions": [{ "question": "...", "owner": "Maya Chen", "raised_in_version": 1, "closed_in_version": null }],

  "changelog": [{                     // A0 builds the diff in code; A5 narrates it
    "version": 2, "risk_from": "Medium", "risk_to": "High",
    "new_source_ids": ["U-03"], "claim_changes": ["C-007 new (unconfirmed)"], "action_changes": ["ACT-004 proposed"],
    "summary": "..."                  // A5 fills the narrative "why"
  }],

  "closure": null,                    // on CLOSE: { "remaining_risk": "...", "open_actions": ["ACT-.."], "reopen_conditions": ["..."] }
  "report": { "pdf_path": "cases/CASE-001/report_v2.pdf",
              "narrative": { "executive_summary": "...", "situation": "...", "changes_summary": "..." },  // + "closure_summary" when closed; omit keys, never null
              "narrative_warnings": [] }   // A5's checks on its own text (null = not run), D-013
}
```

**Merge rules (enforced in code by A0, not trusted to the LLM):**
- Sources, claims, and actions are **never deleted**. They are merged by ID.
- A claim status change requires a `change_history` entry with a reason and at least one `source_id`.
- An action can only move to `verified_effective` / `verified_ineffective` if `result_evidence_source_ids` is non-empty.
- `risk` is only ever written by `risk.py`.

---

## 5. Evidence classification method (A1, used by everyone)

| Dimension | Values | Rule of thumb |
|---|---|---|
| **Claim status** | confirmed | Verified by an ACME record or test, or by ≥2 *independent* reliable sources that agree |
| | unconfirmed | Reported but not verified (default for a single post/screenshot/customer message) |
| | disproved | Contradicted by stronger evidence (e.g. lab test, log review) |
| | misleading | Based on something real but presented out of context (old post re-shared as new, other product, copy counted as new report, partial screenshot) |
| **Evidence strength** | strong / moderate / weak | Primary record or test = strong; named first-hand report = moderate; screenshot / repost / hearsay = weak |
| **Source category** | incident_evidence, company_record, historical_case, informal_note, planning_assumption, reference | §8 pre-assigns the KB |
| **Time relevance** | current / historical | Historical cases are **precedents**, never evidence about the current incident |

Independence rule: copies, reposts, articles quoting the same post, and the PNGs in `original_screenshots/` are **not** extra evidence (`duplicate_of`).

---

## 6. Risk assessment method (canonical — implemented in `risk.py`)

**Step 1, per domain (A2a/b/c):** score **Severity (S)** and **Likelihood/Exposure (L)**, each 1–4, using the anchors below. Domain score = S × L.

| | Severity (how bad if it happens / continues) | Likelihood / Exposure (how probable and how widespread *now*) |
|---|---|---|
| 1 | Minor: isolated, single customer, no safety/data dimension, cost < €10k | Remote: claim disproved or no plausible mechanism; no exposure |
| 2 | Moderate: several customers or limited public visibility; cost €10k–100k | Possible: single unverified report; limited reach |
| 3 | Major: safety or personal-data question on a product line in market; broad public attention; cost €100k–1M; regulatory notification possible | Likely: multiple independent reports, or a defect confirmed in samples; affected units in market; reach growing |
| 4 | Severe: confirmed injury/fire, confirmed access to recordings, authority action, withdrawal across markets; cost > €1M | Occurring: harm, media coverage, retailer or authority action already happening |

Likelihood is about the **world** (exposure, spread, mechanism). Evidence strength is about **our sources**. Both are reported; they are not merged.

**Reading the anchors (D-014):** the clauses inside one anchor are **alternatives**: meeting any one of them is enough for that score. **Reach and spread are scored in Likelihood, never in Severity.** Example: a single unconfirmed screenshot of a PCX-100 smoking → reputational **S=3** ("safety question on a product line in market") × **L=2** ("single unverified report; limited reach") = 6.

**Step 2, overall level (code):** take the highest domain score →

| Max domain score | 1–3 | 4–6 | 8–9 | 12–16 |
|---|---|---|---|---|
| Level | **Low** | **Medium** | **High** | **Critical** |

**Step 3, floors (code, applied after Step 2; reasons printed):**
- **F1** Credible report of fire, smoke, burning, electric shock, or injury involving a product on the market, **even if unconfirmed** → at least **High**. (Elena, KB-02: "do not wait for a complete diagnosis before flagging a possible safety issue.")
- **F2** Confirmed injury, a hazardous defect confirmed in market units, or a request/contact from an authority → **Critical**.
- **F3** Confirmed or likely unauthorised access to customer personal data or recordings → at least **High**.
- **F4 (de-escalation guard)** The level may only drop versus the previous version if a claim was disproved or downgraded, or an action reached `verified_effective`. The report must name which. "No news" is not a reason.

**Focus:** a user-set focus reorders the report and actions and deepens the analysis. It **never** changes S, L, or the level.

---

## 7. Report structure (fixed every version — A5)

0. Header: case ID, version, timestamp, status, **Risk: previous → current**, evidence confidence, focus
1. Situation
2. Evidence: confirmed / unconfirmed / disproved-or-misleading (tables with source IDs)
3. Risk and reasons (domain matrix, floors applied, reasons)
4. Impacts: reputational, economic, legal/regulatory (incl. "if left unaddressed")
5. Stakeholders
6. Action plan (ID, action, what it does, owner, timing, priority, status, basis, expected effect)
7. Outlook if priority actions succeed (residual risk, assumptions, what cannot be estimated)
8. Changes since previous version and open questions
9. *(Closed cases only)* Remaining risk, open actions, conditions for reopening
- Appendix A: sources cited · Appendix B: risk method · Appendix C: QA notes / agent trace

---

## 8. Knowledge base: source registry and known traps

All agents cite these IDs. Paths are relative to `knowledge_base/ACME_company_files/`.

| ID | File | Date | Category | What it is good for |
|---|---|---|---|---|
| KB-01 | ACME_company_overview_2026.pdf | Sep 2026 | reference | Company size (€180M rev, 620 staff), markets IT/DE/FR, sites, who does what; marketplace listings can't all be verified |
| KB-02 | Operations_contacts_Oct26.pdf | 20 Oct 2026 | reference | **Action owners** and escalation; no crisis playbook exists; flag safety early |
| KB-03 | Product_PCX100_v4_sales_copy.pdf | 8 Sep 2026 | reference | PCX-100 specs: 100 W GaN, H3.1, throttle 65 °C, shutdown 75±2 °C internal; **no network/no remote fix**; smoke/sparks → Care+Quality; label photo for authenticity |
| KB-04 | SafeCam_Home_notes_for_retail.pdf | 22 Oct 2026 | reference | SCH-2 fw 2.6.1; 18,000 devices / 12,000 cloud accounts (**not** a count of affected people); data handled; don't overpromise |
| KB-05 | Sep26_customer_care_review.pdf | 5 Oct, upd. 22 Oct 2026 | company_record | Sept tickets: PCX 420 (18 heat, 16 closed no defect, 2 awaiting samples); SafeCam 310 (7 access, 5 resolved, 2 under review). **Contacts ≠ failure rate** |
| KB-06 | FW_4471_charging_stops.pdf | 13 May 2026 | historical_case | Ticket #4471: cable fault, not charger. **Must not be generalised**; smoke cases must not be closed with the cable explanation |
| KB-07 | Screen_TravelPlug_post_181125.pdf | 18 Nov 2025 | historical_case | Old social post about **TravelPlug 30 (different product)**; reach figures at capture |
| KB-08 | RE_TravelPlug_social_followup.pdf | 18–21 Nov 2025 | historical_case | **Response precedent**: short acknowledgement, private follow-up, test, no fault found, answer kept visible; the newspaper link was a repeat, not a 2nd customer |
| KB-09 | SafeCam_account_case_120226.pdf | 12–13 Feb 2026 | historical_case | SC-219 precedent: reused password, 1 session, contained; **can't generalise to platform**; recovery ≠ proof nothing was viewed |
| KB-10 | Replies_working_notes_AK.pdf | 7 Jul 2026 | informal_note | Holding-statement wording; don't claim "authorities contacted"/"independent tests"/"all units tested" unless true; **not approved policy** |
| KB-11 | VN3_visit_note_Jul26.pdf | 21 Jul 2026 | company_record | 30 July units sampled OK; **September batches not covered**; no hold raised |
| KB-12 | RE_costs_for_PowerCharge_returns.pdf | 30 Sep 2026 | planning_assumption | €30/unit replacement+logistics; €5,000 per-batch hold setup; delivered ≠ sold; CEO for large remedy |
| KB-13 | PCX_stock_export_22Oct.csv | 22 Oct 2026 | company_record | Batch PCX-2609-A: 2,000 warehouse + 6,000 delivered (DE 2,500/IT 2,000/FR 1,500). Batch PCX-2609-B: 3,000 warehouse + 5,000 delivered (DE 2,200/IT 1,800/FR 1,000). **Delivered to channels ≠ sold** |

`original_screenshots/*.png` = copies of images inside KB-06/07/09. They are **not independent sources**.

**Known traps the system must handle (A4 checks every one):**
1. Treating the TravelPlug 2025 case as evidence about PCX-100 (different product, historical).
2. Counting reposts, newspaper copies, or duplicate screenshots as independent reports.
3. Accepting a screenshot as proof.
4. Turning ticket counts into failure rates, or treating "perceived heat" as a confirmed thermal fault.
5. Using the #4471 cable explanation to close smoke/damage reports.
6. Claiming VN-3 proves September batches are fine (they were not sampled).
7. Cost = €30 × every unit ever shipped (scope must be justified; delivered ≠ sold; show ranges).
8. Promising a remote/firmware fix for PCX-100 (impossible).
9. Saying "a password change proves no recording was viewed", or generalising SC-219 to the platform.
10. Treating Anna's working notes as approved policy.
11. Public wording that blames customers, includes personal data, or claims "all units tested" / "authorities contacted" without confirmation.
12. Committing large remedies or withdrawals without CEO (Daniel Moretti); injury, authority, or personal-data issues without Legal/DPO (Sophie Laurent).

**General domain knowledge** (e.g. EU product-safety and GDPR breach-notification duties, basic economics) **is allowed** but must be labelled `basis: "general_knowledge"` and never presented as an ACME fact.

---

## 9. Tech stack and repo layout

**Approach: Python code in Git** (see D-007 for why not n8n or Railway/Inngest/Supabase).

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM | Claude via the official `anthropic` SDK. Hybrid models (D-012): `claude-sonnet-5-5` for A1–A4, `claude-haiku-5-5` for A0 intent/answers and A5 (set in `.env`: `ACME_MODEL`, `ACME_MODEL_LIGHT`); tune cost per agent with `output_config.effort` (low for A0 intent/A5, high for A1/A4). Structured outputs via `output_config.format` + Pydantic validation in `src/llm.py` (D-011). Adaptive thinking. Prompt caching on the KB block. **Before writing LLM code, load the `claude-api` skill in Claude Code** (APIs changed in 2026: no prefill, forced `tool_choice` returns 400, etc.) |
| KB loading | No vector DB needed: the KB is ~10k tokens of text. Extract once to `knowledge_base/extracted/KB-xx.md` and put it in the cached system prompt for every agent. User-uploaded PDFs/images go to A1 natively (document/image blocks) |
| Contracts | Pydantic models in `src/contracts.py` (= §4) |
| Risk engine | `src/risk.py`, pure Python, unit-tested |
| UI | Streamlit chat (`st.chat_input` + file upload), PDF download button |
| PDF | Jinja2 HTML template + CSS → PDF with Playwright (Chromium print-to-PDF; works on Windows/Mac/Linux) |
| State | `cases/<case_id>/state_vN.json` + `report_vN.pdf` (immutable per version) |
| Secrets | `.env` with `ANTHROPIC_API_KEY` (gitignored). Each teammate uses their own key |

```
/
├─ AGENTS.md  CLAUDE.md  PROJECT.md  STATUS.md  README.md  .gitignore
├─ agents/            A0…A5 specs (one per agent; A2 covers 2a/2b/2c)
├─ sessions/          one file per work session (see AGENTS.md)
├─ docs/              brief + original plan
├─ knowledge_base/    ACME files (+ extracted/ text, generated)
├─ src/
│  ├─ app.py          Streamlit chat (A0 UI)
│  ├─ pipeline.py     A0 orchestration
│  ├─ contracts.py    CaseState models
│  ├─ llm.py          shared Claude client wrapper (caching, parse, retries)
│  ├─ kb.py           KB loader + source registry
│  ├─ risk.py         deterministic risk engine
│  ├─ diff.py         version diff
│  ├─ agents/         a1_evidence.py, a2_impact.py, a3_actions.py, a4_critic.py, a5_report.py
│  ├─ prompts/        runtime system prompts (a1.md …)
│  └─ report/         template.html, style.css, render.py
├─ tests/
│  ├─ scenarios/      S1 PCX overheating, S2 SafeCam access, S3 misleading repost (multi-turn scripts)
│  └─ test_*.py
└─ cases/             runtime output (gitignored except demo runs)
```

Each agent module exposes one function: `run(state: CaseState, turn: TurnInput) -> <AgentOutput>`, so it can be developed and tested alone with a fixture state.

---

## 10. Roadmap

| Phase | Dates | Deliverables |
|---|---|---|
| P0 Foundations | Sat 21 – Sun 22 Nov | `contracts.py`, `llm.py`, `kb.py` + extracted KB, `risk.py` + tests, repo on GitHub |
| P1 Thin slice | Sun 22 – Mon 23 Nov | A1, A2 (3 domains), basic A5 PDF, A0 single-turn → **v1 PDF for scenario S1** |
| **Playback 2** | **Tue 24 Nov** | Demo v1 + architecture + risk method |
| P2 Full loop | 25 – 28 Nov | A3, A4 + revise loop, multi-turn versioning + diff, QUESTION/CLOSE intents |
| P3 Hardening | 29 Nov – 1 Dec | Scenarios S1–S3 end-to-end, trap checklist passes, PDF polish, demo script, rehearsal |
| Final | Wed 2 Dec | Submission |

---

## 11. Ways of working (short; full protocol in [AGENTS.md](AGENTS.md))
- **Director chat** (the project lead's main Claude Code chat): owns PROJECT.md, the Decision log, contracts, and integration. Bring questions about planning, interfaces, and other chats' outputs there.
- **Agent chats**: one chat per agent. Each loads AGENTS.md → STATUS.md → PROJECT.md → its own `agents/Ax_*.md`. It builds only its module and asks the director for contract changes.
- **Sessions**: every work session gets a file in `sessions/`; STATUS.md always shows the current state.

---

## 12. Decision log

| ID | Date | Decision | Why |
|---|---|---|---|
| D-001 | 2026-11-21 | Add A0 Case Orchestrator (state, versioning, diff, intents, close-out) | The brief's core is the multi-version loop; the original plan was one-shot |
| D-002 | 2026-11-21 | Keep A2a/b/c parallel domain assessors; one shared spec | Distinct knowledge per domain; parallel = no latency cost |
| D-003 | 2026-11-21 | Single A3 Action Planner (no 3a/3b/3c) | Actions are cross-functional; avoids conflicting or duplicate actions; one coherent owner/timing plan |
| D-004 | 2026-11-21 | Risk = S×L per domain → 4 levels + floors F1–F4, computed in code | Brief requires 4 levels, consistency, and risk ≠ evidence strength |
| D-005 | 2026-11-21 | Focus issue changes ordering and depth, never scores | Consistency of method |
| D-006 | 2026-11-21 | A4 = Critic (grounding + trap checklist) + Outlook (residual risk, pattern traps); max 1 revise loop | Verifies A3 as the team planned, bounded cost |
| D-007 | 2026-11-21 | Build as Python code in Git (not n8n JSON, not Railway/Inngest/Supabase) | Git-friendly team collaboration and one-chat-per-agent mapping, testable, deterministic risk engine, no infra overhead in an 11-day window. **Open:** confirm with the instructors whether IBM watsonx Orchestrate is expected; if yes, the agents' prompts and contracts port to Orchestrate ADK agents + Python tools |
| D-008 | 2026-11-21 | KB loaded as cached full text, no RAG/vector DB | ~10k tokens; citations by source ID are more reliable than retrieval |
| D-009 | 2026-11-21 | §4 implemented in `src/contracts.py` with: unknown fields rejected; ID formats enforced (`KB-xx`/`U-xx`/`C-xxx`/`ACT-xxx`/`CASE-xxx`), unique per state; `score` auto-filled = S×L (mismatch rejected); every claim/action has ≥1 history entry and its status = last entry; `verified_*` needs result evidence; `turn_input.attachments` = file paths before A1, `U-xx` IDs after; `report.narrative` = free dict (A5 owns keys); `evidence_confidence` ∈ low/medium/high; QA `target` may be A2a/b/c; `Source.date` free text; empty case = version 0 | Validation catches bad agent output early (one retry per agent); fills gaps §4 left open |
| D-010 | 2026-11-21 | Extracted KB (`knowledge_base/extracted/KB-xx.md`, generated by `scripts/extract_kb.py`) adds, clearly labelled: `[Extraction note: …]` lines for images (screenshot PNGs = copies, not independent sources); computed per-batch totals for KB-13 (delivered ≠ sold); a `time_relevance` header field (historical_case → historical) | Helps agents avoid traps #2 and #7; the KB block tells agents these notes are not ACME content |
| D-011 | 2026-11-21 | `src/llm.py` is the only way agents call Claude: own validation instead of `messages.parse()`; the one validation retry lives in `call_structured` (not the pipeline); shared `COMMON_RULES` text (draft-only, cite IDs, label general knowledge, state unknowns) before the KB in every system prompt; server-side refusal fallback on (`fallbacks="default"`); effort per agent, cache effect to be measured in `trace.jsonl` | Keeps token usage and raw text on failures; the model sees its own error; one consistent guardrail for R18 and R2 |
| D-012 | 2026-11-21 | Hybrid models instead of Opus 5.5 everywhere: Sonnet 5.5 for the reasoning agents (A1–A4), Haiku 5.5 for A0 intent/answers and A5 narrative; overridable in `.env`. Refusal fallback only on models that support it (not Haiku 5.5) | API budget: ≈ $0.35/turn vs ≈ $1.00 with Opus (estimate; check `trace.jsonl`). Can switch the main model to Opus for the final demo if quality needs it |
| D-013 | 2026-11-21 | Director review of Serdar's A5 items (PR #2). Contract additions: `Action.focus_related: bool \| null` (A3, ordering only); `report.narrative_warnings: list \| null` (+ `A5Output`); impact `basis` value `incident_evidence`. No change needed: `executive_summary`/`closure_summary` (narrative is a free dict, omit instead of null); agent trace = `trace.jsonl`; readable KB titles = `kb.py` / `kb_source()`. Keep the brief's report section order (§7). A5 must use `llm.call_structured` | Additive only (existing data stays valid); matches what the A5 renderer already reads; section order follows the brief that graders compare against |
| D-014 | 2026-11-21 | Severity/Likelihood anchors (§6): clauses within an anchor are alternatives (any one is enough); reach and spread are scored only in Likelihood. S1 turn 1 reputational = S3 × L2 = 6 (answers Alibek's question) | Keeps the two dimensions separate, so every agent scores the same evidence the same way; counting reach in both would double-count it |
| D-015 | 2026-11-23 | `A3Output.warnings: list[str]` (Serdar's proposal, PR #10). A0 turns each warning into a non-blocking `QAIssue(target="A3")`, so it appears in the report's Appendix C; after an A4 revise, only the latest A3 run's warnings are kept | A3's soft checks (e.g. a High domain with no action) otherwise only reached a log file nobody reads; additive, existing data stays valid; same pattern as A5's `narrative_warnings` (D-013) |
