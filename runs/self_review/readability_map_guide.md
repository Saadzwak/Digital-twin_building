# Self-review — readability, live map, chat guide

Date: 2026-07-19. Verified live (port 61737), console clean incl. external CDN,
84 tests green, no horizontal overflow (scrollWidth == clientWidth), no truncation.

## Chantier 2 — readability (priority 1)

The dashboard is a strict scroll narrative: **01 The building** (identity card +
dominant map + 3 stats: DPE, current bill €/yr, current emissions) → **02 The
digital twin** (lead verdict + 3 stats: heat-loss, responsiveness, dated change;
drift chart; thermal 3D; interpretation leads) → **03 Recommendations** (best-move
banner with €/CO₂/payback + regulation chips + subsidies) → **04 The decision**
(ROI table ranked by payback) → **05 Methodology** (collapsed). Each section has a
numbered header, a one-line "what you'll understand" subtitle, at most three
highlighted numbers, and generous spacing. Someone scrolling reads: here is the
building → here is what's wrong → here is what to do → here is the return.

## Chantier 3 — chat as guide

A sticky bottom **guide dock** replaces the buried chat: a persistent input, a
contextual label, and 2–3 suggestion chips that **change with the section in view**
(scroll-position detector, verified: "About the building" → "About the decision").
Answers are pedagogical — they explain what a value means, what it implies, and
what to check next — across both the thermal diagnosis and the renovation domain
(DPE, bill, drift, heat loss, subsidies, regulation, ROI, neighbours). Out-of-scope
questions keep the refusal-with-alternative behaviour. Everything stays sourced.

## Chantier 1 — dynamic 3D map

MapLibre GL + deck.gl (CDN), IGN ortho WMTS basemap, oblique pitch, the target
building extruded and coloured by DPE, neighbours extruded grey, free zoom / rotate
/ pan (3 nav controls). It returns success only once the canvas exists (not gated
on full tile load) and **falls back cleanly to the real static IGN-tile map** if the
CDN is unavailable or errors — verified both paths, console clean either way. The
building extrusion uses the real footprint area (1084 m²) at the real centroid; the
exact BDNB polygon isn't available without their DB, so the emprise is extruded as
allowed.

## Verification

Full English journey from vierge: home → demo → live execution (34.6 s) → onboarding
→ building → twin → recommendations → decision → guided chat → refused chat. Console
clean including MapLibre/deck.gl/IGN. Map manipulable (zoom/rotate/pan). No overflow,
no truncation. Sections read as a narrative. 84 tests green.

## What was cut

Nothing was cut this iteration. Two notes: (1) the guide contextual chips update on
real scroll (a rapid programmatic scrollIntoView loop doesn't fire scroll events,
but a genuine scroll or a dispatched scroll event does — verified); (2) the 3D map
extrudes the real footprint area, not the exact BDNB polygon (unavailable offline),
which is the sanctioned fallback.
