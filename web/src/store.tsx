import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AreaStatic, type LedgerRow, type Market, type State, type Zone } from "./api";

type Toast = { kind: "ok" | "err" | "busy"; text: string } | null;
type Store = {
  st: State | null; market: Market | null; zones: Zone[]; zoneMap: Record<string, Zone>; mpa: [number, number][][];
  areas: AreaStatic[]; areaMap: Record<string, AreaStatic>;
  ledger: LedgerRow[]; busy: boolean; toast: Toast;
  refresh: () => Promise<void>;
  run: <T>(label: string, fn: () => Promise<T>) => Promise<T | undefined>;
};
const Ctx = createContext<Store>(null as any);
export const useStore = () => useContext(Ctx);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [st, setSt] = useState<State | null>(null);
  const [market, setMarket] = useState<Market | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [mpa, setMpa] = useState<[number, number][][]>([]);
  const [areas, setAreas] = useState<AreaStatic[]>([]);
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast>(null);

  const refresh = useCallback(async () => {
    const [s, m, l] = await Promise.all([api.state(), api.market(), api.ledger()]);
    setSt(s); setMarket(m); setLedger(l);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setToast({ kind: "err", text: `Can't reach the demo server: ${e.message}` }));
    api.zones().then((z) => setZones(z.zones));
    api.mpa().then(setMpa);
    api.areas().then(setAreas);
  }, [refresh]);

  const run = useCallback(async <T,>(label: string, fn: () => Promise<T>) => {
    setBusy(true); setToast({ kind: "busy", text: label });
    try {
      const r = await fn();
      await refresh();
      setToast({ kind: "ok", text: "Done" });
      setTimeout(() => setToast((t) => (t?.kind === "ok" ? null : t)), 1800);
      return r;
    } catch (e: any) {
      setToast({ kind: "err", text: e.message });
      setTimeout(() => setToast(null), 5000);
    } finally { setBusy(false); }
  }, [refresh]);

  const zoneMap = Object.fromEntries(zones.map((z) => [z.id, z]));
  const areaMap = Object.fromEntries(areas.map((a) => [a.id, a]));
  return <Ctx.Provider value={{ st, market, zones, zoneMap, mpa, areas, areaMap, ledger, busy, toast, refresh, run }}>{children}</Ctx.Provider>;
}

// --- tiny hash router: #/map, #/recover?net=12, #/net/12 ---
export function useRoute() {
  const parse = () => {
    const h = window.location.hash.replace(/^#/, "") || "/";
    const [path, q] = h.split("?");
    return { path, params: new URLSearchParams(q ?? "") };
  };
  const [r, setR] = useState(parse);
  useEffect(() => {
    const on = () => { const n = parse(); setR((o) => { if (o.path !== n.path) window.scrollTo(0, 0); return n; }); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}
export const go = (to: string) => { window.location.hash = to; };
