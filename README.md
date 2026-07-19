<p align="center">
  <img src="assets/best_paper_award.png" alt="Best Paper Award — SASBE / BDT 2026, Cambridge" width="760">
</p>

# Thermal Twin — a physics world-model of a building, from a plan and a CSV

**Category: Work and productivity.** · Built by the corresponding author of the
peer-reviewed, **Best-Paper-awarded** method it implements
([see below](#built-on-peer-reviewed-award-winning-research)).

**For the French building sector** — owners / social landlords, engineering firms,
architects and operators — using public French databases: **BDNB** (national building
database), **ADEME DPE** (energy-performance diagnostics), and **IGN BD TOPO**
(geometry). An energy audit today costs thousands of euros, needs site visits, and
takes months — and the result travels as a PDF between the owner, the engineering
firm, the architect and the operator, each re-reading it from scratch. **Thermal Twin
turns a floor plan and one CSV of hourly measurements into a physics-constrained
digital twin of the building** — a *world model* that reproduces a year of real
thermal behaviour and can **simulate counterfactuals**: what the building *would
become* if its envelope changed. From that, it produces a costed renovation
decision (euros, CO₂, payback, eligible subsidies, regulation) and lets **four
trades read one source of truth** — no document handed off between them. A
GPT-5.6 guide explains any of it in plain language, grounded strictly on the
computed numbers.

---

## Built on peer-reviewed, award-winning research

The physics engine is not a hackathon approximation — it is a faithful
implementation of the project author's own **peer-reviewed method**:

> **Systematic xR+yC Structure Selection for RC-Based Building Digital Twins:
> Accuracy–Complexity Trade-Off and Practical Identifiability Considerations Under
> Real Operational Data** — S. El Babidi, S. Zoumehri, Z. Lafhaj, R. Zerrari,
> L. Ducoulombier. *Centrale Lille · Univ. Lille · CNRS, UMR 9013 – LaMcube, Lille,
> France.* **Selected for the Best Paper Award — SASBE / BDT 2026 (Cambridge).**
>
> 📄 Paper: [`paper_RC_structure_selection.pdf`](paper_RC_structure_selection.pdf) ·
> 🖥 Slides: [`presentation_SASBE_BDT_2026.pdf`](presentation_SASBE_BDT_2026.pdf)

The **19 RC (xR+yC) structures**, the accuracy–complexity trade-off, the BIC-based
selection, and the **practical-identifiability / degeneracy** analysis you find in
this repository *are* that method — implemented in
[`src/thermal_twin/rc_core.py`](src/thermal_twin/rc_core.py),
[`identification.py`](src/thermal_twin/identification.py) and
[`multistart_impl.py`](src/thermal_twin/multistart_impl.py), tested (**87 tests**),
and wrapped into a usable product. This is the angle: **a domain researcher turning
his own published, award-winning work into a working tool with Codex and GPT-5.6** —
an expert of the field putting these models to work, not a toy.

**Data provenance (open and real on both sides).** The thermal twin is identified on
real operational measurements from the **open PLEIAData dataset** (Martínez Ibarra,
González-Vidal & Skarmeta, *Nature Scientific Data*, 2023 —
📄 [`s41597-023-02023-3.pdf`](s41597-023-02023-3.pdf)): one year of hourly indoor and
outdoor temperature and heating for a real building. The renovation and decision layer
(cost, CO₂, subsidies, regulation, 3D map) is then contextualised on a real French
social-housing building, **98 Rue des Sarrazins, Wazemmes, Lille**, from its public
**BDNB / DPE** records. Nothing is fabricated.

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

## Run it & test it — step by step for judges (Python 3.12)

> ### 🔑 You need an OpenAI API key
> GPT-5.6 powers the guide **and** the two QA checks (plan-reading vision + optimization
> review). **Set your own `OPENAI_API_KEY`** to see them. Without a key the diagnosis
> still runs end-to-end — the chat falls back to a deterministic guide and the QA
> endpoints report `available: false` — but the GPT-5.6 features are off. The public
> repo intentionally contains **no key**.

### 1 · Install (one command)
```bash
python -m pip install -r requirements.txt
```
Installs `fastapi uvicorn numpy pandas scipy PyMuPDF`. No database, no build step, no
account. (Python **3.12** recommended.)

### 2 · Add your OpenAI API key
```bash
# macOS / Linux
export OPENAI_API_KEY="sk-…your key…"
export OPENAI_CHAT_MODEL="gpt-5.6-terra"      # optional (this is the default)

# Windows PowerShell
$env:OPENAI_API_KEY = "sk-…your key…"
$env:OPENAI_CHAT_MODEL = "gpt-5.6-terra"
```

### 3 · Launch
```bash
cd webapp
python -m uvicorn server:app --port 61740
```
On startup you should see **`[chat] OpenAI LLM enabled — model gpt-5.6-terra`** (or the
fallback line if you skipped step 2). Open **http://localhost:61740/** in a real
desktop browser (Chrome / Edge / Firefox, WebGL on for the 3D building).

### 4 · Test it — two ways, both from files already in the repo

**Path A · one-click demo (fastest).** On the landing page click
**“▶ Run the demo diagnosis.”** It runs on two real inputs already committed here — the
2D floor plan [`Edificio PLEIADES (planta baja).pdf`](Edificio%20PLEIADES%20%28planta%20baja%29.pdf)
and one year of hourly measurements
[`data/processed/hourly_reference.csv`](data/processed/hourly_reference.csv):
1. Watch the live run — the structure counter climbs **1 → 19** as it searches the
   physical model space (~34 s), the RC schematic reconfigures, the 3D building reveals.
2. Click **“Continue to the dashboard.”**
3. **01 The building** — the real record (DPE class F, current bill and emissions, all computed).
4. **Switch roles** in the top bar (**Owner / Engineering / Architect / Operator**): the
   page visibly reorganises around each trade; “The building” stays first for everyone.
5. **Drag to rotate / scroll to zoom** the 3D building — a real **IGN BD TOPO** footprint
   (with setbacks) at real height, among its real neighbours. *(WebGL off → it falls back
   to a real IGN-ortho map, never blank.)*
6. Scroll to **04 The decision** — renovation scenarios ranked by payback (€, CO₂, grants).
7. Open the **“◆ Guide”** bottom-right (this is **GPT-5.6**) and ask e.g.
   *“honestly, how bad is this building and will it cost me a fortune?”*, then
   *“will interest rates go down next year?”* — it **refuses and offers the closest
   answerable thing**, and never invents a number.

**Path B · upload the sample data yourself.** On the landing page choose
**“Analyze my files,”** pick the CSV
[`data/processed/hourly_reference.csv`](data/processed/hourly_reference.csv)
(columns `Date, Tin, Tout, Qhvac_W_A`), optionally drop the 2D plan
[`Edificio PLEIADES (planta baja).pdf`](Edificio%20PLEIADES%20%28planta%20baja%29.pdf),
then click **Analyze**. This runs the **full live pipeline** (not a replay): it reads the
2D plan server-side to build the geometry and identifies the twin on your CSV. To try
another building, upload any CSV with the same four columns.

### 5 · GPT-5.6 QA checks (evidence — needs the key)
```bash
curl http://localhost:61740/api/verify-geometry     # GPT-5.6 VISION: verifies the plan-reading (the extracted footprint)
curl http://localhost:61740/api/verify-selection    # GPT-5.6: reviews the model-selection optimization
```

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
repository's **[Releases](https://github.com/Saadzwak/Digital-twin_building/releases)**
page (it is too large for the git repo).
To reproduce the processing from scratch, download it, place `Data_Nature.zip` at the
repo root, and the ingestion (`src/thermal_twin/reference_ingestion.py`) will extract
and rebuild the processed file.

---

## Architecture

- **Backend** — FastAPI ([`webapp/server.py`](webapp/server.py)) serving a vanilla-JS
  ES-module SPA ([`webapp/static/`](webapp/static)), streaming the live run as NDJSON.
  Every JSON response is sanitized (no NaN/Inf reaches the client).
- **Identification engine** ([`src/thermal_twin/`](src/thermal_twin)) — 19 RC
  (resistance–capacitance) network topologies; continuous state-space with **exact
  discretization by matrix exponential** ([`rc_core.py`](src/thermal_twin/rc_core.py));
  **L-BFGS-B calibration in log-parameter space**
  ([`identification.py`](src/thermal_twin/identification.py),
  [`multistart_impl.py`](src/thermal_twin/multistart_impl.py)); metrics + **BIC**
  model selection.
- **Renovation engine** ([`renovation.py`](src/thermal_twin/renovation.py) +
  [`data/fdes_static.json`](data/fdes_static.json)) — deterministic operational +
  embodied carbon, cost, and eligible-subsidy computation → the ROI decision table.
- **Real 3D geometry** ([`building_3d.py`](src/thermal_twin/building_3d.py)) — building
  footprints fetched from the **IGN BD TOPO WFS** (public mapping service), cached;
  rendered with MapLibre GL + deck.gl over IGN ortho tiles, with a static-tile fallback.
- **GPT-5.6 layer** — the grounded guide
  ([`llm_chat.py`](src/thermal_twin/llm_chat.py)) plus two QA supervisors
  ([`llm_supervisor.py`](src/thermal_twin/llm_supervisor.py)): a vision check of the
  plan-reading and a review of the structure-selection optimization. See "How Codex
  and GPT-5.6 were used" below.

Repo layout (essentials): [`webapp/`](webapp) (product), [`src/thermal_twin/`](src/thermal_twin)
(engine), [`tests/`](tests) (87 tests), [`data/`](data) (sample input + carbon factors),
[`runs/geometry/`](runs/geometry) & [`runs/demo/reference/`](runs/demo/reference)
(committed caches so it runs offline), [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)
(demo shoot pack).

---

## How Codex and GPT-5.6 were used

> **In one line:** **Codex** compressed weeks of research-code archaeology and
> reimplementation into a **tested** engine, and **GPT-5.6 — including its vision —**
> turned that engine into a tool four trades can actually use and audit. A domain
> researcher shipped a working product in days, not months, because of these two.

**Codex — the accelerator.** It implemented and tested the scientific core — the
author's own published method
([`paper_RC_structure_selection.pdf`](paper_RC_structure_selection.pdf), above).
Working from the paper and the research notebook, it re-specified the pipeline into a
tested engine **in a fraction of the time a from-scratch reimplementation would
take**: it extracted the **19 xR+yC connectivities**, the simulation protocol
and the data pipeline, and listed the divergences it found between the published
method and the notebook code. It reimplemented the identification engine — topologies, the
continuous state-space, **exact discretization by matrix exponential**, an
**L-BFGS-B calibration loop in log-parameter space**, the error metrics and the BIC
selection criterion. It then did the analysis that matters scientifically: a
**multi-start stability study** showing that the best-fitting two-mass basins are
*physically degenerate*, and a quantification of how the heat-loss level is **not
robust across calibrations** — the practical-identifiability result the paper
formalises, and why the product surfaces the twin's structure and its uncertainty
rather than a single false number. Codex also ported the **operational-carbon and
subsidy engines** ([`renovation.py`](src/thermal_twin/renovation.py) +
[`data/fdes_static.json`](data/fdes_static.json), reproducing the reference figures —
1,727 tCO₂ over 30 years, €650,400 — under test), retrieved the building's **real
footprint from the IGN BD TOPO WFS** ([`building_3d.py`](src/thermal_twin/building_3d.py)),
and found and fixed the bugs surfaced during verification. The repository ships
**87 passing tests**.

**GPT-5.6** is used in **three places** — model **gpt-5.6-terra** (the `gpt-5.6`
alias routes to Sol; the low-latency variant is used for the live demo), all via the
OpenAI Chat Completions API. GPT-5.6 is what makes a correct-but-opaque engine
**usable by four trades and auditable** — from plain-language answers to
**reading the floor plan with vision** — while it never computes an engineering value.

1. **The in-product guide** — `POST /api/chat` ([`src/thermal_twin/llm_chat.py`](src/thermal_twin/llm_chat.py)). The
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
   ([`src/thermal_twin/llm_supervisor.py`](src/thermal_twin/llm_supervisor.py)). GPT-5.6 **looks at the footprint polygon**
   the PyMuPDF reader extracted and judges whether it is a plausible single-building
   outline or shows extraction artifacts (self-intersection, a captured title block,
   a degenerate blob). *Why it matters:* a classical CV reader cannot self-diagnose a
   bad extraction; GPT-5.6 is the QA safety net over an automated pipeline.

3. **Review of the optimization** — `GET /api/verify-selection`
   ([`src/thermal_twin/llm_supervisor.py`](src/thermal_twin/llm_supervisor.py)). GPT-5.6 audits the RC structure-selection
   bench and gives an independent second opinion. On the reference run it
   **independently flagged the degeneracy** the engine warns about (an
   over-parameterised structure reaching a suspiciously low error; near-ties around
   5 °C). *Why it matters:* the identification is initialization-sensitive by nature;
   an LLM audit of that fragile step catches what a single automated rule can miss.

Without an `OPENAI_API_KEY`, all three degrade gracefully (the chat falls back to a
deterministic guide; the supervisors report `available: false`) — the app still runs
end-to-end.

**What is *not* the models.** The numerical computation is classical, deterministic
code — the RC identification, the matrix-exponential simulation, the carbon, cost
and subsidy arithmetic, the dated-drift detection and the ROI ranking. It is tested
and reproducible; **the language model never computes a value shown as a figure.**
Codex built and verified that engine; GPT-5.6 makes it usable, explainable, and
self-auditing.

---

## License

MIT — see [LICENSE](LICENSE).
