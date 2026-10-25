import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Building2, CalendarDays, Camera, Check, Lock, MapPinned, Package } from "lucide-react";
import { api, fmtDate, netName, usd, type Forecast } from "../api";
import { useStore } from "../store";
import OceanMap, { cloudLayers, medianTrack, mpaLayers, pinLayer } from "../OceanMap";
import { describeTx } from "../txinfo";

function RewardChart({ data }: { data: [number, number][] }) {
  const w = 560, h = 140, xs = data.map((d) => d[0]), ys = data.map((d) => d[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(...ys) * 1.15;
  const sx = (x: number) => 50 + ((x - x0) / Math.max(1, x1 - x0)) * (w - 60), sy = (y: number) => h - 20 - (y / y1) * (h - 30);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%">
      {[0, 0.5, 1].map((t) => <g key={t}><line x1={50} x2={w - 10} y1={sy((y1 * t) / 1.15)} y2={sy((y1 * t) / 1.15)} stroke="#e7e2d6" />
        <text x={44} y={sy((y1 * t) / 1.15) + 4} fontSize={11} textAnchor="end" fill="#6e7a81" fontFamily="IBM Plex Mono">{usd((y1 * t) / 1.15)}</text></g>)}
      <polyline points={data.map((d) => `${sx(d[0])},${sy(d[1])}`).join(" ")} fill="none" stroke="#c2410c" strokeWidth={2} />
      {data.map((d, i) => <circle key={i} cx={sx(d[0])} cy={sy(d[1])} r={2.4} fill="#c2410c" />)}
    </svg>
  );
}

export default function Passport({ id }: { id: number }) {
  const { st, market, mpa } = useStore();
  const [d, setD] = useState<any>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  useEffect(() => {
    api.net(id).then((x) => { setD(x); if (x.loss && x.chain.status === "Lost") api.forecast(id).then(setFc).catch(() => setFc(null)); else setFc(null); }).catch(() => setD(null));
  }, [id, market?.epoch]);
  const ti = fc ? Math.max(0, fc.frames.findIndex((x) => x.day >= fc.today)) : 0;
  const frame = useMemo(() => {
    if (!fc) return null;
    for (let k = ti; k >= 0; k--) if (fc.frames[k].contours) return { ...fc.frames[ti], contours: fc.frames[k].contours };
    return fc.frames[ti];
  }, [fc, ti]);
  const layers = useMemo(() => [...mpaLayers(mpa), ...cloudLayers(frame, fc ? medianTrack(fc.frames, ti) : []),
    ...(d?.loss ? pinLayer([{ lat: d.loss.lat, lon: d.loss.lon, label: "Reported lost", color: [180, 35, 24] }]) : [])], [mpa, frame, d, fc, ti]);
  if (!st || !d) return <div className="page"><div className="muted">Loading…</div></div>;

  const s = d.chain.status;
  const steps: [string, boolean][] = s === "Returned" ? [["Registered", true], ["In use", true], ["Retired", true]]
    : [["Registered", true], ["Lost at sea", !!d.loss], ["Claim filed", d.claims?.length > 0 || s === "ClaimPending" || s === "Recovered"], ["Recovered", s === "Recovered"]];
  const paid = d.claims?.find((c: any) => c.outcome === "accept");
  const byAddr = Object.fromEntries(Object.values(st.actors).map((a) => [a.address.toLowerCase(), a.name]));
  const name = (k: string) => st.actors[k]?.name ?? byAddr[String(k).toLowerCase()] ?? k;
  const events = d.timeline.map((t: any) => ({ t, x: describeTx({ actor: t.args.claimant ?? "", events: [{ event: t.event, args: t.args }] } as any, name) })).filter((e: any) => e.x);

  return (
    <div className="page">
      <a className="btn link small" onClick={() => history.back()}><ArrowLeft size={14} />Back</a>
      <div className="pp" style={{ marginTop: 12 }}>
        <div>
          <div className="card"><img src={api.tagUrl(id)} alt="QR tag" style={{ width: "100%", borderRadius: 6 }} /><div className="tiny muted" style={{ textAlign: "center", marginTop: 6 }}>The QR tag attached to this net</div></div>
          <div className="card facts-list" style={{ marginTop: 14 }}>
            <div><Building2 size={16} /><div><b>{d.ownerName}</b><span>owner (simulated company)</span></div></div>
            <div><Package size={16} /><div><b>{d.product}</b><span>registered {fmtDate(d.registeredDate)}</span></div></div>
            {d.loss && <div><CalendarDays size={16} /><div><b>Lost {fmtDate(d.loss.date)}</b><span>{d.loss.area}</span></div></div>}
            <div><Lock size={16} /><div><b>{usd(d.chain.deposit)} deposit</b><span>{s === "Active" ? "held, refunded when the net is retired" : s === "Returned" ? "refunded to the owner" : "moved to the reward fund"}</span></div></div>
          </div>
        </div>
        <div>
          <div className="card">
            <div className="kicker">Net passport</div>
            <div className="row" style={{ marginTop: 6 }}><h1 style={{ fontSize: 30 }}>{netName(id)}</h1><span className={`tag ${s.toLowerCase()}`}>{({ Active: "In use", Lost: "Lost at sea", ClaimPending: "Claim in review", Returned: "Retired" } as any)[s] ?? s}</span></div>
            <div className="steps-line">{steps.map(([l, done]) => <div key={l} className={`s ${done ? "done" : ""}`}><div className="d">{done && <Check size={14} />}</div>{l}</div>)}</div>
            {d.chain.unreported && <div className="note warn">Recovered without a loss report. This is recorded against the owner.</div>}
          </div>
          {paid && <div className="note good" style={{ fontSize: 15 }}><Check size={18} style={{ flex: "none" }} /><div><b>Recovered: {usd(paid.bounty)} paid to {name(paid.claimant)}</b><br /><span className="small">{fmtDate(paid.date)}, after every automated check passed</span></div></div>}
          {d.price && s === "Lost" && (
            <div className="reward">
              <div className="row"><div className="grow"><div className="small" style={{ fontWeight: 600 }}>Reward for recovering it</div><div className="amt">{usd(d.price.bounty)}</div></div>
                <a className="btn signal" href={`#/claim?net=${id}`}><Camera size={15} />I recovered this net</a></div>
              <div className="bd">{d.price.eligible ? `The owner's ${usd(d.price.deposit)} deposit plus ${usd(d.price.topUp)} from sponsors for where it's drifting.` : `For the first ${st.params.coolingDays} days after a loss, the reward is only the owner's deposit.`}</div>
            </div>
          )}
          {fc && (
            <div className="card" style={{ marginTop: 14 }}>
              <div className="row"><div className="grow"><h3>Where it probably is today</h3><div className="sub">{d.forecast?.area}</div></div><a className="btn sm" href={`#/explore?net=${id}`}><MapPinned size={13} />Open on the map</a></div>
              <div className="mapwrap" style={{ height: 250, borderRadius: 8, marginTop: 10 }}><OceanMap layers={layers} focus={d.forecast ? { lat: d.forecast.centroid[0], lon: d.forecast.centroid[1], zoom: 5, key: id } : null} /></div>
            </div>
          )}
          {d.prices?.length > 1 && <div className="card" style={{ marginTop: 14 }}><h3>Reward over time</h3><div className="sub">Recalculated every day as the forecast moves</div><RewardChart data={d.prices} /></div>}
          <div className="card" style={{ marginTop: 14 }}>
            <h3>History on the blockchain</h3>
            <div className="sub">Each line is a transaction anyone can verify</div>
            <div style={{ marginTop: 6 }}>
              {events.map(({ t, x }: any, i: number) => { const Ic = x.icon; return (
                <div className="feedrow" key={i} style={{ cursor: "default" }}><span className={`ic ${x.color}`}><Ic size={15} /></span>
                  <div><b>{x.title}</b><div className="small muted">{fmtDate(t.date)} · {x.sub}</div></div><span className="hash">block {t.block}</span></div>); })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
