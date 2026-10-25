"""Precomputed example for the landing-page story: one net lost at the featured point, its drift over
60 days, and how its reward would evolve. Uses the same drift engine and zones as the live system,
but never touches the chain or the live forecast files."""
import json

import numpy as np

from engine import config as C
from engine import drift as D
from engine import forecast as F
from engine import places
from engine import scenario as S
from engine import zones as Z

STORY = C.RUNTIME / "story.json"
DAYS = 60


def build(lam=280.0):
    cur = D.currents()
    start = cur.day_index(S.TODAY)
    sug = S.FEATURED_SUGGESTION
    e = D.simulate(sug["lat"], sug["lon"], start, n=800, horizon_days=DAYS, seed=11)
    zones = Z.load()
    idx = np.random.default_rng(0).choice(800, 260, replace=False)
    frames = []
    for d in range(DAYS + 1):
        la, lo = e.lat[d], e.lon[d]
        cells = Z.cell_of(la, lo)
        w = float(np.mean([zones[c]["priority"] if c in zones else 1.0 for c in cells]))
        reward = C.DEPOSIT + (lam * w if d >= C.COOLING_DAYS else 0)
        frames.append({"day": d, "date": cur.dates[int(start) + d].isoformat(),
                       "particles": np.round(np.c_[la[idx], lo[idx]], 3).tolist(),
                       "contours": F.contours(la, lo) if d % 2 == 0 else None,
                       "reward": round(reward), "priority": round(w, 2),
                       "area": places.describe(float(np.median(la)), float(np.median(lo)))})
    out = {"loss": {"lat": sug["lat"], "lon": sug["lon"], "date": S.TODAY.isoformat(),
                    "area": places.describe(sug["lat"], sug["lon"])}, "frames": frames}
    STORY.write_text(json.dumps(out))
    return out


def load():
    if STORY.exists():
        return json.loads(STORY.read_text())
    return build()
