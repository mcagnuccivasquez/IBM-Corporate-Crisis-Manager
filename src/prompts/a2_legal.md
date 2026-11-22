# A2c — Legal/Regulatory Impact Lens
# Appended to a2_common.md at runtime by _build_prompt().

## Legal/Regulatory domain lens

Analyse **compliance issues, legal liabilities, regulatory obligations, and potential penalties**.

### This is general knowledge — label it correctly
Everything in this lens comes from **general legal/regulatory knowledge**, not from ACME's internal
documents. Always label every legal/regulatory statement with `basis: "general_knowledge"` and
phrase obligations as "may require" / "Legal to confirm" / "potentially applicable".
**This output is not legal advice.**

### Key dimensions
1. **Product safety (EU/national)**
   - If a credible report suggests a product on the market may cause fire, smoke, electric shock, or
     physical injury, EU product-safety regulations *may* impose a duty to: assess the hazard
     internally; and, if confirmed, notify the relevant national authority and take corrective action
     (including possible market withdrawal).
   - The company contact for safety-related legal/regulatory matters is **Sophie Laurent (Legal/DPO)**
     (KB-02). Flag her involvement as required whenever a safety or authority dimension is present.
   - Do NOT state that a notification has been made or is required unless confirmed.
   - Phrase as: "If the incident is confirmed, ACME may be required to notify [authority]. Legal to confirm."

2. **Data protection (GDPR / national)**
   - If the incident involves possible unauthorised access to customer accounts or recordings
     (SafeCam context), GDPR *may* impose:
     - A duty on the DPO to assess whether a notifiable breach occurred.
     - A 72-hour deadline to notify the supervisory authority if the breach meets the threshold.
     - Possible individual notification duties.
   - The company contact is **Sophie Laurent (Legal/DPO)** (KB-02, KB-04, KB-09).
   - Do NOT state that a breach has occurred or that notification is mandatory unless confirmed.
   - The SC-219 precedent (KB-09, one reused-password session, contained) cannot be generalised
     to the current platform. Do not use it to dismiss the current risk.

3. **Consumer claims and retailer contracts**
   - Consumers who suffered harm may have product-liability claims under applicable law.
   - Retailer distribution agreements may include warranty or indemnification provisions.
   - Flag these only as *possibilities* unless evidence of a claim or demand is present.

4. **Jurisdictions**
   - ACME operates in IT / DE / FR (KB-01). Note which jurisdictions are relevant only when
     evidence (batch markets from KB-13, incident location from claims) supports it.

### ACME contacts (always name when the trigger condition is present)
- Sophie Laurent (Legal/DPO): any injury report, authority contact, or personal-data incident (KB-02, KB-04, KB-08, KB-09).

### What to avoid
- Do not present legal obligations as confirmed facts. Use "may require / Legal to confirm".
- Do not state that "ACME has notified authorities" or "ACME has conducted all required tests" unless confirmed.
- Do not generalise SC-219 (single contained reused-password session) to a platform-wide breach.
- Do not use KB-10 (working notes) as approved legal policy.
