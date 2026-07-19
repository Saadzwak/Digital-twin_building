import { Building } from "./building.js";
import { Topology } from "./topology.js";
import { ComplexityScatter, renderDriftTimeline, renderScenarioBars } from "./charts.js";
import { renderNeighbourhoodMap, DPE_COLOR } from "./map.js";

const money = (v) => "€" + Math.round(v).toLocaleString("en-US");
const tSep = (v) => Math.round(v).toLocaleString("en-US");

const $ = (s) => document.querySelector(s);
const state = { source: "reference", payload: null, topologies: null, geometry: null };

const building = new Building($("#exec-building"));
const topo = new Topology($("#exec-topo"));
const scatter = new ComplexityScatter($("#exec-scatter"));

function show(id) {
  for (const s of document.querySelectorAll("#app > section")) s.classList.add("hidden");
  const el = $(id); el.classList.remove("hidden"); el.classList.add("fade-in");
  window.scrollTo(0, 0);
  if (id !== "#screen-dash") hideGuide();
}

async function boot() {
  const [g, t] = await Promise.all([
    fetch("/api/geometry").then(r => r.json()),
    fetch("/api/topologies").then(r => r.json()),
  ]);
  state.geometry = g; state.topologies = t;
  building.setModel(g.footprint, g.floors);
  $("#exec-honesty").textContent = g.honesty_note || "";
}
boot();

// ---- landing interactions ----
for (const p of document.querySelectorAll(".pick")) {
  p.addEventListener("click", (e) => { e.preventDefault(); $("#" + p.dataset.for).click(); });
}
$("#file-csv").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (f) {
    $("#dz-csv").classList.add("filled");
    $("#btn-analyze-upload").disabled = false; $("#btn-analyze-upload").style.opacity = 1;
    $("#upload-status").textContent = f.name;
  }
});
$("#file-pdf").addEventListener("change", (e) => {
  if (e.target.files.length) $("#dz-pdf").classList.add("filled");
});

$("#btn-demo").addEventListener("click", () => startRun("reference"));
$("#btn-analyze-upload").addEventListener("click", () => {
  const f = $("#file-csv").files[0]; if (!f) return;
  startRun("upload", f);
});

// ---- execution stream ----
let execT0 = 0;
function stageLine(text, cls) {
  const div = document.createElement("div");
  div.className = "stage-line " + (cls || "");
  div.innerHTML = `<span class="ic">${cls === "done" ? "✓" : "•"}</span><span>${text}</span>`;
  $("#exec-stages").prepend(div);
}

async function startRun(source, file) {
  state.source = source;
  show("#screen-exec");
  scatter.reset();
  $("#exec-stages").innerHTML = "";
  building.setModel(state.geometry.footprint, state.geometry.floors);
  building.setIntensity(0.35);
  building.setRevealProgress(0);
  execT0 = performance.now();
  const tick = setInterval(() => { $("#exec-elapsed").textContent = ((performance.now() - execT0) / 1000).toFixed(0) + " s"; }, 200);

  let url = "/api/run/reference", opts = { method: "POST" };
  if (source === "upload") {
    const fd = new FormData(); fd.append("file", file);
    url = "/api/run/upload"; opts = { method: "POST", body: fd };
  }
  let structuresTotal = 19, structuresDone = 0, fitsDone = 0, fitsTotal = 57;
  const resp = await fetch(url, opts);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim(); buffer = buffer.slice(nl + 1);
      if (!line) continue;
      let ev; try { ev = JSON.parse(line); } catch { continue; }
      handleEvent(ev, { setStructuresTotal: (n) => structuresTotal = n, setFitsTotal: (n) => fitsTotal = n });
      if (ev.kind === "fit_done") { fitsDone++; $("#exec-progress").style.width = Math.min(100, fitsDone / fitsTotal * 100) + "%"; }
      if (ev.kind === "structure_done") {
        structuresDone++;
        $("#exec-counter").innerHTML = `STRUCTURE ${structuresDone}/${structuresTotal} <small id="exec-substep">· ${ev.model.replace(/_/g, " ")}</small>`;
        building.setRevealProgress(structuresDone / structuresTotal);
      }
    }
  }
  clearInterval(tick);
  await afterRun();
}

