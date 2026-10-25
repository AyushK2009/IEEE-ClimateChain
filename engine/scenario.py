"""The simulated world: fishing organizations, their nets, and past loss events.

Everything here is SIMULATED and labeled as such in the app. Loss locations are drawn from
fishing-ground-like bands in the North Pacific; they are not real fishing data. The currents they
drift on are real (OSCAR 2021, historical replay).
"""
from datetime import date

import numpy as np

from engine import config as C
from engine import drift as D

SEED = 2026
TODAY = date(2021, 7, 1)                      # demo "today" at the start of the replay
NETS_PER_ORG = 110
LOST_PER_ORG = 90
BACKGROUND_PARTICLES = 200
FEATURED_PARTICLES = 1000
BACKGROUND_END_DAY = 240
FEATURED_SUGGESTION = {"lat": 27.0, "lon": 176.0,
                       "why": "Open water west of Papahanaumokuakea; over ~60 days the forecast drifts into the monument"}

PRODUCTS = ["Gillnet panel, 50 m", "Purse seine section", "Midwater trawl net", "Longline set (lines + floats)"]
# (name, lat mean, lon mean, lat sd, lon sd, weight); 0-360 longitudes
GROUNDS = [
    ("Transition zone, west", 40.0, 180.0, 1.5, 3.0, 0.30),
    ("Transition zone, central", 37.0, 197.0, 1.5, 3.5, 0.30),
    ("Subtropical front, east", 33.0, 213.0, 1.5, 3.0, 0.20),
    ("North of the Hawaiian chain", 29.5, 186.0, 1.2, 2.5, 0.20),
]


def plan(org_names):
    """Deterministic list of past losses: dicts with org, loss_day, lat, lon, ground."""
    rng = np.random.default_rng(SEED)
    cur = D.currents()
    today = cur.day_index(TODAY)
    w = np.array([g[5] for g in GROUNDS]); w /= w.sum()
    losses = []
    for org in org_names:
        for _ in range(LOST_PER_ORG):
            while True:
                g = GROUNDS[rng.choice(len(GROUNDS), p=w)]
                lat, lon = rng.normal(g[1], g[3]), rng.normal(g[2], g[4])
                if 16 < lat < 44 and 171 < lon < 229 and not cur.is_land(np.array([lat]), np.array([lon]))[0]:
                    break
            losses.append({"org": org, "loss_day": int(rng.integers(3, today + 1)), "lat": round(float(lat), 3),
                           "lon": round(float(lon), 3), "ground": g[0]})
    return int(today), losses
