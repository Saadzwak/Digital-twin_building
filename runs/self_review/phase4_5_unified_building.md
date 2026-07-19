# Self-review — one unified building + Phases 4 & 5

Date: 2026-07-19. Verified live (port 61736), console clean, 84 tests green.

## One building, no two sources

The whole interface is one building: **98 Rue des Sarrazins, Wazemmes, Lille**
(real BDNB/DPE record). The hourly measurements feed the thermal identification
without ever being attributed to a different building. Every Pleiades/PLEIAData/
Murcia/planta/"block A" trace removed — from the title, brand, landing, demo
button, execution log (plan filenames scrubbed on the wire, not just hidden),
onboarding question, geometry provenance, and the journaled payload. Verified:
`pleiades_visible: []` on the dashboard; plan events clean on the API wire;
`block A in payload: False`. The 3D building keeps the existing axonometric
render, unlabelled (ConX LiDAR was a non-functional stub).

## Numbers are real or computed (no fabrication)

- Building attributes: real BDNB/DPE ADEME (millésime 2025-07.a), RNB
  2D9YFEZTSAC9, ADEME DPE 2259E0904747H.
- Carbon engine ported from ConX (pure Python) — operational + embodied (FDES) +
  off-site avoided. The **deep retrofit reproduces ConX's real figures exactly:
  1727 tCO₂ over 30 yr and €650,400** (test-pinned).
- Cost/subsidy rules ported from ConX; scenarios ranked by payback.
- Labelled assumptions (one line each): gas tariff 0.11 €/kWh; footprint-area &
  DPE-theoretical basis (ConX convention); target DPE per scenario; facade =
  perimeter × height; Éco-PLS treated as a loan (not deducted), only the CEE
  grant reduces net cost.

## Phase 4 — interpretation (leads, not conclusions)

Three leads, grounded in the real record: (1) ~96% direct-path loss → air
infiltration/ventilation dominates; consistent with the building's declared
window-only ventilation (no VMC) and U_wall 1.0 — check airtightness first;
(2) dated break → ranked hypotheses (heating season/old boiler first);
(3) slow response → anticipatory control, with the very-long constant flagged as
partly a model artifact.

## Phase 5 — ConX integrated

Building identity + real IGN aerial neighbourhood map (Géoplateforme WMTS, target
+ 5 real neighbours by DPE) · owner KPIs (energy €/yr, CO₂/yr, dated change,
best-ROI retrofit) · renovation decision table ranked by payback with € and CO₂ ·
regulation chips (energy sieve/loi Climat, social landlord, QPV, heat network,
AC1, PMR) · eligible support schemes · neighbour comparison. All English.

## Verification

Full English journey from vierge: landing → demo → live execution (34.7 s) →
onboarding → dashboard (identity, map, KPIs, ROI table, regulation, thermal
diagnosis, interpretation, neighbourhood) → chat (answer + refusal-with-
alternative + out-of-scope). Console clean; 0 NaN in SVGs; 6/6 IGN tiles loaded;
84 tests green.

## What was cut / changed scope

- The old RC-physics "% energy at equal comfort" **bar chart** (and its
  hover-the-building interaction) was **replaced** by the renovation €/CO₂/ROI
  decision table — the priority-1/2 deliverable. The physics scenarios remain
  reachable via the chat. Net: one interaction (scenario→building hover) dropped
  in favour of the money-and-carbon table.
- Nothing else cut. Map neighbour bearings are a layout choice (real distances +
  real DPE shown; positions not claimed as exact).
