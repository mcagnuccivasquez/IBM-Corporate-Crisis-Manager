# A2b — Economic Impact Lens
# Appended to a2_common.md at runtime by _build_prompt().

## Economic domain lens

Analyse **financial losses, operational disruption, compensation costs, revenue losses, and business continuity**.

### Key dimensions
1. **Replacement and logistics costs** (KB-12): Use only KB-12 assumptions:
   - €30 per unit for replacement + logistics.
   - €5,000 per batch for a warehouse hold setup.
   - **Always show scoped ranges**, not a single figure:
     - Minimum: warehouse-only hold (units not yet shipped).
     - Maximum: replacement of all delivered units for the suspect batch(es).
   - **Delivered ≠ sold**: KB-13 gives delivered-to-channel quantities, not consumer sales.
     Do not multiply €30 by all units ever shipped without clear justification.
2. **Stock quantities** (KB-13):
   - Batch PCX-2609-A: 2,000 warehouse + 6,000 delivered (DE 2,500 / IT 2,000 / FR 1,500).
   - Batch PCX-2609-B: 3,000 warehouse + 5,000 delivered (DE 2,200 / IT 1,800 / FR 1,000).
   - Use these figures directly; do not extrapolate to "all units ever shipped".
3. **Large remedy → CEO involvement**: Any remedy costing significantly above normal thresholds
   requires Daniel Moretti (CEO) involvement per KB-02 and KB-12. Mention this as a fact.
4. **Exclusions from Finance (KB-12)**: The following are explicitly *not estimated* by Finance
   and must be named as such: lost sales revenue, retailer effects, legal costs, marketing campaigns.
   Do not invent figures for these categories.
5. **Operational disruption**: Warehouse hold, Quality testing resources, Customer Care workload.
   Cite KB-05 ticket data for current workload baseline.
6. **Business continuity**: Does the incident threaten production, supply, or key market access?

### Worked example for scope illustration
- Warehouse-only hold on PCX-2609-B: €5,000 (KB-12).
- Replacement of all delivered PCX-2609-B units: 5,000 × €30 = €150,000 (KB-12/13).
  Lower bound = confirmed affected units (unknown without lab results); upper bound = 5,000.
- Both batches replaced: (6,000 + 5,000) × €30 = €330,000.
State these as ranges and note that "delivered ≠ sold" so the actual exposure is likely lower.

### What to avoid
- Never multiply €30 by all units ever shipped without scope and justification.
- Never state a single precise financial figure without showing the range and the assumptions.
- Do not include Finance exclusions (lost sales, legal, campaigns) as your estimates.
- Do not use VN-3 (KB-11, July sampling) to clear September batches — it did not cover them.
