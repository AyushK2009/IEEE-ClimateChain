import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowRight, Building2, CalendarDays, Camera, CheckCircle2, ChevronRight, FileText, Leaf, Pause, Play, Search } from "lucide-react";
import { api, fmtDate, netName, usd, type AreaLive, type Forecast } from "../api";
import { go, useStore } from "../store";
import { useTour } from "../tour/TourProvider";
import { bus } from "../tour/bus";
import OceanMap, { areaPicker, cloudLayers, densityLayers, hotspotLayers, kfmt, medianTrack, mpaLayers, pinLayer, priorityLayers } from "../OceanMap";

type Layers = { density: boolean; hotspots: boolean; priority: boolean; grid: boolean };
let priorityCache: any = null;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const likelihood = (p: number) => (p >= 0.5 ? "Very likely here" : p >= 0.2 ? "Likely here" : "Possibly here");
const priorityWord = (p: number) => (p >= 4 ? "Very high" : p >= 2.5 ? "High" : p >= 1.6 ? "Moderate" : "Low");

/** Legend swatches drawn like the map symbols they explain. */
const SWATCHES: Record<string, ReactNode> = {
  likely: <ellipse cx="15" cy="8" rx="12" ry="6" fill="rgba(28,93,140,.43)" stroke="#102a3a" strokeWidth="1.4" />,
  possible: <ellipse cx="15" cy="8" rx="13" ry="6.5" fill="rgba(28,93,140,.18)" stroke="rgba(28,93,140,.67)" />,
  copies: <g fill="rgba(16,42,58,.75)">{[[5, 9], [9, 5], [12, 11], [15, 7], [18, 3], [20, 10], [24, 6], [26, 11]].map(([x, y]) => <circle key={`${x}${y}`} cx={x} cy={y} r="1.4" />)}</g>,
  path: <path d="M3 13 C 10 12, 14 4, 27 3" fill="none" stroke="#102a3a" strokeWidth="1.6" />,
  lost: <circle cx="15" cy="8" r="5.5" fill="#b42318" stroke="#fff" strokeWidth="2" />,
  protected: <path d="M3 13 C 2 4, 12 2, 17 5 S 28 5, 27 13 Z" fill="rgba(46,107,75,.16)" stroke="#2e6b4b" strokeWidth="1.4" />,
  density: <g><ellipse cx="15" cy="8" rx="13.5" ry="7" fill="rgba(28,93,140,.16)" /><ellipse cx="15" cy="8" rx="9" ry="4.8" fill="rgba(28,93,140,.26)" /><ellipse cx="15" cy="8" rx="4.5" ry="2.5" fill="rgba(28,93,140,.5)" /></g>,
  hotspot: <g><circle cx="15" cy="8" r="7" fill="rgba(255,254,250,.9)" stroke="#c2410c" strokeWidth="1.8" /><text x="15" y="10.6" fontSize="7.5" textAnchor="middle" fill="#c2410c" fontWeight="700">$</text></g>,
  priority: <path d="M3 12 C 4 4, 12 3, 16 5 S 27 4, 27 11 Z" fill="rgba(46,107,75,.42)" />,
  grid: <path d="M7 2 L14 2 L18 8 L14 14 L7 14 L3 8 Z M18 8 L25 8 L28 13" fill="rgba(194,65,12,.3)" stroke="rgba(194,65,12,.65)" />,
};
const Sw = ({ k }: { k: string }) => <svg className="sw" width="30" height="16" viewBox="0 0 30 16" aria-hidden>{SWATCHES[k]}</svg>;

