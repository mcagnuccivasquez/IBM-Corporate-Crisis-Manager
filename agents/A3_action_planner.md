# A3 — Action Planner

> **New chat? Load in this order:** `AGENTS.md` → `STATUS.md` → `PROJECT.md` (esp. §4 actions, §8 KB) → this file.
> **Owns:** `src/agents/a3_actions.py`, `src/prompts/a3_actions.md`, `tests/test_a3_*.py`.
> **Updated 2026-11-23 (Serdar, session 3):** output section now follows the pipeline contract (`A3Output`), code-built records, checks (§4b). Listed under *Needs director review* in `sessions/2026-11-23_serdar_a3-actions.md`.
> Replaces the original 3a/3b/3c split (D-003): one planner sees all three domains and produces **one coherent plan**.

## 1. Mission
Maintain the **action register**: what ACME should do, why (grounded in precedent or policy), who owns it, by when, and the current status of each action. Also produce the **stakeholder map**.
A3 drafts and recommends. It never claims anything was done unless the user said so.

## 2. Input
`claims`, `impacts` (3 domains), `risk`, `focus`, previous `actions` + `stakeholders`, the current turn's user text (for status updates), A4 issues (on a revise run), KB (cached).

## 3. Output (pipeline contract, `src/contracts.py`)
`run(state, turn) -> A3Output(actions=[...], stakeholders=[...])`
- `actions`: only **new or changed** actions, as full `Action` objects. A0 merges them by ID, never deletes, and rejects an update that does not keep the earlier `status_history` entries.
- `stakeholders`: the full current map (replaces the previous one; an empty list keeps the old map).
- No `closure_open_actions`: on CLOSE the pipeline computes `closure.open_actions` itself (statuses proposed / approved / in_progress).
- On an A4 REVISE targeting A3, A3 runs once more and finds the critic's issues in `state.qa.issues` (target `A3`).
- API errors (`LLMError`) go up to the pipeline, like A1/A2.

**How the records are built (session 3 design):** the LLM returns a short *plan*, and **code** builds the `Action` records:
```json
{
  "new_actions": [ { "title": "...", "what_it_does": "...", "owner": "...", "approver": "", "timing": "within 24h", "priority": "P1",
                     "focus_related": true, "domains": ["economic"], "options_considered": [ ... ], "basis_source_ids": ["KB-12"],
                     "expected_effect": "...", "initial_status": "proposed", "result_evidence_source_ids": [], "reason": "..." } ],
  "changes":     [ { "action_id": "ACT-001", "new_status": "completed", "reason": "User: hold done", "result_evidence_source_ids": ["U-03"],
                     "title": "", "what_it_does": "", "owner": "", "approver": "", "timing": "", "priority": "unchanged",
                     "focus_related": "unchanged", "domains": [], "options_considered": [], "basis_source_ids": [], "expected_effect": "" } ],
  "stakeholders": [ { "name": "...", "type": "external", "interest": "...", "impact": "...", "acme_contact": "" } ],
  "no_action_reasons": [ "economic: no action, because …" ]
}
```
**Plan format rule (session 4, live API):** the API compiles the plan schema into a grammar and rejected the first version as too large (31 optional + 15 nullable fields). So every plan field is **required** and **nothing is nullable**; "none / unchanged" is written as `""` (text), `[]` (list) or `"unchanged"` (`new_status`, `priority`, `focus_related` = `"true"`/`"false"`/`"unchanged"`). Stakeholders and options use plan-local models (`PlanStakeholder` with `acme_contact` `""` = none, `PlanOption`), converted to the contract in code. An offline test guards this.

Code assigns new IDs (continuing the numbering, never reused), writes a `status_history` entry for this version for every status change (with the reason), keeps all earlier entries, and keeps `status` equal to the last entry. A new action starts as `proposed`, or at the status the **user** reported (approved / in_progress / completed, never verified). Without a case focus, `focus_related` is always `null` (D-013).

## 4. Planning rules
1. **Cover the impacts.** Every High/Critical domain impact gets at least one action, or an explicit "no action, because…".
2. **Options for major decisions.** Any action with significant cost, market, or legal consequence (holds, replacements, withdrawals, public statements, notifications) needs **≥2 options** in `options_considered`, with pros/cons, the probable result, and which one is recommended and why.
3. **Grounded, not hopeful.** `basis_source_ids` must point to a precedent or policy (e.g. KB-08 acknowledgement + private follow-up; KB-03 refer smoke/sparks to Care+Quality and collect the physical sample; KB-12 hold cost; KB-09 containment + careful wording). If no precedent exists (ACME has **no crisis playbook**, KB-02), say so and label it `general_knowledge`.
4. **What it does.** `what_it_does` explains the mechanism in one or two sentences (requirement R10).
5. **Owners from KB-02 only**: Elena Rossi (COO, cross-team), Daniel Moretti (CEO, withdrawals and large remedies), Maya Chen (Quality), Luca Ferri (Supply Chain), Tom Weber (Customer Care), Aisha Khan (Security), Sophie Laurent (Legal/DPO), Anna Keller (Communications), Marco Bianchi (Finance). Set `approver` when policy requires it (CEO for withdrawal or large remedy; Sophie for injury, authority, or personal data; Maya for technical wording; Elena for messages affecting availability or the media).
6. **Timing + priority**: P1 = now/24h (containment, safety, evidence capture), P2 = this week, P3 = later/improvement (e.g. finally create the incident playbook and one shared incident record, KB-02/KB-05/KB-10).
7. **Status discipline**: proposed → approved → in_progress → completed → verified_effective / verified_ineffective (or dropped). Move status **only** on user-reported facts. `verified_*` needs result evidence (a source). If a completed action shows no effect, propose a follow-up instead of repeating it.
8. **Feasibility and policy**: no remote/firmware fix for PCX-100 (KB-03); no asking customers for passwords or recordings (KB-04); public text must not blame customers, contain personal data, or claim "all units tested" / "authorities contacted" / "independent tests" unless confirmed (KB-10); the system only drafts statements and notifications and never "sends" them.
9. **Draft wording**: for communication actions, include a short draft holding statement in `what_it_does` or an attached field, following KB-10 dos and don'ts (marked "draft, needs Anna + Maya/Sophie review").

