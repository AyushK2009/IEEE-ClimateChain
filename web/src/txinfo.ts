import { CheckCircle2, Coins, Fingerprint, Lock, PackageCheck, Undo2, Waves, XCircle, AlertTriangle } from "lucide-react";
import { netName, shortHash, usd, type LedgerRow } from "./api";

const WEI = 1e18;
export type TxInfo = { kind: string; title: string; sub: string; icon: any; color: string; nets: number[] };

/** Plain-English description of a blockchain transaction from its decoded contract events. */
export function describeTx(r: Pick<LedgerRow, "events" | "actor">, name: (k: string) => string): TxInfo | null {
  const ev = r.events.filter((e) => !["Transfer", "Approval", "RoleGranted"].includes(e.event));
  const first = ev[0];
  if (!first) return null;
  const a = first.args;
  const nets = ev.map((e) => e.args.netId).filter((x) => x != null);
  switch (first.event) {
    case "NetRegistered":
      return { kind: "passports", title: ev.length > 1 ? `${ev.length} nets registered` : `${netName(a.netId)} registered`, sub: `${name(String(a.owner))} · ${usd((ev.length * a.deposit) / WEI)} in deposits held`, icon: PackageCheck, color: "sea", nets };
    case "NetLost":
      return { kind: "losses", title: ev.length > 1 ? `${ev.length} nets reported lost` : `${netName(a.netId)} reported lost`, sub: `${usd((ev.length * a.depositToPool) / WEI)} deposit moved to the reward fund`, icon: Waves, color: "alert", nets };
    case "NetReturned":
      return { kind: "passports", title: `${netName(a.netId)} returned`, sub: `${usd(a.refund / WEI)} deposit refunded`, icon: Undo2, color: "ok", nets };
    case "Sponsored":
      return { kind: "rewards", title: "Sponsor added funds", sub: `${usd(a.amount / WEI)} into the reward fund`, icon: Coins, color: "signal", nets };
    case "EpochPublished":
      return { kind: "rewards", title: "Daily reward list published", sub: `${usd(a.totalAdvertised / WEI)} in rewards · fingerprint ${shortHash(String(a.root))}`, icon: Fingerprint, color: "chain", nets };
    case "ClaimSubmitted":
      return { kind: "claims", title: `Recovery claimed: ${netName(a.netId)}`, sub: `${usd(a.bounty / WEI)} reward locked for ${name(r.actor)}`, icon: Lock, color: "signal", nets };
    case "ClaimResolved": {
      const o = Number(a.outcome);
      if (o === 1) return { kind: "claims", title: `Paid: ${netName(a.netId)} recovered`, sub: `${usd(a.paid / WEI)} paid automatically`, icon: CheckCircle2, color: "ok", nets };
      if (o === 2) return { kind: "claims", title: `Claim rejected: ${netName(a.netId)}`, sub: "reward returned to the fund", icon: XCircle, color: "alert", nets };
      return { kind: "claims", title: `Claim flagged: ${netName(a.netId)}`, sub: "reward held for review", icon: AlertTriangle, color: "signal", nets };
    }
    default:
      return null;
  }
}
