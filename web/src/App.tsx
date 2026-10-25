import { Anchor, CalendarDays, Camera, Link2, Map as MapIcon, RotateCcw, Ship } from "lucide-react";
import { useState } from "react";
import { api, fmtDate } from "./api";
import { StoreProvider, useRoute, useStore } from "./store";
import { TourProvider, useTour } from "./tour/TourProvider";
import Home from "./pages/Home";
import Explore from "./pages/Explore";
import Fleet from "./pages/Fleet";
import Claim from "./pages/Claim";
import Records from "./pages/Records";
import Passport from "./pages/Passport";

export const APP_NAME = "Ghost Gear Recovery";
const LINKS = [["/explore", "Recovery map", MapIcon], ["/claim", "Claim a recovery", Camera], ["/fleet", "My fleet", Ship]] as const;

function Clock() {
  const { st, busy, run } = useStore();
  const [confirm, setConfirm] = useState(false);
  if (!st) return null;
  return (
    <div className="clock" title="The demo replays real 2021 ocean currents. Move the date forward to watch nets drift and rewards update.">
      <CalendarDays size={13} /><b>{fmtDate(st.date)}</b>
      <button disabled={busy} onClick={() => run("Moving forward one day…", () => api.advance(1))}>+1 day</button>
      <button disabled={busy} onClick={() => run("Moving forward one week…", () => api.advance(7))}>+1 week</button>
      <button disabled={busy} title="Restore the demo world to its starting point" onClick={() => {
        if (!confirm) { setConfirm(true); setTimeout(() => setConfirm(false), 3000); return; }
        setConfirm(false); run("Restoring the demo world…", api.reset);
      }}>{confirm ? "Confirm reset" : <RotateCcw size={12} style={{ verticalAlign: -2 }} />}</button>
    </div>
  );
}

function Nav({ path }: { path: string }) {
  const tour = useTour();
  return (
    <nav className="nav">
      <a className="wordmark" href="#/"><Anchor size={20} />{APP_NAME}</a>
      <div className="nav-links">
        {LINKS.map(([to, label, Icon]) => <a key={to} href={`#${to}`} className={path.startsWith(to) ? "on" : ""}><Icon size={15} />{label}</a>)}
      </div>
      <div className="nav-right">
        <a className={`quiet ${path.startsWith("/records") ? "on" : ""}`} href="#/records"><Link2 size={14} />Records</a>
        {tour.active
          ? <div className="demo-pill">Guided demo · {tour.chapter} <button onClick={tour.start}>Restart</button><button onClick={tour.exit}>Exit</button></div>
          : <><button className="btn sm" onClick={tour.start}>Start guided demo</button><Clock /></>}
      </div>
    </nav>
  );
}

function Toast() {
  const { toast } = useStore();
  const tour = useTour();
  if (!toast || (tour.active && toast.kind !== "err")) return null;
  return <div className={`toast ${toast.kind}`}>{toast.kind === "busy" && <span className="spin" />}{toast.text}</div>;
}

function Shell() {
  const { path, params } = useRoute();
  const num = (k: string) => (params.get(k) ? +params.get(k)! : null);
  let page;
  if (path === "/" || path === "") page = <Home />;
  else if (path.startsWith("/explore") || path.startsWith("/map")) page = <Explore area={params.get("area")} net={num("net")} isNew={params.get("new") === "1"} />;
  else if (path.startsWith("/claim") || path.startsWith("/recover")) page = <Claim key={`claim-${params.get("net")}`} net={num("net")} crew={params.get("crew")} />;
  else if (path.startsWith("/fleet")) page = <Fleet />;
  else if (path.startsWith("/records") || path.startsWith("/ledger")) page = <Records />;
  else if (path.startsWith("/net/")) page = <Passport id={+path.split("/")[2]} />;
  else page = <Home />;
  return <><Nav path={path} />{page}<Toast /></>;
}

export default function App() {
  return <StoreProvider><TourProvider><Shell /></TourProvider></StoreProvider>;
}
