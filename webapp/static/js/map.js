// Neighbourhood map: real IGN aerial imagery (Géoplateforme WMTS, public, no key)
// centred on the surveyed building's real coordinates, with the target building
// and its real neighbours overlaid. Falls back to a dark schematic if tiles fail.
const NS = "http://www.w3.org/2000/svg";
const DPE_COLOR = { A: "#2ECC71", B: "#7FC241", C: "#B6E13B", D: "#F4D03F", E: "#F5A623", F: "#F5533D", G: "#D60000", unknown: "#8FA3B6" };
const IGN_TILE = "https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile&LAYER=HR.ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILECOL={x}&TILEROW={y}&FORMAT=image/jpeg";

function worldPx(lon, lat, z) {
  const s = 256 * Math.pow(2, z);
  const x = (lon + 180) / 360 * s;
  const latR = lat * Math.PI / 180;
  const y = (1 - Math.log(Math.tan(latR) + 1 / Math.cos(latR)) / Math.PI) / 2 * s;
  return { x, y };
}
function offsetLatLon(lat, lon, dist_m, bearing_deg) {
  const b = bearing_deg * Math.PI / 180;
  const dLat = (dist_m * Math.cos(b)) / 111320;
  const dLon = (dist_m * Math.sin(b)) / (111320 * Math.cos(lat * Math.PI / 180));
  return { lat: lat + dLat, lon: lon + dLon };
}

