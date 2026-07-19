// Custom SVG charts. No Vega/Altair -> the "Infinite extent" class of errors is
// gone by construction. Every series is still guarded against NaN/Inf here.
const NS = "http://www.w3.org/2000/svg";
const isNum = (v) => typeof v === "number" && Number.isFinite(v);

function el(name, attrs = {}) {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}
function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }
function extent(vals, fallback) {
  const f = vals.filter(isNum);
  if (!f.length) return fallback;
  let lo = Math.min(...f), hi = Math.max(...f);
  if (lo === hi) { lo -= 1; hi += 1; }
  return [lo, hi];
}

// Complexity (x = params) vs error (y = validation °C). Points added incrementally.
export class ComplexityScatter {
  constructor(svg) { this.svg = svg; this.points = []; this.selected = null; this.reference = null; }
  reset() { this.points = []; this.selected = null; this.reference = null; this.render(); }
  add(p) { if (isNum(p.x) && isNum(p.y)) { this.points.push(p); this.render(); } }
  setSelected(name) { this.selected = name; this.render(); }
  setReference(ref) { if (ref && isNum(ref.x) && isNum(ref.y)) this.reference = ref; this.render(); }

  render() {
    const svg = this.svg; clear(svg);
    const W = svg.clientWidth || 480, H = svg.clientHeight || 300;
    const m = { l: 46, r: 16, t: 16, b: 34 };
    const all = this.points.concat(this.reference ? [this.reference] : []);
    const xs = all.map(p => p.x), ys = all.map(p => p.y);
    const [x0, x1] = extent(xs, [1, 12]);
    const [y0, y1] = extent(ys, [4.5, 5.1]);
    const px = v => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r);
    const py = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);

    // axes
    svg.appendChild(el("line", { x1: m.l, y1: H - m.b, x2: W - m.r, y2: H - m.b, stroke: "#2a3646", "stroke-width": 1 }));
    svg.appendChild(el("line", { x1: m.l, y1: m.t, x2: m.l, y2: H - m.b, stroke: "#2a3646", "stroke-width": 1 }));
    const xl = el("text", { x: (m.l + W - m.r) / 2, y: H - 6, fill: "#6b7d90", "font-size": 10, "text-anchor": "middle", "font-family": "var(--mono)" });
    xl.textContent = "MODEL COMPLEXITY →"; svg.appendChild(xl);
    const yl = el("text", { x: 12, y: (m.t + H - m.b) / 2, fill: "#6b7d90", "font-size": 10, "text-anchor": "middle", transform: `rotate(-90 12 ${(m.t + H - m.b) / 2})`, "font-family": "var(--mono)" });
    yl.textContent = "ERROR (°C) →"; svg.appendChild(yl);

    for (const p of this.points) {
      const sel = this.selected && p.name === this.selected;
      const c = el("circle", { cx: px(p.x).toFixed(1), cy: py(p.y).toFixed(1), r: sel ? 7 : 4.5,
        fill: sel ? "#37e0c8" : "rgba(120,150,180,.65)", stroke: sel ? "#eafffb" : "none", "stroke-width": sel ? 1.5 : 0 });
      if (sel) c.style.filter = "drop-shadow(0 0 8px #37e0c8)";
      svg.appendChild(c);
    }
    if (this.reference) {
      const r = this.reference;
      const d = el("path", { d: diamond(px(r.x), py(r.y), 7), fill: "#8ce563", stroke: "#eafff0", "stroke-width": 1 });
      d.style.filter = "drop-shadow(0 0 6px #8ce563)";
      svg.appendChild(d);
    }
  }
}
function diamond(x, y, r) { return `M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`; }

