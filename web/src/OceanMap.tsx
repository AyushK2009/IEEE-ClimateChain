import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import type { AreaLive, AreaStatic, Frame } from "./api";

// Data is in 0-360 longitudes. The map is centred near -165, so everything is drawn at lon-360 on one world copy.
export const L = (lon360: number) => lon360 - 360;
export const to360 = (lng: number) => ((lng % 360) + 360) % 360;

type Focus = { lat: number; lon: number; zoom: number; key: string | number; duration?: number };
type Props = {
  layers: any[]; center?: [number, number]; zoom?: number; interactive?: boolean; focus?: Focus | null;
  onClick?: (lat: number, lon360: number, info: any) => void; tooltip?: (info: any) => any; cursor?: string; tourId?: string;
  locator?: boolean;
};

// Chart colours applied to the CARTO Voyager basemap once it loads.
const WATER = "#c4d8e2", LAND = "#ece7da";
const STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";
function chartStyle(m: maplibregl.Map) {
  for (const layer of m.getStyle().layers ?? []) {
    const id = layer.id;
    try {
      if (layer.type === "background") m.setPaintProperty(id, "background-color", LAND);
      else if (/water/.test(id) && layer.type === "fill") m.setPaintProperty(id, "fill-color", WATER);
      else if (/landcover|landuse|park|building|aeroway/.test(id)) m.setLayoutProperty(id, "visibility", "none");
      else if (/road|rail|tunnel|bridge|transit|housenum|poi/.test(id)) m.setLayoutProperty(id, "visibility", "none");
      else if (/watername|water_name/.test(id)) m.setLayoutProperty(id, "visibility", "none");
      else if (/boundary/.test(id) && layer.type === "line") m.setPaintProperty(id, "line-color", "#b8ae98");
    } catch { /* layer without that property */ }
  }
}

