import type { Step } from "react-joyride";
import { api, netName, usd, type Market, type Scenario } from "../api";
import { go } from "../store";
import { bus, settle, waitForElement } from "./bus";
import { setLoading } from "./state";

export const CHAPTERS = ["Introduction", "Register gear", "Report a loss", "Forecast", "Recovery marketplace", "Recovery claim", "Payout", "Fraud check", "Wrap-up"];

export type TourCtx = {
  scenario: () => Scenario | null; setScenario: (s: Scenario) => void; refresh: () => Promise<void>; market: () => Market | null;
  flags: { current: { advanced: boolean; fraudNet: number | null } };
};

const sel = (s: string) => `[data-tour="${s}"]`;

/** Center an element in its own scrolling panel (or the page), without also scrolling the page behind a panel. */
function reveal(el: HTMLElement) {
  const r = el.getBoundingClientRect();
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
    const o = getComputedStyle(p).overflowY;
    if ((o === "auto" || o === "scroll") && p.scrollHeight > p.clientHeight) {
      const pr = p.getBoundingClientRect();
      p.scrollTop += r.top - pr.top - Math.max(12, (p.clientHeight - r.height) / 2);
      return;
    }
  }
  const nav = 60;
  window.scrollTo({ top: window.scrollY + r.top - nav - Math.max(16, (innerHeight - nav - r.height) / 2), behavior: "instant" as ScrollBehavior });
}

/** Wait for a target, then let layout settle so the spotlight measures the final position. */
async function ready(selector: string, message = "Loading…", timeout = 20000) {
  setLoading(message);
  const el = await waitForElement(selector, timeout);
  if (el) reveal(el);
  await settle();
  setLoading("");
}