function handleEvent(ev, ctl) {
  switch (ev.kind) {
    case "mode":
      $("#exec-mode").textContent = ev.mode === "live" ? "LIVE REAL COMPUTATION" : "REAL COMPUTATION";
      if (ev.note) stageLine(ev.note, "run");
      break;
    case "plan":
      stageLine(`Floor plan read${ev.detected_scale ? " · scale " + ev.detected_scale : ""}`, "done");
      break;
    case "data_summary":
      stageLine(`Data · ${ev.rows} h · calibration ${ev.splits.train} / check ${ev.splits.validation} / test ${ev.splits.test}`, "done");
      break;
    case "stage":
      if (ev.stage === "bank" && ev.status === "start") { ctl.setStructuresTotal(ev.structures.length); ctl.setFitsTotal(ev.structures.length * ev.n_starts); }
      if (ev.status === "start") stageLine(stageLabel(ev.stage), "run");
      break;
    case "fit_start": {
      const g = state.topologies[ev.model];
      if (g) { topo.render(g); $("#topo-name").textContent = ev.model.replace(/_/g, " "); }
      $("#exec-substep").textContent = `· start ${ev.start_id}/${ev.n_starts}`;
      building.pulseAllFloors(0.25 + 0.5 * ((ev.start_id * 7) % 10) / 10);
      break;
    }
    case "structure_done":
      scatter.add({ name: ev.model, x: ev.n_parameters, y: ev.val_rmse });
      break;
    case "selection":
      scatter.setSelected(ev.model);
      if (ev.article_reference) scatter.setReference({ x: ev.article_reference.n_parameters, y: ev.article_reference.val_rmse });
      stageLine(`Selection · ${ev.model.replace(/_/g, " ")}`, "done");
      break;
    case "twin":
      building.setIntensity(0.62);
      building.settleFloors();
      stageLine(`Twin · ${ev.model.replace(/_/g, " ")} · check ${ev.val_rmse.toFixed(2)} °C`, "done");
      break;
    case "drift_done":
      stageLine(`Dated drift · ${ev.structural_switch ? ev.structural_switch.date : "none"}`, "done");
      break;
    case "scenario_done":
      stageLine(`Scenario · ${ev.title}`, "done");
      break;
    case "error":
      stageLine("ERROR · " + ev.message, "run");
      break;
  }
}
function stageLabel(s) {
  return { plans: "Reading plans…", data: "Preparing data…", bank: "Structure bench…", drift: "Drift diagnosis…", scenarios: "Intervention scenarios…" }[s] || s;
}

async function afterRun() {
  state.payload = await fetch(`/api/payload?source=${state.source}`).then(r => r.json());
  $("#run-source").textContent = "run " + (state.payload.run_source || "");
  renderOnboarding();
  show("#screen-onboarding");
}

// ---- onboarding ----
function renderOnboarding() {
  const box = $("#onboarding-questions");
  box.innerHTML = "";
  (state.payload.onboarding_questions || []).forEach((q, i) => {
    const row = document.createElement("div");
    row.style.cssText = "padding:12px 0;border-bottom:1px solid var(--line)";
    row.innerHTML = `<div style="color:var(--ink);font-size:14px;margin-bottom:4px">${i + 1}. ${q.prompt}</div>
      <div class="faint" style="font-size:12px;margin-bottom:8px">${q.why_needed}</div>
      <div class="chat-suggest">
        <span class="chip" data-q="${i}" data-v="known">I can provide it</span>
        <span class="chip" data-q="${i}" data-v="unknown" style="border-color:var(--cyan)">Unknown for now</span>
      </div>`;
    box.appendChild(row);
  });
  box.querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => {
    c.parentElement.querySelectorAll(".chip").forEach(x => x.style.background = "rgba(55,224,200,.05)");
    c.style.background = "rgba(55,224,200,.22)";
  }));
}
$("#btn-onboarding-done").addEventListener("click", () => { renderDashboard(); show("#screen-dash"); });

