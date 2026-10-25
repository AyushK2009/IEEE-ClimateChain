import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowRight, Ban, CheckCircle2, CircleDashed, Link2, Lock, MapPin, ScanLine, ShieldCheck, Upload, XCircle } from "lucide-react";
import { api, fmtDate, latlon, netName, usd, type ClaimResult, type Forecast, type Identity } from "../api";
import { useStore } from "../store";
import { useTour } from "../tour/TourProvider";
import { bus } from "../tour/bus";
import OceanMap, { cloudLayers, medianTrack, mpaLayers, pinLayer } from "../OceanMap";

type Photo = { key: string; url: string; blob: Blob; staged: boolean };
const CHECK_LABEL: Record<string, string> = {
  identity: "The tag matches a registered net", eligibility: "The net is eligible for a reward", timing: "Claimed after the net was lost",
  reach: "The net could have drifted that far", cloud: "The spot matches the forecast", scene: "A real net is in the photo (AI check, runs locally)",
};

/** Plain-language version of a check's detail. The stored report keeps the technical text. */
function friendly(c: any): string {
  const d: string = c.detail ?? "";
  if (c.status === "skip") return "Doesn't apply: this net has no loss report to compare against.";
  switch (c.id) {
    case "identity": return "The QR tag matches this net's registration.";
    case "eligibility": return d.startsWith("Net was never") ? "It was never reported lost, so the reward is the owner's deposit." : "It's reported lost, and you aren't its owner.";
    case "reach": {
      const ok = d.match(/([\d,]+) km from the loss point; physical limit with margin ([\d,]+) km/);
      if (ok) return `Found ${ok[1]} km from where it was lost. A net could have drifted up to ${ok[2]} km by now.`;
      const bad = d.match(/Claimed spot is ([\d,]+) km .*farther than ([\d,]+) km/);
      if (bad) return `This spot is ${bad[1]} km from where the net was lost, but in our forecast no copy of it drifted more than ${bad[2]} km.`;
      return d;
    }
    case "cloud":
      if (d.includes("core")) return "Right where our forecast expected the net to be.";
      if (d.includes("90%")) return "Inside the area our forecast expected.";
      if (d.includes("edge")) return "At the edge of the forecast area: unusual, but possible.";
      return "Outside the forecast area. Held for review rather than rejected, because forecasts can be wrong.";
    case "scene": {
      const saw = d.match(/model saw: ([^;)]*)/)?.[1];
      if (c.status === "pass") return `The AI model saw real fishing gear in the photo${saw ? ` (${saw})` : ""}.`;
      if (c.status === "fail") return `The AI model saw only a tag on paper or a screen, with no net${saw ? ` (${saw})` : ""}.`;
      return d.includes("did not run") ? "The AI check couldn't run, so the claim is held for a second look." : "The AI model couldn't confirm a real net in the photo.";
    }
    default: return d;
  }
}
const STAGES = [["Reading the tag", ScanLine], ["Locking the reward", Lock], ["Running the checks", ShieldCheck], ["Recording the result", Link2]] as const;