export default function OceanMap({ layers, center = [196, 29], zoom = 3.4, interactive = true, focus, onClick, tooltip, cursor, tourId, locator = true }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const locBox = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const overlay = useRef<MapboxOverlay | null>(null);
  const cb = useRef({ onClick, tooltip, cursor });
  cb.current = { onClick, tooltip, cursor };
  // deck.gl layer instances can't be shared between maps, so each map builds its own cartography
  const [detail, setDetail] = useState(zoom >= DETAIL_ZOOM);
  const base = useMemo(() => makeBaseLayers(detail), [detail]);
  const top = useMemo(() => makeTopLabels(detail), [detail]);
  const [locLabels, setLocLabels] = useState<{ t: string; x: number; y: number }[]>([]);

  useEffect(() => {
    const m = new maplibregl.Map({
      container: box.current!, style: STYLE,
      center: [L(center[0]), center[1]], zoom, minZoom: 2, maxZoom: 8.5, interactive, attributionControl: { compact: true },
    });
    if (interactive) m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    m.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }), "bottom-right");
    m.on("load", () => { chartStyle(m); box.current?.setAttribute("data-loaded", "true"); });
    m.on("zoomend", () => setDetail(m.getZoom() >= DETAIL_ZOOM));
    const o = new MapboxOverlay({
      interleaved: false, layers: [...base, ...layers, ...top],
      onClick: (info: any) => { if (cb.current.onClick && info.coordinate) cb.current.onClick(info.coordinate[1], to360(info.coordinate[0]), info); },
      getTooltip: (info: any) => (cb.current.tooltip ? cb.current.tooltip(info) : null),
      getCursor: ({ isHovering }: any) => cb.current.cursor ?? (isHovering ? "pointer" : "grab"),
    });
    m.addControl(o as any);
    map.current = m; overlay.current = o;

    // Locator inset: the whole North Pacific, with the main map's view drawn on it.
    let lm: maplibregl.Map | null = null;
    if (locator && locBox.current) {
      lm = new maplibregl.Map({ container: locBox.current, style: STYLE, center: [L(185), 24], zoom: 0, minZoom: 0, interactive: false, attributionControl: false });
      const view = () => {
        const b = m.getBounds(), c = m.getCenter(), [w, sth, e, n] = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
        return { type: "FeatureCollection", features: [
          { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[w, sth], [e, sth], [e, n], [w, n], [w, sth]]] } },
          { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [c.lng, c.lat] } }] } as any;
      };
      // Set up as soon as the style is parsed: waiting for "load" also waits for tiles, which can lag behind the main map.
      let ready = false;
      const setup = () => {
        if (ready || !lm!.isStyleLoaded()) return;
        ready = true;
        chartStyle(lm!);
        for (const l of lm!.getStyle().layers ?? []) if (l.type === "symbol") lm!.setLayoutProperty(l.id, "visibility", "none");
        lm!.addSource("view", { type: "geojson", data: view() });
        lm!.addLayer({ id: "view-fill", type: "fill", source: "view", filter: ["==", "$type", "Polygon"], paint: { "fill-color": "#c2410c", "fill-opacity": 0.16 } });
        lm!.addLayer({ id: "view-line", type: "line", source: "view", filter: ["==", "$type", "Polygon"], paint: { "line-color": "#c2410c", "line-width": 1.4 } });
        lm!.addLayer({ id: "view-dot", type: "circle", source: "view", filter: ["==", "$type", "Point"],
          paint: { "circle-radius": 3, "circle-color": "#c2410c", "circle-stroke-color": "#fff", "circle-stroke-width": 1.2 } });
      };
      lm.on("styledata", setup);
      lm.on("load", setup);
      setLocLabels(LOCATOR_LABELS.map(([t, lat, lon]) => { const p = lm!.project([L(lon), lat]); return { t, x: p.x, y: p.y }; }));
      const redraw = () => (lm?.getSource("view") as maplibregl.GeoJSONSource | undefined)?.setData(view());
      // the main map can still be resizing (e.g. inside an opening drawer) when the inset first draws
      for (const ev of ["move", "resize", "load", "idle"] as const) m.on(ev, redraw);
    }
    return () => { m.remove(); lm?.remove(); };
  }, []);

  useEffect(() => { overlay.current?.setProps({ layers: [...base, ...layers, ...top] }); }, [layers, base, top]);
  useEffect(() => {
    if (focus && map.current) map.current.flyTo({ center: [L(focus.lon), focus.lat], zoom: focus.zoom, duration: focus.duration ?? 1600, essential: true });
  }, [focus?.key]);

  return (<>
    <div ref={box} className="map" data-tour={tourId} />
    {locator && (
      <div className="locator" aria-hidden>
        <div ref={locBox} className="map" />
        {locLabels.map((l) => <span key={l.t} style={{ left: l.x, top: l.y }}>{l.t}</span>)}
      </div>
    )}
  </>);
}