// ---- dashboard ----
async function renderDashboard() {
  const p = state.payload;
  const dash = $("#screen-dash");
  const sw = p.drift.structural_switch;
  const hl = p.indicators.heat_loss;

  const [reno, interp] = await Promise.all([
    fetch("/api/renovation").then(r => r.json()),
    fetch(`/api/interpretation?source=${state.source}`).then(r => r.json()),
  ]);
  state.reno = reno;
  const b = reno.building, k = reno.kpis;
  const best = reno.scenarios[0];

  const verdict = sw
    ? `From <span class="hot">${enDate(sw.date)}</span>, the building stops behaving like the calibrated model — the gap is <span class="hot">structural</span>, not noise.`
    : `Over the measured year, the building stays within its <span class="cool">calibrated behaviour band</span>.`;

  const verdictStmt = sw
    ? `From <span class="hot">${enDate(sw.date)}</span>, this building stops behaving like its calibrated model — a <span class="hot">structural</span> change, not noise.`
    : `Over the measured year, the building stays within its <span class="cool">calibrated behaviour band</span>.`;
  const heatShare = hl.direct_path_share;

  dash.innerHTML = `
    <div class="dash-intro">
      <div class="eyebrow">Thermal diagnosis &amp; renovation</div>
      <h1 class="dash-h1">${b.address}, ${b.district}</h1>
      <p class="dash-sub">From one year of measurements to a costed renovation decision — every figure computed or from real data.</p>
      <div class="role-bar">
        <div class="role-tabs" id="role-tabs">
          <button class="role-tab" data-role="owner"><span class="rt-name">Owner</span><span class="rt-who">landlord / decision</span></button>
          <button class="role-tab" data-role="engineering"><span class="rt-name">Engineering</span><span class="rt-who">thermal / model</span></button>
          <button class="role-tab" data-role="architect"><span class="rt-name">Architect</span><span class="rt-who">design / constraints</span></button>
          <button class="role-tab" data-role="operator"><span class="rt-name">Operator</span><span class="rt-who">field / maintenance</span></button>
        </div>
        <div class="role-meta">
          <div class="role-question" id="role-question"></div>
          <div class="role-explain">One diagnosis, four readings — the same evidence reorganised for each role. Nothing is removed; non-priority sections just fold. No document handoff between actors.</div>
        </div>
      </div>
    </div>

    <div id="dash-sections">
    <!-- 01 THE BUILDING -->
    <section class="sec" data-sec="building">
      <div class="sec-head"><span class="sec-n">01</span><div><h2>The building</h2><div class="sec-sub">Who it is</div></div></div>
      <div class="sec-grid-map">
        <div class="panel"><div class="panel-b id-card">
          <div class="id-top">${dpeBadge(b.dpe_class)}<div>
            <div style="font-family:var(--display);font-size:20px">${b.type}, ${b.levels}</div>
            <div class="faint" style="font-size:12px">${b.city} · social landlord · RNB ${b.rnb_id}</div>
          </div></div>
          <div>
            <div class="id-row"><span class="k">Built</span><span class="v">${b.year}</span></div>
            <div class="id-row"><span class="k">Dwellings</span><span class="v">${b.dwellings}</span></div>
            <div class="id-row"><span class="k">Floor area</span><span class="v">${tSep(b.living_area_m2)} m² · ${tSep(b.footprint_m2)} m² footprint</span></div>
            <div class="id-row"><span class="k">Walls</span><span class="v">${b.wall_material}</span></div>
            <div class="id-row"><span class="k">Heating</span><span class="v">${b.heating}</span></div>
            <div class="id-row"><span class="k">Ventilation</span><span class="v">${b.ventilation}</span></div>
          </div>
        </div></div>
        <div class="panel map-wrap"><div id="dash-map" class="mapbox"></div></div>
      </div>
      <div class="stat-strip" style="margin-top:18px">
        ${stat("Energy rating", "DPE " + b.dpe_class, b.dpe_kwh_ep_m2_an + " kWh/m²/yr", "danger")}
        ${stat("Current energy", money(k.current_energy_eur_year) + "/yr", "theoretical, whole building", "hot")}
        ${stat("Current emissions", tSep(k.current_co2_t_year) + " tCO₂/yr", b.dpe_kg_co2_m2_an + " kgCO₂/m²/yr", "hot")}
      </div>
    </section>

    <!-- 02 THE DIGITAL TWIN -->
    <section class="sec" data-sec="twin">
      <div class="sec-head"><span class="sec-n">02</span><div><h2>The digital twin</h2><div class="sec-sub">What the measurements reveal</div></div></div>
      <div class="lead-stmt">${verdictStmt}</div>
      <div class="stat-strip">
        ${stat("Heat-loss level", hl.physically_readable ? Math.round(hl.value) + " W/°C" : "not readable", heatShare ? Math.round(heatShare*100) + "% via direct air path" : "whole-building", "cool")}
        ${stat("Responsiveness", p.indicators.response_time_hours != null ? "≈ " + Math.round(p.indicators.response_time_hours) + " h" : "—", "to most of a heating change", "cool")}
        ${stat("Behaviour change", sw ? enDate(sw.date) : "none", sw ? "drift from " + enDate(sw.onset_date) : "within band", sw ? "danger" : "cool")}
      </div>
      <div class="panel" style="margin-top:8px"><div class="panel-b">
        <div class="legend"><span><i class="swatch" style="background:#37e0c8"></i>measured</span><span><i class="swatch" style="background:#ffb020"></i>model expectation</span><span><i class="swatch" style="background:#ff4d5e"></i>break</span></div>
        <svg class="drift-svg" id="dash-drift"></svg>
        <svg class="drift-cum-svg" id="dash-drift-cum"></svg>
        <div class="scen-note">${p.drift.message}</div>
      </div></div>
      <div class="two-col" style="margin-top:16px">
        <div class="panel building-wrap" style="min-height:300px">
          <svg class="building-svg" id="dash-building" data-w="520" data-h="300" style="height:300px"></svg>
          <div class="honesty">Thermal massing coloured by the identified heat intensity. ${state.geometry.honesty_note}</div>
        </div>
        <div class="panel"><div class="panel-b">
          <div class="label eyebrow" style="color:var(--ink-faint)">What it means</div>
          <p style="margin:8px 0">${hl.sentence}</p>
          <p class="dim" style="font-size:13px;margin-top:10px">${p.indicators.cannot_distinguish_text}</p>
          ${hl.robustness_note ? `<div class="reliability" style="margin-top:8px">${hl.robustness_note}</div>` : ""}
        </div></div>
      </div>
      <h3 class="sub-head">What the physics suggests — leads, not conclusions</h3>
      <div class="leads">${(interp.leads || []).map(leadCard).join("") || '<div class="faint">No readable leads on this calibration.</div>'}</div>
    </section>

    <!-- 03 RECOMMENDATIONS -->
    <section class="sec" data-sec="reco">
      <div class="sec-head"><span class="sec-n">03</span><div><h2>Recommendations</h2><div class="sec-sub">What to do, and what it returns</div></div></div>
      <div class="reco-banner">
        <div><div class="r-title">Best first move: ${best.title}</div><div class="faint" style="font-size:12px;margin-top:2px">→ DPE ${best.target_class} · ${best.note}</div></div>
        <div class="r-metrics">
          <div class="rm hot"><div class="rv">${money(best.savings_eur_year)}</div><div class="rl">per year saved</div></div>
          <div class="rm cool"><div class="rv">${tSep(best.co2_avoided_t_year)}</div><div class="rl">tCO₂ per year</div></div>
          <div class="rm"><div class="rv">${best.payback_years} yr</div><div class="rl">payback</div></div>
        </div>
      </div>
      <div class="two-col">
        <div class="panel"><div class="panel-b">
          <div class="label eyebrow" style="color:var(--ink-faint)">Regulatory context</div>
          <div class="chips">${reno.regulation.map(regChip).join("")}</div>
        </div></div>
        <div class="panel"><div class="panel-b">
          <div class="label eyebrow" style="color:var(--ink-faint)">Eligible support schemes</div>
          ${aidesList(reno.aides)}
        </div></div>
      </div>
    </section>

    <!-- 04 THE DECISION -->
    <section class="sec" data-sec="decision">
      <div class="sec-head"><span class="sec-n">04</span><div><h2>The decision</h2><div class="sec-sub">Ranked by return on investment</div></div></div>
      <div class="panel"><div class="panel-b">
        ${renoTable(reno)}
        <div class="faint" style="font-size:11px;margin-top:12px">${reno.assumptions.map(a => "• " + a).join("<br>")}</div>
      </div></div>
    </section>

    <!-- 05 METHODOLOGY -->
    <section class="sec" data-sec="method">
      <div class="sec-head"><span class="sec-n">05</span><div><h2>Methodology</h2><div class="sec-sub">Full rigor, on demand</div></div></div>
      ${methodBlock(p, reno)}
    </section>
    </div>

    <div style="margin-top:40px"><button class="btn ghost" id="btn-home">← New analysis</button></div>
  `;

  // neighbourhood map (dynamic if the CDN loads cleanly, else the real static IGN tiles)
  await renderMap(b, reno.neighbors);

  // 3D thermal building coloured by drift intensity
  const dashBuilding = new Building($("#dash-building"));
  dashBuilding.setModel(state.geometry.footprint, state.geometry.floors);
  const driftIntensity = sw ? Math.min(0.85, 0.5 + Math.abs(sw.offset_from_calibrated_c) / 25) : 0.5;
  dashBuilding.setIntensity(driftIntensity);
  dashBuilding.settleFloors();
  state.dashBuilding = dashBuilding;

  const daily = (await fetch(`/api/drift?source=${state.source}`).then(r => r.json())).daily;
  renderDriftTimeline($("#dash-drift"), daily, p.drift);
  renderCumulative($("#dash-drift-cum"), daily);
  setupGuide();
  initRoleSections();
  applyRole("owner");  // default lens: the decision-maker's return-on-works reading
  window.addEventListener("resize", () => {
    dashBuilding.render();
    renderDriftTimeline($("#dash-drift"), daily, p.drift);
  });
}