export default function Claim({ net, crew: crew0 }: { net: number | null; crew?: string | null }) {
  const { st, market, busy, run, mpa } = useStore();
  const tour = useTour();
  const [crew, setCrew] = useState(crew0 === "crew_b" ? "crew_b" : "crew_a");
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [idn, setIdn] = useState<Identity | null>(null);
  const [reading, setReading] = useState(false);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [point, setPoint] = useState<{ lat: number; lon: number } | null>(null);
  const [stage, setStage] = useState(-1);
  const [res, setRes] = useState<ClaimResult | null>(null);
  const [tech, setTech] = useState(false);
  const resRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bus.emit("claim:ready", net); }, [net]);
  const exampleNets = useMemo(() => (net ? [net] : [...(market?.entries ?? [])].sort((a, b) => b.bounty - a.bounty).slice(0, 2).map((e) => e.netId)), [net, market?.entries.length]);
  const examples = useMemo(() => {
    const [a, b] = exampleNets;
    if (!a) return [];
    const list = [{ key: `r${a}`, tour: "evidence-real", net: a, variant: "recovered", title: "Recovered net with its tag", sub: "Expected result: accepted" }];
    if (b) list.push({ key: `r${b}`, tour: "", net: b, variant: "recovered", title: "Another recovered net", sub: "Expected result: accepted" });
    list.push({ key: `p${a}`, tour: "evidence-fake", net: a, variant: "printout", title: "Printed copy of a tag, no net", sub: "Fraud test: expected to be rejected" });
    return list;
  }, [exampleNets]);

  const choose = async (blob: Blob, key: string, staged: boolean) => {
    setPhoto({ key, url: URL.createObjectURL(blob), blob, staged });
    setIdn(null); setFc(null); setPoint(null); setRes(null); setStage(-1); setTech(false); setReading(true);
    try { setIdn(await api.identify(blob)); } finally { setReading(false); }
  };
  const pickExample = async (ex: (typeof examples)[number]) => choose(await (await fetch(api.stagedUrl(ex.net, ex.variant, 0))).blob(), ex.key, true);
  // the forecast loads after identification; the tour only moves on once it has rendered
  const [fcDone, setFcDone] = useState(false);
  useEffect(() => {
    setFcDone(false);
    if (!idn) return;
    if (idn.ok && idn.netId && idn.status !== "Active") api.forecast(idn.netId).then(setFc).catch(() => setFc(null)).finally(() => setFcDone(true));
    else setFcDone(true);
  }, [idn]);
  useEffect(() => { if (idn && fcDone) bus.emit("claim:identified", idn); }, [idn, fcDone]);
  useEffect(() => { if (point) bus.emit("claim:located", point); }, [point]);
  // during the guided demo the tour positions the page itself
  useEffect(() => { if (res && !tour.active) setTimeout(() => resRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 80); }, [res]);

  const today = useMemo(() => {
    if (!fc) return null;
    const i = Math.max(0, fc.frames.findIndex((f) => f.day >= fc.today));
    for (let k = i; k >= 0; k--) if (fc.frames[k].contours) return { ...fc.frames[i], contours: fc.frames[k].contours };
    return fc.frames[i];
  }, [fc]);
  const core = useMemo(() => {
    if (!today) return null;
    const la = today.particles.map((p) => p[0]).sort((a, b) => a - b), lo = today.particles.map((p) => p[1]).sort((a, b) => a - b);
    return { lat: la[la.length >> 1], lon: lo[lo.length >> 1] };
  }, [today]);
  const coreRef = useRef(core); coreRef.current = core;
  // a request to use the likely spot that arrives before the forecast is ready is applied once it is
  const wantCore = useRef(false);
  useEffect(() => bus.on("cmd:claim:useCore", () => { if (coreRef.current) setPoint(coreRef.current); else wantCore.current = true; }), []);
  useEffect(() => { if (core && wantCore.current) { wantCore.current = false; setPoint(core); } }, [core]);
  useEffect(() => bus.on("cmd:claim:openTech", () => setTech(true)), []);
  const track = useMemo(() => (fc ? medianTrack(fc.frames, Math.max(0, fc.frames.findIndex((f) => f.day >= fc.today))) : []), [fc]);
  const layers = useMemo(() => [...mpaLayers(mpa), ...cloudLayers(today, track),
    ...(fc ? pinLayer([{ lat: fc.loss.lat, lon: fc.loss.lon, label: "Reported lost", color: [180, 35, 24] }], "loss") : []),
    ...(point ? pinLayer([{ ...point, label: "Found here", color: [23, 112, 63] }], "found") : [])], [mpa, today, track, fc, point]);
  const focus = core ? { lat: core.lat, lon: core.lon, zoom: 5.0, key: `c${idn?.netId}` } : null;

  const identified = !!idn?.ok;
  const claimable = identified && ["Lost", "Active", "Recovered"].includes(idn!.status ?? "");
  const submit = async () => {
    if (!photo || !point) return;
    setRes(null); setStage(0);
    const t = setInterval(() => setStage((s) => Math.min(s + 1, 2)), 1100);
    const r = await run("Verifying the claim…", () => api.claim(photo.blob, crew, point.lat, point.lon));
    clearInterval(t); setStage(r?.ok ? 4 : -1);
    if (r) { setRes(r); requestAnimationFrame(() => bus.emit("claim:done", r)); }
  };
  if (!st) return null;

  return (
    <div className="claim">
      <div className="head row" style={{ alignItems: "flex-end" }}>
        <div className="grow">
          <div className="kicker">Claim a recovery</div>
          <h1>Recovered a lost net? Claim the reward.</h1>
          <p>Show the net's tag and where you found it. Automated checks verify the claim, and the smart contract pays you if it passes.</p>
        </div>
        <label className="field" style={{ margin: 0, width: 240 }}><span>Claiming as <span className="tag sim">simulated crew</span></span>
          <select value={crew} onChange={(e) => setCrew(e.target.value)} disabled={tour.active}>{["crew_a", "crew_b"].map((c) => <option key={c} value={c}>{st.actors[c]?.name}</option>)}</select>
        </label>
      </div>

      <div className="cstep">
        <div className="cstep-h"><div className={`n ${identified ? "done" : ""}`}>{identified ? <CheckCircle2 size={16} /> : 1}</div>
          <div><h3>Show the net's tag</h3><div className="small muted">Every registered net carries a QR tag. Reading it identifies exactly which net you recovered.</div></div></div>
        <div className="examples">
          {examples.map((ex) => (
            <button key={ex.key} className={`example ${photo?.key === ex.key ? "on" : ""}`} data-tour={ex.tour || undefined} onClick={() => pickExample(ex)}>
              <img src={api.stagedUrl(ex.net, ex.variant, 0)} alt="" />
              <div className="cap"><span className="tag staged" style={{ marginBottom: 4 }}>Staged example</span>{ex.title}<span>{ex.sub}</span></div>
            </button>
          ))}
        </div>
        <label className="upload"><Upload size={16} />Or upload your own photo of a tag
          <input type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => { const f = e.target.files?.[0]; if (f) choose(f, "up", false); }} /></label>
        {reading && <div className="note info"><span className="spin" />Reading the tag…</div>}
        {photo && idn && !idn.ok && <div className="note bad"><XCircle size={17} style={{ flex: "none" }} />{idn.error}</div>}
        {photo && identified && (
          <div className="identity fade" data-tour="identity">
            <img src={photo.url} alt="" />
            <div>
              <div className="small muted"><ScanLine size={13} style={{ verticalAlign: -2 }} /> Tag read {photo.staged && <span className="tag staged">staged photo</span>}</div>
              <div style={{ font: "600 22px/1.2 var(--serif)", margin: "4px 0 2px" }}>{netName(idn!.netId!)}</div>
              <div className="small ink2">{idn!.product} · owned by {idn!.ownerName}</div>
              {idn!.status === "Lost" && <div className="small" style={{ marginTop: 6 }}>Reported lost {idn!.lossDate && fmtDate(idn!.lossDate)} · reward <span className="money">{usd(idn!.bounty ?? 0)}</span></div>}
            </div>
          </div>
        )}
        {identified && idn!.status === "Recovered" && <div className="note bad"><Ban size={17} style={{ flex: "none" }} />Already recovered and paid. You can still submit: the smart contract will refuse a second payout.</div>}
        {identified && idn!.status === "Active" && <div className="note warn"><AlertTriangle size={17} style={{ flex: "none" }} />Never reported lost. If verified, you receive the owner's {usd(st.params.deposit)} deposit and the owner's record shows an unreported loss.</div>}
        {identified && idn!.status === "Returned" && <div className="note bad"><Ban size={17} style={{ flex: "none" }} />Retired at end of life, so it can't be claimed.</div>}
      </div>

      <div className={`cstep ${claimable ? "" : "locked"}`} data-tour="location">
        <div className="cstep-h"><div className={`n ${point ? "done" : ""}`}>{point ? <CheckCircle2 size={16} /> : 2}</div>
          <div className="grow"><h3>Where did you recover it?</h3><div className="small muted">Click the map. {fc ? "Blue is where the forecast expects this net today." : ""} The location is only used to check the claim. It never changes the reward.</div></div></div>
        <div className="mapwrap" style={{ height: 290, borderRadius: 8, border: "1px solid var(--rule)" }}>
          {claimable && <OceanMap layers={layers} focus={focus} center={[190, 28]} zoom={3.6} cursor="crosshair" onClick={(lat, lon) => setPoint({ lat: +lat.toFixed(3), lon: +lon.toFixed(3) })} />}
        </div>
        <div className="row wrap" style={{ marginTop: 10, justifyContent: "space-between" }}>
          <span className="small ink2"><MapPin size={14} style={{ verticalAlign: -2 }} /> {point ? latlon(point.lat, point.lon) : "No location chosen yet"}</span>
          <div className="row">
            {core && <button className="btn sm" data-tour="use-core" onClick={() => setPoint(core)}>Use the most likely spot</button>}
            {!fc && claimable && <button className="btn sm" onClick={() => setPoint({ lat: 30, lon: 200 })}>Use an example spot</button>}
            {fc && !tour.active && <button className="btn sm" onClick={() => setPoint({ lat: 21, lon: 226 })}>Try a spot far away (fraud test)</button>}
          </div>
        </div>
      </div>

      <div className={`cstep ${claimable && point ? "" : "locked"}`}>
        <div className="cstep-h"><div className="n">3</div><div className="grow"><h3>Get verified and paid</h3><div className="small muted">The reward is locked the moment you submit, so later price changes don't affect you.</div></div>
          <button className="btn signal lg" data-tour="submit" disabled={busy || !claimable || !point || !!res} onClick={submit}>{res ? "Claim submitted" : "Submit claim"}</button></div>
        {stage >= 0 && (
          <div className="pipeline">
            {STAGES.map(([t, Ic], i) => <div key={t} className={`pnode ${i < stage ? "done" : i === stage ? "now" : ""}`}>{i < stage ? <CheckCircle2 size={20} /> : i === stage ? <span className="spin" /> : <Ic size={20} />}{t}</div>)}
          </div>
        )}
        <div ref={resRef} style={{ scrollMarginTop: 76 }}>{res && <Outcome r={res} crewName={st.actors[crew]?.name ?? crew} fund={st.pool.poolAvailable} tech={tech} setTech={setTech} />}</div>
      </div>
    </div>
  );
}

