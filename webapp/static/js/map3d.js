// Dynamic 3D neighbourhood map: MapLibre GL + deck.gl (CDN), IGN ortho WMTS,
// oblique pitch. Real BD TOPO footprints (from /api/buildings-3d): the target
// building extruded and coloured by DPE, the real urban neighbours extruded grey,
// each at its real height. Free zoom/rotate/pan. Returns true on clean success,
// false to fall back to the static IGN-tile map. Raster-only style => no
// glyph/sprite console noise.

const MAPLIBRE_JS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js";
const MAPLIBRE_CSS = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css";
const DECK_JS = "https://unpkg.com/deck.gl@9.0.38/dist.min.js";

const DPE_RGB = { A: [46, 204, 113], B: [127, 194, 65], C: [182, 225, 59], D: [244, 208, 63], E: [245, 166, 35], F: [245, 83, 61], G: [214, 0, 0] };
const IGN_WMTS = "https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile&LAYER=HR.ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&TILEMATRIX={z}&TILECOL={x}&TILEROW={y}&FORMAT=image/jpeg";

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if ([...document.scripts].some(s => s.src === src)) return resolve();
    const el = document.createElement("script");
    el.src = src; el.async = true;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error("load fail " + src));
    document.head.appendChild(el);
  });
}
function loadCss(href) {
  if ([...document.styleSheets].some(s => s.href === href)) return;
  const l = document.createElement("link"); l.rel = "stylesheet"; l.href = href; document.head.appendChild(l);
}
function withTimeout(promise, ms) {
  return Promise.race([promise, new Promise((_, rej) => setTimeout(() => rej(new Error("timeout")), ms))]);
}

// centroid of a lon/lat ring (for centring / fallback footprints)
function ringCentroid(ring) {
  let x = 0, y = 0;
  for (const p of ring) { x += p[0]; y += p[1]; }
  return [x / ring.length, y / ring.length];
}
// rectangle polygon (lon/lat) of the given ground area centred on the point
function footprintRing(lon, lat, area_m2) {
  const s = Math.sqrt(area_m2) / 2;
  const dLat = s / 111320, dLon = s / (111320 * Math.cos(lat * Math.PI / 180));
  return [[lon - dLon, lat - dLat], [lon + dLon, lat - dLat], [lon + dLon, lat + dLat], [lon - dLon, lat + dLat], [lon - dLon, lat - dLat]];
}

let _loaded = null;
async function ensureLibs() {
  if (_loaded) return _loaded;
  loadCss(MAPLIBRE_CSS);
  await withTimeout(loadScript(MAPLIBRE_JS), 8000);
  await withTimeout(loadScript(DECK_JS), 8000);
  if (!window.maplibregl || !window.deck || !window.deck.MapboxOverlay) throw new Error("libs missing");
  _loaded = true;
  return true;
}

let _cachedBuildings = null;
async function fetchBuildings() {
  if (_cachedBuildings) return _cachedBuildings;
  try {
    const r = await withTimeout(fetch("/api/buildings-3d"), 6000);
    const data = await r.json();
    if (data && Array.isArray(data.buildings) && data.buildings.length) {
      _cachedBuildings = data;
      return data;
    }
  } catch (e) { /* fall through */ }
  return null;
}

