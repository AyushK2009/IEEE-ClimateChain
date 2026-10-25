"""Blockchain gateway: deploy the contracts, sign transactions for the simulated actors, read state.

Local chain (anvil) by default. Each simulated actor has its own address; on anvil these are the
standard development accounts (publicly known keys, play money only, never use them elsewhere).
"""
import json
import os
import time
from dataclasses import dataclass

from eth_account import Account
from web3 import Web3

from engine import config as C

ARTIFACTS = C.ROOT / "contracts" / "out"
DEPLOYMENT = C.RUNTIME / "deployment.json"
ANVIL_MNEMONIC = "test test test test test test test test test test test junk"
WEI = 10**18

# Simulated actors -> HD account index. The chain enforces their separate identities.
ACTORS = {
    "admin":      (0, "Oracle service (pricing + verification)"),
    "supplier":   (1, "NetWorks Supply Co. (gear supplier)"),
    "sponsor":    (2, "Blue Ocean Fund (sponsor)"),
    "pacific":    (3, "Pacific Longline Co-op"),
    "kai":        (4, "Kai Fisheries"),
    "northstar":  (5, "Northstar Seafoods"),
    "aleutian":   (6, "Aleutian Gillnet Group"),
    "crew_a":     (7, "Tern Island Recovery Crew"),
    "crew_b":     (8, "Midway Salvage Collective"),
}
FISHING_ORGS = ["pacific", "kai", "northstar", "aleutian"]
STATUS = ["None", "Active", "Lost", "ClaimPending", "Recovered", "Returned"]
OUTCOME = {"accept": 1, "reject": 2, "flag": 3}


def _artifact(name):
    a = json.loads((ARTIFACTS / f"{name}.sol" / f"{name}.json").read_text())
    return a["abi"], a["bytecode"]["object"]


@dataclass
class Tx:
    hash: str
    block: int
    gas: int
    label: str
    actor: str
    events: list