// Drift timeline: measured vs model expectation over the full year, with a
// sign-coloured gap ribbon (cool = measured BELOW model, warm = above) so the
// dated departure matches the verdict sign at a glance. Residual = measured - estimated.
const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function renderDriftTimeline(svg, daily, drift) {
  clear(svg);
  const W = svg.clientWidth || 900, H = svg.clientHeight || 260;
  const m = { l: 44, r: 64, t: 14, b: 26 };
  const pts = (daily || [])
    .map(d => ({ t: new Date(d.date).getTime(), meas: d.measured, exp: d.expected }))
    .filter(d => isNum(d.t) && isNum(d.meas) && isNum(d.exp));
  if (!pts.length) return;
  const t0 = Math.min(...pts.map(d => d.t)), t1 = Math.max(...pts.map(d => d.t));
  const temps = pts.flatMap(d => [d.meas, d.exp]);
  const [y0, y1] = extent(temps, [15, 30]);
  const px = t => m.l + (t - t0) / (t1 - t0) * (W - m.l - m.r);
  const py = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);

  // month gridlines + labels
  const year0 = new Date(t0).getUTCFullYear();
  for (let mo = 0; mo < 12; mo++) {
    const tm = Date.UTC(year0, mo, 1);
    if (tm < t0 || tm > t1) continue;
    svg.appendChild(el("line", { x1: px(tm), y1: m.t, x2: px(tm), y2: H - m.b, stroke: "#141c26", "stroke-width": 1 }));
    const lab = el("text", { x: px(tm) + 2, y: H - m.b + 14, fill: "#4a5a6b", "font-size": 9, "font-family": "var(--mono)" });
    lab.textContent = MONTHS_EN[mo]; svg.appendChild(lab);
  }
  svg.appendChild(el("line", { x1: m.l, y1: H - m.b, x2: W - m.r, y2: H - m.b, stroke: "#2a3646" }));

  // sign-coloured gap ribbon between measured and expected (per day segment)
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const below = ((a.meas - a.exp) + (b.meas - b.exp)) / 2 < 0; // measured colder than model
    const poly = el("polygon", {
      points: [[px(a.t), py(a.meas)], [px(b.t), py(b.meas)], [px(b.t), py(b.exp)], [px(a.t), py(a.exp)]]
        .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" "),
      fill: below ? "#2f6fb0" : "#caa23a",
      "fill-opacity": below ? 0.30 : 0.20, stroke: "none",
    });
    svg.appendChild(poly);
  }

  const line = (key, color, width) => {
    let d = "";
    pts.forEach((p, i) => { d += `${i ? "L" : "M"} ${px(p.t).toFixed(1)} ${py(p[key]).toFixed(1)} `; });
    svg.appendChild(el("path", { d, fill: "none", stroke: color, "stroke-width": width }));
  };
  line("exp", "#ffb020", 1.6);   // model expectation (open-loop)
  line("meas", "#37e0c8", 1.9);  // measured

  // rupture + onset markers
  const sw = drift && drift.structural_switch;
  if (sw) {
    const rt = new Date(sw.timestamp).getTime();
    if (isNum(rt)) {
      svg.appendChild(el("line", { x1: px(rt), y1: m.t, x2: px(rt), y2: H - m.b, stroke: "#ff4d5e", "stroke-width": 2 }));
      const lab = el("text", { x: px(rt) + 6, y: m.t + 12, fill: "#ff8894", "font-size": 11, "font-family": "var(--mono)" });
      lab.textContent = "BREAK " + sw.date; svg.appendChild(lab);
    }
    if (sw.onset_date) {
      const ot = new Date(sw.onset_date).getTime();
      if (isNum(ot)) svg.appendChild(el("line", { x1: px(ot), y1: m.t, x2: px(ot), y2: H - m.b, stroke: "#ff4d5e", "stroke-width": 1.2, "stroke-dasharray": "4 4", opacity: 0.7 }));
    }
  }

  // end-of-year gap annotation (matches the verdict sign)
  const last = pts[pts.length - 1];
  const gap = last.meas - last.exp;
  const gy = (py(last.meas) + py(last.exp)) / 2;
  const gtxt = el("text", { x: W - m.r + 6, y: gy, fill: gap < 0 ? "#7fb8ea" : "#e6c14a", "font-size": 11, "font-family": "var(--mono)" });
  gtxt.textContent = `${gap >= 0 ? "+" : ""}${gap.toFixed(1)}°C`;
  svg.appendChild(gtxt);
  const gsub = el("text", { x: W - m.r + 6, y: gy + 13, fill: "#5a6b7c", "font-size": 8.5, "font-family": "var(--mono)" });
  gsub.textContent = gap < 0 ? "below model" : "above model";
  svg.appendChild(gsub);
}