// ---- dashboard sub-renderers ----
function dpeBadge(cls) {
  return `<span class="dpe-badge" style="background:${DPE_COLOR[cls] || '#8FA3B6'}">${cls}<small>DPE</small></span>`;
}
function fact(t) { return `<span class="fact">${t}</span>`; }

function renoTable(reno) {
  const rows = reno.scenarios.map((s, i) => `
    <tr class="${i === 0 ? 'reco' : ''}">
      <td>${i === 0 ? '★ ' : ''}${s.title}<div class="faint" style="font-size:10px">→ target DPE ${s.target_class}${i === 0 ? ' · recommended' : ''}</div></td>
      <td class="tabular">−${s.energy_saved_pct}%</td>
      <td class="tabular hot-t">${money(s.savings_eur_year)}/yr</td>
      <td class="tabular cool-t">${tSep(s.co2_avoided_t_year)} t/yr</td>
      <td class="tabular">${money(s.cost_eur)}</td>
      <td class="tabular">−${money(s.cee_grant_eur)}</td>
      <td class="tabular"><b>${s.payback_years} yr</b></td>
    </tr>`).join("");
  return `<div style="overflow-x:auto"><table class="reno-table">
    <tr><th>Renovation scenario</th><th>Energy</th><th>Savings</th><th>CO₂ avoided</th><th>Cost</th><th>CEE grant</th><th>Payback</th></tr>
    ${rows}
  </table></div>
  <div class="faint" style="font-size:11px;margin-top:6px">Deep retrofit (→B) matches the reference figures: ${tSep(reno.scenarios.find(s=>s.key==='deep_retrofit')?.co2_avoided_t_30y||0)} tCO₂ over 30 yr, ${money(reno.scenarios.find(s=>s.key==='deep_retrofit')?.cost_eur||0)}. All scenarios are carbon-virtuous over 30 years (bio-sourced materials).</div>`;
}

