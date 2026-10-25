"""Per-net drift forecasts: run, cache on disk, and turn into map-ready clouds and zone probabilities."""
from collections import Counter
from functools import lru_cache

import contourpy
import numpy as np

from engine import config as C
from engine import drift as D
from engine import zones as Z

DIR = C.RUNTIME / "forecasts"
END_DAY = 299                      # last day of the 2021 currents data (index into the 300-day run)


def path(net_id):
    return DIR / f"net_{net_id}.npz"


def run_group(net_ids, lats, lons, loss_day, particles):
    """Simulate several nets lost on the same day in one batch and save each net's ensemble."""
    DIR.mkdir(parents=True, exist_ok=True)
    LA = np.repeat(lats, particles); LO = np.repeat(lons, particles)
    e = D.simulate(LA, LO, loss_day, n=LA.size, horizon_days=END_DAY - loss_day, seed=int(loss_day) * 7919 + int(net_ids[0]))
    for k, nid in enumerate(net_ids):
        s = slice(k * particles, (k + 1) * particles)
        np.savez_compressed(path(nid), start_day=loss_day, lat=e.lat[:, s].astype(np.float32),
                            lon=e.lon[:, s].astype(np.float32), status=e.status[:, s])
    load.cache_clear()


@lru_cache(maxsize=1024)
def load(net_id):
    z = np.load(path(net_id))
    return int(z["start_day"]), z["lat"], z["lon"], z["status"]


def at(net_id, day):
    """Particle positions and statuses on an absolute day (clamped to the forecast range)."""
    start, lat, lon, st = load(net_id)
    i = int(np.clip(day - start, 0, lat.shape[0] - 1))
    return lat[i], lon[i], st[i]


def zone_probs(net_id, day):
    lat, lon, st = at(net_id, day)
    inside = st != D.OUT
    cells = Z.cell_of(lat[inside], lon[inside]) if inside.any() else []
    cnt = Counter(cells)
    n = lat.size
    probs = {c: k / n for c, k in cnt.items()}
    out = 1 - inside.mean()
    if out > 0:
        probs["outside"] = float(out)
    return probs


def grid_contours(g, ye, xe, levels):
    """Highest-density-region polygons for a normalised grid: {level: [[outer, *holes], ...]}."""
    thr = D.hdr_thresholds(g, levels)
    gen = contourpy.contour_generator(0.5 * (xe[:-1] + xe[1:]), 0.5 * (ye[:-1] + ye[1:]), g,
                                      fill_type=contourpy.FillType.OuterOffset)
    out = {}
    for lvl, t in zip(levels, thr):
        polys, offsets = gen.filled(t, g.max() + 1)
        out[str(lvl)] = [[np.round(pts[a:b], 3).tolist() for a, b in zip(off[:-1], off[1:])]
                         for pts, off in zip(polys, offsets) if len(pts) >= 4]
    return out


def contours(lat, lon, levels=(0.5, 0.9)):
    """GeoJSON-ready polygons for the highest-density regions holding 50% / 90% of particles."""
    g, ye, xe = D.density(lat, lon, res=0.1, smooth_cells=1.5)
    thr = D.hdr_thresholds(g, levels)
    gen = contourpy.contour_generator(0.5 * (xe[:-1] + xe[1:]), 0.5 * (ye[:-1] + ye[1:]), g,
                                      fill_type=contourpy.FillType.OuterOffset)
    out = {}
    for lvl, t in zip(levels, thr):
        polys, offsets = gen.filled(t, g.max() + 1)
        out[str(lvl)] = [[np.round(pts[a:b], 3).tolist() for a, b in zip(off[:-1], off[1:])]   # [outer, *holes]
                         for pts, off in zip(polys, offsets) if len(pts) >= 4]
    return out


def summary(net_id, day):
    lat, lon, st = at(net_id, day)
    start, *_ = load(net_id)
    return {"day": int(day), "daysSinceLoss": int(day - start), "drifting": float(np.mean(st == D.DRIFTING)),
            "beached": float(np.mean(st == D.BEACHED)), "outside": float(np.mean(st == D.OUT)),
            "centroid": [float(np.median(lat)), float(np.median(lon))]}


def max_reach_km(net_id, day, lat0, lon0):
    lat, lon, _ = at(net_id, day)
    return float(D.haversine_km(lat0, lon0, lat, lon).max())


def hdr_level(net_id, day, lat, lon):
    plat, plon, _ = at(net_id, day)
    g, ye, xe = D.density(plat, plon, res=0.1, smooth_cells=1.5)
    return D.hdr_level_of_point(g, ye, xe, lat, lon)
