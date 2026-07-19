# Demo shoot pack — Thermal Twin (< 3 min)

Everything below is calibrated for a single continuous screen-recording, narrated
live. Total target: **~2 min 50 s**. The platform is at `http://127.0.0.1:61740/`.

---

## 0. What to have ready before you hit record

**Launch command** (paste your own key — it is read only from the environment,
never stored in a file):

```
cd webapp
OPENAI_API_KEY=<your-openai-api-key>  OPENAI_CHAT_MODEL=gpt-5.6-terra  python -m uvicorn server:app --port 61740
```

Wait for the log line: `[chat] OpenAI LLM enabled — model gpt-5.6-terra`. If you
see `OPENAI_API_KEY not set …` instead, the chat will still work but on the
deterministic fallback — stop and re-export the key.

**Browser state before recording**
- Open `http://127.0.0.1:61740/` once, **before** filming, so tiles/CDN warm up,
  then reload to the clean landing page and leave it there.
- Use a real desktop browser (Chrome/Edge/Firefox), window ~1280×800 or larger.
  On a real browser the 3D building paints; if WebGL is disabled it falls back to a
  real IGN-ortho map (never blank) — but for the shoot you want the 3D, so confirm
  WebGL is on (visit `chrome://gpu` once if unsure).
- Close other tabs; hide bookmarks bar; set OS "Do Not Disturb".
- Have the chat questions copy-paste ready (below) so you don't fumble typing.

**One rehearsal pass.** Run the whole thing once end-to-end before the real take —
the execution is a paced ~34 s and you want your Message-1 narration to land inside it.

---

## 1. Second-by-second storyboard

| Time | On screen | You do | You say (see §2) |
|---|---|---|---|
| 0:00–0:10 | Landing page: "98 Rue des Sarrazins", upload zone + demo button | Nothing; let it sit | Hook + Message 2 (the problem) |
| 0:10–0:14 | — | **Click "▶ Run the demo diagnosis"** | "Watch what one plan and one CSV give us." |
| 0:14–0:48 | Execution view: STRUCTURE n/19 counting up, RC topology animating, building revealing, elapsed clock | Nothing; let it run | **Message 1 (world model)** — full |
| 0:48–0:55 | Onboarding: "what we'd need to go further" | **Click "Continue to the dashboard"** | "It even tells us what it doesn't yet know." |
| 0:55–1:12 | Dashboard, **01 The building** (identity card + map + DPE / bill / emissions) | Slow scroll a touch | One real building, real public record |
| 1:12–1:38 | Role bar at top | **Click Architect → Operator → Engineering → back to Owner** | **Message 2 (four readings, one source)** |
| 1:38–2:00 | 3D building on the map | **Drag to rotate, scroll to zoom once** | The real building, its real shape + neighbourhood |
| 2:00–2:12 | Drift chart + **04 The decision** ROI table | Scroll to the ROI table | **Message 1 payoff** (counterfactuals → costed actions) |
| 2:12–2:40 | Chat widget | **Click "◆ Guide"**, send Q1, then Q2 | **Message 3 — GPT-5.6** (spoken while it answers) |
| 2:40–2:55 | Dashboard (let it rest, chat open) | Nothing | **Message 3 — Codex** + closing line |

Chat questions (copy-paste):
- **Q1 (reformulated):** `honestly, how bad is this building and will it cost me a fortune?`
- **Q2 (out of scope):** `will interest rates go down next year?`

---

## 2. Narration script (English, ~460 words, ~2:50 at a calm pace)

> **[0:00 — Landing]**
> "An energy audit of a building today costs thousands of euros, needs site
> visits, and takes months. The result travels as a PDF between the owner, the
> engineering firm, the architect and the operator — each re-reading it from
> scratch. Here's the same job from a floor plan and one CSV of measurements."

> **[0:12 — click Run]**
> "No new sensors. Three signals — indoor temperature, outdoor temperature,
> heating — and a plan."

> **[0:15 — execution running — MESSAGE 1]**
> "What's running now is the system learning a *world model* of this building.
> It searches nineteen physical structures — resistance-capacitance networks —
> and identifies the one whose internal state reproduces a year of real thermal
> behaviour. From that model it can simulate counterfactuals: what this building
> *would become* if the envelope changed. Very little data, no labels, and yet a
> model that predicts the consequences of an action. What makes it different from
> a world model learned by a neural network is that it's constrained by physics —
> so it's identifiable from a few thousand hours of one building, where a learned
> model would need thousands of episodes."

> **[0:48 — onboarding → click Continue]**
> "It's also honest about its limits — it lists what it would need to go further."

> **[0:55 — dashboard, The building]**
> "One real building: 98 Rue des Sarrazins in Lille, from the public building and
> energy-performance registries. Class F — an energy sieve — with its current
> bill and emissions computed, not guessed."

> **[1:12 — roles — MESSAGE 2]**
> "Now the same diagnosis, four readings. Owner: the return on the works.
> Architect: the building, its constraints, the options. Operator: what changed
> and what to inspect. Engineer: does the model hold. Nothing is recomputed and
> nothing is hidden — the sections just reorder around each role. Four trades read
> one source of truth, with no document handed off between them."

> **[1:38 — 3D building + zoom]**
> "This is the real footprint, its real shape and height from the national mapping
> service, in its real neighbourhood."

> **[2:00 — ROI table]**
> "And this is the payoff of the world model: every intervention here is a
> simulated counterfactual, costed — euros, CO₂, payback — ranked for a decision."

> **[2:12 — chat, send Q1, then Q2 — MESSAGE 3 / GPT-5.6]**
> "The guide is GPT-5.6. The entire computed diagnosis is injected as its context,
> and it's told to answer only from those numbers, to name the quantity each answer
> comes from, and to refuse when a question leaves the scope — like this one, where
> it declines and offers what it *can* answer. It phrases and reformulates; it never
> invents a figure — every number under the answer still comes from the computation."

