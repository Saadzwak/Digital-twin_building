# Self-review — Phase 2 (two bugs) + Phase 3 (English)

Date: 2026-07-19. Verified live in the browser (port 61734), console clean, 79 tests green.

## Bug A — drift chart vs verdict sign + year coverage

Investigation (end-to-end): residual convention is `measured − estimated`
throughout; at year-end the measured daily mean (24 °C) is genuinely **below**
the model estimate (35 °C), residual ≈ −11 °C, and the daily series covers to
Dec 31 (361 rows). So the data and sign were already correct — but the chart
was confusing because (a) the open-loop model line drifts to an absurd 35 °C by
December and (b) measured is slightly *above* the model in summer, so a glance
read the wrong way.

Fix (chart, not data):
- Sign-coloured gap ribbon between the two lines — cool blue where measured is
  BELOW the model (the autumn/winter story), warm amber where above. The large
  blue band after the break makes "below model" unmistakable.
- End-of-year annotation "−11.3 °C below model", matching the verdict.
- Month gridlines Jan…Dec + amber line labelled "model expectation (open-loop)"
  so the 35 °C is understood as extrapolation.
- Verified live: measured line rightmost y is lower on screen than the model
  line (measured below), months Jan/Nov/Dec present (full-year coverage).

## Bug B — scenario chart labels + axis/origin

Cause: labels were SVG text anchored near the bar and clipped off the left edge;
identical values could look unequal because of label overlap. The two −13 %
scenarios (−12.6068 each) are numerically identical.

Fix:
- Full title placed ABOVE each bar, left-aligned inside the plot — never clipped.
- Shared zero-origin axis; bar length = |zx(value) − zx(0)|, so identical values
  give identical bars. Verified live: both −13 % bars render at width 531.2 =
  531.2 (previously appeared unequal). Axis labelled
  "HEATING ENERGY AT EQUAL COMFORT (%)".

## Phase 3 — English

Every user-facing string translated: backend (`live_run`, `product_chat`,
`annual_drift`, `counterfactuals`, `business_language`, `onboarding`,
`building_geometry`), charts (axis labels, drift/scenario), frontend
(`index.html`, `app.js`), RC schematic labels. The reference bank was
re-precomputed so the journaled payload text is English. Chat trigger keywords
accept English (and still tolerate French). Tests updated to the English
assertions; the superseded Streamlit UI and its module (`constrained_chat.py`)
were left as-is (not the product).

Verified live: landing, execution view, onboarding, dashboard, chat (answer +
refusal-with-alternative + out-of-scope refusal) all in English; console clean;
79 tests green.