function regChip(c) {
  const tone = { danger: "chip-danger", warn: "chip-warn", success: "chip-success", info: "chip-info", muted: "chip-muted" }[c.tone] || "chip-info";
  return `<span class="reg-chip ${tone}" title="${c.detail}">${c.label}</span>`;
}
function aidesList(aides) {
  return `<div class="aides">${aides.map(a => `
    <div class="aide">
      <div><b>${a.name}</b> <span class="aide-kind ${a.kind}">${a.kind}</span></div>
      <div class="faint" style="font-size:11px">${a.condition} · ${a.source}</div>
      ${a.amount_eur ? `<div class="cool-t tabular">${money(a.amount_eur)}${a.kind === 'loan' ? ' (financing)' : ' grant'}</div>` : `<div class="faint" style="font-size:11px">amount project-specific</div>`}
    </div>`).join("")}</div>`;
}
function leadCard(l) {
  return `<div class="panel lead"><div class="panel-b">
    <div class="lead-title">${l.title}</div>
    <p style="margin:8px 0;font-size:13px">${l.reading}</p>
    <div class="lead-check"><span class="eyebrow" style="color:var(--amber)">Check first</span> ${l.check_first}</div>
  </div></div>`;
}

function stat(label, value, sub, cls) {
  return `<div class="panel stat ${cls || ""}">
    <div class="s-label">${label}</div>
    <div class="s-value">${value}</div>
    ${sub ? `<div class="s-sub">${sub}</div>` : ""}
  </div>`;
}

function renderCumulative(svg, daily) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const NS = "http://www.w3.org/2000/svg";
  const pts = (daily || []).filter(d => Number.isFinite(d.cumulative));
  if (!pts.length) return;
  const W = svg.clientWidth || 900, H = svg.clientHeight || 90, m = { l: 44, r: 16, t: 6, b: 16 };
  const times = pts.map(d => new Date(d.date).getTime());
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const vals = pts.map(d => d.cumulative);
  const y0 = Math.min(0, ...vals), y1 = Math.max(0, ...vals);
  const px = t => m.l + (t - t0) / (t1 - t0) * (W - m.l - m.r);
  const py = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  let d = `M ${px(times[0])} ${py(0)}`;
  pts.forEach(p => { d += ` L ${px(new Date(p.date).getTime())} ${py(p.cumulative)}`; });
  d += ` L ${px(times[times.length - 1])} ${py(0)} Z`;
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", d); path.setAttribute("fill", "rgba(255,77,94,.28)"); path.setAttribute("stroke", "#ff4d5e"); path.setAttribute("stroke-width", "1");
  svg.appendChild(path);
  const lab = document.createElementNS(NS, "text");
  lab.setAttribute("x", m.l); lab.setAttribute("y", 12); lab.setAttribute("fill", "#6b7d90"); lab.setAttribute("font-size", "10"); lab.setAttribute("font-family", "var(--mono)");
  lab.textContent = "CUMULATIVE GAP (°C·h)"; svg.appendChild(lab);
}

// ---- role lens: one diagnosis, four readings (reorganise, never recompute) ----
// Each role surfaces (expands, orders first) a subset of the SAME sections and
// folds the rest — nothing is removed, so every reader keeps full access.
const ROLES = {
  owner: {
    question: "Should I launch the works — and what's the return?",
    surface: ["reco", "decision", "building"], collapse: ["twin", "method"],
  },
  engineering: {
    question: "Does the model hold — and what does the measurement really say?",
    surface: ["twin", "building", "method"], collapse: ["reco", "decision"],
  },
  architect: {
    question: "What can I do here — and under what constraints?",
    surface: ["building", "reco", "decision"], collapse: ["twin", "method"],
  },
  operator: {
    question: "What changed — and what should I go inspect on site?",
    surface: ["twin", "building"], collapse: ["reco", "decision", "method"],
  },
};
const SEC_SUMMARY = {
  building: "Identity · map · DPE · current bill &amp; emissions",
  twin: "Heat-loss · responsiveness · dated drift · physical leads",
  reco: "Best first move · regulation · eligible subsidies",
  decision: "ROI table ranked by payback",
  method: "Identification, bench, accuracy, reproduction verdict",
};
const ROLE_GUIDE = {
  owner: { label: "Owner — return on the works", chips: [["Best payback?", "Which option has the best payback?"], ["What subsidies apply?", "What subsidies apply?"], ["What does the 2028 law require?", "What does the 2028 law require?"]] },
  engineering: { label: "Engineering — does the model hold", chips: [["How accurate is the twin?", "How accurate is the twin?"], ["When does it drift?", "When does the building drift?"], ["Heat-loss level?", "What is the heat-loss level?"]] },
  architect: { label: "Architect — options & constraints", chips: [["Best CO₂ retrofit?", "Which retrofit saves the most CO₂?"], ["2028 requirement?", "What does the 2028 law require?"], ["How do neighbours compare?", "How do the neighbours compare?"]] },
  operator: { label: "Operator — what to inspect", chips: [["When does it drift?", "When does the building drift?"], ["How responsive is it?", "How responsive is the building?"], ["Heat-loss level?", "What is the heat-loss level?"]] },
};