export async function renderDynamicMap(container, building, neighbors) {
  try {
    await ensureLibs();
  } catch (e) {
    return false;  // CDN unavailable -> caller uses the static map
  }
  try {
    const real = await fetchBuildings();

    // Build the polygon dataset. Prefer the real BD TOPO footprints; if the cache
    // is empty (offline first-run), degrade to an extruded emprise (never a bare
    // cube with fake neighbours — we simply centre on the real coordinates).
    let center, targetData = [], neighbourData = [], usedReal = false;
    if (real) {
      usedReal = true;
      center = [real.target_lon, real.target_lat];
      for (const b of real.buildings) {
        const rings = b.rings || [];
        if (!rings.length) continue;
        if (b.is_target) {
          for (const ring of rings) targetData.push({ polygon: ring, height: b.height });
        } else {
          for (const ring of rings) neighbourData.push({ polygon: ring, height: b.height, dpe: b.dpe });
        }
      }
      if (!targetData.length && neighbourData.length) {
        // no confirmed target flag but we have fabric: still render neighbourhood
        center = ringCentroid(neighbourData[0].polygon);
      }
    } else {
      center = [building.centroid_lon, building.centroid_lat];
      targetData = [{ polygon: footprintRing(building.centroid_lon, building.centroid_lat, building.footprint_m2), height: 11 }];
    }

    container.innerHTML = "";
    const map = new maplibregl.Map({
      container,
      center,
      zoom: 17.6, pitch: 54, bearing: -20, attributionControl: false,
      preserveDrawingBuffer: true,  // allow frame capture (filming / verification)
      style: {
        version: 8,
        sources: {
          osm: { type: "raster", tiles: ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256 },
          ign: { type: "raster", tiles: [IGN_WMTS], tileSize: 256, maxzoom: 19 },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#0b1017" } },
          { id: "osm", type: "raster", source: "osm", maxzoom: 14, paint: { "raster-opacity": 0.7 } },
          { id: "ign", type: "raster", source: "ign", minzoom: 13, paint: { "raster-brightness-max": 0.95 } },
        ],
      },
    });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.dragRotate.enable();
    map.touchZoomRotate.enableRotation();

    const { MapboxOverlay, PolygonLayer } = window.deck;
    const dpeClass = (real && real.target_dpe) || building.dpe_class || "F";
    const targetRgb = DPE_RGB[dpeClass] || [245, 83, 61];

    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [
        new PolygonLayer({
          id: "neighbours", data: neighbourData, extruded: true, getPolygon: d => d.polygon,
          getElevation: d => d.height, getFillColor: [150, 165, 180, 205], getLineColor: [11, 16, 23],
          getLineWidth: 0.5, material: { ambient: 0.5, diffuse: 0.6 }, pickable: false,
        }),
        new PolygonLayer({
          id: "target", data: targetData, extruded: true, getPolygon: d => d.polygon,
          getElevation: d => d.height, getFillColor: [...targetRgb, 240], getLineColor: [255, 255, 255],
          getLineWidth: 1.2, material: { ambient: 0.65, diffuse: 0.75 }, pickable: false,
        }),
      ],
    });
    map.addControl(overlay);
    map.on("error", () => {});  // swallow tile hiccups (do not spam console)
    map.triggerRepaint();       // force a paint in renderers where rAF is throttled
    // verification/filming handles (harmless): reach the live map + deck overlay
    try { window.__map = map; window.__deckOverlay = overlay; window.__deckCounts = { target: targetData.length, neighbours: neighbourData.length }; } catch (e) {}

    // legend + attribution
    const nCount = new Set(neighbourData.map(d => d.polygon)).size;
    const legend = document.createElement("div");
    legend.style.cssText = "position:absolute;top:8px;left:8px;z-index:2;font-size:10px;color:#cfe0ee;font-family:var(--mono);background:rgba(7,10,15,.62);padding:6px 8px;border-radius:4px;line-height:1.5;pointer-events:none";
    legend.innerHTML = `<b style='color:#F5533D'>98 Rue des Sarrazins</b> — DPE ${dpeClass}` +
      (usedReal ? `<br><span style='color:#9fb2c6'>real BD TOPO footprint · ${nCount} neighbours · drag to rotate</span>`
                : `<br><span style='color:#9fb2c6'>drag to rotate · scroll to zoom</span>`);
    container.appendChild(legend);
    const attr = document.createElement("div");
    attr.style.cssText = "position:absolute;bottom:4px;right:8px;z-index:2;font-size:9px;color:#9fb2c6;font-family:var(--mono);background:rgba(7,10,15,.5);padding:2px 6px;border-radius:3px;pointer-events:none";
    attr.textContent = (real && real.attribution) ? "© " + real.attribution : "© IGN Géoplateforme · © OpenStreetMap";
    container.appendChild(attr);

    // Succeed only if MapLibre actually finishes loading its style within a few
    // seconds — that is the honest signal that WebGL rendering works here and the
    // extruded buildings will paint. On a capable browser this is <1s (no needless
    // fallback). Where WebGL/rAF is throttled (some headless/embedded renderers)
    // the style never loads, so we return false and the caller shows the reliable
    // static IGN-tile map instead of a blank canvas.
    const ok = await new Promise((res) => {
      let done = false;
      const finish = (v) => { if (!done) { done = true; res(v); } };
      const check = () => { if (map.loaded && map.loaded()) finish(true); };
      map.on("load", () => finish(true));
      map.on("idle", check);
      const iv = setInterval(check, 250);
      setTimeout(() => { clearInterval(iv); finish(!!(map.loaded && map.loaded())); }, 5000);
    });
    if (!ok || !container.querySelector("canvas")) return false;
    return true;
  } catch (e) {
    return false;
  }
}
