// Axonometric SVG building — stacked extruded floors from the real plan footprint.
// No WebGL, no external library: fully offline, clean console, full styling control.
// Coloring is a GLOBAL envelope intensity (honest: never per-facade).

const SVGNS = "http://www.w3.org/2000/svg";

function lerp(a, b, t) { return a + (b - a) * t; }

// Cool -> warm ramp for global thermal intensity (0 cool .. 1 warm).
function thermalColor(t) {
  t = Math.max(0, Math.min(1, t));
  const stops = [
    [0.00, [46, 120, 168]],   // deep cool blue
    [0.35, [55, 224, 200]],   // cyan
    [0.6,  [180, 210, 90]],   // chartreuse
    [0.8,  [255, 176, 32]],   // amber
    [1.0,  [255, 77, 94]],    // warm red
  ];
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (t >= stops[i][0] && t <= stops[i + 1][0]) { a = stops[i]; b = stops[i + 1]; break; }
  }
  const span = (b[0] - a[0]) || 1;
  const k = (t - a[0]) / span;
  const c = [0, 1, 2].map(i => Math.round(lerp(a[1][i], b[1][i], k)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export class Building {
  constructor(svg) {
    this.svg = svg;
    this.footprint = null;      // [[x,y]...] normalized, y-down
    this.floors = [];           // [{level, activity}]
    this.intensity = 0.5;       // global thermal intensity 0..1
    this.floorGlow = [];        // per-floor illumination 0..1
    this.baseIntensity = 0.5;
    this.scenarioDelta = 0;     // shift of envelope tint on scenario hover
    // Projection params
    this.iso = { s: 200, tilt: 0.52, floorH: 26, ox: 0, oy: 0 };
  }

  setModel(footprint, floors) {
    // Normalize + center footprint around its centroid.
    const cx = footprint.reduce((s, p) => s + p[0], 0) / footprint.length;
    const cy = footprint.reduce((s, p) => s + p[1], 0) / footprint.length;
    this.footprint = footprint.map(p => [p[0] - cx, p[1] - cy]);
    this.floors = floors;
    this.floorGlow = floors.map(() => 0);
    this._baseIso = null;
    this._ensureWinding();
  }

  // Throttle repeated renders with a timestamp (no rAF — some controlled
  // browsers don't fire requestAnimationFrame). Always renders a trailing frame.
  render(opts) {
    const now = Date.now();
    if (!this._last) this._last = 0;
    const gap = now - this._last;
    if (gap >= 45) { this._last = now; this._render(opts); return; }
    if (this._pending) return;
    this._pending = setTimeout(() => { this._pending = null; this._last = Date.now(); this._render(opts); }, 45 - gap);
  }

  _ensureWinding() {
    // Force counter-clockwise (positive signed area in screen sense not needed;
    // we only use it for painter ordering).
    let area = 0;
    const f = this.footprint;
    for (let i = 0; i < f.length; i++) {
      const a = f[i], b = f[(i + 1) % f.length];
      area += a[0] * b[1] - b[0] * a[1];
    }
    if (area < 0) this.footprint = f.slice().reverse();
  }

  // Raw dimetric projection with a given scale (no offset).
  _raw(x, y, z, s, floorH, tilt) {
    return [(x - y) * s, (x + y) * s * tilt - z * floorH];
  }

  project(x, y, z) {
    const v = this._view;
    const p = this._raw(x, y, z, v.s, v.floorH, v.tilt);
    return [v.ox + p[0], v.oy + p[1]];
  }

  setIntensity(v) { this.baseIntensity = v; this.intensity = v; }
  setScenarioDelta(d) { this.scenarioDelta = d; }
  clearScenario() { this.scenarioDelta = 0; }

  _render(opts = {}) {
    if (!this.footprint) return;
    const svg = this.svg;
    // Fixed logical canvas + viewBox so rendering never depends on measured
    // width (which can be 0 in some fl\/grid layouts). CSS scales it responsively.
    const W = Number(svg.dataset.w) || 560;
    const H = Number(svg.dataset.h) || (svg.clientHeight || 420);
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    // Idempotent auto-fit: base scale = 1, measure bounds, derive fit scale + offset.
    const nFloors = Math.max(1, this.floors.length);
    const tilt = this.iso.tilt, baseFloorH = 0.11; // floor height in footprint units
    const test = [];
    for (const [x, y] of this.footprint) {
      test.push(this._raw(x, y, 0, 1, baseFloorH, tilt));
      test.push(this._raw(x, y, nFloors, 1, baseFloorH, tilt));
    }
    const xs = test.map(p => p[0]), ys = test.map(p => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const pad = 46;
    const s = Math.min((W - pad * 2) / (maxX - minX || 1), (H - pad * 2) / (maxY - minY || 1));
    const floorH = baseFloorH * s;
    // center
    const midX = (minX + maxX) / 2 * s, midY = (minY + maxY) / 2 * s;
    this._view = { s, floorH, tilt, ox: W / 2 - midX, oy: H / 2 - midY };
    this.iso.floorH = floorH; // used by callers referencing floor height

    const grad = thermalColor(this.baseIntensity);
    const shift = thermalColor(Math.max(0, Math.min(1, this.baseIntensity + this.scenarioDelta)));

    // Ground shadow (flat, no blur filter -> cheap repaint).
    const g0 = this.footprint.map(([x, y]) => this.project(x, y, 0));
    const shadow = document.createElementNS(SVGNS, "polygon");
    shadow.setAttribute("points", g0.map(p => `${p[0].toFixed(1)},${(p[1] + 8).toFixed(1)}`).join(" "));
    shadow.setAttribute("fill", "rgba(0,0,0,0.35)");
    svg.appendChild(shadow);

    // Build faces per floor band, back-to-front.
    const faces = [];
    const f = this.footprint;
    for (let fl = 0; fl < nFloors; fl++) {
      const zb = fl, zt = fl + 1; // z as floor index; project() scales by floorH
      for (let i = 0; i < f.length; i++) {
        const a = f[i], b = f[(i + 1) % f.length];
        // outward normal (plan): edge (b-a), normal = (dy, -dx) for CCW gives outward
        const dx = b[0] - a[0], dy = b[1] - a[1];
        const nx = dy, ny = -dx;
        // viewer direction in plan ~ (+1,+1) (near = larger x+y). Front if normal·(1,1) > 0
        const front = (nx + ny) > 0;
        const depth = (a[0] + a[1] + b[0] + b[1]) / 2 + fl * 0.001;
        faces.push({ type: "wall", fl, i, a, b, zb, zt, front, depth });
      }
    }
    faces.sort((p, q) => p.depth - q.depth);

    for (const face of faces) {
      const { a, b, zb, zt, front, fl } = face;
      const p1 = this.project(a[0], a[1], zb);
      const p2 = this.project(b[0], b[1], zb);
      const p3 = this.project(b[0], b[1], zt);
      const p4 = this.project(a[0], a[1], zt);
      const poly = document.createElementNS(SVGNS, "polygon");
      poly.setAttribute("points", [p1, p2, p3, p4].map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" "));
      const glow = this.floorGlow[fl] || 0;
      // Envelope color is GLOBAL; front faces brighter, back faces darker (form only).
      // Glow is expressed via opacity/stroke (no SVG filters -> fast, clean repaint).
      const base = this.scenarioDelta ? shift : grad;
      poly.setAttribute("fill", base);
      poly.setAttribute("fill-opacity", ((front ? 0.30 : 0.15) + 0.5 * glow).toFixed(3));
      poly.setAttribute("stroke", glow > 0.4 ? "#eafffb" : base);
      poly.setAttribute("stroke-opacity", (front ? 0.85 : 0.4) + 0.15 * glow);
      poly.setAttribute("stroke-width", (1 + 1.4 * glow).toFixed(2));
      poly.dataset.floor = fl;
      svg.appendChild(poly);
    }

    // Roof slab (top).
    const roofPts = f.map(([x, y]) => this.project(x, y, nFloors));
    const roof = document.createElementNS(SVGNS, "polygon");
    roof.setAttribute("points", roofPts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" "));
    const roofBase = this.scenarioDelta ? shift : grad;
    roof.setAttribute("fill", roofBase);
    roof.setAttribute("fill-opacity", "0.42");
    roof.setAttribute("stroke", "#eaf6ff");
    roof.setAttribute("stroke-opacity", "0.5");
    roof.setAttribute("stroke-width", "1.2");
    svg.appendChild(roof);

    // Roof edge highlight vertices.
    for (const p of roofPts) {
      const dot = document.createElementNS(SVGNS, "circle");
      dot.setAttribute("cx", p[0].toFixed(1)); dot.setAttribute("cy", p[1].toFixed(1));
      dot.setAttribute("r", "1.6"); dot.setAttribute("fill", "#eaf6ff"); dot.setAttribute("fill-opacity", "0.6");
      svg.appendChild(dot);
    }
    this._roofCentroid = [
      roofPts.reduce((s, p) => s + p[0], 0) / roofPts.length,
      Math.min(...roofPts.map(p => p[1])) - 6,
    ];
  }

  // Sequential floor illumination during analysis. progress in 0..1 over floors.
  setRevealProgress(progress) {
    const n = this.floors.length;
    for (let i = 0; i < n; i++) {
      const start = i / n, end = (i + 1) / n;
      let g = (progress - start) / (end - start);
      g = Math.max(0, Math.min(1, g));
      // decay trailing floors slightly for a sweep look
      this.floorGlow[i] = g;
    }
    this.render();
  }

  pulseAllFloors(level) {
    this.floorGlow = this.floors.map(() => level);
    this.render();
  }

  settleFloors(activities) {
    // At diagnosis, floors keep a low ambient glow proportional to drawn activity.
    this.floorGlow = (activities || this.floors.map(f => f.activity)).map(a => 0.12 + 0.18 * a);
    this.render();
  }
}

export { thermalColor };