// ---------- always-on cartography: grid, place names ----------
const PLACES: [string, number, number, number, boolean][] = [
  // name, lat, lon(0-360), size class (1 inhabited island, 2 atoll / reef), shown at regional zoom too
  ["Kure", 28.42, 181.67, 2, false], ["Midway", 28.21, 182.63, 2, true], ["Pearl & Hermes", 27.85, 184.17, 2, false], ["Lisianski", 26.06, 186.04, 2, false],
  ["Laysan", 25.77, 188.27, 2, true], ["French Frigate Shoals", 23.75, 193.83, 2, true], ["Necker", 23.58, 195.30, 2, false], ["Nihoa", 23.06, 198.08, 2, false],
  ["Kauaʻi", 22.05, 200.48, 1, false], ["Oʻahu", 21.47, 202.02, 1, false], ["Maui", 20.8, 203.7, 1, false], ["Hawaiʻi", 19.6, 204.5, 1, false],
];
// labels drawn to the left of their dot, where a neighbour sits close on the right
const LEFT = new Set(["Kure", "French Frigate Shoals"]);
// at regional zoom the main islands sit too close to label one by one
const GROUP_LABELS = [{ t: "Main Hawaiian Islands", lat: 20.4, lon: 205.6 }];
const DETAIL_ZOOM = 4.6;
const LOCATOR_LABELS: [string, number, number][] = [["JAPAN", 41, 139], ["HAWAIʻI", 13.6, 204], ["USA", 40, 241]];
// The protected area's name sits just below its boundary at regional zoom, and inside it when zoomed in.
const makeTopLabels = (detail: boolean) => [
  new TextLayer({ id: "mpa-label", data: detail ? [[30.4, 181.8], [24.6, 191.0]] : [[20.6, 186.5]], getText: () => "Papahānaumokuākea\nprotected marine area",
    getPosition: (d: any) => [L(d[1]), d[0]], getSize: 11.5, getColor: [46, 107, 75, 255], lineHeight: 1.15, characterSet: "auto",
    fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 600, updateTriggers: { getPosition: detail } } as any),
];
const grid: number[][][] = [];
for (let lat = 15; lat <= 45; lat += 5) grid.push([[L(165), lat], [L(240), lat]]);
for (let lon = 165; lon <= 240; lon += 5) grid.push([[L(lon), 10], [L(lon), 50]]);
const gridLabels = [20, 25, 30, 35, 40].map((lat) => ({ t: `${lat}°N`, p: [L(170.6), lat + 0.35] }))
  .concat([175, 180, 185, 190, 195, 200, 205, 210, 215, 220].map((lon) => ({ t: lon <= 180 ? `${lon}°E` : `${360 - lon}°W`, p: [L(lon + 0.2), 15.4] })));
const makeBaseLayers = (detail: boolean) => [
  new PathLayer({ id: "graticule", data: grid, getPath: (d: any) => d, getColor: [120, 140, 150, 55], widthMinPixels: 0.6 }),
  new TextLayer({ id: "graticule-labels", data: gridLabels, getText: (d: any) => d.t, getPosition: (d: any) => d.p, getSize: 10.5,
    getColor: [90, 108, 118, 200], fontFamily: "IBM Plex Mono, monospace", getTextAnchor: "start", characterSet: "auto" } as any),
  new TextLayer({ id: "ocean-name", data: [{ t: "N O R T H   P A C I F I C   O C E A N", p: [L(201), 41.2] }], getText: (d: any) => d.t, getPosition: (d: any) => d.p,
    getSize: 15, getColor: [88, 122, 142, 150], fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 600, characterSet: "auto" } as any),
  new ScatterplotLayer({ id: "place-dots", data: PLACES, getPosition: (d: any) => [L(d[2]), d[1]], getRadius: (d: any) => (d[3] === 1 ? 2.6 : 2.2),
    radiusUnits: "pixels", getFillColor: [60, 60, 50, 220] }),
  new TextLayer({ id: "place-names", data: [...PLACES.filter((p) => detail || p[4]), ...(detail ? [] : GROUP_LABELS.map((g) => [g.t, g.lat, g.lon, 1, true]))],
    getText: (d: any) => d[0], getPosition: (d: any) => [L(d[2]), d[1]], getPixelOffset: (d: any) => [LEFT.has(d[0]) ? -7 : 7, 0],
    getSize: (d: any) => (d[3] === 1 ? 12.5 : 11), getTextAnchor: (d: any) => (LEFT.has(d[0]) ? "end" : "start"), getAlignmentBaseline: "center", getColor: [45, 45, 38, 230],
    fontFamily: '"Source Serif 4", Georgia, serif', fontWeight: 600, characterSet: "auto" } as any),
];

// ---------- data layers ----------
const SEA: [number, number, number] = [28, 93, 140];
const rings = (polys: number[][][][]) => polys.map((rs) => rs.map((r) => r.map(([x, y]) => [L(x), y])));