function initRoleSections() {
  // fold affordance: a chevron + one-line summary in every section header
  document.querySelectorAll("#dash-sections section[data-sec]").forEach(sec => {
    const head = sec.querySelector(".sec-head");
    if (!head || head.querySelector(".chev")) return;
    const chev = document.createElement("span");
    chev.className = "chev"; chev.textContent = "▾";
    head.appendChild(chev);
    const hint = document.createElement("div");
    hint.className = "collapsed-hint";
    hint.innerHTML = SEC_SUMMARY[sec.dataset.sec] || "";
    head.insertAdjacentElement("afterend", hint);
    head.addEventListener("click", () => sec.classList.toggle("collapsed"));
  });
  document.querySelectorAll("#role-tabs .role-tab").forEach(t => {
    t.addEventListener("click", () => applyRole(t.dataset.role));
  });
}
function applyRole(role) {
  const cfg = ROLES[role]; if (!cfg) return;
  state.role = role;
  document.querySelectorAll("#role-tabs .role-tab").forEach(t => t.classList.toggle("active", t.dataset.role === role));
  const q = $("#role-question"); if (q) q.textContent = cfg.question;
  // "The building" is the shared entry point: always first and always expanded,
  // whatever the role — you always know which building before anything else.
  const rest = [...cfg.surface, ...cfg.collapse].filter(k => k !== "building");
  const order = ["building", ...rest];
  order.forEach((key, i) => {
    const sec = document.querySelector(`#dash-sections section[data-sec="${key}"]`);
    if (!sec) return;
    sec.style.order = String(i);
    sec.classList.toggle("collapsed", key !== "building" && cfg.collapse.includes(key));
  });
  // Engineering reads the method in full: expand the methodology details for it.
  const methDetails = document.querySelector('#dash-sections section[data-sec="method"] details.method');
  if (methDetails && role === "engineering") methDetails.open = true;
  setRoleGuide(role);
}
function setRoleGuide(role) {
  const g = ROLE_GUIDE[role];
  if (!g || !$("#guide-chips")) return;
  _guideSection = "__role_" + role;  // distinct key so the next real scroll still refines
  $("#guide-ctx").textContent = g.label;
  $("#guide-chips").innerHTML = g.chips.map(c => `<span class="chip" data-q="${c[1]}">${c[0]}</span>`).join("");
  $("#guide-chips").querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => { openGuide(); askGuide(c.dataset.q); }));
}

// ---- chat guide (sticky dock, contextual suggestions) ----
const GUIDE_CTX = {
  building: { label: "About the building", chips: [["What does DPE F mean?", "What does DPE F mean?"], ["What is the current bill?", "What is the current energy bill?"], ["Who is this building?", "Who is this building?"]] },
  twin: { label: "About the diagnosis", chips: [["When does it drift?", "When does the building drift?"], ["Heat-loss level?", "What is the heat-loss level?"], ["How responsive is it?", "How responsive is the building?"]] },
  reco: { label: "About the recommendations", chips: [["Best CO₂ retrofit?", "Which retrofit saves the most CO₂?"], ["What subsidies apply?", "What subsidies apply?"], ["What does the 2028 law require?", "What does the 2028 law require?"]] },
  decision: { label: "About the decision", chips: [["Best payback?", "Which option has the best payback?"], ["Explain the table", "Explain the decision table"], ["Deep vs quick win?", "Deep retrofit versus quick win?"]] },
};
let _guideSection = "building";

