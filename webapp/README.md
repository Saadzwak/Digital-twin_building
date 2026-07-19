# Web product (`webapp/`)

FastAPI backend (`server.py`) + a vanilla-JS ES-module SPA (`static/`) that serves
the Thermal Twin experience: landing → live diagnosis run → onboarding → dashboard
(building, digital twin, recommendations, decision) with a role selector, a real 3D
building on an IGN map, and a GPT-5.6 guide.

Run it from the repository root instructions in the top-level [README](../README.md):

```bash
cd webapp
python -m uvicorn server:app --port 61740
# open http://localhost:61740/
```

Key endpoints: `/`, `/api/geometry`, `/api/topologies`, `/api/buildings-3d`,
`/api/run/reference` (NDJSON stream), `/api/run/upload`, `/api/payload`,
`/api/drift`, `/api/renovation`, `/api/interpretation`, `/api/chat`.

The live diagnosis view replays a real pre-computed run at an accelerated cadence
(the honest fast path for a demo); uploaded CSVs always run the pipeline live. The
GPT-5.6 chat uses `OPENAI_API_KEY` when set, and falls back to a deterministic
guide otherwise. See the top-level README for setup, testing, and the Codex /
GPT-5.6 usage details.
