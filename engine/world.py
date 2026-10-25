"""The running demo world: one object that owns the chain gateway, the off-chain store, the demo clock,
forecasts, price lists and claims. The API layer calls into this; nothing else mutates state."""
import hashlib
import json
import secrets
import threading
from collections import defaultdict
from datetime import timedelta

import numpy as np
from eth_utils import keccak

from engine import config as C
from engine import drift as D
from engine import forecast as F
from engine import places
from engine import pricing as P
from engine import regions as R
from engine import scenario as S
from engine import store
from engine import tags as T
from engine import verify as VF
from engine import vision as V
from engine import zones as Z
from engine.chain import ACTORS, FISHING_ORGS, WEI, Chain

EVIDENCE = C.RUNTIME / "evidence"


def locked(fn):
    """Serialize access: the API runs handlers in parallel threads, but one SQLite connection must not be shared concurrently."""
    def wrap(self, *a, **k):
        with self.lock:
            return fn(self, *a, **k)
    wrap.__name__ = fn.__name__
    wrap.__doc__ = fn.__doc__
    return wrap


class World:
    def __init__(self):
        self.chain = Chain()
        self.con = None
        self.lock = threading.RLock()
        self.status = {}
        self._forecast_cache = {}

    # ================================================================ lifecycle
    def start(self, reseed=False):
        if not self.chain.connected():
            raise RuntimeError(f"No blockchain node at {self.chain.rpc}. Start one with: anvil --accounts 12")
        if not reseed and store.DB.exists() and self.chain.attach_existing():
            self.con = store.connect()
            if store.get(self.con, "seeded"):
                self.resync()
                return "attached"
        self.seed()
        return "seeded"

    def seed(self):
        with self.lock:
            self.con = store.fresh()
            self.chain.ledger.clear()
            ch = self.chain
            ch.deploy()
            today, losses = S.plan(FISHING_ORGS)
            store.put(self.con, "today", today)
            ch.mint("sponsor", 1_000_000); ch.approve_escrow("sponsor")
            for org in FISHING_ORGS:
                ch.mint(org, 50_000); ch.approve_escrow(org)
            for actor in ("crew_a", "crew_b"):
                ch.mint(actor, 1_000)
            # purchases: each org bought its nets at the start of the season (day 0)
            owned = defaultdict(list)
            for k, org in enumerate(FISHING_ORGS):
                _, ids = ch.register(org, S.NETS_PER_ORG, C.DEPOSIT)
                for i in ids:
                    owned[org].append(i)
                    self.con.execute("INSERT INTO nets (id, owner, product, registered_day) VALUES (?,?,?,0)",
                                     (i, org, S.PRODUCTS[(i + k) % len(S.PRODUCTS)]))
                    self.status[i] = "Active"
            self._flush_ledger(0)
            # past losses, reported on-chain in batches per org and day
            by_org = defaultdict(list)
            for L in losses:
                by_org[L["org"]].append(L)
            groups = defaultdict(list)          # (org, day) -> [(net_id, loss)]
            for org, ls in by_org.items():
                for net_id, L in zip(owned[org], ls):
                    groups[(org, L["loss_day"])].append((net_id, L))
            for (org, day), items in sorted(groups.items(), key=lambda kv: kv[0][1]):
                ids, hashes = [], []
                for net_id, L in items:
                    salt = secrets.token_hex(8)
                    self.con.execute("UPDATE nets SET loss_day=?, loss_lat=?, loss_lon=?, loss_salt=? WHERE id=?",
                                     (day, L["lat"], L["lon"], salt, net_id))
                    ids.append(net_id); hashes.append(self._loss_hash(net_id, L["lat"], L["lon"], day, salt))
                    self.status[net_id] = "Lost"
                ch.report_loss(org, ids, hashes)
                self._flush_ledger(day)
            ch.sponsor("sponsor", C.SPONSOR_SEED)
            self._flush_ledger(today)
            # forecasts for all past losses (cached on disk: the scenario is deterministic)
            sig = hashlib.sha1(json.dumps(losses).encode()).hexdigest()
            if store.get(self.con, "forecast_sig") != sig or not all(F.path(i).exists() for (_, _), it in groups.items() for i, _ in it):
                by_day = defaultdict(list)
                for (org, day), items in groups.items():
                    by_day[day] += items
                for day, items in sorted(by_day.items()):
                    self._run_forecasts([i for i, _ in items], [L["lat"] for _, L in items],
                                        [L["lon"] for _, L in items], day, S.BACKGROUND_PARTICLES, S.BACKGROUND_END_DAY)
            store.put(self.con, "forecast_sig", sig)
            # a week of daily price lists so prices have history
            for day in range(today - 7, today + 1):
                self._publish(day)
            store.put(self.con, "featured_suggestion", S.FEATURED_SUGGESTION)
            store.put(self.con, "seeded", True)
            store.put(self.con, "snapshot", ch.snapshot())
            store.save_seed(self.con)

    def reset(self):
        """Return chain and records to the freshly seeded state (for rehearsing the demo)."""
        with self.lock:
            snap = store.get(self.con, "snapshot")
            ok = self.chain.revert(snap)
            if not ok:
                raise RuntimeError("chain snapshot missing; restart with reseed")
            self.con.close()
            self.con = store.restore_seed()
            store.put(self.con, "snapshot", self.chain.snapshot())   # a revert consumes the snapshot
            store.save_seed(self.con)
            self.chain.ledger.clear()
            self._forecast_cache.clear()
            F.load.cache_clear()
            self.resync()

    def scenario(self):
        """The fixed example used by the guided demo. Net IDs are deterministic from the seeded state."""
        first = self.con.execute("SELECT MAX(id) FROM nets").fetchone()[0] + 1
        sug = store.get(self.con, "featured_suggestion")
        return {"org": "kai", "product": "Gillnet panel, 50 m", "count": 6, "netId": first,
                "loss": {"lat": sug["lat"], "lon": sug["lon"]}, "fastForwardDays": 21, "crew": "crew_a",
                "seeded": store.get(self.con, "today") == S.plan(FISHING_ORGS)[0]}

    def start_demo(self):
        """Restore the seeded world (chain snapshot + records) so the guided demo always plays out identically.
        Transactions from earlier sessions are reverted, so no misleading records remain."""
        self.reset()
        return self.scenario()

    def resync(self):
        rows = self.con.execute("SELECT id FROM nets").fetchall()
        self.status = {r["id"]: self.chain.net(r["id"])["status"] for r in rows}

    # ================================================================ helpers
    @staticmethod
    def _loss_hash(net_id, lat, lon, day, salt):
        return keccak(f"{net_id}|{lat:.4f}|{lon:.4f}|{day}|{salt}".encode())

    def _run_forecasts(self, ids, lats, lons, day, particles, end_day):
        saved = F.END_DAY
        F.END_DAY = end_day
        try:
            F.run_group(ids, np.array(lats), np.array(lons), day, particles)
        finally:
            F.END_DAY = saved

    def _flush_ledger(self, day):
        for t in self.chain.ledger:
            self.con.execute("INSERT INTO ledger (day, tx, block, actor, label, gas, events) VALUES (?,?,?,?,?,?,?)",
                             (day, t.hash, t.block, t.actor, t.label, t.gas, json.dumps(t.events, default=str)))
        self.chain.ledger.clear()
        self.con.commit()

    @property
    def today(self):
        return store.get(self.con, "today")

    def date_of(self, day):
        return (D.currents().dates[0] + timedelta(days=int(day))).isoformat()

    @locked
    def net_row(self, net_id):
        r = self.con.execute("SELECT * FROM nets WHERE id=?", (net_id,)).fetchone()
        return dict(r) if r else None

    @locked
    def lost_nets(self):
        rows = self.con.execute("SELECT id, owner, loss_day FROM nets WHERE loss_day IS NOT NULL").fetchall()
        return [{"id": r["id"], "owner": r["owner"], "loss_day": r["loss_day"], "deposit": C.DEPOSIT}
                for r in rows if self.status.get(r["id"]) == "Lost"]

    @locked
    def board(self):
        r = self.con.execute("SELECT * FROM epochs ORDER BY epoch DESC LIMIT 1").fetchone()
        return json.loads(r["board"]) if r else None

    def _publish(self, day):
        epoch = self.chain.current_epoch() + 1
        pool = self.chain.pool()["poolAvailable"]
        b = P.build(self.lost_nets(), day, pool, epoch)
        b["date"] = self.date_of(day)
        t = self.chain.publish_epoch(bytes.fromhex(b["root"][2:]), b["total"] * WEI, f"price-list/epoch-{epoch}.json")
        b["tx"] = t.hash
        self.con.execute("INSERT INTO epochs VALUES (?,?,?,?,?,?,?,?)", (epoch, day, b["root"], b["total"], b["lambda"],
                                                                         b["sponsorAvailable"], json.dumps(b), t.hash))
        self.con.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?)",
                             [(e["netId"], epoch, day, e["bounty"]) for e in b["entries"]])
        self._flush_ledger(day)
        return b

    # ================================================================ actions
    def checkout(self, org, count, product):
        with self.lock:
            if org not in FISHING_ORGS:
                raise ValueError("unknown fishing organization")
            t, ids = self.chain.register(org, int(count), C.DEPOSIT)
            for i in ids:
                self.con.execute("INSERT INTO nets (id, owner, product, registered_day) VALUES (?,?,?,?)",
                                 (i, org, product, self.today))
                self.status[i] = "Active"
            self._flush_ledger(self.today)
            return {"ids": ids, "tx": t.hash, "deposit": C.DEPOSIT, "count": len(ids)}

    def report_loss(self, net_id, lat, lon, featured=True):
        with self.lock:
            row = self.net_row(net_id)
            if not row or self.status.get(net_id) != "Active":
                raise ValueError("only an active registered net can be reported lost")
            if not (C.LAT_MIN < lat < C.LAT_MAX and C.LON_MIN < lon < C.LON_MAX):
                raise ValueError("loss point must be inside the demo region")
            day, salt = self.today, secrets.token_hex(8)
            t = self.chain.report_loss(row["owner"], [net_id], [self._loss_hash(net_id, lat, lon, day, salt)])
            self.con.execute("UPDATE nets SET loss_day=?, loss_lat=?, loss_lon=?, loss_salt=?, featured=? WHERE id=?",
                             (day, lat, lon, salt, int(featured), net_id))
            self.status[net_id] = "Lost"
            self._flush_ledger(day)
            self._run_forecasts([net_id], [lat], [lon], day, S.FEATURED_PARTICLES, F.END_DAY)
            board = self._publish(day)
            return {"tx": t.hash, "epoch": board["epoch"], "forecast": F.summary(net_id, day)}

    def advance(self, days):
        with self.lock:
            days = int(max(1, min(days, 31)))
            last = min(self.today + days, S.BACKGROUND_END_DAY)
            for d in range(self.today + 1, last + 1):
                store.put(self.con, "today", d)
                self._publish(d)
            return {"today": self.today, "date": self.date_of(self.today)}

    def return_net(self, net_id):
        """End of life: the supplier takes the net back and the owner's deposit is refunded."""
        with self.lock:
            row = self.net_row(net_id)
            if not row or self.status.get(net_id) != "Active":
                raise ValueError("only an active net can be returned")
            before = self.chain.balance(row["owner"])
            t = self.chain.confirm_return(net_id)
            self.status[net_id] = "Returned"
            self._flush_ledger(self.today)
            return {"tx": t.hash, "refund": self.chain.balance(row["owner"]) - before, "owner": row["owner"]}

    def sponsor(self, amount):
        with self.lock:
            t = self.chain.sponsor("sponsor", int(amount))
            self._flush_ledger(self.today)
            b = self._publish(self.today)
            return {"tx": t.hash, "epoch": b["epoch"]}

    @locked
    def staged_photo(self, net_id, variant="recovered", seed=0):
        row = self.net_row(net_id)
        if not row:
            raise ValueError("unknown net")
        tag = T.tag_image(self.chain.chain_id, self.chain.escrow.address, net_id, ACTORS[row["owner"]][1])
        return T.to_jpeg(T.staged_photo(tag, variant, seed))

    @locked
    def tag_png(self, net_id):
        import io
        row = self.net_row(net_id)
        tag = T.tag_image(self.chain.chain_id, self.chain.escrow.address, net_id, ACTORS[row["owner"]][1])
        buf = io.BytesIO(); tag.save(buf, "PNG"); return buf.getvalue()

    @locked
    def identify(self, photo: bytes):
        """Read the QR tag in a photo and describe that net. Nothing is submitted."""
        text = T.decode(photo)
        if not text:
            return {"ok": False, "error": "We couldn't find a readable QR tag in this photo. Try a clearer, closer photo of the tag."}
        try:
            net_id = T.parse(text, self.chain.chain_id, self.chain.escrow.address)
        except ValueError as e:
            return {"ok": False, "error": str(e)[0].upper() + str(e)[1:] + "."}
        row = self.net_row(net_id)
        if row is None:
            return {"ok": False, "error": "This tag is valid, but the net isn't in the registry."}
        out = {"ok": True, "netId": net_id, "status": self.status.get(net_id), "product": row["product"],
               "owner": row["owner"], "ownerName": ACTORS[row["owner"]][1]}
        if row["loss_day"] is not None:
            out["lossDate"] = self.date_of(row["loss_day"])
            la, lo, _ = F.at(net_id, self.today)
            out["area"] = places.describe(float(np.median(la)), float(np.median(lo)))
        b = self.board()
        e = next((x for x in (b["entries"] if b else []) if x["netId"] == net_id), None)
        if e and out["status"] == "Lost":
            out["bounty"] = e["bounty"]
        return out

    def claim(self, photo: bytes, claimant: str, lat: float, lon: float):
        """Identity from the QR tag -> lock the advertised bounty on-chain -> verify -> resolve on-chain."""
        with self.lock:
            text = T.decode(photo)
            if not text:
                return {"ok": False, "stage": "identity", "error": "No readable QR tag found in the photo. "
                        "Take a clearer photo of the tag; no claim was created."}
            try:
                net_id = T.parse(text, self.chain.chain_id, self.chain.escrow.address)
            except ValueError as e:
                return {"ok": False, "stage": "identity", "error": str(e)}
            row = self.net_row(net_id)
            if row is None:
                return {"ok": False, "stage": "identity", "error": "Tag is valid but the net is not in the registry"}
            status = self.status.get(net_id)
            photo_hash = keccak(photo)
            day = self.today
            bounty, epoch, proof = 0, 0, []
            if status == "Lost":
                b = self.board()
                e = next((x for x in b["entries"] if x["netId"] == net_id), None) if b else None
                if e is None:
                    return {"ok": False, "stage": "price", "error": "Net is not on the current price list yet"}
                bounty, epoch, proof = e["bounty"], b["epoch"], [bytes.fromhex(p[2:]) for p in e["proof"]]
            # Submit on-chain even when the net is not claimable, so the contract's own refusal is shown.
            try:
                t, cid = self.chain.submit_claim(claimant, net_id, bounty * WEI, epoch, proof, photo_hash)
            except Exception as ex:
                self.chain.ledger.clear()
                return {"ok": False, "stage": "contract", "netId": net_id, "chainStatus": status,
                        "error": f"The smart contract refused the claim: {_revert_reason(ex, self.chain.escrow.abi)}"}
            locked = self.chain.escrow.functions.claims(cid).call()[2] / WEI
            self.status[net_id] = "ClaimPending"
            self._flush_ledger(day)
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            photo_path = EVIDENCE / f"claim_{cid}.jpg"
            photo_path.write_bytes(photo)
            net = dict(row, chainStatus=status)
            ai = V.check(photo)
            outcome, report, report_hash = VF.run(net, {"claimant": claimant, "day": day, "lat": lat, "lon": lon,
                                                        "tag": text, "photo_hash": "0x" + photo_hash.hex()}, ai)
            t2 = self.chain.resolve_claim(cid, outcome, report_hash)
            new = self.chain.net(net_id)["status"]
            self.status[net_id] = new
            self._flush_ledger(day)
            self.con.execute("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (cid, net_id, claimant, day, lat, lon, str(photo_path.name), "0x" + photo_hash.hex(),
                              locked, epoch, outcome, json.dumps(report), t.hash, t2.hash))
            self.con.commit()
            return {"ok": True, "claimId": cid, "netId": net_id, "outcome": outcome, "bountyLocked": locked,
                    "paid": locked if outcome == "accept" else 0, "report": report,
                    "reportHash": "0x" + report_hash.hex(), "txSubmit": t.hash, "txResolve": t2.hash,
                    "blockSubmit": t.block, "blockResolve": t2.block, "contract": self.chain.escrow.address,
                    "netStatus": new, "claimantBalance": self.chain.balance(claimant)}

    # ================================================================ views
    @locked
    def state(self):
        pool = self.chain.pool()
        counts = defaultdict(int)
        for s in self.status.values():
            counts[s] += 1
        b = self.board()
        from engine.chain import DEPLOYMENT
        dep = json.loads(DEPLOYMENT.read_text())
        return {"today": self.today, "date": self.date_of(self.today), "dataRange": [self.date_of(0), self.date_of(299)],
                "epoch": self.chain.current_epoch(), "pool": {k: v for k, v in pool.items() if k != "poolAvailableWei"},
                "advertised": b["total"] if b else 0, "lambda": b["lambda"] if b else None, "counts": counts,
                "deployment": dep, "network": "Local chain (anvil)" if dep["chainId"] == 31337 else f"chain {dep['chainId']}",
                "actors": {k: {"name": n, "address": self.chain.addr(k), "balance": self.chain.balance(k),
                               "kind": "org" if k in FISHING_ORGS else k.split("_")[0]} for k, (_, n) in ACTORS.items()},
                "featuredSuggestion": store.get(self.con, "featured_suggestion"),
                "vision": {"model": V.MODEL, "available": V.available()},
                "params": {"deposit": C.DEPOSIT, "coolingDays": C.COOLING_DAYS, "lambdaCap": C.LAMBDA_CAP,
                           "budgetFraction": C.BUDGET_FRACTION, "formula": "1 + 2*protected + 2*encounter60 + 1*productivity"}}

    @locked
    def market(self):
        b = self.board()
        lost = self.lost_nets()
        bounties = {e["netId"]: e["bounty"] for e in b["entries"]} if b else {}
        agg = P.zone_aggregates(lost, self.today, bounties)
        # 24 h change and short history per net
        hist = defaultdict(list)
        for r in self.con.execute("SELECT net_id, day, bounty FROM prices WHERE day >= ? ORDER BY epoch", (self.today - 14,)):
            hist[r["net_id"]].append([r["day"], r["bounty"]])
        entries = []
        products = {r["id"]: dict(r) for r in self.con.execute("SELECT id, product FROM nets WHERE loss_day IS NOT NULL")}
        for e in (b["entries"] if b else []):
            if self.status.get(e["netId"]) != "Lost":      # claimed since this list was published
                continue
            h = hist.get(e["netId"], [])
            prev = [v for d, v in h if d < self.today]
            la, lo, _ = F.at(e["netId"], self.today)
            c_lat, c_lon = float(np.median(la)), float(np.median(lo))
            row = products.get(e["netId"], {})
            entries.append({k: v for k, v in e.items() if k != "proof"} | {
                "change": e["bounty"] - prev[-1] if prev else 0, "history": h[-15:],
                "product": row.get("product"), "centroid": [round(c_lat, 3), round(c_lon, 3)],
                "area": places.describe(c_lat, c_lon),
                "priority": round(e["weight"], 2)})
        # hotspot density of all open lost nets on today's date
        lats, lons, wts = [], [], []
        for n in lost:
            la, lo, st = F.at(n["id"], self.today)
            m = st != D.OUT
            lats.append(la[m]); lons.append(lo[m]); wts.append(np.full(m.sum(), 1.0 / la.size))
        hot, density = [], {}
        if lats:
            la, lo, w = np.concatenate(lats), np.concatenate(lons), np.concatenate(wts)
            # where all lost nets together most likely are: 50/75/90% highest-density regions
            from scipy.ndimage import gaussian_filter as _gf
            g, gy, gx = np.histogram2d(la, lo, bins=[120, 240], range=[[C.LAT_MIN, C.LAT_MAX], [C.LON_MIN, C.LON_MAX]], weights=w)
            g = _gf(g, 1.6); g = g / g.sum()
            density = F.grid_contours(g, gy, gx, (0.5, 0.75, 0.9))
            h, ye, xe = np.histogram2d(la, lo, bins=[60, 120], range=[[C.LAT_MIN, C.LAT_MAX], [C.LON_MIN, C.LON_MAX]], weights=w)
            from scipy.ndimage import gaussian_filter
            h = gaussian_filter(h, 1.0)
            iy, ix = np.nonzero(h > h.max() * 0.03)
            hot = [[round(float(ye[i] + 0.25), 2), round(float(xe[j] + 0.25), 2), round(float(h[i, j]), 4)] for i, j in zip(iy, ix)]
        # recovery areas (H3 res 2): expected nets, reward value and the nets likely inside each
        areas = {}
        static_areas = R.static()
        for n in lost:
            for z, p in F.zone_probs(n["id"], self.today).items():
                if z == "outside":
                    continue
                rid = R.parent(z)
                a = areas.setdefault(rid, {"expected": 0.0, "value": 0.0, "nets": {}})
                a["expected"] += p
                a["value"] += p * bounties.get(n["id"], 0)
                a["nets"][n["id"]] = a["nets"].get(n["id"], 0.0) + p
        for rid, a in areas.items():
            a.update({k: v for k, v in static_areas.get(rid, {}).items() if k != "boundary"})
            a["expected"] = round(a["expected"], 2); a["value"] = round(a["value"])
            a["nets"] = sorted(({"netId": i, "p": round(p, 3), "bounty": bounties.get(i, 0)} for i, p in a["nets"].items() if p >= 0.03),
                               key=lambda x: -x["p"] * x["bounty"])
        return {"day": self.today, "date": self.date_of(self.today), "epoch": b["epoch"] if b else 0, "areas": areas,
                "root": b["root"] if b else None, "total": b["total"] if b else 0, "lambda": b["lambda"] if b else None,
                "sponsorAvailable": b["sponsorAvailable"] if b else 0, "entries": entries, "zones": agg, "hotspots": hot,
                "density": density}

    @locked
    def net_detail(self, net_id):
        row = self.net_row(net_id)
        if not row:
            raise ValueError("unknown net")
        chain_net = self.chain.net(net_id)
        timeline = []
        for r in self.con.execute("SELECT * FROM ledger ORDER BY seq"):
            evs = [e for e in json.loads(r["events"]) if e["args"].get("netId") == net_id]
            for e in evs:
                timeline.append({"day": r["day"], "date": self.date_of(r["day"]), "event": e["event"], "tx": r["tx"],
                                 "block": r["block"], "label": r["label"], "args": e["args"]})
        prices = [[r["day"], r["bounty"]] for r in self.con.execute(
            "SELECT day, bounty FROM prices WHERE net_id=? ORDER BY epoch", (net_id,))]
        claims = [dict(r) | {"report": json.loads(r["report"]), "date": self.date_of(r["day"])} for r in self.con.execute(
            "SELECT * FROM claims WHERE net_id=? ORDER BY id", (net_id,))]
        out = {"id": net_id, "owner": row["owner"], "ownerName": ACTORS[row["owner"]][1], "product": row["product"],
               "registeredDate": self.date_of(row["registered_day"]), "chain": chain_net, "timeline": timeline,
               "prices": prices, "claims": claims, "simulated": not row["featured"], "featured": bool(row["featured"])}
        if row["loss_day"] is not None:
            out["loss"] = {"day": row["loss_day"], "date": self.date_of(row["loss_day"]),
                           "lat": row["loss_lat"], "lon": row["loss_lon"]}
            out["forecast"] = F.summary(net_id, self.today)
            out["loss"]["area"] = places.describe(row["loss_lat"], row["loss_lon"])
            out["forecast"]["area"] = places.describe(*out["forecast"]["centroid"])
        b = self.board()
        e = next((x for x in (b["entries"] if b else []) if x["netId"] == net_id), None)
        if e:
            out["price"] = {k: v for k, v in e.items() if k != "proof"} | {"epoch": b["epoch"]}
        return out

    @locked
    def net_forecast(self, net_id, max_days=90, sample=300):
        row = self.net_row(net_id)
        if not row or row["loss_day"] is None:
            raise ValueError("net has no loss report")
        key = (net_id, self.today)
        if key in self._forecast_cache:
            return self._forecast_cache[key]
        start, lat, lon, st = F.load(net_id)
        last = min(start + lat.shape[0] - 1, max(self.today, start) + max_days)
        idx = np.random.default_rng(0).choice(lat.shape[1], min(sample, lat.shape[1]), replace=False)
        frames = []
        for d in range(start, last + 1, 1):
            la, lo, s = F.at(net_id, d)
            frames.append({"day": d, "date": self.date_of(d),
                           "particles": np.round(np.c_[la[idx], lo[idx]], 3).tolist(),
                           "contours": F.contours(la, lo) if (d - start) % 2 == 0 or d == last else None,
                           "beached": float(np.mean(s == D.BEACHED)), "outside": float(np.mean(s == D.OUT))})
        res = {"netId": net_id, "loss": {"day": start, "lat": row["loss_lat"], "lon": row["loss_lon"]},
               "today": self.today, "frames": frames, "particles": int(lat.shape[1])}
        self._forecast_cache[key] = res
        return res

    @locked
    def ledger(self, since=0, limit=200):
        rows = self.con.execute("SELECT * FROM ledger WHERE seq > ? ORDER BY seq DESC LIMIT ?", (since, limit)).fetchall()
        return [dict(r) | {"events": json.loads(r["events"]), "date": self.date_of(r["day"])} for r in rows]

    @locked
    def nets_of(self, owner):
        rows = self.con.execute("SELECT * FROM nets WHERE owner=? ORDER BY id", (owner,)).fetchall()
        b = self.board()
        bounty = {e["netId"]: e["bounty"] for e in (b["entries"] if b else [])}
        paid = {r["net_id"]: r["bounty"] for r in self.con.execute("SELECT net_id, bounty FROM claims WHERE outcome='accept'")}
        out = []
        for r in rows:
            st = self.status.get(r["id"])
            n = {"id": r["id"], "product": r["product"], "status": st, "registeredDate": self.date_of(r["registered_day"]),
                 "featured": bool(r["featured"])}
            if r["loss_day"] is not None:
                n["lossDate"] = self.date_of(r["loss_day"])
                n["daysLost"] = self.today - r["loss_day"]
                if st in ("Lost", "ClaimPending"):
                    la, lo, _ = F.at(r["id"], self.today)
                    n["area"] = places.describe(float(np.median(la)), float(np.median(lo)))
                    n["bounty"] = bounty.get(r["id"])
            if r["id"] in paid:
                n["paid"] = paid[r["id"]]
            out.append(n)
        return out


def _revert_reason(ex, abi):
    """Turn a custom-error revert into its name, e.g. BadStatus(Recovered)."""
    from eth_abi import decode as abi_decode
    from engine.chain import STATUS
    data = getattr(ex, "data", None) or (ex.args[1] if len(ex.args) > 1 else "") or str(ex)
    data = data if isinstance(data, str) else str(data)
    for item in abi:
        if item.get("type") != "error":
            continue
        types = [i["type"] for i in item["inputs"]]
        sel = "0x" + keccak(f"{item['name']}({','.join(types)})".encode())[:4].hex()
        if sel in data:
            args = data[data.index(sel) + 10:]
            vals = abi_decode(types, bytes.fromhex(args[:64 * len(types)])) if types and len(args) >= 64 * len(types) else ()
            if item["name"] == "BadStatus" and vals:
                return f"BadStatus({STATUS[vals[0]]}): this net is not claimable in its current state"
            return item["name"]
    return str(ex)[:200]
