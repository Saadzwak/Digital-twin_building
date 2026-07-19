# Thermal Twin — a physics world-model of a building, from a plan and a CSV

**Category: Work and productivity.**

An energy audit today costs thousands of euros, needs site visits, and takes
months — and the result travels as a PDF between the owner, the engineering firm,
the architect and the operator, each re-reading it from scratch. **Thermal Twin
turns a floor plan and one CSV of hourly measurements into a physics-constrained
digital twin of the building** — a *world model* that reproduces a year of real
thermal behaviour and can **simulate counterfactuals**: what the building *would
become* if its envelope changed. From that, it produces a costed renovation
decision (euros, CO₂, payback, eligible subsidies, regulation) and lets **four
trades read one source of truth** — no document handed off between them. A
GPT-5.6 guide explains any of it in plain language, grounded strictly on the
computed numbers.

The subject building is real: **98 Rue des Sarrazins, Wazemmes, Lille** (public
building and energy-performance registries).

---

## Why the model is interesting

- **A world model with almost no data.** It learns an internal state-space model
  from **three signals** (indoor temperature, outdoor temperature, heating) plus a
  plan — no added sensors, no labels — and can then predict the consequences of an
  action (an envelope change). What separates it from a world model learned by a
  neural network is that it is **constrained by physics** (resistance–capacitance
  networks), so it is *identifiable* from a few thousand hours of one building where
  a learned model would need thousands of episodes.
- **One diagnosis, four readings.** A role selector (Owner / Engineering /
  Architect / Operator) **reorganises** the same evidence — never recomputes it.
  Nothing is hidden; non-priority sections just fold. "The building" stays first for
  everyone.
- **Grounded, honest numbers.** Every figure on screen is a real record or an
  executed computation. The chat may phrase and reformulate, but it **never invents
  a number** — the estimates under an answer always come from the deterministic
  engine.

---

## Run it (Python 3.12)

```bash
# 1. install
python -m pip install -r requirements.txt

# 2. (optional) enable the GPT-5.6 guide — without a key the chat falls back to a
#    deterministic guide, so the app still runs end-to-end.
export OPENAI_API_KEY=<your-openai-api-key>        # Windows PowerShell: $env:OPENAI_API_KEY="..."
export OPENAI_CHAT_MODEL=gpt-5.6-terra             # optional; default is gpt-5.6-terra

# 3. launch
cd webapp
python -m uvicorn server:app --port 61740
```

Open **http://localhost:61740/**. On startup you'll see either
`[chat] OpenAI LLM enabled — model gpt-5.6-terra` or
`[chat] OPENAI_API_KEY not set — chat falls back to the deterministic guide`.

The app ships **pre-computed caches**, so the whole demo runs **offline** with just
`fastapi uvicorn numpy pandas scipy` — no database, no build step, no external
account required to see the diagnosis.

## How judges test it (2 minutes)

1. On the landing page, click **"▶ Run the demo diagnosis"**. Watch the live view:
   the structure counter climbs **1 → 19** as it searches the physical model space
   (~34 s), the RC schematic reconfigures, the building reveals.
2. Click **"Continue to the dashboard."**
3. **01 The building** shows the real record (DPE class F, current bill and
   emissions computed).
4. **Switch roles** in the top bar (Owner / Engineering / Architect / Operator) —
   the page visibly reorganises around each trade; "The building" stays first.
5. **Drag to rotate / scroll to zoom** the 3D building — a real BD TOPO footprint
   (with setbacks) extruded to real height, among its real neighbours. *(If your
   browser has WebGL disabled it falls back to a real IGN-ortho map — never blank.)*
6. Scroll to **04 The decision** — renovation options ranked by payback (€, CO₂,
   grants).
7. Open the **"◆ Guide"** (bottom-right) and ask anything, e.g.
   *"honestly, how bad is this building and will it cost me a fortune?"* — with a key
   this is **GPT-5.6**; then ask *"will interest rates go down next year?"* to see it
   **refuse and offer the closest answerable thing**.

**GPT-5.6 QA endpoints (evidence).** With a key set, you can hit the two internal
supervision endpoints directly:
```bash
curl http://localhost:61740/api/verify-geometry     # vision QA of the extracted footprint
curl http://localhost:61740/api/verify-selection     # GPT-5.6 review of the model-selection bench
```

**Testing the real GPT-5.6 path:** the public repo contains **no API key**. To let
GPT-5.6 run (guide + both QA endpoints), set your own `OPENAI_API_KEY` (step 2).
Without it, the app is fully functional on the deterministic fallback.

## Run the tests

```bash
python -m pytest tests        # 87 passing
```

## Data

The app and the tests run entirely from the committed **processed** dataset
(`data/processed/hourly_reference.csv`, one year of hourly measurements) and the
cached artifacts under `runs/` — **no download is needed to test**.

The **full raw dataset** (the original sensor / consumption / weather dump the
processed file is derived from) is optional and provided as `Data_Nature.zip` on the
repository's **[Releases](../../releases)** page (it is too large for the git repo).
To reproduce the processing from scratch, download it, place `Data_Nature.zip` at the
repo root, and the ingestion (`src/thermal_twin/reference_ingestion.py`) will extract
and rebuild the processed file.

---

## Architecture

- **Backend** — FastAPI (`webapp/server.py`) serving a vanilla-JS ES-module SPA
  (`webapp/static/`), streaming the live run as NDJSON. Every JSON response is
  sanitized (no NaN/Inf reaches the client).