function setupGuide() {
  document.body.classList.add("has-guide");
  let fab = $("#guide-fab");
  if (!fab) {
    fab = document.createElement("button");
    fab.id = "guide-fab";
    fab.title = "Ask the diagnostic guide";
    fab.innerHTML = `<span class="gf-ic">◆</span><span class="gf-lbl">Guide</span>`;
    document.getElementById("app").appendChild(fab);

    const panel = document.createElement("div");
    panel.id = "guide-panel";
    panel.className = "closed";
    panel.innerHTML = `
      <div class="gp-head">
        <div><div class="gp-title">Diagnostic guide</div><div class="gp-ctx" id="guide-ctx">Ask the guide</div></div>
        <button class="gp-close" id="guide-close" title="Close">✕</button>
      </div>
      <div class="gp-msgs" id="guide-msgs"></div>
      <div class="gp-foot">
        <div class="guide-chips" id="guide-chips"></div>
        <div class="guide-row">
          <input id="guide-input" placeholder="Ask about this building or its diagnosis…" autocomplete="off" />
          <button class="btn" id="guide-send">Ask</button>
        </div>
      </div>`;
    document.getElementById("app").appendChild(panel);

    fab.addEventListener("click", () => toggleGuide());
    $("#guide-close").addEventListener("click", () => closeGuide());
    $("#guide-send").addEventListener("click", () => askGuide($("#guide-input").value));
    $("#guide-input").addEventListener("keydown", (e) => { if (e.key === "Enter") askGuide($("#guide-input").value); });
  }
  fab.classList.remove("hidden");
  // Fresh dashboard session: clear history, start closed, seed with a welcome line.
  const msgs = $("#guide-msgs");
  msgs.innerHTML = `<div class="g-msg g-bot"><div class="answer-card"><div class="txt faint">Ask me anything about this building or its diagnosis — I answer from the computed figures, and I'll say so when something is outside what the measurements can show.</div></div></div>`;
  closeGuide();
  _guideSection = "__init__";
  updateGuideChips("building");
  // contextual chips follow whichever section is nearest the viewport centre
  const onScroll = () => {
    const mid = window.innerHeight * 0.42;
    let bestSec = null, bestDist = Infinity;
    document.querySelectorAll("#screen-dash section[data-sec]").forEach(s => {
      const r = s.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight) return;
      const c = (r.top + r.bottom) / 2;
      const d = Math.abs(c - mid);
      if (d < bestDist) { bestDist = d; bestSec = s.dataset.sec; }
    });
    if (bestSec) updateGuideChips(bestSec);
  };
  state.guideScroll = onScroll;
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}
function openGuide() { const p = $("#guide-panel"); if (p) { p.classList.remove("closed"); document.body.classList.add("guide-open"); $("#guide-fab") && $("#guide-fab").classList.add("active"); setTimeout(() => $("#guide-input") && $("#guide-input").focus(), 60); } }
function closeGuide() { const p = $("#guide-panel"); if (p) { p.classList.add("closed"); document.body.classList.remove("guide-open"); $("#guide-fab") && $("#guide-fab").classList.remove("active"); } }
function toggleGuide() { const p = $("#guide-panel"); if (!p) return; p.classList.contains("closed") ? openGuide() : closeGuide(); }

function updateGuideChips(section) {
  const ctx = GUIDE_CTX[section]; if (!ctx || section === _guideSection && $("#guide-chips") && $("#guide-chips").children.length) return;
  _guideSection = section;
  if (!$("#guide-ctx")) return;
  $("#guide-ctx").textContent = ctx.label;
  $("#guide-chips").innerHTML = ctx.chips.map(c => `<span class="chip" data-q="${c[1]}">${c[0]}</span>`).join("");
  $("#guide-chips").querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => { openGuide(); askGuide(c.dataset.q); }));
}
function cardHtml(card) {
  const cls = card.kind === "answer" ? "" : card.kind;
  let html = `<div class="answer-card ${cls}"><div class="txt">${card.text}</div>`;
  if (card.estimates && card.estimates.length) html += estTable(card.estimates);
  if (card.alternative_text) html += `<div class="alt">${card.alternative_text}</div>`;
  if (card.alternative_estimates && card.alternative_estimates.length) html += estTable(card.alternative_estimates);
  if (card.scope_note) html += `<div class="scope">${card.scope_note}</div>`;
  return html + `</div>`;
}
async function askGuide(query) {
  if (!query || !query.trim()) return;
  openGuide();
  const msgs = $("#guide-msgs");
  const q = document.createElement("div"); q.className = "g-msg g-user"; q.textContent = query.trim();
  msgs.appendChild(q);
  const botWrap = document.createElement("div"); botWrap.className = "g-msg g-bot";
  botWrap.innerHTML = `<div class="answer-card"><div class="txt faint">…</div></div>`;
  msgs.appendChild(botWrap);
  $("#guide-input").value = "";
  msgs.scrollTop = msgs.scrollHeight;
  try {
    const card = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, source: state.source }) }).then(r => r.json());
    botWrap.innerHTML = cardHtml(card);
  } catch (e) {
    botWrap.innerHTML = `<div class="answer-card refusal"><div class="txt">The guide is unreachable right now. Please try again.</div></div>`;
  }
  msgs.scrollTop = msgs.scrollHeight;
}
function hideGuide() {
  const fab = $("#guide-fab"); if (fab) fab.classList.add("hidden");
  closeGuide();
  document.body.classList.remove("has-guide");
  if (state.guideScroll) { window.removeEventListener("scroll", state.guideScroll); state.guideScroll = null; }
}

// ---- map wrapper: dynamic MapLibre+deck.gl if the CDN loads cleanly, else static IGN tiles ----
async function renderMap(building, neighbors) {
  const el = $("#dash-map"); if (!el) return;
  try {
    const mod = await import("./map3d.js");
    const ok = await mod.renderDynamicMap(el, building, neighbors);
    if (ok) return;
  } catch (e) { /* fall through to static */ }
  try { renderNeighbourhoodMap(el, building, neighbors); } catch (e) {}
}

function estTable(est) {
  let h = `<table class="est-table"><tr><th>Value</th><th>Range</th><th>Unit</th><th>Period</th><th>Source</th></tr>`;
  for (const e of est) h += `<tr><td>${e.value.toFixed(2)}</td><td>${e.lower.toFixed(2)} – ${e.upper.toFixed(2)}</td><td>${e.unit}</td><td>${e.period}</td><td class="faint">${e.run_source}</td></tr>`;
  return h + `</table>`;
}

