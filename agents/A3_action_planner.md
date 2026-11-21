# A3 — Action Planner

> **New chat? Load in this order:** `AGENTS.md` → `STATUS.md` → `PROJECT.md` (esp. §4 actions, §8 KB) → this file.
> **Owns:** `src/agents/a3_actions.py`, `src/prompts/a3_actions.md`, `tests/test_a3_*.py`.
> Replaces the original 3a/3b/3c split (D-003): one planner sees all three domains and produces **one coherent plan**.

## 1. Mission
Maintain the **action register**: what ACME should do, why (grounded in precedent or policy), who owns it, by when, and the current status of each action. Also produce the **stakeholder map**.
A3 drafts and recommends. It never claims anything was done unless the user said so.

## 2. Input
`claims`, `impacts` (3 domains), `risk`, `focus`, previous `actions` + `stakeholders`, the current turn's user text (for status updates), A4 issues (on a revise run), KB (cached).

## 3. Output
```json
{
  "actions_new":     [ /* Action objects (PROJECT §4), IDs ACT-xxx continuing */ ],
  "actions_updated": [ { "action_id": "ACT-004", "to": "completed", "reason": "User: hold done 22 Nov", "result_evidence_source_ids": [] } ],
  "stakeholders":    [ /* full current map */ ],
  "closure_open_actions": []          // only on CLOSE: action IDs still not completed/verified
}
```

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

## 5. Draft runtime system prompt
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
- [ ] S1 turn 1: P1 actions include sample collection via Care→Quality (KB-03), holding statement draft (KB-08/10), warehouse-hold **options** for PCX-2609-A/B with KB-12 cost, Legal/DPO looped in (F1). All owners are from KB-02.
- [ ] No action says "remote update", "all units tested", or "authorities contacted" (unless the user said so).
- [ ] User says "Elena approved the hold" → ACT status proposed→approved with reason. No jump to completed.
- [ ] User reports a result with data → `verified_effective` only with a result source.
- [ ] CLOSE → `closure_open_actions` lists everything not completed/verified.