export const mpaLayers = (mpa: [number, number][][]) => [
  new PolygonLayer({ id: "mpa-fill", data: mpa, getPolygon: (r: any) => r.map(([x, y]: number[]) => [L(x), y]), getFillColor: [46, 107, 75, 30], stroked: false } as any),
  new PathLayer({ id: "mpa", data: mpa, getPath: (r: any) => r.map(([x, y]: number[]) => [L(x), y]), getColor: [46, 107, 75, 230], widthMinPixels: 1.6 } as any),
];

/** Where all lost nets together most likely are: 90 / 75 / 50 % regions. */
export function densityLayers(density: Record<string, number[][][][]> | undefined) {
  if (!density) return [];
  return [["0.9", 38], ["0.75", 62], ["0.5", 100]].map(([lvl, a]) => new PolygonLayer({
    id: `density-${lvl}`, data: rings(density[lvl as string] ?? []), getPolygon: (d: any) => d, getFillColor: [...SEA, a as number] as any,
    getLineColor: [...SEA, 150] as any, lineWidthMinPixels: lvl === "0.5" ? 1.2 : 0.6, stroked: true }));
}

/** Smooth ecological-priority bands (high / very high). */
export function priorityLayers(p: { high: number[][][][]; veryHigh: number[][][][] } | null) {
  if (!p) return [];
  return [
    new PolygonLayer({ id: "prio-high", data: rings(p.high), getPolygon: (d: any) => d, getFillColor: [46, 107, 75, 55], getLineColor: [46, 107, 75, 120], lineWidthMinPixels: 0.6, stroked: true }),
    new PolygonLayer({ id: "prio-vhigh", data: rings(p.veryHigh), getPolygon: (d: any) => d, getFillColor: [46, 107, 75, 95], stroked: false }),
  ];
}