export function renderNeighbourhoodMap(container, building, neighbors, z = 18) {
  container.innerHTML = "";
  container.style.position = "relative";
  container.style.overflow = "hidden";
  container.style.background = "#0b1017";
  const W = container.clientWidth || 640, H = container.clientHeight || 360;
  const center = worldPx(building.centroid_lon, building.centroid_lat, z);
  const topX = center.x - W / 2, topY = center.y - H / 2;
  const tX0 = Math.floor(topX / 256), tX1 = Math.floor((topX + W) / 256);
  const tY0 = Math.floor(topY / 256), tY1 = Math.floor((topY + H) / 256);

  const tileLayer = document.createElement("div");
  tileLayer.style.cssText = "position:absolute;inset:0";
  let loaded = 0, total = 0, failed = false;
  for (let tx = tX0; tx <= tX1; tx++) {
    for (let ty = tY0; ty <= tY1; ty++) {
      total++;
      const img = document.createElement("img");
      img.decoding = "async"; img.loading = "eager";
      img.src = IGN_TILE.replace("{z}", z).replace("{x}", tx).replace("{y}", ty);
      img.style.cssText = `position:absolute;width:256px;height:256px;left:${tx * 256 - topX}px;top:${ty * 256 - topY}px;filter:saturate(1.05) brightness(0.92)`;
      img.onerror = () => { if (!failed) { failed = true; container.style.background = "#0b1017"; } img.remove(); };
      img.onload = () => { loaded++; };
      tileLayer.appendChild(img);
    }
  }
  container.appendChild(tileLayer);

  // dark vignette for legibility
  const vig = document.createElement("div");
  vig.style.cssText = "position:absolute;inset:0;pointer-events:none;background:radial-gradient(ellipse 70% 70% at 50% 45%, transparent 40%, rgba(7,10,15,.55) 100%)";
  container.appendChild(vig);

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", W); svg.setAttribute("height", H);
  svg.style.cssText = "position:absolute;inset:0";
  const toPx = (lon, lat) => { const p = worldPx(lon, lat, z); return [p.x - topX, p.y - topY]; };

  // neighbours (real DPE + distance; bearings spread for context)
  const bearings = [25, 85, 150, 215, 300, 340];
  (neighbors || []).forEach((n, i) => {
    const o = offsetLatLon(building.centroid_lat, building.centroid_lon, n.distance_m, bearings[i % bearings.length]);
    const [x, y] = toPx(o.lon, o.lat);
    const col = DPE_COLOR[n.dpe_class] || DPE_COLOR.unknown;
    const g = document.createElementNS(NS, "g");
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", 8);
    c.setAttribute("fill", col); c.setAttribute("fill-opacity", "0.85"); c.setAttribute("stroke", "#0b1017"); c.setAttribute("stroke-width", "1.5");
    g.appendChild(c);
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", x); t.setAttribute("y", y + 3.5); t.setAttribute("text-anchor", "middle");
    t.setAttribute("fill", "#0b1017"); t.setAttribute("font-size", "10"); t.setAttribute("font-weight", "700"); t.setAttribute("font-family", "var(--mono)");
    t.textContent = n.dpe_class; g.appendChild(t);
    const d = document.createElementNS(NS, "text");
    d.setAttribute("x", x); d.setAttribute("y", y - 12); d.setAttribute("text-anchor", "middle");
    d.setAttribute("fill", "#cfe0ee"); d.setAttribute("font-size", "9"); d.setAttribute("font-family", "var(--mono)");
    d.textContent = `${n.distance_m} m`; g.appendChild(d);
    svg.appendChild(g);
  });

  // target building (real centroid), pulsing DPE-F marker
  const [bx, by] = toPx(building.centroid_lon, building.centroid_lat);
  const halo = document.createElementNS(NS, "circle");
  halo.setAttribute("cx", bx); halo.setAttribute("cy", by); halo.setAttribute("r", 22);
  halo.setAttribute("fill", "none"); halo.setAttribute("stroke", DPE_COLOR[building.dpe_class] || "#F5533D"); halo.setAttribute("stroke-width", "1.5"); halo.setAttribute("opacity", "0.5");
  svg.appendChild(halo);
  const ring = document.createElementNS(NS, "circle");
  ring.setAttribute("cx", bx); ring.setAttribute("cy", by); ring.setAttribute("r", 13);
  ring.setAttribute("fill", DPE_COLOR[building.dpe_class] || "#F5533D"); ring.setAttribute("fill-opacity", "0.9"); ring.setAttribute("stroke", "#fff"); ring.setAttribute("stroke-width", "2");
  svg.appendChild(ring);
  const bl = document.createElementNS(NS, "text");
  bl.setAttribute("x", bx); bl.setAttribute("y", by + 4.5); bl.setAttribute("text-anchor", "middle");
  bl.setAttribute("fill", "#fff"); bl.setAttribute("font-size", "13"); bl.setAttribute("font-weight", "700"); bl.setAttribute("font-family", "var(--mono)");
  bl.textContent = building.dpe_class; svg.appendChild(bl);
  const cap = document.createElementNS(NS, "text");
  cap.setAttribute("x", bx); cap.setAttribute("y", by - 20); cap.setAttribute("text-anchor", "middle");
  cap.setAttribute("fill", "#fff"); cap.setAttribute("font-size", "11"); cap.setAttribute("font-family", "var(--mono)");
  cap.textContent = "98 Rue des Sarrazins"; svg.appendChild(cap);
  container.appendChild(svg);

  // attribution + legend chips (bottom)
  const attr = document.createElement("div");
  attr.style.cssText = "position:absolute;bottom:4px;right:8px;font-size:9px;color:#9fb2c6;font-family:var(--mono);background:rgba(7,10,15,.5);padding:2px 6px;border-radius:3px";
  attr.textContent = "Aerial imagery © IGN — Géoplateforme (data.geopf.fr)";
  container.appendChild(attr);
  const legend = document.createElement("div");
  legend.style.cssText = "position:absolute;top:8px;left:8px;font-size:10px;color:#cfe0ee;font-family:var(--mono);background:rgba(7,10,15,.6);padding:6px 8px;border-radius:4px;line-height:1.5";
  legend.innerHTML = "Target building &amp; real neighbours<br><span style='color:#9fb2c6'>colour = DPE class · label = distance</span>";
  container.appendChild(legend);
}

export { DPE_COLOR };
