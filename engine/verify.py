"""Claim verification (TECHNICAL_PROPOSAL.md section 6). Identity comes from the QR tag before this runs.

Hard failures reject, soft signals flag, otherwise accept. Each check carries a strength label so the
report never presents a photo check as proof of recovery from the sea.
"""
import json

from eth_utils import keccak

from engine import config as C
from engine import drift as D
from engine import forecast as F
from engine import vision as V

REACH_FACTOR, REACH_MARGIN_KM = 1.3, 50.0
CLOUD_PASS, CLOUD_FLAG = 0.90, 0.99


def run(net, claim, ai_answer):
    """net: off-chain record + chain status; claim: claimant, day, lat, lon, tag text, photo hash."""
    checks = []

    def add(cid, name, status, detail, strength):
        checks.append({"id": cid, "name": name, "status": status, "detail": detail, "strength": strength})

    add("identity", "Net identity from QR tag", "pass",
        f"Tag decoded to net #{net['id']} (registry match, checksum ok)", "deterministic")
    reported = net["chainStatus"] == "Lost"
    if reported:
        add("eligibility", "Eligible for a reward", "pass",
            f"Net is reported lost on-chain; claimant is not the owner", "enforced on-chain")
    else:
        add("eligibility", "Eligible for a reward", "pass",
            "Net was never reported lost: unreported recovery, reward is only the owner's forfeited deposit",
            "enforced on-chain")

    if reported:
        days = claim["day"] - net["loss_day"]
        if days < 0:
            add("timing", "Claim after the loss", "fail", "Claim date is before the reported loss", "strong")
        else:
            add("timing", "Claim after the loss", "pass", f"Claimed {days} days after the loss", "strong")
        dist = float(D.haversine_km(net["loss_lat"], net["loss_lon"], claim["lat"], claim["lon"]))
        reach = F.max_reach_km(net["id"], claim["day"], net["loss_lat"], net["loss_lon"])
        limit = reach * REACH_FACTOR + REACH_MARGIN_KM
        if dist > limit:
            add("reach", "Within physical drift reach", "fail",
                f"Claimed spot is {dist:,.0f} km from the loss point, but no simulated copy drifted farther than "
                f"{reach:,.0f} km (limit with margin {limit:,.0f} km)", "strong")
        else:
            add("reach", "Within physical drift reach", "pass",
                f"{dist:,.0f} km from the loss point; physical limit with margin {limit:,.0f} km", "strong")
        level = F.hdr_level(net["id"], claim["day"], claim["lat"], claim["lon"])
        if level <= 0.5:
            add("cloud", "Inside the forecast cloud", "pass",
                "In the core of the forecast cloud (inside the 50% region) on the claim date", "moderate")
        elif level <= CLOUD_PASS:
            add("cloud", "Inside the forecast cloud", "pass",
                f"Inside the 90% forecast cloud on the claim date ({level:.0%} contour)", "moderate")
        elif level <= CLOUD_FLAG:
            add("cloud", "Inside the forecast cloud", "pass",
                f"At the edge of the cloud ({level:.0%} region): unusual but plausible", "moderate")
        else:
            add("cloud", "Inside the forecast cloud", "flag",
                "Outside the 99% cloud (within physical reach, so flagged, not rejected: forecasts can be wrong)",
                "moderate")
    else:
        for cid, name in (("timing", "Claim after the loss"), ("reach", "Within physical drift reach"),
                          ("cloud", "Inside the forecast cloud")):
            add(cid, name, "skip", "No loss report, so there is no forecast to compare against", "n/a")

    st, detail = V.decide(ai_answer)
    add("scene", "Physical gear in the photo (local AI)", st, detail, "moderate (model opinion)")

    statuses = [c["status"] for c in checks]
    outcome = "reject" if "fail" in statuses else "flag" if "flag" in statuses else "accept"
    report = {"netId": net["id"], "claimant": claim["claimant"], "claimDay": claim["day"],
              "claimLocation": [claim["lat"], claim["lon"]], "photoHash": claim["photo_hash"],
              "tag": claim["tag"], "unreported": not reported, "checks": checks, "outcome": outcome,
              "ai": {k: v for k, v in ai_answer.items()}, "thresholds": {
                  "reachFactor": REACH_FACTOR, "reachMarginKm": REACH_MARGIN_KM,
                  "cloudPass": CLOUD_PASS, "cloudFlag": CLOUD_FLAG},
              "model": {"drift": "OSCAR v2.0 2021, RK4 3h, K=%g m2/s" % C.DIFFUSIVITY_M2S, "vision": V.MODEL}}
    report_hash = keccak(json.dumps(report, sort_keys=True, separators=(",", ":")).encode())
    return outcome, report, report_hash