export function buildSteps(ctx: TourCtx): Step[] {
  const net = () => ctx.scenario()?.netId ?? 0;
  const N = () => netName(net());
  // every targeted step scrolls its target into view in `ready`, so Joyride's own scrolling is off
  const base = { skipBeacon: true, skipScroll: true, spotlightPadding: 6, targetWaitTimeout: 6000 } as const;
  const center = { ...base, target: "body", placement: "center" as const };

  const Reward = () => {
    const e = ctx.market()?.entries.find((x) => x.netId === net());
    return <>{e ? <><b>{usd(e.bounty)}</b>: Kai's {usd(e.deposit)} plus {usd(e.topUp)} from sponsors</> : "more"}</>;
  };
  const NetName = () => <b>{N()}</b>;

  return [
    // ---------- Introduction ----------
    { ...center, id: "intro", title: "Lost fishing nets keep killing for years.",
      content: (<><p>About 2% of all fishing gear in use is lost at sea every year. A lost net doesn't stop fishing: it drifts for years,
        entangling turtles, seabirds and endangered Hawaiian monk seals, and smothering coral reefs.</p>
        <p>Nets make up nearly half of the Great Pacific Garbage Patch by weight. Today, nobody knows where a lost net is, nobody is paid to recover it, and nobody is accountable for losing it.</p></>),
      data: { chapter: 0, wide: true, media: "/img/monk-seal-net.jpg", mediaCaption: "Hawaiian monk seal entangled in a derelict net, Papahānaumokuākea. Photo: NOAA Fisheries (public domain).", nextLabel: "What we built" } },
    { ...center, id: "solution", title: "Three things lost nets don't have today.",
      content: (<><div className="tour-pillars">
        <div><b>An owner</b>Nets aren't traceable today. We register each one when it's sold, with a QR tag and a refundable deposit.</div>
        <div><b>A location</b>Nobody knows where lost nets go. We forecast their drift on real ocean currents.</div>
        <div><b>A price</b>Nobody is paid to bring them back. We post a reward, paid automatically once a recovery is verified.</div></div>
        <p style={{ marginTop: 14 }}>You'll follow one net from purchase to a paid recovery. The companies, crews and money are simulated; the forecasts, checks and blockchain transactions are real.</p></>),
      data: { chapter: 0, wide: true, nextLabel: "Start: buy some nets" } },

    // ---------- B. Register ----------
    { ...base, id: "checkout", target: sel("checkout"), placement: "right", title: "New: a deposit on every net",
      content: (<p>It works like a bottle deposit. Kai Fisheries buys six nets and pays a refundable $200 for each, locked in a smart contract.
        Kai gets it back when a net is retired. If a net is lost, its deposit becomes the start of the reward for recovering it.</p>),
      before: async () => {
        setLoading("Preparing a fresh demo world…", "Restoring the starting state, so no records from earlier sessions remain.");
        bus.clear("fleet:registered", "fleet:lossDrawer", "fleet:lost", "explore:area", "explore:net", "claim:ready", "claim:identified", "claim:located", "claim:done");
        const s = await api.startDemo();
        ctx.setScenario(s); ctx.flags.current = { advanced: false, fraudNet: null };
        await ctx.refresh();
        go("/fleet");
        await ready(sel("buy"), "Opening the fleet…");
      },
      data: { chapter: 1, wait: "fleet:registered", doIt: sel("buy"), doLabel: "Buy them for me", loading: "Preparing a fresh demo world…" } },
    { ...base, id: "passport", target: sel("passport"), placement: "right", title: "New: every net has an identity",
      content: (<p>A net found at sea today can't be traced to anyone. <NetName /> now has a blockchain record of its owner, deposit and status, and a QR tag on the net itself, so whoever finds it can prove which net it is.</p>),
      before: () => ready(sel("passport")),
      data: { chapter: 1, noBack: true } },

    // ---------- C. Report a loss ----------
    { ...base, id: "report", target: () => document.querySelector(sel(`report-${net()}`)) as HTMLElement, placement: "left", title: "Weeks later, a net goes missing",
      content: (<p>In a storm, <NetName /> breaks loose about 580 km west of Kure Atoll. Kai reports it: a report starts the search, and a net found without one counts against its owner.</p>),
      before: () => ready(sel(`report-${net()}`)),
      data: { chapter: 2, wait: "fleet:lossDrawer", doIt: "@target", doLabel: "Report it for me" } },
    { ...base, id: "loss-confirm", target: sel("loss-drawer"), placement: "top", title: "Mark where it was lost",
      content: (<p>Its last known position is filled in. Reporting costs Kai the $200 deposit, which becomes the first part of the reward. Losing gear now has a price.</p>),
      before: () => ready(sel("loss-confirm")),
      data: { chapter: 2, noBack: true, wait: "fleet:lost", doIt: sel("loss-confirm"), doLabel: "Report it for me" } },
    { ...base, id: "net-status", target: sel("net-status"), placement: "right", title: "Recorded on the blockchain",
      content: (<p><NetName /> is now <b>Lost</b> and its $200 is in the reward fund, in one blockchain transaction. It's a shared record the fishing company, sponsors and crews can all check, and nobody can quietly edit.</p>),
      before: () => ready(sel("net-status"), "Recording the loss and starting the forecast…"),
      data: { chapter: 2, noBack: true } },

    // ---------- D. Forecast ----------
    { ...base, id: "forecast", target: sel("map"), placement: "left", spotlightPadding: 0, title: "Where will it drift?",
      content: (<><p>We release 1,000 virtual copies of the net at the red point and let real 2021 ocean currents (NASA OSCAR) carry them.</p>
        <p><b>Dark blue</b>: most likely here. <b>Light blue</b>: could be here. The cloud spreads because currents are uncertain. <b>Green</b>: protected reefs, where we least want it to end up.</p></>),
      before: async () => { await ready(sel("map") + '[data-loaded="true"]', "Loading the map…"); bus.emit("cmd:explore:play"); },
      data: { chapter: 3 } },
    { ...base, id: "reward", target: sel("reward"), placement: "right", title: "Who pays the reward?",
      content: (<p>At first, only Kai's forfeited $200. After three days, sponsors add more: the kind of governments, conservation funds and seafood companies that pay for ghost-net cleanups today.
        Here they pay only for nets actually recovered, and more for nets drifting toward protected reefs. One simulated sponsor funds this demo.</p>),
      before: () => ready(sel("reward")),
      data: { chapter: 3 } },
    { ...center, id: "time", title: "Three weeks later…",
      content: (<p>Three weeks pass in the 2021 ocean replay. Each day, every forecast and reward was recalculated and that day's reward list was sealed on the blockchain, so a reward can't be cut after a crew sets out.</p>),
      before: async () => {
        if (!ctx.flags.current.advanced) {
          const days = ctx.scenario()?.fastForwardDays ?? 21;
          setLoading(`Moving the clock forward ${days} days…`, `Recalculating every forecast and reward each day, and sealing ${days} daily reward lists on the blockchain.`);
          await api.advance(days);
          ctx.flags.current.advanced = true;
          await ctx.refresh();
          setLoading("");
        }
      },
      data: { chapter: 3, noBack: true, nextLabel: "See the whole ocean", loading: "Moving the clock forward…" } },

    // ---------- E. Marketplace ----------
    { ...base, id: "region", target: sel("map"), placement: "left", spotlightPadding: 0, title: `This isn't the only lost net`,
      content: (<p>Here are 360 more simulated losses from four fishing fleets, each with its own forecast. Combined, the <b>blue bands</b> show where lost nets are concentrated right now. The darkest band holds half of them.</p>),
      before: async () => { go("/explore"); await ready(sel("hotspots"), "Zooming out to the whole region…"); await ready(sel("map") + '[data-loaded="true"]'); bus.emit("cmd:explore:layers", { priority: false, density: true }); },
      data: { chapter: 4, noBack: true } },
    { ...base, id: "hotspots", target: sel("hotspots"), placement: "right", title: "Hotspots: where recovery pays",
      content: (<p><b>Orange circles</b> show where the most reward money is waiting. For recovery crews this is a job board: where a trip pays best, and why each area matters.</p>),
      before: () => ready(sel("hotspots")),
      data: { chapter: 4 } },
    { ...base, id: "priority", target: sel("layers"), placement: "left", title: "Ecological priority is a separate question",
      content: (<><p><b>Green</b> shows ecological priority: the protected reefs of Papahānaumokuākea, and waters whose currents carry gear into them.</p>
        <p>Blue says where nets are. Green says where recovering them matters most. Rewards combine both.</p></>),
      before: async () => { bus.emit("cmd:explore:layers", { priority: true, density: true }); await ready(sel("layers")); },
      data: { chapter: 4 } },
    { ...base, id: "focus-area", target: sel("focus-area"), placement: "right", title: "Find our net's area",
      content: (<p><NetName /> has drifted for three weeks. This is the recovery area it's most likely in now. Open it to see every net likely there.</p>),
      before: async () => { bus.emit("cmd:explore:layers", { priority: false, density: true }); bus.clear("explore:area"); await ready(sel("focus-area")); },
      data: { chapter: 4, wait: "explore:area", doIt: sel("focus-area") } },
    { ...base, id: "area-net", target: () => document.querySelector(sel(`net-row-${net()}`)) as HTMLElement, placement: "right", title: "Every net in this area, with its reward",
      content: (<p><NetName />'s reward is now <Reward />, because it is drifting toward protected waters. Open it.</p>),
      before: async () => { bus.clear("explore:net"); await ready(sel(`net-row-${net()}`), "Opening the area…"); },
      data: { chapter: 4, noBack: true, wait: "explore:net", doIt: "@target", doLabel: "Open it for me" } },

    // ---------- F. Recovery claim ----------
    { ...base, id: "claim-btn", target: sel("claim-btn"), placement: "right", title: "A crew recovers it",
      content: (<p>Anyone except the owner can claim: fishing boats, salvage teams, cleanup groups. A crew from Tern Island searches where the forecast points, finds <NetName /> and hauls it aboard.</p>),
      before: async () => { bus.clear("claim:ready"); await ready(sel("claim-btn"), "Loading the net…"); },
      data: { chapter: 5, noBack: true, wait: "claim:ready", doIt: sel("claim-btn") } },
    { ...base, id: "evidence", target: sel("evidence-real"), placement: "right", title: "Step 1: photograph the tag",
      content: (<p>The crew photographs the net with its tag attached. This is <b>staged evidence</b>: a real public-domain photo of a derelict net, with the tag added digitally.</p>),
      before: async () => { bus.clear("claim:identified", "claim:located", "claim:done"); await ready(sel("evidence-real"), "Opening the claim…"); },
      data: { chapter: 5, noBack: true, wait: "claim:identified", doIt: sel("evidence-real"), doLabel: "Select it for me" } },
    { ...base, id: "identity", target: sel("identity"), placement: "bottom", title: "The tag identifies the net",
      content: (<p>Reading the QR code tells the system exactly which net this is, <NetName />, and that it's eligible for the reward. No one types an ID, so a claim can't be filed against the wrong net.</p>),
      before: () => ready(sel("identity"), "Reading the tag…"),
      data: { chapter: 5, noBack: true } },
    { ...base, id: "location", target: sel("location"), placement: "top", title: "Step 2: where was it found?",
      content: (<p>Use the forecast's most likely spot, or click the map. The location is only used to check the claim. It never changes the reward.</p>),
      before: () => ready(sel("use-core")),
      data: { chapter: 5, wait: "claim:located", doIt: sel("use-core"), doLabel: "Use the likely spot" } },
    { ...base, id: "submit", target: sel("submit"), placement: "left", title: "Step 3: submit for verification",
      content: (<p>Submitting locks the reward on the blockchain. Then automated checks run on the claim. It takes a few seconds.</p>),
      before: () => ready(sel("submit")),
      data: { chapter: 5, noBack: true, wait: "claim:done", doIt: sel("submit"), doLabel: "Submit for me" } },

    // ---------- G. Payout ----------
    { ...base, id: "payout", target: sel("outcome-head"), placement: "top", title: "Paid automatically",
      content: (<p>Every check passed, so the smart contract released the reward to the crew. <NetName /> is now marked <b>Recovered</b> and can never be paid for twice. The reward fund went down by exactly this amount.</p>),
      before: () => ready(sel("outcome-head"), "Verifying the claim…"),
      data: { chapter: 6, noBack: true } },
    { ...base, id: "checks", target: sel("checks"), placement: "top", title: "What was checked",
      content: (<p>The tag matches a registered lost net. The net could have drifted this far. The spot matches the forecast. And an AI model running on this computer confirmed a real net is in the photo, not just a tag.</p>),
      before: () => ready(sel("checks")),
      data: { chapter: 6 } },
    { ...base, id: "tx", target: sel("tx"), placement: "top", title: "The blockchain record",
      content: (<p>Both steps are real transactions on a test blockchain with play money: the reward was locked, then released after verification. Losses and daily reward lists are recorded the same way. All of them are listed under Records.</p>),
      before: async () => { bus.emit("cmd:claim:openTech"); await ready(sel("tx") + " .txline"); },
      data: { chapter: 6 } },

    // ---------- Fraud ----------
    { ...center, id: "fraud-intro", title: "What if someone cheats?",
      content: (<p>Someone has seen another lost net's tag and printed a copy, hoping to collect its reward without recovering anything. Let's file that claim, as a second simulated crew.</p>),
      data: { chapter: 7, nextLabel: "Try the fake claim" } },
    { ...base, id: "fraud-evidence", target: sel("evidence-fake"), placement: "right", title: "A photo of a printed tag",
      content: (<p>Select the staged photo of a printed copy of this net's tag. There's no net in it.</p>),
      before: async () => {
        const m = ctx.market();
        const pick = ctx.flags.current.fraudNet ?? [...(m?.entries ?? [])].filter((e) => e.netId !== net() && e.eligible).sort((a, b) => b.bounty - a.bounty)[0]?.netId ?? 1;
        ctx.flags.current.fraudNet = pick;
        bus.clear("claim:identified", "claim:located", "claim:done");
        go(`/claim?net=${pick}&crew=crew_b`);
        await ready(sel("evidence-fake"), "Opening another claim…");
      },
      data: { chapter: 7, noBack: true, wait: "claim:identified", doIt: sel("evidence-fake"), doLabel: "Select it for me" } },
    { ...base, id: "fraud-submit", target: sel("submit"), placement: "left", title: "A real tag, a plausible spot, no net",
      content: (<p>The tag is genuine and the location matches the forecast. Submit it and see what the checks say.</p>),
      before: async () => { bus.emit("cmd:claim:useCore"); await bus.wait("claim:located", 15000).catch(() => null); await ready(sel("submit")); },
      data: { chapter: 7, noBack: true, wait: "claim:done", doIt: sel("submit"), doLabel: "Submit for me" } },
    { ...base, id: "fraud-result", target: sel("outcome-head"), placement: "top", title: "Rejected",
      content: (<p>The AI model saw only paper and a QR code, with no net. The locked reward went straight back to the fund, and the net stays listed as lost for an honest crew to find.</p>),
      before: () => ready(sel("outcome-head"), "Verifying the claim…"),
      data: { chapter: 7, noBack: true } },

    // ---------- Wrap-up ----------
    { ...center, id: "finale", title: "That's the whole loop.",
      content: (<><p>Owners pay a deposit, so losing a net costs them. That deposit, topped up by sponsors, pays whoever brings the net back.
        Forecasts show where to look, and the blockchain holds the money and pays out automatically once the checks pass. A fake claim gets nothing.</p>
        <p>Now explore freely: other hotspots and nets, registering gear, or filing your own claim. Everything here is the live system.</p></>),
      data: { chapter: 8, wide: true, finale: true, nextLabel: "Explore on my own" } },
  ];
}
