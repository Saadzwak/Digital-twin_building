# Self-review — LLM-backed chat + floating widget

Date: 2026-07-19. Verified live (port 61740, `OPENAI_API_KEY` set,
model `gpt-5.6-terra`). 87 tests green, console clean, no horizontal overflow.

## Correction 1 — the chat calls the OpenAI API

`src/thermal_twin/llm_chat.py` replaces the keyword logic with a real call to the
OpenAI Chat Completions API (`gpt-5.6` → Sol, or `gpt-5.6-terra` for demo latency;
`OPENAI_CHAT_MODEL` overrides). The **entire computed payload** — building record,
DPE, current cost/emissions, heat-loss level and its direct-path share, dated
drift, twin structure + RMSE, every renovation scenario (€/CO₂/cost/grant/payback),
subsidies, regulation, neighbours, uncertainties, geometry status — is injected as
system context. The system prompt forbids inventing any number, requires each
answer to name the quantity it derives from, and requires an explicit refusal +
alternative when the question is out of scope.

Verified against the live API:
- **Anticipated** ("What does DPE F mean?") → grounded answer citing 324 kWhEP/m²,
  71 kgCO₂/m², the 2028 letting ban.
- **Reformulated** ("honestly how bad is this building… will it cost me a
  fortune?") → understood; answered with class F, €38,634/yr, the 96% direct-path
  finding.
- **Out of scope** ("Will interest rates go down next year?") → refusal + the
  closest answerable thing (the identified financing: Éco-PLS €768,000, CEE grant).
- **Unanticipated** ("If I only had money for one thing this year…") → useful
  answer from the ROI table (MV + air-sealing, 12.3-yr payback, €42,600 net).

**No invented numbers.** Every figure the model produced was cross-checked against
`/api/renovation`: current energy €38,634 ✓, MV net €42,600 / CEE €120,000 /
payback 12.3 ✓, Éco-PLS €768,000 ✓. All exact.

**Traceability preserved.** The natural-language text comes from the model, but the
numeric estimates rendered under the answer keep coming from the deterministic
engine (payload) — e.g. the heat-loss answer shows 63.35 W/°C tagged with its run
source `demo-live-…`. The model is never the source of a displayed estimate.

**Graceful fallback.** If `OPENAI_API_KEY` is absent, `llm_available()` is False,
`answer_llm()` returns None, and `/api/chat` serves the deterministic guide — no
crash. Verified directly (no key → deterministic DPE answer). The startup log
states which backend is active: `[chat] OpenAI LLM enabled — model gpt-5.6-terra`
or `[chat] OPENAI_API_KEY not set — chat falls back to the deterministic guide`.
The key is read only from the environment; it is written to no file.

## Correction 2 — the chat is a floating widget

The full-width sticky dock is gone. Now: a discreet **"◆ Guide" button bottom-right**
(always accessible on the dashboard), which opens a **bounded side panel** (390 px,
`min(74vh,640px)`) with an explicit **✕ close**, a **scrollable conversation
history** (user bubbles + answer cards), the **contextual suggestions inside the
panel**, and the input row. It floats over the bottom-right; the dashboard stays
readable (no horizontal overflow).

Verified live: FAB present and panel initially closed; opening shows role-aware
chips; two Q&A turns render in the scrollable history; **close → reopen preserves
the history** (5 messages before and after); the panel **stays open while
scrolling** and its suggestions **adapt to both the active role and the section in
view** (Owner/Operator/Engineering labels + chips, and "About the recommendations"
on scroll). Console clean throughout. Control-room styling (dark glass panel, cyan
accents) matches the dashboard.

## What remains imperfect
- The tracer estimates appear only when the deterministic engine recognises the
  same topic as the LLM answer (same query → same topic, so they align); for a
  purely novel question the model still cites the figure in prose (grounded by the
  injected exact value) but no separate estimate table is shown.
- Latency is ~1–2 s per answer with `gpt-5.6-terra` (fine for the demo); `gpt-5.6`
  (Sol) is available via `OPENAI_CHAT_MODEL` if higher quality is preferred over
  speed.