> **[2:40 — closing — MESSAGE 3 / Codex]**
> "And the engine behind it was reverse-engineered and rebuilt with Codex — the
> research notebook re-specified, the identification model reimplemented and tested,
> the carbon and subsidy engines ported, the real geometry pulled from the mapping
> API — eighty-seven tests green. A slow, paper-bound process, turned into minutes."

---

## 3. Moments not to miss (and why)

1. **The structure counter climbing 1→19 during execution.** This is the visible
   proof that a real search over physical models is happening, not a canned
   animation. Keep it on screen while you deliver Message 1.
2. **The role bar visibly reordering the page.** Click the roles slowly enough that
   the reorder is legible — this is the "one source of truth, four trades" claim made
   concrete. It's the strongest Work-and-productivity-track moment.
3. **The 3D building rotating.** One clean drag + one zoom. It proves the geometry is
   real (a jagged footprint with setbacks, neighbours around it), not a box.
4. **The refusal in chat.** The out-of-scope question refusing *and* offering an
   alternative is what separates a grounded product from a chatbot. Don't cut it.
5. **"eighty-seven tests green."** Say the number; it signals the engine is verified,
   not a demo prop.

---

## 4. Pitfalls — what drags, what may load badly, what not to show

- **The execution is ~34 s.** Do **not** wait through it silently — Message 1 is
  written to fill exactly that window. If you're over time in rehearsal, you can cut
  from ~0:35 (jump once the counter passes ~14/19); never cut before the counter is
  visibly climbing.
- **First map load can be slow** (IGN tiles + CDN). That's why you warm the browser
  before recording. If the 3D still hasn't painted after a few seconds on the day,
  it will fall back to the flat ortho map — fine, but you lose the rotate shot, so
  warm it up first and confirm.
- **Don't open the Methodology / Engineering deep panel on camera.** It's honest but
  dense (RC bench table, bootstrap, reproduction verdict) and reads as clutter in a
  90-second-per-message budget. Mention "does the model hold" and move on.
- **Don't type slowly in the chat.** Paste Q1/Q2. GPT-5.6-terra answers in ~1–2 s;
  if the network is slow it can take ~5 s — paste, then talk over the wait.
- **Don't show the terminal** (the launch command contains your key). Start from the
  browser already open.
- **One-take safety:** if the chat is mid-answer when you reach the close, keep
  talking — the answer lands within a couple of seconds and the "…" placeholder is
  brief.

---

## 5. Devpost — Codex & GPT-5.6 usage (paste-ready, factually exact)

> **How we used Codex and GPT-5.6.** The scientific core of this project was
> reverse-engineered and rebuilt with **Codex**. Codex read a research notebook on
> RC (resistance–capacitance) thermal models and re-specified it into a tested
> engine: it extracted the **19 network connectivities**, the simulation protocol
> and the data pipeline, and listed the divergences it found between the published
> article and the notebook code. It reimplemented the identification engine —
> topologies, the continuous state-space, **exact discretization by matrix
> exponential**, an **L-BFGS-B calibration loop in log-parameter space**, the error
> metrics and the BIC model-selection criterion. It then did the analysis that
> matters scientifically: a **multi-start stability study** showing that the
> best-fitting 4R3C basins are *physically degenerate*, and a quantification of how
> the heat-loss level is **not robust across calibrations** — which is why the
> product surfaces the twin's structure and its uncertainty rather than a single
> false number. Codex also ported the **operational-carbon and subsidy engines**
> (reproducing the reference figures — 1,727 tCO₂ over 30 years, €650,400 — under
> test), retrieved the building's **real footprint from the IGN BD TOPO WFS**, and
> found and fixed the bugs surfaced during verification. The repository ships **87
> passing tests** across ingestion, identification, the reproduction verdict, the
> carbon engine, the web layer and the chat.
>
> **GPT-5.6** powers the in-product guide. The model is **gpt-5.6-terra** (the
> `gpt-5.6` alias routes to Sol; we use the low-latency variant for the live demo),
> called server-side in `/api/chat` (`src/thermal_twin/llm_chat.py`). The **entire
> computed diagnosis** — building record, DPE, current cost and emissions, the
> heat-loss level and its direct-path share, the dated drift, the twin's structure
> and RMSE, every renovation scenario with euros / CO₂ / payback, subsidies,
> regulation, neighbours and uncertainties — is injected as system context, with a
> strict instruction to answer **only** from those values, to name the quantity each
> answer derives from, and to refuse (with the closest answerable alternative) when a
> question leaves the scope. It **explains, reformulates for non-experts, and handles
> unanticipated questions**, but it **does not produce the numbers**: every estimate
> shown under an answer comes from the deterministic engine, not the model. We audited
> its truthfulness by cross-checking cited figures against the computed payload — e.g.
> €38,634/yr current energy, the €42,600 net cost and 12.3-year payback of the
> recommended measure, the €768,000 subsidised loan — all exact.
>
> **What is *not* the models.** The numerical computation is classical, deterministic
> code — the RC identification, the matrix-exponential simulation, the carbon, cost
> and subsidy arithmetic, the dated-drift detection and the ROI ranking. It is tested
> and reproducible; the language model never computes a value that is displayed as a
> figure. Codex built and verified that engine; GPT-5.6 makes it explainable.

---

## 6. One-line relaunch (for your notes)

```
cd webapp && OPENAI_API_KEY=<your-key> OPENAI_CHAT_MODEL=gpt-5.6-terra python -m uvicorn server:app --port 61740
```
Without the key it still launches; the chat falls back to the deterministic guide.
