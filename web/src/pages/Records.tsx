import { useMemo, useState } from "react";
import { ChevronDown, Coins } from "lucide-react";
import { api, fmtDate, netName, usd } from "../api";
import { useStore } from "../store";
import { describeTx } from "../txinfo";

const FILTERS = [["all", "Everything"], ["claims", "Claims & payouts"], ["losses", "Losses"], ["passports", "Registrations"], ["rewards", "Reward lists"]] as const;
const RULES = [
  ["Never pays twice", "Once a net is recovered and paid, any further claim is refused."],
  ["Never promises more than it holds", "A daily reward list worth more than the fund is rejected."],
  ["Owners can't claim their own nets", "The claimant must not be the net's owner."],
  ["Rewards can't be changed afterwards", "A claim must match the sealed daily reward list."],
  ["Deposits stay separate", "Refundable deposits are never spent on rewards."],
  ["Only approved services set prices and verdicts", "Each needs a role granted on the contract."],
] as const;

export default function Records() {
  const { st, ledger, busy, run } = useStore();
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState<number | null>(null);
  const byAddr = useMemo(() => Object.fromEntries(Object.values(st?.actors ?? {}).map((a) => [a.address.toLowerCase(), a.name])), [st]);
  const name = (k: string) => st?.actors[k]?.name ?? byAddr[String(k).toLowerCase()] ?? k;
  const rows = useMemo(() => ledger.map((r) => ({ r, d: describeTx(r, name) })).filter((x) => x.d && (filter === "all" || x.d.kind === filter)), [ledger, filter, st]);
  if (!st) return null;
  const p = st.pool, total = Math.max(1, p.depositsHeld + p.poolAvailable + p.poolReserved);

  return (
    <div className="page">
      <div className="head">
        <div className="kicker">Records</div>
        <h1>What the blockchain has recorded</h1>
        <p>Registrations, losses, daily reward lists and payouts are written to a shared record that fishing companies, sponsors and crews can all check, and that nobody can quietly edit. This demo uses a local test blockchain and play money.</p>
      </div>

      <div className="card">
        <div className="row"><h3 className="grow">Money held by the smart contract</h3><span className="num">{usd(p.balance)}</span></div>
        <div className="bar3">
          <span style={{ width: `${(100 * p.depositsHeld) / total}%`, background: "var(--sea)" }} />
          <span style={{ width: `${(100 * p.poolAvailable) / total}%`, background: "var(--signal)" }} />
          <span style={{ width: `${(100 * p.poolReserved) / total}%`, background: "#d8a31a" }} />
        </div>
        <div className="figures" style={{ gridTemplateColumns: "repeat(3, 1fr)", border: "none" }}>
          <div><div className="k"><span style={{ color: "var(--sea)" }}>■</span> Refundable deposits</div><div className="v">{usd(p.depositsHeld)}</div><div className="tiny muted">for nets still in use</div></div>
          <div><div className="k"><span style={{ color: "var(--signal)" }}>■</span> Reward fund</div><div className="v">{usd(p.poolAvailable)}</div><div className="tiny muted">sponsors + lost nets' deposits</div></div>
          <div><div className="k"><span style={{ color: "#d8a31a" }}>■</span> Locked for claims</div><div className="v">{usd(p.poolReserved)}</div><div className="tiny muted">waiting for verification</div></div>
        </div>
        <div className="row wrap" style={{ marginTop: 10 }}>
          <span className="small ink2 grow">Today's rewards add up to <span className="money">{usd(st.advertised)}</span>, never more than the fund holds.</span>
          <button className="btn sm" disabled={busy} onClick={() => run("Adding sponsor funds…", () => api.sponsor(25000))}><Coins size={13} />Add $25,000 as a sponsor</button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="row wrap"><h3 className="grow">Recent transactions</h3>
          <div className="tabs">{FILTERS.map(([k, l]) => <button key={k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{l}</button>)}</div></div>
        <div style={{ marginTop: 8 }}>
          {rows.slice(0, 40).map(({ r, d }) => {
            const Ic = d!.icon;
            return (
              <div key={r.seq}>
                <div className="feedrow" onClick={() => setOpen(open === r.seq ? null : r.seq)}>
                  <span className={`ic ${d!.color}`}><Ic size={16} /></span>
                  <div><b>{d!.title}</b><div className="small muted">{d!.sub}</div></div>
                  <div className="row small muted" style={{ gap: 10 }}><span>{fmtDate(r.date)}</span><span className="hash">block {r.block}</span><ChevronDown size={15} /></div>
                </div>
                {open === r.seq && (
                  <div className="fade small" style={{ padding: "4px 0 12px 46px" }}>
                    Sent by <b>{name(r.actor)}</b> · transaction <span className="mono">{r.tx}</span>
                    {d!.nets.length > 0 && <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>{[...new Set(d!.nets)].slice(0, 14).map((n) => <a key={n} className="tag sim" href={`#/net/${n}`}>{netName(n)}</a>)}</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <h3 style={{ margin: "26px 0 10px" }}>Rules the contract enforces on its own</h3>
      <div className="rules">{RULES.map(([t, s]) => <div key={t}><b>{t}</b><span>{s}</span></div>)}</div>
    </div>
  );
}