export default function Explore({ area, net, isNew }: { area: string | null; net: number | null; isNew: boolean }) {
  const { st, market, areas, areaMap, mpa } = useStore();
  const tour = useTour();
  const [layers, setLayers] = useState<Layers>({ density: true, hotspots: true, priority: false, grid: false });
  const [prio, setPrio] = useState<any>(priorityCache);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [fi, setFi] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [detail, setDetail] = useState<any>(null);
  const [q, setQ] = useState("");
  const live = market?.areas ?? {};
  const entry = market?.entries.find((e) => e.netId === net) ?? null;

  useEffect(() => { if (!priorityCache) api.priorityLayer().then((p) => { priorityCache = p; setPrio(p); }); }, []);
  useEffect(() => bus.on("cmd:explore:layers", (l: Partial<Layers>) => setLayers((o) => ({ ...o, ...l }))), []);

  const areaOf = (id: number | null | undefined) => {
    if (!id) return null;
    let best: string | null = null, bp = 0;
    for (const [aid, a] of Object.entries(live)) { const n = a.nets.find((x) => x.netId === id); if (n && n.p > bp) { bp = n.p; best = aid; } }
    return best;
  };
  const areaId = area ?? areaOf(net);
  const A: AreaLive | null = areaId ? (live[areaId] ?? (areaMap[areaId] ? ({ ...areaMap[areaId], expected: 0, value: 0, nets: [] } as any) : null)) : null;
  const demoNet = tour.scenario?.netId ?? null;
  const demoEntry = market?.entries.find((e) => e.netId === demoNet) ?? null;
  const demoArea = demoEntry ? areaOf(demoNet) : null;

  // load the selected net
  useEffect(() => {
    setFc(null); setDetail(null); setPlaying(false);
    if (!net) return;
    let alive = true;
    Promise.all([api.net(net), api.forecast(net).catch(() => null)]).then(([d, f]) => {
      if (!alive) return;
      setDetail(d); setFc(f);
      if (f) setFi(Math.max(0, f.frames.findIndex((x) => x.day >= f.today)));
    });
    return () => { alive = false; };
  }, [net, market?.epoch]);
  useEffect(() => { if (net && detail) bus.emit("explore:net", net); }, [net, detail]);
  useEffect(() => { if (areaId && !net && A) bus.emit("explore:area", areaId); }, [areaId, net, !!A]);

  // forecast playback (also triggered by the guided demo)
  const todayIdx = fc ? Math.max(0, fc.frames.findIndex((x) => x.day >= fc.today)) : 0;
  const endIdx = fc ? Math.min(fc.frames.length - 1, todayIdx + 28) : 0;
  const play = () => { if (!fc) return; setFi(0); setPlaying(true); };
  const playRef = useRef(play); playRef.current = play;
  useEffect(() => bus.on("cmd:explore:play", () => playRef.current()), []);
  useEffect(() => {
    if (!playing || !fc) return;
    const t = setInterval(() => setFi((i) => { if (i >= endIdx) { setPlaying(false); bus.emit("explore:played"); return i; } return i + 1; }), 110);
    return () => clearInterval(t);
  }, [playing, fc, endIdx]);
  const frame = useMemo(() => {
    if (!fc) return null;
    const i = Math.min(fi, fc.frames.length - 1);
    for (let k = i; k >= 0; k--) if (fc.frames[k].contours) return { ...fc.frames[i], contours: fc.frames[k].contours };
    return fc.frames[i];
  }, [fc, fi]);
  const track = useMemo(() => (fc ? medianTrack(fc.frames, fi) : []), [fc, fi]);

  const deck = useMemo(() => {
    const out: any[] = [...mpaLayers(mpa)];
    if (layers.priority) out.push(...priorityLayers(prio));
    if (layers.density && !net) out.push(...densityLayers(market?.density));
    out.push(...areaPicker(areas, live, net ? null : areaId, layers.grid));
    if (layers.hotspots && !net) out.push(...hotspotLayers(Object.values(live), areaId));
    if (frame) out.push(...cloudLayers(frame, track));
    if (fc) out.push(...pinLayer([{ lat: fc.loss.lat, lon: fc.loss.lon, label: "Reported lost", color: [180, 35, 24] }]));
    return out;
  }, [layers, prio, market, areas, live, areaId, net, mpa, frame, track, fc]);

  const focus = useMemo(() => {
    if (net && fc) { const f = fc.frames[todayIdx]; const la = f.particles.map((p) => p[0]).sort((a, b) => a - b), lo = f.particles.map((p) => p[1]).sort((a, b) => a - b);
      return { lat: la[la.length >> 1], lon: lo[lo.length >> 1], zoom: 5.1, key: `n${net}-${fc.today}` }; }
    if (areaId && A) return { lat: A.center[0], lon: A.center[1], zoom: 5.1, key: `a${areaId}` };
    return { lat: 29.2, lon: 195, zoom: 3.55, key: "all" };
  }, [net, !!fc, areaId, !!A]);

  const tooltip = ({ object, layer }: any) => {
    if (!object || !layer || !["areas", "hotspots", "hotspot-labels"].includes(layer.id)) return null;
    const a: any = { ...(areaMap[object.id] ?? {}), ...(live[object.id] ?? {}) };
    if (!a.name) return null;
    return { className: "maplabel-tip", html: `<b>${cap(a.name)}</b><br/><span style="color:#6e7a81">${a.why}</span>` +
      (a.value ? `<br/><b>${usd(a.value)}</b> in rewards · about ${Math.max(1, Math.round(a.expected))} lost nets` : "") };
  };
  const onClick = (_la: number, _lo: number, info: any) => {
    const id = info?.object?.id;
    if (id && ["areas", "hotspots", "hotspot-labels"].includes(info.layer.id) && live[id]) go(`/explore?area=${id}`);
  };
  const top = useMemo(() => Object.values(live).sort((a, b) => b.value - a.value).slice(0, 6), [live]);
  const status = detail?.chain?.status;

  return (
    <div className="explore">
      <aside className="side">
        <div className="side-in fade" key={`${areaId}-${net}`}>
          {!areaId && !net && (<>
            <div className="kicker">Recovery map</div>
            <h2>Where are the lost nets?</h2>
            <p className="lede">Blue bands forecast where lost nets have drifted. Orange circles are recovery hotspots, sized by the reward money waiting there. Choose a hotspot to see its nets.</p>
            <div className="kv2">
              <div><div className="k">Lost nets tracked</div><div className="v">{market?.entries.length ?? "—"}</div></div>
              <div><div className="k">Rewards waiting</div><div className="v money">{usd(market?.total ?? 0)}</div></div>
            </div>
            {demoEntry && demoArea && (
              <div className="focus-card" data-tour="focus-area" onClick={() => go(`/explore?area=${demoArea}`)}>
                <div className="row"><div className="grow"><div className="tiny muted">Your demo net</div><b>{netName(demoEntry.netId)}</b> is most likely {demoEntry.area}</div>
                  <div style={{ textAlign: "right" }}><div className="money">{usd(demoEntry.bounty)}</div><ChevronRight size={16} /></div></div>
              </div>
            )}
            <div data-tour="hotspots">
              <div className="section-label">Recovery hotspots</div>
              {top.map((a) => (
                <div key={a.id} className="list-item" onClick={() => go(`/explore?area=${a.id}`)}>
                  <div className="t">{cap(a.name)}</div><div className="v money">{kfmt(a.value)}</div>
                  <div className="s">{a.why}</div><div className="s" style={{ textAlign: "right" }}>~{Math.max(1, Math.round(a.expected))} nets</div>
                </div>
              ))}
            </div>
            <form className="row" style={{ marginTop: 16, border: "1px solid var(--rule)", borderRadius: 8, padding: "6px 8px", background: "#fff" }}
              onSubmit={(e) => { e.preventDefault(); const n = parseInt(q.replace(/\D/g, "")); if (n) go(`/explore?net=${n}`); }}>
              <Search size={15} color="var(--muted)" /><input className="grow" style={{ border: "none", outline: "none" }} placeholder="Look up a net by number" value={q} onChange={(e) => setQ(e.target.value)} />
              <button className="btn sm" type="submit">Find</button>
            </form>
          </>)}

          {areaId && !net && A && (<>
            <div className="crumbs"><a onClick={() => go("/explore")}>All hotspots</a><ChevronRight size={13} /><span>Area</span></div>
            <div className="kicker">Recovery area</div>
            <h2>{cap(A.name)}</h2>
            <div className="why"><Leaf size={17} style={{ flex: "none", marginTop: 1 }} /><div><b>{priorityWord(A.priority)} ecological priority.</b> {A.why}.</div></div>
            <div className="kv2">
              <div><div className="k">Nets expected here</div><div className="v">~{Math.max(A.nets.length ? 1 : 0, Math.round(A.expected))}</div></div>
              <div><div className="k">Expected reward money</div><div className="v money">{usd(A.value)}</div></div>
            </div>
            <p className="tiny muted" style={{ margin: "6px 0 0" }}>Each net counts by its chance of being in this area, so these are averages rather than totals.</p>
            <div data-tour="area-nets">
              <div className="section-label">Nets likely in this area</div>
              {A.nets.length === 0 && <p className="small muted">No lost nets are likely to be here today.</p>}
              {A.nets.slice(0, 20).map((n) => {
                const e = market?.entries.find((x) => x.netId === n.netId);
                const mine = n.netId === demoNet;
                return (
                  <div className="list-item" key={n.netId} data-tour={`net-row-${n.netId}`} style={mine ? { background: "var(--sea-l)", margin: "0 -8px", padding: "11px 8px", borderRadius: 6 } : undefined}
                    onClick={() => go(`/explore?area=${areaId}&net=${n.netId}`)}>
                    <div className="t">{netName(n.netId)}{mine && <span className="tag active" style={{ marginLeft: 8 }}>demo net</span>}</div><div className="v money">{usd(n.bounty)}</div>
                    <div className="likely"><span className="bar"><i style={{ width: `${Math.min(100, n.p * 100)}%` }} /></span>{likelihood(n.p)}</div>
                    <div className="s" style={{ textAlign: "right" }}>{e ? `lost ${e.daysLost} days ago` : ""}</div>
                  </div>
                );
              })}
            </div>
          </>)}

          {net && (<>
            <div className="crumbs"><a onClick={() => go("/explore")}>All hotspots</a>{areaId && A && <><ChevronRight size={13} /><a onClick={() => go(`/explore?area=${areaId}`)}>{cap(A.name)}</a></>}<ChevronRight size={13} /><span>{netName(net)}</span></div>
            <div data-tour="net-status">
              <div className="kicker">Lost net</div>
              <div className="row" style={{ marginTop: 4 }}><h2>{netName(net)}</h2>{status && <span className={`tag ${String(status).toLowerCase()}`}>{status === "Lost" ? "Lost at sea" : status}</span>}</div>
              {detail && <div className="small muted">{detail.product} · owned by {detail.ownerName}</div>}
              {isNew && <div className="note good"><CheckCircle2 size={17} style={{ flex: "none" }} /><div><b>Loss recorded on the blockchain.</b> Status changed to Lost, and the {usd(st?.params.deposit ?? 200)} deposit moved into the reward fund.</div></div>}
            </div>
            {fc && frame && (<>
              <div className="section-label">Where is it now?</div>
              <div style={{ fontWeight: 600 }}>{fi === todayIdx ? `Most likely ${entry?.area ?? detail?.forecast?.area ?? ""}` : fi < todayIdx ? `Earlier: ${fmtDate(frame.date)}` : `Forecast for ${fmtDate(frame.date)}`}</div>
              <div className="timeline">
                {([["Lost", 0], ["Today", todayIdx], ["+1 wk", todayIdx + 7], ["+2 wk", todayIdx + 14], ["+4 wk", todayIdx + 28]] as [string, number][])
                  .filter(([, i], k, arr) => i < fc.frames.length && (k === 0 || i !== arr[k - 1][1])).map(([l, i]) => (
                  <button key={l} className={fi === i ? "on" : ""} onClick={() => { setPlaying(false); setFi(i); }}>{l}</button>))}
              </div>
              <div className="row" style={{ marginTop: 8 }}>
                <button className="btn sm" onClick={() => (playing ? setPlaying(false) : play())}>{playing ? <Pause size={13} /> : <Play size={13} />}{playing ? "Pause" : "Play the drift"}</button>
                <span className="tiny muted">Day {frame.day - fc.loss.day} after the loss · 1,000 simulated copies</span>
              </div>
            </>)}
            {entry && (
              <div className="reward" data-tour="reward">
                <div className="small" style={{ fontWeight: 600 }}>Reward for recovering it</div>
                <div className="amt">{usd(entry.bounty)}</div>
                <div className="bd">{entry.eligible ? <>The owner's forfeited {usd(entry.deposit)} deposit, plus {usd(entry.topUp)} from sponsors for where it's drifting.</> : <>For the first {st?.params.coolingDays} days after a loss, the reward is only the owner's {usd(entry.deposit)} deposit. Sponsor money is added after that.</>}</div>
              </div>
            )}
            {status === "Recovered" && <div className="note good"><CheckCircle2 size={17} style={{ flex: "none" }} />Recovered, and the crew was paid.</div>}
            {detail && (
              <div className="facts-list">
                {detail.loss && <div><CalendarDays size={16} /><div><b>Lost {fmtDate(detail.loss.date)}</b><span>{detail.loss.area}</span></div></div>}
                <div><Building2 size={16} /><div><b>{detail.ownerName}</b><span>owner (simulated company)</span></div></div>
                {A && <div><Leaf size={16} /><div><b>{priorityWord(A.priority)} ecological priority</b><span>{A.why}</span></div></div>}
              </div>
            )}
            {entry && <a className="btn signal lg block" data-tour="claim-btn" href={`#/claim?net=${net}`}><Camera size={17} />I recovered this net</a>}
            <a className="btn block" style={{ marginTop: 8 }} href={`#/net/${net}`}><FileText size={15} />Full record <ArrowRight size={14} /></a>
          </>)}
        </div>
      </aside>

      <div className="mapwrap">
        <OceanMap layers={deck} focus={focus} tooltip={tooltip} onClick={onClick} tourId="map" />
        {!net && (
          <div className="mapcard layers" data-tour="layers">
            <h4>Map layers</h4>
            <label><input type="checkbox" checked={layers.density} onChange={(e) => setLayers({ ...layers, density: e.target.checked })} /><i style={{ background: "rgba(28,93,140,.55)" }} />Where lost nets are</label>
            <label><input type="checkbox" checked={layers.hotspots} onChange={(e) => setLayers({ ...layers, hotspots: e.target.checked })} /><i style={{ border: "2px solid #c2410c", borderRadius: 6 }} />Recovery hotspots</label>
            <label><input type="checkbox" checked={layers.priority} onChange={(e) => setLayers({ ...layers, priority: e.target.checked })} /><i style={{ background: "rgba(46,107,75,.55)" }} />Ecological priority</label>
            <label><input type="checkbox" checked={layers.grid} onChange={(e) => setLayers({ ...layers, grid: e.target.checked })} /><i style={{ background: "rgba(194,65,12,.35)" }} />Scoring grid (H3 areas)</label>
          </div>
        )}
        <div className="mapcard legend" data-tour="legend">
          {net ? (<>
            <h4>Forecast for {netName(net)}</h4>
            <div className="li"><Sw k="likely" />Most likely here (half of the simulated copies)</div>
            <div className="li"><Sw k="possible" />Could be here (90% of copies)</div>
            <div className="li"><Sw k="copies" />Each dot is one simulated copy</div>
            <div className="li"><Sw k="path" />Most likely path so far</div>
            <div className="li"><Sw k="lost" />Where it was reported lost</div>
            <div className="li"><Sw k="protected" />Protected marine area</div>
          </>) : (<>
            <h4>Reading the map</h4>
            {layers.density && <div className="li"><Sw k="density" />Where lost nets are: darker bands hold more of them</div>}
            {layers.hotspots && <div className="li"><Sw k="hotspot" />Hotspot: circle size is the reward money waiting</div>}
            {layers.priority && <div className="li"><Sw k="priority" />Ecological priority: protected reefs and waters drifting into them</div>}
            {layers.grid && <div className="li"><Sw k="grid" />Scoring grid: reward money per H3 area</div>}
            <div className="li"><Sw k="protected" />Protected marine area</div>
          </>)}
        </div>
      </div>
    </div>
  );
}
