// Hosted mode: the public site has no Python server, so it answers API calls from a recording of one real run
// (web/public/replay, made by driving the guided demo against the live backend). Locally nothing changes.
type Entry = { seq: number; step: string; m: string; u: string; h: string | null; s: number; t: string; f: string };

export const REPLAY = typeof window !== "undefined" &&
  (!["127.0.0.1", "localhost"].includes(window.location.hostname) || new URLSearchParams(window.location.search).has("replay"));

let entries: Entry[] = [];
const posts: Entry[] = [];
// Requests see the world as it was just before the next recorded change. Before any change: the final state.
let clock = Infinity;

const file = (e: Entry) => `/replay/b/${e.f}`;
const nextPostAfter = (seq: number) => posts.find((p) => p.seq > seq);
const notRecorded = (what: string) => new Response(JSON.stringify({ detail: `${what} isn't part of the recorded demo. Run the project locally for the live system (see the GitHub README).` }),
  { status: 409, headers: { "Content-Type": "application/json" } });
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function photoHash(body: FormData) {
  const p = body.get("photo");
  if (!(p instanceof Blob)) return null;
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", await p.arrayBuffer()));
  return Array.from(d).map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

async function answer(e: Entry, delay: number) {
  await sleep(delay);
  const r = await fetch(file(e));
  return new Response(await r.blob(), { status: e.s, headers: { "Content-Type": e.t } });
}

async function replayFetch(url: string, init?: RequestInit): Promise<Response> {
  const method = (init?.method || "GET").toUpperCase();
  if (method === "GET") {
    const same = entries.filter((e) => e.m === "GET" && e.u === url);
    if (!same.length) return notRecorded("This view");
    const e = [...same].reverse().find((x) => x.seq <= clock) ?? same[0];
    return answer(e, 120);
  }
  const path = url.split("?")[0];
  const h = init?.body instanceof FormData ? await photoHash(init.body) : null;
  const same = posts.filter((e) => e.u.split("?")[0] === path && (h === null || e.h === h));
  if (!same.length) return notRecorded(h ? "Checking your own photo" : "This action");
  const e = same.find((x) => x.seq > (Number.isFinite(clock) ? clock : -1)) ?? same[0];
  const nxt = nextPostAfter(e.seq);
  clock = nxt ? nxt.seq - 1 : Infinity;
  return answer(e, path.endsWith("/claims") ? 2600 : path.endsWith("/identify") ? 900 : 400);
}

/** Load the recording and route /api/* through it (hosted mode only). */
export async function startReplay() {
  if (!REPLAY) return;
  entries = (await (await fetch("/replay/manifest.json")).json()).entries as Entry[];
  posts.push(...entries.filter((e) => e.m !== "GET").sort((a, b) => a.seq - b.seq));
  const orig = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const u = typeof input === "string" ? input : input instanceof URL ? input.pathname + input.search : input.url;
    const rel = u.startsWith(window.location.origin) ? u.slice(window.location.origin.length) : u;
    return rel.startsWith("/api/") ? replayFetch(rel, init) : orig(input, init);
  };
}

/** Image URLs (<img src>) can't go through fetch: point them at the recorded files. */
export function replayUrl(url: string) {
  if (!REPLAY) return url;
  const e = entries.find((x) => x.m === "GET" && x.u === url);
  return e ? file(e) : url;
}
