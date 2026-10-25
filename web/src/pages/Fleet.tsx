import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Lock, MapPin, QrCode, ShoppingCart, Undo2, Waves, X } from "lucide-react";
import { api, fmtDate, latlon, netName, usd, type OwnedNet } from "../api";
import { go, useStore } from "../store";
import { useTour } from "../tour/TourProvider";
import { bus } from "../tour/bus";
import OceanMap, { mpaLayers, pinLayer } from "../OceanMap";

const ORGS = ["kai", "pacific", "northstar", "aleutian"];
const PRODUCTS = ["Gillnet panel, 50 m", "Purse seine section", "Midwater trawl net", "Longline set (lines + floats)"];
const TABS = [["all", "All"], ["Active", "In use"], ["Lost", "Lost at sea"], ["Recovered", "Recovered"], ["Returned", "Retired"]] as const;
const LABEL: Record<string, string> = { Active: "In use", Lost: "Lost at sea", ClaimPending: "Claim in review", Recovered: "Recovered", Returned: "Retired" };

export default function Fleet() {
  const { st, busy, run, mpa } = useStore();
  const tour = useTour();
  const sc = tour.active ? tour.scenario : null;
  const [org, setOrg] = useState(sc?.org ?? "kai");
  const [product, setProduct] = useState(sc?.product ?? PRODUCTS[0]);
  const [count, setCount] = useState(sc?.count ?? 6);
  const [nets, setNets] = useState<OwnedNet[]>([]);
  const [tab, setTab] = useState("all");
  const [fresh, setFresh] = useState<number[]>([]);
  const [lossFor, setLossFor] = useState<number | null>(null);
  const [point, setPoint] = useState<{ lat: number; lon: number } | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => { if (sc) { setOrg(sc.org); setProduct(sc.product); setCount(sc.count); } }, [sc?.netId]);
  // refetch on every state refresh: a demo restart restores the seed without changing the epoch
  const load = () => api.orgNets(org).then((ns) => { setNets(ns); setFresh((f) => f.filter((id) => ns.some((n) => n.id === id))); });
  useEffect(() => { load(); }, [org, st]);
  useEffect(() => { if (fresh.length && nets.some((n) => n.id === fresh[0])) bus.emit("fleet:registered", fresh); }, [fresh, nets]);
  useEffect(() => { if (lossFor) bus.emit("fleet:lossDrawer", lossFor); }, [lossFor]);

  const counts = useMemo(() => nets.reduce((a: Record<string, number>, n) => ({ ...a, [n.status]: (a[n.status] ?? 0) + 1 }), {}), [nets]);
  const order = (n: OwnedNet) => (fresh.includes(n.id) ? 0 : n.status === "Lost" ? 1 : n.status === "Active" ? 2 : 3);
  const shown = useMemo(() => nets.filter((n) => tab === "all" || n.status === tab || (tab === "Lost" && n.status === "ClaimPending"))
    .sort((a, b) => order(a) - order(b) || (order(a) === 0 ? a.id - b.id : b.id - a.id)), [nets, tab, fresh]);
  const mapLayers = useMemo(() => [...mpaLayers(mpa), ...(point ? pinLayer([{ ...point, label: "Lost here", color: [180, 35, 24] }]) : [])], [mpa, point]);
  const first = fresh.length ? nets.find((n) => n.id === fresh[0]) : null;
  if (!st) return null;
  const orgName = st.actors[org]?.name ?? org;
  const dep = st.params.deposit;

  const buy = async () => {
    const r = await run(`Registering ${count} nets…`, () => api.checkout(org, count, product));
    if (r) { await load(); setFresh(r.ids); setTab("all"); setNote(null); }
  };
  const openLoss = (id: number) => {
    setLossFor(id);
    const s = tour.scenario;
    setPoint(s && s.netId === id ? { lat: s.loss.lat, lon: s.loss.lon } : null);
    requestAnimationFrame(() => document.querySelector('[data-tour="loss-drawer"]')?.scrollIntoView({ block: "center", behavior: "smooth" }));
  };
  const report = async () => {
    if (!lossFor || !point) return;
    const id = lossFor;
    const r = await run(`Reporting ${netName(id)} lost…`, () => api.loss(id, point.lat, point.lon));
    if (r) { bus.emit("fleet:lost", id); go(`/explore?net=${id}&new=1`); }
  };
  const retire = async (id: number) => {
    const r = await run(`Retiring ${netName(id)}…`, () => api.returnNet(id));
    if (r) { setNote(`${netName(id)} was returned to the supplier and your ${usd(r.refund)} deposit was refunded.`); await load(); }
  };

  return (
    <div className="page">
      <div className="head row" style={{ alignItems: "flex-end" }}>
        <div className="grow">
          <div className="kicker">My fleet · simulated company</div>
          <h1>{orgName}'s nets</h1>
          <p>Buy nets with a deposit, follow any that are lost, and get the deposit back when a net is retired.</p>
        </div>
        {!tour.active && <label className="field" style={{ margin: 0, width: 230 }}><span>Viewing as</span>
          <select value={org} onChange={(e) => { setOrg(e.target.value); setFresh([]); setLossFor(null); }}>{ORGS.map((o) => <option key={o} value={o}>{st.actors[o]?.name}</option>)}</select></label>}
      </div>

      <div className="flow">
        <div className="card checkout" data-tour="checkout">
          <div className="row"><ShoppingCart size={18} /><h3 className="grow">Buy nets</h3><span className="tag sim">from NetWorks Supply Co.</span></div>
          <p className="small muted" style={{ margin: "6px 0 14px" }}>Registration happens at checkout: each net gets a blockchain passport, a printed QR tag, and a refundable deposit.</p>
          <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
            <label className="field grow" style={{ margin: 0 }}><span>Product</span><select value={product} onChange={(e) => setProduct(e.target.value)} disabled={tour.active}>{PRODUCTS.map((p) => <option key={p}>{p}</option>)}</select></label>
            <label className="field" style={{ margin: 0, width: 96 }}><span>Quantity</span><input type="number" min={1} max={40} value={count} disabled={tour.active} onChange={(e) => setCount(Math.max(1, Math.min(40, +e.target.value || 1)))} /></label>
          </div>
          <div style={{ marginTop: 12 }}>
            <div className="line"><span>Refundable deposit ({count} × {usd(dep)})</span><b className="num">{usd(count * dep)}</b></div>
            <div className="line"><span className="muted">Returned when each net is retired. Funds the recovery reward if a net is lost.</span></div>
          </div>
          <button className="btn primary lg block" data-tour="buy" disabled={busy} onClick={buy} style={{ marginTop: 12 }}>Complete purchase · register {count} nets</button>
          {first && (
            <div className="passport-card fade" data-tour="passport">
              <img src={api.tagUrl(first.id)} alt="QR tag" />
              <div>
                <div className="kicker" style={{ color: "var(--ok)" }}>Passport created</div>
                <div style={{ font: "600 20px/1.2 var(--serif)", marginTop: 4 }}>{netName(first.id)}</div>
                <dl><dt>Owner</dt><dd>{orgName}</dd><dt>Type</dt><dd>{first.product}</dd><dt>Deposit</dt><dd>{usd(dep)} held</dd><dt>Status</dt><dd>In use</dd></dl>
                <div className="tiny muted" style={{ marginTop: 6 }}>+ {fresh.length - 1} more passports · <QrCode size={11} style={{ verticalAlign: -1 }} /> tags ready to print</div>
              </div>
            </div>
          )}
        </div>
        <div>
          <div className="figures" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div><div className="k">In use</div><div className="v">{counts.Active ?? 0}</div></div>
            <div><div className="k">Deposits held</div><div className="v">{usd((counts.Active ?? 0) * dep)}</div></div>
          </div>
          <div className="figures" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 10 }}>
            <div><div className="k">Lost at sea</div><div className="v" style={{ color: "var(--alert)" }}>{(counts.Lost ?? 0) + (counts.ClaimPending ?? 0)}</div></div>
            <div><div className="k">Recovered by crews</div><div className="v" style={{ color: "var(--ok)" }}>{counts.Recovered ?? 0}</div></div>
          </div>
          <div className="card" style={{ marginTop: 10 }}>
            <h3 style={{ fontSize: 15 }}>How the deposit works</h3>
            <div className="small ink2" style={{ marginTop: 6 }}><Lock size={13} style={{ verticalAlign: -2 }} /> Held by the smart contract while a net is in use.<br />
              <Undo2 size={13} style={{ verticalAlign: -2 }} /> Refunded when you retire the net.<br />
              <Waves size={13} style={{ verticalAlign: -2 }} /> If you report a net lost, it becomes part of the reward for recovering it.</div>
          </div>
        </div>
      </div>

      {lossFor && (
        <div className="drawer fade" data-tour="loss-drawer">
          <div className="row"><h3 className="grow">Report {netName(lossFor)} lost</h3><button className="btn sm" onClick={() => { setLossFor(null); setPoint(null); }}><X size={14} /></button></div>
          <p className="small muted" style={{ margin: "4px 0 12px" }}>Click where the net was lost. We'll start forecasting where it drifts and post a reward for recovering it.</p>
          <div className="mapwrap" style={{ height: 280, borderRadius: 8, border: "1px solid var(--rule)" }}>
            <OceanMap layers={mapLayers} center={[188, 25]} zoom={3.6} cursor="crosshair" onClick={(lat, lon) => setPoint({ lat: +lat.toFixed(2), lon: +lon.toFixed(2) })} />
          </div>
          <div className="row wrap" style={{ marginTop: 12, justifyContent: "space-between" }}>
            <span className="small ink2"><MapPin size={14} style={{ verticalAlign: -2 }} /> {point ? `${latlon(point.lat, point.lon)} · ${fmtDate(st.date)}` : "No location chosen yet"}</span>
            <button className="btn primary" data-tour="loss-confirm" disabled={busy || !point} onClick={report}><Waves size={15} />Report lost and start the forecast</button>
          </div>
        </div>
      )}
      {note && <div className="note good"><span className="grow">{note}</span><X size={15} style={{ cursor: "pointer" }} onClick={() => setNote(null)} /></div>}

      <div className="row" style={{ margin: "26px 0 12px" }}>
        <h2 className="grow" style={{ fontSize: 22 }}>All nets</h2>
        <div className="tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}</div>
      </div>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table className="inv">
          <thead><tr><th>Net</th><th>Type</th><th>Status</th><th>Details</th><th style={{ textAlign: "right" }}>Action</th></tr></thead>
          <tbody>
            {shown.slice(0, 120).map((n) => (
              <tr key={n.id} className={fresh.includes(n.id) ? "new" : ""}>
                <td><a href={`#/net/${n.id}`} style={{ fontWeight: 600, color: "var(--ink)" }}>{netName(n.id)}</a>{fresh.includes(n.id) && <span className="tag recovered" style={{ marginLeft: 8 }}>new</span>}</td>
                <td className="ink2">{n.product}</td>
                <td><span className={`tag ${n.status.toLowerCase()}`}>{LABEL[n.status] ?? n.status}</span></td>
                <td className="small ink2">
                  {n.status === "Active" && <>Registered {fmtDate(n.registeredDate)} · {usd(dep)} deposit held</>}
                  {(n.status === "Lost" || n.status === "ClaimPending") && <>Probably {n.area}{n.bounty ? <> · reward <span className="money">{usd(n.bounty)}</span></> : null}</>}
                  {n.status === "Recovered" && <>Recovered by a crew{n.paid ? <> · paid {usd(n.paid)}</> : null}</>}
                  {n.status === "Returned" && <>Retired · deposit refunded</>}
                </td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {n.status === "Active" && <>
                    <button className="btn sm alert" data-tour={`report-${n.id}`} onClick={() => openLoss(n.id)}><Waves size={13} />Report lost</button>
                    <button className="btn sm" style={{ marginLeft: 6 }} disabled={busy || tour.active} onClick={() => retire(n.id)}><Undo2 size={13} />Retire</button>
                  </>}
                  {(n.status === "Lost" || n.status === "ClaimPending") && <a className="btn sm" href={`#/explore?net=${n.id}`}>Follow its drift <ArrowRight size={13} /></a>}
                  {(n.status === "Recovered" || n.status === "Returned") && <a className="btn sm" href={`#/net/${n.id}`}>View record</a>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