export const kfmt = (v: number) => (v >= 1000 ? `$${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : `$${Math.round(v)}`);

/** Recovery hotspots: the top areas by reward money, as circles sized by value. */
export function hotspotLayers(areas: AreaLive[], selected: string | null, top = 8) {
  const pick: AreaLive[] = [];
  for (const a of [...areas].sort((x, y) => y.value - x.value)) {
    if (pick.length >= top) break;
    if (pick.every((t) => Math.hypot(t.center[0] - a.center[0], (t.center[1] - a.center[1]) * 0.87) > 3.2)) pick.push(a);
  }
  const max = Math.max(1, ...pick.map((a) => a.value));
  const r = (a: AreaLive) => 9 + 22 * Math.sqrt(a.value / max);
  return [
    new ScatterplotLayer<AreaLive>({ id: "hotspots", data: pick, pickable: true, getPosition: (a) => [L(a.center[1]), a.center[0]], getRadius: r, radiusUnits: "pixels",
      getFillColor: (a) => (a.id === selected ? [194, 65, 12, 230] : [255, 250, 244, 215]), stroked: true, getLineColor: [194, 65, 12, 255], lineWidthMinPixels: 2.2,
      updateTriggers: { getFillColor: [selected] } }),
    new TextLayer<AreaLive>({ id: "hotspot-labels", data: pick, pickable: true, getPosition: (a: AreaLive) => [L(a.center[1]), a.center[0]], getText: (a: AreaLive) => kfmt(a.value),
      getSize: 12, getColor: (a: AreaLive) => (a.id === selected ? [255, 255, 255, 255] : [154, 52, 18, 255]), fontFamily: "IBM Plex Mono, monospace", fontWeight: 600,
      characterSet: "auto", updateTriggers: { getColor: [selected] } } as any),
  ];
}

/** Invisible area polygons so a click anywhere on the map selects the recovery area under it. */
export function areaPicker(statics: AreaStatic[], live: Record<string, AreaLive>, selected: string | null, showGrid = false) {
  const maxV = Math.max(1, ...Object.values(live).map((a) => a.value));
  const sel = statics.find((a) => a.id === selected);
  return [
    new PolygonLayer<AreaStatic>({ id: "areas", data: statics, pickable: true, stroked: showGrid, filled: true,
      getPolygon: (a) => a.boundary.map(([x, y]) => [L(x), y]),
      getFillColor: (a) => (showGrid && live[a.id] ? [194, 65, 12, Math.round(20 + 150 * Math.sqrt(live[a.id].value / maxV))] : [0, 0, 0, 0]),
      getLineColor: [154, 52, 18, 90], lineWidthMinPixels: 0.6, autoHighlight: true, highlightColor: [16, 42, 58, 28],
      updateTriggers: { getFillColor: [showGrid, maxV] } }),
    ...(sel ? [new PathLayer({ id: "area-sel", data: [sel], getPath: (a: any) => [...a.boundary, a.boundary[0]].map(([x, y]: number[]) => [L(x), y]),
      getColor: [16, 42, 58, 230], widthMinPixels: 2.2 } as any)] : []),
  ];
}

/** One net's forecast: 90% / 50% regions, sample positions, and the path of its most likely position. */
export function cloudLayers(frame: Frame | null, track: number[][] = [], id = "cloud") {
  if (!frame) return [];
  const polys = (lvl: string) => rings(frame.contours?.[lvl] ?? []);
  return [
    new PolygonLayer({ id: `${id}-90`, data: polys("0.9"), getPolygon: (d: any) => d, getFillColor: [...SEA, 45] as any, getLineColor: [...SEA, 170] as any, lineWidthMinPixels: 1, stroked: true }),
    new PolygonLayer({ id: `${id}-50`, data: polys("0.5"), getPolygon: (d: any) => d, getFillColor: [...SEA, 110] as any, getLineColor: [16, 42, 58, 230] as any, lineWidthMinPixels: 1.4, stroked: true }),
    new ScatterplotLayer({ id: `${id}-pts`, data: frame.particles, getPosition: (d: number[]) => [L(d[1]), d[0]], getRadius: 1.5, radiusUnits: "pixels", getFillColor: [16, 42, 58, 150] }),
    ...(track.length > 1 ? [new PathLayer({ id: `${id}-track`, data: [track.map(([la, lo]) => [L(lo), la])], getPath: (d: any) => d, getColor: [16, 42, 58, 220], widthMinPixels: 1.6 })] : []),
  ];
}

export function pinLayer(points: { lat: number; lon: number; label: string; color: [number, number, number] }[], id = "pins") {
  return [
    new ScatterplotLayer({ id, data: points, getPosition: (d: any) => [L(d.lon), d.lat], getRadius: 7, radiusUnits: "pixels", getFillColor: (d: any) => d.color,
      stroked: true, getLineColor: [255, 255, 255], lineWidthMinPixels: 2.5 }),
    new TextLayer({ id: `${id}-t`, data: points, getPosition: (d: any) => [L(d.lon), d.lat], getText: (d: any) => d.label, getPixelOffset: [0, -18], getSize: 12.5,
      getColor: [19, 35, 46, 255], fontFamily: "IBM Plex Sans, sans-serif", fontWeight: 600, outlineWidth: 4, outlineColor: [255, 254, 250, 240],
      fontSettings: { sdf: true }, characterSet: "auto" } as any),
  ];
}

/** Median position of each forecast frame: the path a judge can follow. */
export function medianTrack(frames: Frame[], upto: number) {
  const out: number[][] = [];
  for (let i = 0; i <= upto && i < frames.length; i++) {
    const p = frames[i].particles; if (!p.length) continue;
    const la = p.map((x) => x[0]).sort((a, b) => a - b), lo = p.map((x) => x[1]).sort((a, b) => a - b);
    out.push([la[la.length >> 1], lo[lo.length >> 1]]);
  }
  return out;
}
