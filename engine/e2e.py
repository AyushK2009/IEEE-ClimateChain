"""End-to-end check of the whole loop on a live local chain (anvil must be running).

    python -m engine.e2e

Seeds a fresh world, then: checkout -> loss -> forecast -> price lists -> good claim (paid) ->
two fraud attempts (rejected) -> double claim (refused by the contract) -> unreported recovery.
Prints every step and asserts the money always adds up.
"""
import time

import numpy as np

from engine import forecast as F
from engine.world import World


def books(w):
    p = w.chain.pool()
    assert abs(p["balance"] - (p["depositsHeld"] + p["poolAvailable"] + p["poolReserved"])) < 1e-6, p
    return p


def main():
    w = World()
    t0 = time.time()
    w.start(reseed=True)
    st = w.state()
    print(f"seeded in {time.time() - t0:.0f}s: today {st['date']}, epoch {st['epoch']}, counts {dict(st['counts'])}")
    p = books(w)
    print(f"  pool: held {p['depositsHeld']:,.0f} | available {p['poolAvailable']:,.0f} | reserved {p['poolReserved']:,.0f}"
          f" | advertised {st['advertised']:,} (lambda {st['lambda']})")
    assert st["advertised"] <= p["poolAvailable"]

    # Scene A: purchase
    r = w.checkout("kai", 12, "Gillnet panel, 50 m")
    featured = r["ids"][0]
    print(f"A. checkout: nets {r['ids'][0]}..{r['ids'][-1]} registered, tx {r['tx'][:12]}")
    # Scene B/C: loss + forecast
    sug = st["featuredSuggestion"]
    r = w.report_loss(featured, sug["lat"], sug["lon"])
    print(f"B. net #{featured} reported lost at {sug['lat']},{sug['lon']}; epoch {r['epoch']}; forecast {r['forecast']}")
    e = next(x for x in w.board()["entries"] if x["netId"] == featured)
    print(f"   day 0 bounty {e['bounty']} (cooling: top-up {e['topUp']})")
    assert e["bounty"] == 200
    # Advance the clock: the cloud drifts, prices update daily
    for _ in range(3):
        w.advance(7)
        e = next(x for x in w.board()["entries"] if x["netId"] == featured)
        print(f"   {w.date_of(w.today)}: bounty {e['bounty']} dUSD, weight {e['weight']}, top zone p={e['zones'][0]['p'] if e['zones'] else 0}")
    books(w)
    t = time.time()
    fc = w.net_forecast(featured)
    print(f"C. forecast frames: {len(fc['frames'])} days, built in {time.time() - t:.1f}s")

    # Scene E/F: a genuine-looking claim inside the cloud
    lat, lon, _ = F.at(featured, w.today)
    i = int(np.argmin((lat - np.median(lat)) ** 2 + (lon - np.median(lon)) ** 2))
    photo = w.staged_photo(featured, "recovered", 0)
    before = w.chain.balance("crew_a")
    r = w.claim(photo, "crew_a", float(lat[i]), float(lon[i]))
    print(f"E/F. good claim on #{featured}: {r['outcome']} | locked {r['bountyLocked']} | paid {r['paid']} | "
          f"crew_a +{w.chain.balance('crew_a') - before:.0f} | net now {r['netStatus']}")
    for c in r["report"]["checks"]:
        print(f"      [{c['status']:4s}] {c['name']}: {c['detail'][:110]}")
    assert r["outcome"] == "accept" and r["netStatus"] == "Recovered"
    books(w)

    # Fraud 1: claimed location far beyond physical reach
    other = w.lost_nets()[5]
    r = w.claim(w.staged_photo(other["id"], "recovered", 1), "crew_b", 20.0, 228.0)
    print(f"Fraud 1 (900+ km away) on #{other['id']}: {r['outcome']} -> " +
          next(c["detail"] for c in r["report"]["checks"] if c["id"] == "reach")[:120])
    assert r["outcome"] == "reject" and w.status[other["id"]] == "Lost"

    # Fraud 2: printed tag, no net
    other2 = w.lost_nets()[6]
    la2, lo2, _ = F.at(other2["id"], w.today)
    r = w.claim(w.staged_photo(other2["id"], "printout"), "crew_b", float(np.median(la2)), float(np.median(lo2)))
    print(f"Fraud 2 (printout) on #{other2['id']}: {r['outcome']} -> " +
          next(c["detail"] for c in r["report"]["checks"] if c["id"] == "scene")[:120])
    assert r["outcome"] == "reject"

    # Double claim on the recovered net: the contract itself refuses
    r = w.claim(photo, "crew_b", float(lat[i]), float(lon[i]))
    print(f"Double claim on #{featured}: ok={r['ok']} -> {r.get('error')}")
    assert not r["ok"] and r["stage"] == "contract"

    # Unreported recovery of an active net: reward is exactly the owner's deposit
    active = next(n for n, s in w.status.items() if s == "Active" and w.net_row(n)["owner"] == "pacific")
    r = w.claim(w.staged_photo(active, "recovered", 2), "crew_b", 30.0, 200.0)
    print(f"Unreported recovery of #{active}: {r['outcome']} | paid {r['paid']} | unreported flag "
          f"{w.chain.escrow.functions.nets(active).call()[3]}")
    assert r["paid"] == 200
    p = books(w)
    print(f"final pool: held {p['depositsHeld']:,.0f} | available {p['poolAvailable']:,.0f} | reserved {p['poolReserved']:,.0f}")
    t = time.time(); w.reset()
    print(f"reset to seed in {time.time() - t:.1f}s; epoch {w.chain.current_epoch()}; status of #{featured}: "
          f"{w.status.get(featured)} (net did not exist at seed time)")
    print("E2E OK")


if __name__ == "__main__":
    main()
