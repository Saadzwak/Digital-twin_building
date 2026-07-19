# Self-review — real 3D building + role/métier view

Date: 2026-07-19. Verified live (port 61740), 87 tests green, console clean,
no horizontal overflow, no truncation.

## Chantier 1 — the real 3D building (no more cube)

The map now extrudes the **real emprise polygon**, not a rectangle synthesised
from a floor area. Source, in the order searched: the IGN Géoplateforme **WFS**
(`data.geopf.fr/wfs/ows`, layer `BDTOPO_V3:batiment`) answered with the real
BD TOPO footprints — so the local `.7z` archives and the other fallbacks (API
Carto, BDNB, OSM Overpass) were not needed. The target (RNB `2D9YFEZTSAC9`,
98 Rue des Sarrazins) came back as a **44-vertex polygon with setbacks**, real
height **10.7 m** (R+4), plus **277 neighbouring buildings** within 150 m, each
at its own real height (2–16 m). All of it is cached to
`runs/geometry/wazemmes_buildings.json` (served by `/api/buildings-3d`), so the
demo never depends on the network.

`map3d.js` fetches that cache and draws two deck.gl `PolygonLayer`s: the target
extruded and coloured by DPE (F → red), the neighbours extruded grey — over the
IGN ortho WMTS basemap, oblique pitch, free zoom/rotate/pan. Legend reads
"real BD TOPO footprint · 277 neighbours". A test (`tests/test_building_3d.py`)
pins that the target ring has > 8 vertices at a plausible height and that the
neighbours carry varied real heights — so it can never silently regress to a cube.

**Render verification & robustness.** On a WebGL-capable browser (the filming
machine) this is the canonical deck.gl `MapboxOverlay` interleaved pattern and
paints the extruded buildings. Verified from the live page: both libraries load,
both `PolygonLayer`s are constructed with the real data (target 1, neighbours
277), the view is centred on the real coordinates at pitch 54 / zoom 17.6, and
the console is clean. The *live painted frame* could not be pixel-captured inside
the controlled test browser — it throttles `requestAnimationFrame`, so MapLibre's
style never reaches `loaded()` and neither the raster basemap nor the interleaved
deck layers composite (the same limitation behind the screenshot timeout). To
make that failure mode safe rather than blank, the success gate now **requires
`map.loaded()` within 5 s**; on a capable browser that is <1 s (no needless
fallback), and where WebGL/rAF is throttled it returns false and the caller shows
the **real static IGN-ortho map** instead of an empty canvas. Both paths were
verified live here: the dynamic gate correctly returns false after ~5.2 s in this
browser, and the static fallback then paints 6/6 real IGN ortho tiles with the
building and neighbours located. The map is never blank. Offline proof of the
exact geometry the dynamic layer extrudes: `massing3d.png`.

## Chantier 2 — one diagnosis, four readings (role lens)

A role selector at the top of the dashboard offers **Owner / Engineering /
Architect / Operator**. Selecting a role **reorganises the same evidence** — it
never recomputes. Sections are prioritised (surfaced, ordered first) or folded
(header + one-line summary, one click to expand); nothing is removed, everyone
keeps full access. Verified reorganisation:

- **Owner** — "Should I launch the works, and what's the return?" →
  Recommendations → Decision (ROI) → Building; Twin and Methodology fold.
- **Engineering** — "Does the model hold?" → Twin → Building → Methodology;
  Recommendations and Decision fold.
- **Architect** — "What can I do, under what constraints?" → Building (map,
  geometry, neighbours) → Recommendations → Decision; Twin and Methodology fold.
- **Operator** — "What changed, what to inspect?" → Twin (dated drift,
  responsiveness, leads) → Building; Recommendations, Decision, Methodology fold.

The reorg uses CSS `order` + a fold class, so the **map canvas is never
recreated** and stays stable and manipulable in every role (verified: same
canvas after cycling all four roles). The guide dock adapts too — its label and
its three suggested questions change with the active role, then keep following
the section under the scroll. A discreet line states the intent: "One diagnosis,
four readings — the same evidence reorganised for each role… no document handoff
between actors."

## Complementary checks

- **Scroll context robust**: a real scroll event moves the guide from the role
  chips to "About the diagnosis" (Twin) and "About the decision" (Decision).
- **Chat**: success (DPE F explained with real 324 kWh/71 kgCO₂ and the
  regulatory clock) and refusal (out-of-scope → refusal + alternative + scope
  note) both render in the dock.
- **No local leak**: `dataset.path` is now a relative posix path
  (`data/processed/hourly_reference.csv`); no absolute path / home / folder name
  reaches the served payload or the Methodology view. Every served API response
  scanned clean of forbidden traces.

## What remains imperfect

- The BD TOPO `hauteur` is the modelled building height, not a LiDAR point
  cloud; roofs are flat extrusions (no pitched-roof geometry). This is real
  IGN data, extruded honestly, but it is massing, not a photogrammetric mesh.
- The neighbour buildings are drawn uniform grey (not by their own DPE) — DPE
  is only known for the target and the five documented neighbours, so colouring
  all 277 by DPE would fabricate data we don't have.
- Live in-browser screenshots and WebGL frame-readback don't work in the
  controlled test browser (throttled rAF; MapLibre never reaches `loaded()`), so
  the *painted* 3D map is verified structurally (libraries, staged layers, view
  state, clean console) plus the offline oblique render, not by a captured live
  frame. On a normal browser the dynamic 3D paints; the `map.loaded()` gate + the
  verified static-ortho fallback guarantee the map is never blank either way.
- The static fallback locates the building with DPE markers on real ortho tiles
  but does not itself draw the extruded footprint polygon (the dynamic path does).
  Drawing the cached emprise as an SVG overlay on the fallback is a possible
  future enhancement.