function Outcome({ r, crewName, fund, tech, setTech }: { r: ClaimResult; crewName: string; fund: number; tech: boolean; setTech: (b: boolean) => void }) {
  if (!r.ok) {
    const refused = r.stage === "contract";
    return (
      <div className={`outcome ${refused ? "refused" : "reject"} fade`}>
        <div className="row" data-tour="outcome-head"><Ban size={28} /><div className="big">{refused ? "The blockchain refused this claim" : "No claim was created"}</div></div>
        <p style={{ marginTop: 8, fontSize: 15.5 }}>{refused ? `${netName(r.netId!)} has already been recovered and paid. The smart contract never pays for the same net twice, whatever the photo shows.` : r.error}</p>
      </div>
    );
  }
  const failed = r.report.checks.find((c: any) => c.status === "fail");
  const flagged = r.report.checks.find((c: any) => c.status === "flag");
  return (
    <div className={`outcome ${r.outcome} fade`}>
      <div data-tour="outcome-head">
        {r.outcome === "accept" && (<>
          <div className="row"><CheckCircle2 size={28} color="var(--ok)" /><div className="big">Paid {usd(r.paid!)} to {crewName}</div></div>
          <p style={{ marginTop: 6, fontSize: 15.5 }}>The smart contract released the reward automatically. {netName(r.netId!)} is now <b>Recovered</b> and can never be claimed again. Reward fund now: <span className="money">{usd(fund)}</span>.</p>
        </>)}
        {r.outcome === "reject" && (<>
          <div className="row"><XCircle size={28} color="var(--alert)" /><div className="big">Claim rejected</div></div>
          <div className="why2"><b>Why:</b> {failed ? friendly(failed) : ""}</div>
          <p style={{ marginTop: 10 }} className="ink2">The locked {usd(r.bountyLocked!)} went back to the reward fund, and {netName(r.netId!)} is still listed as lost.</p>
        </>)}
        {r.outcome === "flag" && (<>
          <div className="row"><AlertTriangle size={28} color="var(--signal)" /><div className="big">Held for review</div></div>
          <div className="why2"><b>Why:</b> {flagged ? friendly(flagged) : ""}</div>
          <p style={{ marginTop: 10 }} className="ink2">The {usd(r.bountyLocked!)} reward stays locked until the claim is resolved.</p>
        </>)}
      </div>
      <ul className="checks" data-tour="checks">
        {r.report.checks.map((c: any, i: number) => (
          <li key={c.id} className="reveal" style={{ animationDelay: `${0.15 * i}s` }}>
            {c.status === "pass" ? <CheckCircle2 size={19} color="var(--ok)" /> : c.status === "fail" ? <XCircle size={19} color="var(--alert)" /> : c.status === "flag" ? <AlertTriangle size={19} color="var(--signal)" /> : <CircleDashed size={19} color="var(--muted)" />}
            <div><b>{CHECK_LABEL[c.id] ?? c.name}</b><span>{friendly(c)}</span></div>
          </li>
        ))}
      </ul>
      <details className="tech" data-tour="tx" open={tech} onToggle={(e) => setTech((e.target as HTMLDetailsElement).open)}>
        <summary><Link2 size={15} />Blockchain record of this claim</summary>
        <div className="txline"><Lock size={15} color="var(--signal)" /><div><b>Reward locked</b> · block {r.blockSubmit?.toLocaleString()}</div><span className="hash">{r.txSubmit?.slice(0, 18)}…</span></div>
        <div className="txline"><CheckCircle2 size={15} color="var(--ok)" /><div><b>{r.outcome === "accept" ? "Verified and paid" : r.outcome === "reject" ? "Rejected, reward released" : "Held for review"}</b> · block {r.blockResolve?.toLocaleString()}</div><span className="hash">{r.txResolve?.slice(0, 18)}…</span></div>
        <div className="tiny muted" style={{ marginTop: 8 }}>Contract <span className="mono">{r.contract}</span> on a local test blockchain (play money). Fingerprint of the full verification report: <span className="mono">{r.reportHash?.slice(0, 18)}…</span></div>
      </details>
      <div className="row" style={{ marginTop: 14 }}>
        <a className="btn" href={`#/net/${r.netId}`}>The net's full record <ArrowRight size={14} /></a>
        <a className="btn" href="#/explore">Back to the map</a>
      </div>
    </div>
  );
}