// ---- helpers ----
function kpi(label, value, sub, cls, extra, flag) {
  return `<div class="panel kpi ${cls || ""}">
    <div class="label">${label}</div>
    <div class="value ${String(value).length > 8 ? "small" : ""}">${value}</div>
    ${sub ? `<div class="sub">${sub}</div>` : ""}
    ${extra ? `<div class="sub faint">${extra}</div>` : ""}
    ${flag ? `<div class="flag">⚠ ${flag}</div>` : ""}
  </div>`;
}
function bestScenario(scen) {
  const a = (scen || []).filter(s => s.applicable && Number.isFinite(s.delta_energy_pct) && !(s.negligible_energy && s.negligible_temperature));
  return a.length ? a.reduce((m, s) => s.delta_energy_pct < m.delta_energy_pct ? s : m) : null;
}
function enDate(iso) {
  if (!iso) return "";
  const d = new Date(iso); const mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${mon[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}
function methodBlock(p, reno) {
  const sel = p.selection, bank = p.bank;
  const renoBlock = reno ? `
      <h4>Renovation cost &amp; carbon (deterministic engine)</h4>
      <p>Operational CO₂: (before − after kWh) × footprint area × emission factor × 30 yr. Embodied CO₂: FDES material quantities. Off-site avoided: 25% of positive process emissions (CSTB range 20–40%). Cost: footprint × indicative €/m². Sources: ${Object.values(reno.sources).join("; ")}.</p>
      <p class="faint">Real record: BDNB/DPE ADEME (release 2025-07.a), RNB ${reno.building.rnb_id}, ADEME DPE ${reno.building.dpe_id_ademe} (${reno.building.dpe_date}). Reference figures reproduced: ${tSep(reno.building.conx_co2_avoided_t_30y)} tCO₂/30yr, ${money(reno.building.conx_cost_estimate_eur)}.</p>` : "";
  return `<details class="method">
    <summary>Methodological detail — full rigor</summary>
    <div class="method-b">
      ${renoBlock}
      <h4>Selected structure and bench↔twin consistency</h4>
      <p>${sel.explainer}</p>
      <p style="margin-top:6px">Operating twin: <b>${p.twin.structure_label.replace(/_/g," ")}</b> — consistent with the headline: <b>${p.twin.consistent_with_selection ? "yes" : "no"}</b>. ${p.twin.policy}</p>
      <p class="faint" style="margin-top:6px">Automated bench selection (declared): ${sel.bank_auto_pick.model.replace(/_/g," ")} — rule: ${sel.bank_auto_pick.rule}.</p>
      <h4>Executed bench (${bank.n_starts} starts/structure, replay of a real computation)</h4>
      <table><tr><th>Structure</th><th>Params</th><th>Check °C</th><th>Status</th></tr>
      ${bank.rows.map(r => `<tr><td>${r.model.replace(/_/g," ")}</td><td>${r.n_parameters}</td><td>${Number.isFinite(r.val_rmse) ? r.val_rmse.toFixed(3) : "—"}</td><td>${r.admissible ? "admissible" : "excluded"}</td></tr>`).join("")}
      </table>
      <h4>Twin accuracy</h4>
      <p>Check: ${p.twin.metrics.validation_rmse.value.toFixed(3)} °C [${p.twin.metrics.validation_rmse.lower.toFixed(3)} ; ${p.twin.metrics.validation_rmse.upper.toFixed(3)}] · test: ${p.twin.metrics.test_rmse.value.toFixed(3)} °C. 24 h block bootstrap, 300 replications.</p>
      <h4>Drift</h4>
      <p>Open-loop over the year; calibrated band = median ± 3 robust deviations of the calibration daily means; break = sustained 14-day departure. Residual = measured − estimated.</p>
      <h4>Reproduction verdict (sealed)</h4>
      <p>Identification is sensitive to initialization; the verdict and its content hashes are sealed in the project record and reproduced under test.</p>
      <h4>Geometry</h4>
      <p>${state.geometry.provenance} ${state.geometry.honesty_note} Status: ${p.geometry_status === "HUMAN_VALIDATION_REQUIRED" ? "pending human validation" : (p.geometry_status || "").toString().replace(/_/g, " ").toLowerCase()}.</p>
      <h4>Data</h4>
      <p class="faint">${p.dataset ? `${tSep(p.dataset.rows)} hourly rows, ${enDate(p.dataset.first)} → ${enDate(p.dataset.last)} · calibration ${p.dataset.splits.train} / check ${p.dataset.splits.validation} / test ${p.dataset.splits.test} · ${p.dataset.missing_hours} missing hours in ${p.dataset.n_gaps} gaps` : ""}</p>
    </div>
  </details>`;
}

document.addEventListener("click", (e) => {
  if (e.target && e.target.id === "btn-home") { state.payload = null; show("#screen-landing"); }
});
