// Client for the Python API. Longitudes from the API are 0-360.
import { replayUrl } from "./replay";
export type Actor = { name: string; address: string; balance: number; kind: string };
export type State = {
  today: number; date: string; dataRange: [string, string]; epoch: number;
  pool: { balance: number; depositsHeld: number; poolAvailable: number; poolReserved: number };
  advertised: number; lambda: number | null; counts: Record<string, number>;
  deployment: { chainId: number; usd: string; escrow: string; rpc: string };
  network: string; actors: Record<string, Actor>;
  featuredSuggestion: { lat: number; lon: number; why: string } | null;
  vision: { model: string; available: boolean };
  params: { deposit: number; coolingDays: number; lambdaCap: number; budgetFraction: number; formula: string };
};
export type Zone = { id: string; lat: number; lon: number; boundary: [number, number][]; protected: number;
  encounter60: number; productivity: number; priority: number };
export type Entry = { netId: number; owner: string; deposit: number; lossDay: number; daysLost: number;
  eligible: boolean; weight: number; priority: number; zones: { zone: string; p: number }[]; modalZone: string | null;
  topUp: number; bounty: number; change: number; history: [number, number][]; product: string;
  centroid: [number, number]; area: string };
export type ZoneAgg = { expected: number; value: number; nets: { netId: number; p: number }[] };
export type AreaStatic = { id: string; boundary: [number, number][]; center: [number, number]; priority: number; name: string; why: string };
export type AreaLive = { expected: number; value: number; nets: { netId: number; p: number; bounty: number }[]; center: [number, number];
  priority: number; name: string; why: string; id: string };
export type Identity = { ok: boolean; error?: string; netId?: number; status?: string; product?: string; owner?: string; ownerName?: string;
  lossDate?: string; area?: string; bounty?: number };
export type OwnedNet = { id: number; product: string; status: string; registeredDate: string; featured: boolean; lossDate?: string;
  daysLost?: number; area?: string; bounty?: number | null; paid?: number };
export type Market = { day: number; date: string; epoch: number; root: string; total: number; lambda: number;
  sponsorAvailable: number; entries: Entry[]; zones: Record<string, ZoneAgg>; areas: Record<string, AreaLive>; hotspots: [number, number, number][];
  density?: Record<string, number[][][][]> };
export type Scenario = { org: string; product: string; count: number; netId: number; loss: { lat: number; lon: number }; fastForwardDays: number; crew: string; seeded: boolean };
export type Frame = { day: number; date: string; particles: [number, number][];
  contours: Record<string, number[][][][]> | null; beached?: number; outside?: number; reward?: number; area?: string; priority?: number };
export type Forecast = { netId: number; loss: { day: number; lat: number; lon: number }; today: number; frames: Frame[]; particles: number };
export type Story = { loss: { lat: number; lon: number; date: string; area: string }; frames: Frame[] };
export type ClaimResult = { ok: boolean; stage?: string; error?: string; claimId?: number; netId?: number;
  outcome?: "accept" | "reject" | "flag"; bountyLocked?: number; paid?: number; report?: any; reportHash?: string;
  txSubmit?: string; txResolve?: string; blockSubmit?: number; blockResolve?: number; contract?: string; netStatus?: string; claimantBalance?: number };
export type LedgerRow = { seq: number; day: number; date: string; tx: string; block: number; actor: string;
  label: string; gas: number; events: { event: string; args: Record<string, any> }[] };

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* not json */ }
    throw new Error(msg);
  }
  return r.json();
}
const post = (url: string, body: unknown = {}) =>
  fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  state: () => fetch("/api/state").then(j<State>),
  zones: () => fetch("/api/zones").then(j<{ zones: Zone[] }>),
  mpa: () => fetch("/api/layers/mpa").then(j<[number, number][][]>),
  market: () => fetch("/api/market").then(j<Market>),
  story: () => fetch("/api/story").then(j<Story>),
  net: (id: number) => fetch(`/api/nets/${id}`).then(j<any>),
  forecast: (id: number) => fetch(`/api/nets/${id}/forecast`).then(j<Forecast>),
  orgNets: (org: string) => fetch(`/api/orgs/${org}/nets`).then(j<OwnedNet[]>),
  areas: () => fetch("/api/areas").then(j<AreaStatic[]>),
  identify: (photo: Blob) => { const f = new FormData(); f.append("photo", photo, "evidence.jpg"); return fetch("/api/identify", { method: "POST", body: f }).then(j<Identity>); },
  ledger: (limit = 120) => fetch(`/api/ledger?limit=${limit}`).then(j<LedgerRow[]>),
  checkout: (org: string, count: number, product: string) => post("/api/checkout", { org, count, product }).then(j<any>),
  loss: (id: number, lat: number, lon: number) => post(`/api/nets/${id}/loss`, { lat, lon }).then(j<any>),
  returnNet: (id: number) => post(`/api/nets/${id}/return`).then(j<any>),
  advance: (days: number) => post("/api/clock/advance", { days }).then(j<any>),
  sponsor: (amount: number) => post("/api/sponsor", { amount }).then(j<any>),
  reset: () => post("/api/reset").then(j<State>),
  scenario: () => fetch("/api/demo/scenario").then(j<Scenario>),
  startDemo: () => post("/api/demo/start").then(j<Scenario>),
  priorityLayer: () => fetch("/api/layers/priority").then(j<{ high: number[][][][]; veryHigh: number[][][][] }>),
  claim: (photo: Blob, claimant: string, lat: number, lon: number) => {
    const f = new FormData();
    f.append("photo", photo, "evidence.jpg"); f.append("claimant", claimant);
    f.append("lat", String(lat)); f.append("lon", String(lon));
    return fetch("/api/claims", { method: "POST", body: f }).then(j<ClaimResult>);
  },
  tagUrl: (id: number) => replayUrl(`/api/nets/${id}/tag.png`),
  stagedUrl: (id: number, variant: string, seed = 0) => replayUrl(`/api/nets/${id}/staged-photo?variant=${variant}&seed=${seed}`),
};

export const usd = (n: number) => "$" + Math.round(n).toLocaleString("en-US");
export const shortHash = (h: string) => (h ? `${h.slice(0, 8)}…${h.slice(-4)}` : "");
export const fmtDate = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
export const latlon = (lat: number, lon360: number) => {
  const w = lon360 > 180, lon = w ? 360 - lon360 : lon360;
  return `${Math.abs(lat).toFixed(1)}°${lat >= 0 ? "N" : "S"}, ${lon.toFixed(1)}°${w ? "W" : "E"}`;
};
export const priorityLevel = (p: number) => (p >= 4 ? "Critical" : p >= 2.5 ? "High" : p >= 1.6 ? "Medium" : "Low");
export const netName = (id: number) => `Net #${String(id).padStart(4, "0")}`;
