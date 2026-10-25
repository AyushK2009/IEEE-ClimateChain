"""Daily price list (TECHNICAL_PROPOSAL.md section 4.7).

bounty_n = D_n + [days lost >= 3] * lambda * sum_z P_n(z) * Priority_z
lambda   = min(LAMBDA_CAP, 0.8 * SponsorAvailable / sum over eligible nets of their weights)
SponsorAvailable = poolAvailable - deposits of the nets on the list (those deposits back each net's base price)

So the advertised total is at most poolAvailable, which the contract also enforces.
"""
import math

from engine import config as C
from engine import forecast as F
from engine import merkle as M
from engine import zones as Z

WEI = 10**18


def build(lost_nets, day, pool_available, epoch):
    """lost_nets: list of dicts with id, owner, loss_day, deposit (only nets currently Lost on-chain)."""
    zones = Z.load()
    entries = []
    for n in lost_nets:
        probs = F.zone_probs(n["id"], day)
        weight = sum(p * (zones[z]["priority"] if z in zones else 1.0) for z, p in probs.items())
        ranked = sorted(((p, z) for z, p in probs.items() if z != "outside"), reverse=True)
        entries.append({"netId": n["id"], "owner": n["owner"], "deposit": n["deposit"], "lossDay": n["loss_day"],
                        "daysLost": day - n["loss_day"], "eligible": day - n["loss_day"] >= C.COOLING_DAYS,
                        "weight": round(weight, 4), "zones": [{"zone": z, "p": round(p, 3)} for p, z in ranked[:3]],
                        "modalZone": ranked[0][1] if ranked else None, "probs": probs})
    deposits = sum(e["deposit"] for e in entries)
    sponsor_available = max(pool_available - deposits, 0.0)
    w_sum = sum(e["weight"] for e in entries if e["eligible"])
    lam = min(C.LAMBDA_CAP, C.BUDGET_FRACTION * sponsor_available / w_sum) if w_sum > 0 else C.LAMBDA_CAP
    for e in entries:
        top_up = lam * e["weight"] if e["eligible"] else 0.0
        e["topUp"] = math.floor(top_up)
        e["bounty"] = int(e["deposit"] + e["topUp"])
    entries.sort(key=lambda e: e["netId"])
    total = sum(e["bounty"] for e in entries)
    assert total <= pool_available + 1e-9, "price list would over-promise"
    root, proofs = None, {}
    if entries:
        leaves = [M.leaf(e["netId"], epoch, e["bounty"] * WEI) for e in entries]
        tree = M.MerkleTree(leaves)
        root = tree.root
        for i, e in enumerate(entries):
            e["proof"] = ["0x" + p.hex() for p in tree.proof(i)]
    for e in entries:
        e.pop("probs")
    return {"epoch": epoch, "day": day, "lambda": round(lam, 4), "sponsorAvailable": round(sponsor_available, 2),
            "poolAvailable": round(pool_available, 2), "total": total, "root": "0x" + root.hex() if root else "0x" + "00" * 32,
            "entries": entries}


def zone_aggregates(lost_nets, day, bounties):
    """Expected number of lost nets and open bounty value per zone (the regional market view)."""
    agg = {}
    for n in lost_nets:
        for z, p in F.zone_probs(n["id"], day).items():
            if z == "outside":
                continue
            a = agg.setdefault(z, {"expected": 0.0, "value": 0.0, "nets": []})
            a["expected"] += p
            a["value"] += p * bounties.get(n["id"], 0)
            if p >= 0.05:
                a["nets"].append({"netId": n["id"], "p": round(p, 3)})
    for a in agg.values():
        a["expected"] = round(a["expected"], 3); a["value"] = round(a["value"], 1)
        a["nets"].sort(key=lambda x: -x["p"])
    return agg