class Chain:
    def __init__(self, rpc=None):
        self.rpc = rpc or os.environ.get("RPC_URL", "http://127.0.0.1:8545")
        self.w3 = Web3(Web3.HTTPProvider(self.rpc, request_kwargs={"timeout": 60}))
        Account.enable_unaudited_hdwallet_features()
        mnemonic = os.environ.get("ACTOR_MNEMONIC", ANVIL_MNEMONIC)
        self.accounts = {k: Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/{i}")
                         for k, (i, _) in ACTORS.items()}
        self.ledger: list[Tx] = []
        self.usd = self.escrow = None

    # ------------------------------------------------------------ setup
    def connected(self):
        try:
            return self.w3.is_connected() and self.w3.eth.chain_id is not None
        except Exception:
            return False

    @property
    def chain_id(self):
        return self.w3.eth.chain_id

    def addr(self, actor):
        return self.accounts[actor].address

    def actor_of(self, address):
        for k, a in self.accounts.items():
            if a.address.lower() == str(address).lower():
                return k
        return None

    def deploy(self):
        admin = self.addr("admin")
        usd_abi, usd_bin = _artifact("DemoUSD")
        esc_abi, esc_bin = _artifact("GearEscrow")
        usd_addr = self._deploy("admin", usd_abi, usd_bin, admin, label="Deploy DemoUSD (play money)")
        esc_addr = self._deploy("admin", esc_abi, esc_bin, usd_addr, admin, label="Deploy GearEscrow")
        self.attach(usd_addr, esc_addr)
        for role, actor in (("SUPPLIER_ROLE", "supplier"), ("PRICER_ROLE", "admin"), ("VERIFIER_ROLE", "admin")):
            rid = self.escrow.functions[role]().call()
            self.send("admin", self.escrow.functions.grantRole(rid, self.addr(actor)), f"Grant {role} to {actor}")
        C.RUNTIME.mkdir(parents=True, exist_ok=True)
        DEPLOYMENT.write_text(json.dumps({"chainId": self.chain_id, "rpc": self.rpc, "usd": usd_addr,
                                          "escrow": esc_addr, "deployedAt": int(time.time())}, indent=1))
        return usd_addr, esc_addr

    def attach(self, usd_addr, esc_addr):
        self.usd = self.w3.eth.contract(address=usd_addr, abi=_artifact("DemoUSD")[0])
        self.escrow = self.w3.eth.contract(address=esc_addr, abi=_artifact("GearEscrow")[0])

    def attach_existing(self):
        if not DEPLOYMENT.exists():
            return False
        d = json.loads(DEPLOYMENT.read_text())
        if d["chainId"] != self.chain_id or self.w3.eth.get_code(d["escrow"]) in (b"", b"\x00"):
            return False
        self.attach(d["usd"], d["escrow"])
        return True

    # ------------------------------------------------------------ transactions
    def _deploy(self, actor, abi, bytecode, *args, label):
        c = self.w3.eth.contract(abi=abi, bytecode=bytecode)
        tx = self._sign_send(actor, c.constructor(*args), label)
        return self.w3.eth.get_transaction_receipt(tx.hash)["contractAddress"]

    def _sign_send(self, actor, fn, label):
        acct = self.accounts[actor]
        tx = fn.build_transaction({"from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address, "pending"),
                                   "chainId": self.chain_id})
        signed = acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        r = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if r["status"] != 1:
            raise RuntimeError(f"transaction failed: {label}")
        events = self._decode(r)
        t = Tx("0x" + h.hex().removeprefix("0x"), r["blockNumber"], r["gasUsed"], label, actor, events)
        self.ledger.append(t)
        return t

    def send(self, actor, fn, label):
        return self._sign_send(actor, fn, label)

    def _decode(self, receipt):
        out = []
        if self.escrow is None:
            return out
        for ev in self.escrow.abi:
            if ev.get("type") != "event":
                continue
            for log in getattr(self.escrow.events, ev["name"])().process_receipt(receipt, errors=_DISCARD):
                args = {k: (v.hex() if isinstance(v, (bytes, bytearray)) else v) for k, v in dict(log["args"]).items()}
                out.append({"event": ev["name"], "args": args})
        return out

    # ------------------------------------------------------------ actions
    def mint(self, actor, amount):
        return self.send("admin", self.usd.functions.mint(self.addr(actor), amount * WEI), f"Mint {amount:,} dUSD to {actor}")

    def approve_escrow(self, actor):
        return self.send(actor, self.usd.functions.approve(self.escrow.address, 2**256 - 1), f"{actor} approves escrow")

    def register(self, buyer, count, deposit):
        t = self.send("supplier", self.escrow.functions.registerNets(self.addr(buyer), count, deposit * WEI),
                      f"Checkout: {count} nets for {buyer}")
        ids = [e["args"]["netId"] for e in t.events if e["event"] == "NetRegistered"]
        return t, ids

    def report_loss(self, owner, ids, loss_hashes):
        return self.send(owner, self.escrow.functions.reportLoss(ids, loss_hashes),
                         f"{owner} reports {len(ids)} net(s) lost")

    def confirm_return(self, net_id):
        return self.send("supplier", self.escrow.functions.confirmReturn(net_id), f"Net #{net_id} returned to supplier")

    def sponsor(self, actor, amount):
        return self.send(actor, self.escrow.functions.sponsor(amount * WEI), f"{actor} sponsors {amount:,} dUSD")

    def publish_epoch(self, root, total_wei, uri):
        return self.send("admin", self.escrow.functions.publishEpoch(root, total_wei, uri), f"Publish price list ({uri})")

    def submit_claim(self, claimant, net_id, bounty_wei, epoch, proof, photo_hash):
        t = self.send(claimant, self.escrow.functions.submitClaim(net_id, bounty_wei, epoch, proof, photo_hash),
                      f"{claimant} claims net #{net_id}")
        cid = next(e["args"]["claimId"] for e in t.events if e["event"] == "ClaimSubmitted")
        return t, cid

    def resolve_claim(self, claim_id, outcome, report_hash):
        return self.send("admin", self.escrow.functions.resolveClaim(claim_id, OUTCOME[outcome], report_hash),
                         f"Verifier: claim #{claim_id} -> {outcome}")

    # ------------------------------------------------------------ reads
    def pool(self):
        bal, held, avail, res = self.escrow.functions.poolState().call()
        return {"balance": bal / WEI, "depositsHeld": held / WEI, "poolAvailable": avail / WEI, "poolReserved": res / WEI,
                "poolAvailableWei": avail}

    def net(self, net_id):
        deposit, lost_at, status, unreported, loss_hash, open_claim = self.escrow.functions.nets(net_id).call()
        return {"id": net_id, "owner": self.actor_of(self.escrow.functions.ownerOf(net_id).call()),
                "deposit": deposit / WEI, "status": STATUS[status], "unreported": unreported, "openClaim": open_claim}

    def current_epoch(self):
        return self.escrow.functions.currentEpoch().call()

    def balance(self, actor):
        return self.usd.functions.balanceOf(self.addr(actor)).call() / WEI

    def snapshot(self):
        return self.w3.provider.make_request("evm_snapshot", [])["result"]

    def revert(self, snap_id):
        return self.w3.provider.make_request("evm_revert", [snap_id])["result"]


class _Discard:
    pass


try:
    from web3.logs import DISCARD as _DISCARD
except Exception:   # pragma: no cover
    _DISCARD = _Discard()