// Scenario comparison: horizontal bars. Full label ABOVE each bar (never clipped),
// shared zero-origin axis so identical values give identical bar lengths, and a
// q05–q95 inter-calibration range tick beneath each bar.
export function renderScenarioBars(svg, scenarios, onHover) {
  clear(svg);
  const rows = (scenarios || []).filter(s => s.applicable && isNum(s.delta_energy_pct) && !(s.negligible_energy && s.negligible_temperature));
  const W = svg.clientWidth || 520, H = svg.clientHeight || 220;
  const m = { l: 12, r: 60, t: 10, b: 24 };
  if (!rows.length) { const t = el("text", { x: 20, y: 30, fill: "#8fa3b6", "font-size": 12 }); t.textContent = "No scenario with an exploitable effect."; svg.appendChild(t); return; }
  const spreadOf = s => (s.dispersion && s.dispersion.delta_energy_pct) || null;
  const vals = rows.flatMap(s => { const sp = spreadOf(s); return [s.delta_energy_pct, sp && sp.q05, sp && sp.q95]; }).filter(isNum);
  let [lo, hi] = extent(vals.concat([0]), [-15, 1]);
  // pad so labels/values fit
  const zx = v => m.l + (v - lo) / (hi - lo) * (W - m.l - m.r);
  const rowH = (H - m.t - m.b) / rows.length;

  // zero baseline
  svg.appendChild(el("line", { x1: zx(0), y1: m.t, x2: zx(0), y2: H - m.b, stroke: "#3a4757", "stroke-dasharray": "2 3" }));

  rows.forEach((s, i) => {
    const top = m.t + i * rowH;
    const barY = top + rowH * 0.58;
    const x0 = zx(0), x1 = zx(s.delta_energy_pct);
    const g = el("g");
    // full label above the bar, left-aligned within the plot (never clipped)
    const label = el("text", { x: m.l, y: top + 14, fill: "#cfe0ee", "font-size": 11.5, "font-family": "var(--mono)" });
    label.textContent = s.title; g.appendChild(label);
    // the bar
    const bar = el("rect", { x: Math.min(x0, x1).toFixed(1), y: (barY - 8).toFixed(1), width: Math.abs(x1 - x0).toFixed(1), height: 16, rx: 2, fill: "#37e0c8", "fill-opacity": 0.85 });
    bar.style.cursor = "pointer"; g.appendChild(bar);
    // value at bar end
    const val = el("text", { x: (x1 + (x1 < x0 ? -6 : 6)).toFixed(1), y: (barY + 4).toFixed(1), fill: "#eafffb", "font-size": 12, "font-family": "var(--mono)", "text-anchor": x1 < x0 ? "end" : "start" });
    val.textContent = `${s.delta_energy_pct >= 0 ? "+" : ""}${s.delta_energy_pct.toFixed(0)} %`; g.appendChild(val);
    // inter-calibration range tick beneath the bar
    const sp = spreadOf(s);
    if (sp && isNum(sp.q05) && isNum(sp.q95)) {
      const ry = barY + 12;
      g.appendChild(el("line", { x1: zx(sp.q05), y1: ry, x2: zx(sp.q95), y2: ry, stroke: "#ff8894", "stroke-width": 1.4 }));
      [sp.q05, sp.q95].forEach(v => g.appendChild(el("line", { x1: zx(v), y1: ry - 3, x2: zx(v), y2: ry + 3, stroke: "#ff8894", "stroke-width": 1.4 })));
    }
    g.style.cursor = "pointer";
    g.addEventListener("mouseenter", () => onHover && onHover(s));
    g.addEventListener("mouseleave", () => onHover && onHover(null));
    svg.appendChild(g);
  });

  const axl = el("text", { x: (m.l + W - m.r) / 2, y: H - 6, fill: "#6b7d90", "font-size": 10, "text-anchor": "middle", "font-family": "var(--mono)" });
  axl.textContent = "HEATING ENERGY AT EQUAL COMFORT (%)"; svg.appendChild(axl);
}
