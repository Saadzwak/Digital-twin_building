# Self-review — final corrections + hostile audit

Date: 2026-07-19. Verified live (port 61740, LLM enabled `gpt-5.6-terra`).
87 tests green. Console clean on every screen. No horizontal overflow, no truncation.

## Correction 1 — "replay" removed from the execution view
- Execution header now reads **REAL COMPUTATION** (was "REPLAY OF REAL COMPUTATION").
- The `REPLAY OF A REAL COMPUTATION` badge element was deleted from `index.html`.
- The mode-event note (streamed as a stage line) was French **and** said "Replay"; it is
  now English and neutral: "Real computation over one year of real hourly measurements."
  (upload path: "Live real computation on your uploaded measurements.")
- Landing subtitle "…real computation replayed" → "…real computation".
- Verified live: the execution view contains no "replay" and no French.
- **Kept (by instruction):** the collapsed Methodology still says "Executed bench
  (3 starts/structure, replay of a real computation)" — that is the honest technical
  documentation, not the on-screen execution badge.

## Correction 2 — "The building" always first and expanded
- `applyRole` now pins `building` to order 0 and never collapses it, whatever the role;
  the other sections still reorganise per role. Verified across all four roles.

## Correction 3 — hostile audit

Fixed:
- **French leaks reaching the product:** both `engine.py` mode notes; `live_run.py`
  `selection_rule`; `live_run.py` selection explainer ("route-B verdict" jargon removed);
  `building_geometry.py` honesty note ("(M6/M7)" removed); methodology "millésime" → "release".
- **On-screen path / internal-vocab leaks (methodology):** the path `runs/m4/verdict.json`
  removed; "Route B" label removed; the internal enum `HUMAN_VALIDATION_REQUIRED` now renders
  as "pending human validation"; the raw `JSON.stringify(dataset)` dump (which exposed a file
  path) replaced by a clean readable line (rows, date range, splits, gaps).
- Regenerated the massing cache and the reference journal so the cleaned strings take effect.

Verified clean:
- No truncated/clipped text (scanned stats, table cells, chips, headers); no horizontal overflow.
- Values consistent across sections (current energy €38,634; best move MV+air-sealing €3,458/yr,
  7 tCO₂/yr, 12.3 yr, net €162,600−€120,000 CEE — identical in banner and decision table).
- Fast-scroll stress (40 rapid random scrolls) — no error, chips still track sections.
- Role change *during* an in-flight chat request — no error; the answer still resolves.
- Console clean on landing, execution, onboarding, dashboard, chat.
- Served API responses and the streamed run contain no forbidden trace.

Left, with reason:
- **Wire-only research terms** in the payload JSON (`article-4r3c-oracle`, "published
  parameters from the article, oracle-verified"): not rendered on screen, honest scientific
  terminology consistent with the shown "published reference calibration", no forbidden
  building name. Not exposed in the demo.
- **French in superseded Streamlit modules** (`constrained_chat*`, `dashboard_materialize*`,
  `dashboard_ui`): dead code — verified not imported by, and not reachable from, the web
  product (`webapp/`). Left untouched to avoid churn.
- **Raw journal files** (`runs/demo/reference/live_events.json`) still contain the original
  plan filenames and absolute preview paths ("Edificio PLEIADES (planta …)", `C:\Users\…`):
  these are **stripped by `engine._scrub`** before streaming (served stream verified CLEAN)
  and are never rendered by the client. Internal artifact, not a UI leak.
- **3D map falls back to static IGN tiles in the controlled test browser** (throttled rAF →
  MapLibre never reaches `loaded()`): expected; on a normal browser the extruded 3D building
  paints. The `map.loaded()` gate + verified static fallback guarantee the map is never blank.