- **Identification engine** (`src/thermal_twin/`) — 19 RC (resistance–capacitance)
  network topologies; continuous state-space with **exact discretization by matrix
  exponential** (`rc_core.py`); **L-BFGS-B calibration in log-parameter space**
  (`identification.py`, `multistart_impl.py`); metrics + **BIC** model selection.
- **Renovation engine** (`renovation.py` + `data/fdes_static.json`) — deterministic
  operational + embodied carbon, cost, and eligible-subsidy computation → the ROI
  decision table.
- **Real 3D geometry** (`building_3d.py`) — building footprints fetched from the
  **IGN BD TOPO WFS** (public mapping service), cached; rendered with
  MapLibre GL + deck.gl over IGN ortho tiles, with a static-tile fallback.
- **GPT-5.6 layer** — the grounded guide (`llm_chat.py`) plus two QA supervisors
  (`llm_supervisor.py`): a vision check of the plan-reading and a review of the
  structure-selection optimization. See "How Codex and GPT-5.6 were used" below.

Repo layout (essentials): `webapp/` (product), `src/thermal_twin/` (engine),
`tests/` (87 tests), `data/` (sample input + carbon factors),
`runs/geometry/` & `runs/demo/reference/` (committed caches so it runs offline),
`docs/DEMO_SCRIPT.md` (demo shoot pack).

---

## How Codex and GPT-5.6 were used

**Codex** reverse-engineered and rebuilt the scientific core. It read a research
notebook on RC thermal models and re-specified it into a tested engine: it
extracted the **19 network connectivities**, the simulation protocol and the data
pipeline, and listed the divergences it found between the published article and the
notebook code. It reimplemented the identification engine — topologies, the
continuous state-space, **exact discretization by matrix exponential**, an
**L-BFGS-B calibration loop in log-parameter space**, the error metrics and the BIC
selection criterion. It then did the analysis that matters scientifically: a
**multi-start stability study** showing that the best-fitting two-mass basins are
*physically degenerate*, and a quantification of how the heat-loss level is **not
robust across calibrations** — which is why the product surfaces the twin's
structure and its uncertainty rather than a single false number. Codex also ported
the **operational-carbon and subsidy engines** (reproducing the reference figures —
1,727 tCO₂ over 30 years, €650,400 — under test), retrieved the building's **real
footprint from the IGN BD TOPO WFS**, and found and fixed the bugs surfaced during
verification. The repository ships **87 passing tests**.

**GPT-5.6** is used in **three places** — model **gpt-5.6-terra** (the `gpt-5.6`
alias routes to Sol; the low-latency variant is used for the live demo), all via the
OpenAI Chat Completions API. GPT-5.6 is what makes a correct-but-opaque engine
**usable by four trades and auditable**; it never computes an engineering value.

1. **The in-product guide** — `POST /api/chat` (`src/thermal_twin/llm_chat.py`). The
   **entire computed diagnosis** (building record, DPE, current cost/emissions, the
   heat-loss level and its direct-path share, the dated drift, the twin's structure
   and RMSE, every renovation scenario with €/CO₂/payback, subsidies, regulation,
   neighbours, uncertainties) is injected as system context, with a strict
   instruction to answer **only** from those values, to name the quantity each answer
   derives from, and to **refuse with an alternative** when a question leaves the
   scope. It explains, reformulates for non-experts, and handles unanticipated
   questions — **without producing a number**: every estimate shown under an answer
   comes from the deterministic engine. Truthfulness was audited against the payload
   (€38,634/yr current energy, €42,600 net cost and 12.3-yr payback of the
   recommended measure, €768,000 subsidised loan — all exact). *Why it matters:* this
   is the productivity thesis — four roles interrogate one source of truth in plain
   language, with no document handoff.

2. **Vision QA of the plan-reading** — `GET /api/verify-geometry`
   (`src/thermal_twin/llm_supervisor.py`). GPT-5.6 **looks at the footprint polygon**
   the PyMuPDF reader extracted and judges whether it is a plausible single-building
   outline or shows extraction artifacts (self-intersection, a captured title block,
   a degenerate blob). *Why it matters:* a classical CV reader cannot self-diagnose a
   bad extraction; GPT-5.6 is the QA safety net over an automated pipeline.

3. **Review of the optimization** — `GET /api/verify-selection`
   (`src/thermal_twin/llm_supervisor.py`). GPT-5.6 audits the RC structure-selection
   bench and gives an independent second opinion. On the reference run it
   **independently flagged the degeneracy** the engine warns about (an
   over-parameterised structure reaching a suspiciously low error; near-ties around
   5 °C). *Why it matters:* the identification is initialization-sensitive by nature;
   an LLM audit of that fragile step catches what a single automated rule can miss.

Uses 2 and 3 are grounded server-side QA capabilities (available as API endpoints);
they inform the diagnosis internally and never overwrite an engine number. Without an
`OPENAI_API_KEY`, all three degrade gracefully (the chat falls back to a deterministic
guide; the supervisors report `available: false`) — the app still runs end-to-end.

**What is *not* the models.** The numerical computation is classical, deterministic
code — the RC identification, the matrix-exponential simulation, the carbon, cost
and subsidy arithmetic, the dated-drift detection and the ROI ranking. It is tested
and reproducible; **the language model never computes a value shown as a figure.**
Codex built and verified that engine; GPT-5.6 makes it usable, explainable, and
self-auditing.

---

## License

MIT — see [LICENSE](LICENSE).
