// RC topology schematic — draws nodes, resistances and capacities for the
// structure currently being fitted, and reconfigures when the structure changes.
const NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}) {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

export class Topology {
  constructor(svg) { this.svg = svg; this.current = null; }

  // graph: {name, nodes:[{id,name,kind}], resistances:[{id,from,to}], capacities:[{node}]}
  render(graph) {
    const svg = this.svg;
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    if (!graph) return;
    this.current = graph;
    const W = svg.clientWidth || 520, H = svg.clientHeight || 300;
    const masses = graph.nodes.filter(n => n.kind === "mass");
    const air = graph.nodes.find(n => n.kind === "air");

    // Layout: outdoor rail (left), air node (mid-left), masses in a rightward chain.
    const railX = 46;
    const airX = 150, airY = H / 2;
    const pos = {};
    pos[air.id] = [airX, airY];
    const gap = Math.min(120, (W - airX - 70) / Math.max(1, masses.length));
    masses.forEach((m, i) => { pos[m.id] = [airX + gap * (i + 1), airY]; });

    // Outdoor rail.
    const rail = el("line", { x1: railX, y1: 30, x2: railX, y2: H - 30, stroke: "#5b6b7a", "stroke-width": 2, "stroke-dasharray": "2 5" });
    svg.appendChild(rail);
    const rlab = el("text", { x: railX - 6, y: 22, fill: "#8fa3b6", "font-size": 11, "text-anchor": "middle", "font-family": "var(--mono)" });
    rlab.textContent = "OUTDOOR"; svg.appendChild(rlab);

    // Resistances.
    graph.resistances.forEach((r, idx) => {
      const from = pos[r.from];
      const to = r.to === "outdoor" ? [railX, from[1] + (idx - graph.resistances.length / 2) * 8] : pos[r.to];
      if (!from || !to) return;
      this._resistor(svg, from, to, idx);
    });

    // Capacities (node -> ground below).
    graph.capacities.forEach((c) => {
      const p = pos[c.node]; if (!p) return;
      this._capacitor(svg, p);
    });

    // Nodes.
    graph.nodes.forEach((n) => {
      const p = pos[n.id]; if (!p) return;
      this._node(svg, p, n);
    });

    // Q injection into air node.
    const q = el("path", { d: `M ${airX - 46} ${airY - 40} L ${airX - 8} ${airY - 12}`, stroke: "#ffb020", "stroke-width": 2.4, "marker-end": "url(#arrowQ)", fill: "none" });
    this._ensureArrow(svg);
    svg.appendChild(q);
    const qlab = el("text", { x: airX - 50, y: airY - 46, fill: "#ffb020", "font-size": 12, "font-family": "var(--mono)" });
    qlab.textContent = "Q = α·P"; svg.appendChild(qlab);
  }

  _ensureArrow(svg) {
    let defs = svg.querySelector("defs");
    if (!defs) { defs = el("defs"); svg.appendChild(defs); }
    if (svg.querySelector("#arrowQ")) return;
    const m = el("marker", { id: "arrowQ", markerWidth: 8, markerHeight: 8, refX: 6, refY: 3, orient: "auto" });
    m.appendChild(el("path", { d: "M0,0 L6,3 L0,6 Z", fill: "#ffb020" }));
    defs.appendChild(m);
  }

  _resistor(svg, a, b, idx) {
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const ux = dx / len, uy = dy / len;
    const px = -uy, py = ux;
    const zpts = [];
    const zStart = 0.32, zEnd = 0.68, zN = 6;
    zpts.push([a[0] + ux * len * zStart, a[1] + uy * len * zStart]);
    for (let i = 0; i <= zN; i++) {
      const t = zStart + (zEnd - zStart) * (i / zN);
      const off = (i % 2 === 0 ? 1 : -1) * 5;
      zpts.push([a[0] + ux * len * t + px * off, a[1] + uy * len * t + py * off]);
    }
    zpts.push([a[0] + ux * len * zEnd, a[1] + uy * len * zEnd]);
    const path = "M " + [ [a[0] + ux * len * 0.08, a[1] + uy * len * 0.08], ...zpts, [b[0] - ux * len * 0.08, b[1] - uy * len * 0.08] ].map(p => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" L ");
    const line = el("path", { d: path, stroke: "#37e0c8", "stroke-width": 2, fill: "none", "stroke-linejoin": "round", opacity: 0 });
    line.style.transition = "opacity .35s ease";
    svg.appendChild(line);
    setTimeout(() => line.setAttribute("opacity", "0.92"), 10);
  }

  _capacitor(svg, p) {
    const y0 = p[1] + 16, y1 = y0 + 12;
    const g = el("g", { opacity: 0 });
    g.style.transition = "opacity .4s ease .1s";
    g.appendChild(el("line", { x1: p[0], y1: p[1] + 7, x2: p[0], y2: y0, stroke: "#7fe0ff", "stroke-width": 1.6 }));
    g.appendChild(el("line", { x1: p[0] - 10, y1: y0, x2: p[0] + 10, y2: y0, stroke: "#7fe0ff", "stroke-width": 2.4 }));
    g.appendChild(el("line", { x1: p[0] - 10, y1: y1, x2: p[0] + 10, y2: y1, stroke: "#7fe0ff", "stroke-width": 2.4 }));
    g.appendChild(el("line", { x1: p[0], y1: y1, x2: p[0], y2: y1 + 8, stroke: "#5b6b7a", "stroke-width": 1.4 }));
    g.appendChild(el("line", { x1: p[0] - 6, y1: y1 + 8, x2: p[0] + 6, y2: y1 + 8, stroke: "#5b6b7a", "stroke-width": 1.4 }));
    svg.appendChild(g);
    setTimeout(() => g.setAttribute("opacity", "1"), 10);
  }

  _node(svg, p, n) {
    const g = el("g", { opacity: 0 });
    g.style.transition = "opacity .3s ease";
    const isAir = n.kind === "air";
    const c = el("circle", { cx: p[0], cy: p[1], r: isAir ? 13 : 10,
      fill: isAir ? "rgba(55,224,200,.18)" : "rgba(127,224,255,.12)",
      stroke: isAir ? "#37e0c8" : "#7fe0ff", "stroke-width": isAir ? 2.4 : 1.8 });
    g.appendChild(c);
    const label = el("text", { x: p[0], y: p[1] + 4, fill: isAir ? "#eafffb" : "#cfeeff", "font-size": 11, "text-anchor": "middle", "font-family": "var(--mono)" });
    label.textContent = isAir ? "AIR" : n.name;
    g.appendChild(label);
    if (isAir) {
      const t = el("text", { x: p[0], y: p[1] + 30, fill: "#37e0c8", "font-size": 10, "text-anchor": "middle", "font-family": "var(--mono)" });
      t.textContent = "measured T"; g.appendChild(t);
    }
    svg.appendChild(g);
    setTimeout(() => g.setAttribute("opacity", "1"), 10);
  }
}