## 4b. Checks (agreed with Serdar, session 3)
| Check | Kind |
|---|---|
| Owner, approver or stakeholder `acme_contact` not on the KB-02 contact sheet | hard |
| `basis_source_ids` not a registered source or KB-01…KB-13; `result_evidence_source_ids` not registered evidence about this incident (KB files can't prove a result) | hard |
| Change to an unknown action ID, or the same action changed twice | hard |
| Invalid action (e.g. `verified_*` without result evidence) | hard |
| New action that duplicates an existing title (e.g. on a revise run) | hard |
| Banned phrases (KB-03, KB-04, KB-09, KB-10, scenario S2: remote fix, all units tested, authorities contacted, independent tests, asking for passwords/recordings, recovery proves nothing was viewed, data is safe / no breach) and personal data in A3's texts (shared `src/report/checks.py`); a negation within 5 words is fine | hard |
| Status changed in a turn where the user reported nothing (no text, no attachment) | hard |
| Empty title or `what_it_does` | hard |
| No `basis_source_ids` and not labelled "no precedent" / "general knowledge"; empty `expected_effect` | soft |
| `focus_related` missing on a live action when the case has a focus | hard |
| High/Critical domain with no action and no "no action, because" | soft |
| Major decision (hold, recall, statement, notification… in the title) without ≥2 options and exactly one chosen | soft |
| Recall / withdrawal / large remedy without Daniel Moretti (CEO) as approver | soft |
| Injury / authority / personal-data action without Sophie Laurent (Legal/DPO) | soft |

Hard problems trigger the single retry in `llm.call_structured`; if they remain, the valid parts are kept and the rest is reported. All warnings are returned in `A3Output.warnings` (D-015, approved 2026-11-23); A0 turns each into a non-blocking `QAIssue(target="A3")`, so they appear in the report's Appendix C (they are also logged).

## 5. Runtime system prompt
The live prompt is `src/prompts/a3_actions.md` (the draft below + the planning rules above, the plan format, the focus and revise rules). `llm.py` adds `COMMON_RULES` and the KB block. Model: Sonnet 5.5 (D-012), effort `high`.

Original draft:
```
You are the Action Planner in ACME's crisis-management system. Using the evidence ledger, the three domain impact
assessments, the overall risk and the ACME knowledge base, maintain a single coordinated action plan.

For each action give: what it does, owner and approver (only people listed in the ACME contacts), timing, priority,
the precedent or policy it is based on (source IDs), the expected effect, and its status. For major decisions present
at least two options with pros, cons and probable results, and say which you recommend and why. Base recommendations
on what ACME's own records show has worked or is required; if there is no precedent, say so and label general
knowledge. Never propose actions outside company policy or the law, never promise a remote fix for PCX-100, never ask
for credentials or recordings, and never state that something has been done unless the user reported it. Change an
action's status only on user-reported facts; mark an action verified effective or ineffective only with evidence of
the result. You draft and recommend; you never execute recalls, notifications or public posts.
```

## 6. Acceptance tests
- [ ] S1 turn 1: P1 actions include sample collection via Care→Quality (KB-03), holding statement draft (KB-08/10), warehouse-hold **options** for PCX-2609-A/B with KB-12 cost, Legal/DPO looped in (F1). *Needs a live run.* Code guarantees: owners only from KB-02 (hard check); major decisions without options flagged (soft).
- [x] No action says "remote update", "all units tested", or "authorities contacted" (unless the evidence says so): hard check, retried (tested).
- [x] User says "Elena approved the hold" → proposed→approved with reason, no jump to completed: the code records exactly the reported status with a version entry (tested through the pipeline over two turns). *Whether the LLM picks "approved" needs a live run.*
- [x] `verified_effective` only with a result source about this incident (contract + hard check, tested).
- [x] CLOSE → open actions listed: done by the pipeline (`closure.open_actions`), not by A3.
- [x] Records: IDs continue, history kept for A0's merge rule, duplicates and unknown IDs rejected (tested).
- [ ] Live run on Sonnet 5.5 with S1 turns 1–4 (planned with the A5 live test).
