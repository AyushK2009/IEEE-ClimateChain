"""Recovery zones (H3 hexagons) and their environmental priority (TECHNICAL_PROPOSAL.md section 4.5).

Priority_z = 1 + 2*Protected + 2*Encounter60 + 1*Productivity, each term in 0..1:
  Protected     share of the hex inside a marine protected area or within 25 km of land
  Encounter60   simulated chance that gear starting in the hex enters such water within 60 days
  Productivity  2021 mean log10 chlorophyll, rescaled between the region's 5th and 95th percentiles

    python -m engine.zones          # precompute data/derived/zones.json (+ figure)
"""
import csv
import json
import struct
from functools import lru_cache

import h3
import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import Polygon

from engine import config as C
from engine import drift as D

ZONES_JSON = C.DERIVED / "zones.json"
SENSITIVE_RES = 0.05
KM_PER_DEG = 111.2


def to180(lon):
    return ((np.asarray(lon) + 180) % 360) - 180


def to360(lon):
    return np.asarray(lon) % 360


def cell_of(lat, lon):
    """H3 cell for a point given in 0-360 longitudes (vectorised over arrays)."""
    lat = np.atleast_1d(lat); lon = to180(np.atleast_1d(lon))
    return [h3.latlng_to_cell(float(a), float(b), C.H3_RES) for a, b in zip(lat, lon)]


def boundary360(cell):
    return [[round(float(lng % 360), 4), round(float(lat), 4)] for lat, lng in h3.cell_to_boundary(cell)]


# ---------- environmental layers (all converted to 0-360 longitudes) ----------

def _shp_rings(path):
    b = open(path, "rb").read()
    rings, i = [], 100
    while i < len(b):
        _, clen = struct.unpack(">ii", b[i:i + 8]); c = b[i + 8:i + 8 + clen * 2]; i += 8 + clen * 2
        if struct.unpack("<i", c[:4])[0] not in (5, 15, 25):
            continue
        npart, npt = struct.unpack("<ii", c[36:44])
        parts = list(struct.unpack(f"<{npart}i", c[44:44 + 4 * npart])) + [npt]
        pts = np.frombuffer(c, "<f8", count=2 * npt, offset=44 + 4 * npart).reshape(-1, 2).copy()
        pts[:, 0] %= 360
        rings += [pts[a:z] for a, z in zip(parts, parts[1:])]
    return rings


def _even_odd_union(rings):
    """Shapefile rings -> one geometry (outer rings minus holes) via symmetric difference."""
    geom = None
    for r in rings:
        p = Polygon(r).buffer(0)
        geom = p if geom is None else geom.symmetric_difference(p)
    return geom


@lru_cache(maxsize=1)
def layers():
    mpa = shapely.union_all([
        _even_odd_union(_shp_rings(C.ENV / "pmnm_py/PMNM_py_files/PMNM_py.shp")),
        _even_odd_union(_shp_rings(C.ENV / "hihwnms_py2/hihwnms_py.shp")),
    ])
    land_polys = []
    for name in ("ne_10m_land", "ne_10m_minor_islands"):
        for f in json.load(open(C.ENV / f"{name}.geojson"))["features"]:
            g = f["geometry"]
            for p in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]):
                r = np.array(p[0], float); r[:, 0] %= 360
                if ((r[:, 0] > C.LON_MIN - 2) & (r[:, 0] < C.LON_MAX + 2)
                        & (r[:, 1] > C.LAT_MIN - 2) & (r[:, 1] < C.LAT_MAX + 2)).any() and np.ptp(r[:, 0]) < 180:
                    land_polys.append(Polygon(r).buffer(0))
    land = shapely.union_all(land_polys)
    return mpa, land


def sensitive_raster(res=SENSITIVE_RES):
    """Boolean grid: inside an MPA or within NEAR_SHORE_KM of land. Returns (grid, lat0, lon0, res)."""
    mpa, land = layers()
    lats = np.arange(C.LAT_MIN + res / 2, C.LAT_MAX, res)
    lons = np.arange(C.LON_MIN + res / 2, C.LON_MAX, res)
    LO, LA = np.meshgrid(lons, lats)
    inside = shapely.contains_xy(mpa, LO, LA) | shapely.contains_xy(land, LO, LA)
    # distance to land via densified coastline vertices in a local km frame
    coast = shapely.segmentize(land.boundary, 0.02)
    xy = shapely.get_coordinates(coast)
    k = np.cos(np.radians(30.0))
    tree = cKDTree(np.c_[xy[:, 0] * k, xy[:, 1]] * KM_PER_DEG)
    dist, _ = tree.query(np.c_[LO.ravel() * k, LA.ravel()] * KM_PER_DEG, distance_upper_bound=C.NEAR_SHORE_KM)
    near = np.isfinite(dist).reshape(LA.shape)
    return inside | near, C.LAT_MIN, C.LON_MIN, res


def lookup(grid, lat0, lon0, res, lat, lon):
    iy = np.clip(((lat - lat0) / res).astype(int), 0, grid.shape[0] - 1)
    ix = np.clip(((lon - lon0) / res).astype(int), 0, grid.shape[1] - 1)
    return grid[iy, ix]


def productivity_by_cell():
    acc = {}
    for name in ("chl_w.csv", "chl_e.csv"):
        rows = csv.reader(open(C.ENV / name)); next(rows); next(rows)
        for _, la, lo, c in rows:
            if c and c != "NaN" and float(c) > 0:
                key = (round(float(la) * 2) / 2, round(float(lo) % 360 * 2) / 2)
                acc.setdefault(key, []).append(np.log10(float(c)))
    pts = {k: float(np.mean(v)) for k, v in acc.items() if len(v) >= 3}
    vals = np.array(list(pts.values()))
    lo_, hi_ = np.percentile(vals, 5), np.percentile(vals, 95)
    keys = np.array(list(pts.keys()))
    return keys, np.clip((vals - lo_) / (hi_ - lo_), 0, 1)


# ---------- precompute ----------

def build(seed_per_cell=64, start_days=(0, 60, 120, 180)):
    step = 0.1
    lats = np.arange(C.LAT_MIN + step / 2, C.LAT_MAX, step)
    lons = np.arange(C.LON_MIN + step / 2, C.LON_MAX, step)
    LO, LA = np.meshgrid(lons, lats)
    sample_cells = np.array(cell_of(LA.ravel(), LO.ravel()))
    cells = sorted(set(sample_cells))
    index = {c: i for i, c in enumerate(cells)}
    idx = np.array([index[c] for c in sample_cells])
    print(f"{len(cells)} H3 res-{C.H3_RES} zones cover the region")

    grid, glat0, glon0, gres = sensitive_raster()
    sens_samples = lookup(grid, glat0, glon0, gres, LA.ravel(), LO.ravel())
    protected = np.bincount(idx, sens_samples, len(cells)) / np.bincount(idx, minlength=len(cells))

    # Encounter60: seed particles uniformly inside each zone's sampled points.
    rng = np.random.default_rng(7)
    seeds = []
    for i in range(len(cells)):
        pts = np.where(idx == i)[0]
        seeds.append(rng.choice(pts, seed_per_cell, replace=len(pts) < seed_per_cell))
    seeds = np.concatenate(seeds)
    owner = np.repeat(np.arange(len(cells)), seed_per_cell)
    hits = np.zeros(len(cells))
    for sd in start_days:
        e = D.simulate(LA.ravel()[seeds], LO.ravel()[seeds], sd, n=seeds.size,
                       horizon_days=C.ENCOUNTER_DAYS, seed=sd, start_sigma_km=0)
        met = np.zeros(seeds.size, bool)
        for d in range(1, e.days + 1):
            met |= lookup(grid, glat0, glon0, gres, e.lat[d], e.lon[d]) | (e.status[d] == D.BEACHED)
        hits += np.bincount(owner, met, len(cells))
    encounter = hits / (seed_per_cell * len(start_days))

    keys, prod = productivity_by_cell()
    chl_cells = np.array(cell_of(keys[:, 0], keys[:, 1]))
    prod_sum = {}
    for c, p in zip(chl_cells, prod):
        prod_sum.setdefault(c, []).append(p)
    centers = np.array([h3.cell_to_latlng(c) for c in cells]); centers[:, 1] %= 360
    tree = cKDTree(keys[:, ::-1])
    productivity = np.array([np.mean(prod_sum[c]) if c in prod_sum else prod[tree.query(centers[i, ::-1])[1]]
                             for i, c in enumerate(cells)])

    priority = 1 + C.W_PROTECTED * protected + C.W_ENCOUNTER * encounter + C.W_PRODUCTIVITY * productivity
    zones = [dict(id=c, lat=round(float(centers[i, 0]), 4), lon=round(float(centers[i, 1]), 4),
                  boundary=boundary360(c), protected=round(float(protected[i]), 3),
                  encounter60=round(float(encounter[i]), 3), productivity=round(float(productivity[i]), 3),
                  priority=round(float(priority[i]), 3)) for i, c in enumerate(cells)]
    ZONES_JSON.write_text(json.dumps({"formula": "1 + 2*protected + 2*encounter60 + 1*productivity",
                                      "h3_res": C.H3_RES, "zones": zones}))
    return zones


@lru_cache(maxsize=1)
def load():
    z = json.loads(ZONES_JSON.read_text())["zones"]
    return {d["id"]: d for d in z}


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    zones = build()
    pr = np.array([z["priority"] for z in zones])
    for k in ("protected", "encounter60", "productivity", "priority"):
        v = np.array([z[k] for z in zones])
        print(f"  {k:12s} min {v.min():.2f}  p10 {np.percentile(v, 10):.2f}  median {np.median(v):.2f}  "
              f"p90 {np.percentile(v, 90):.2f}  max {v.max():.2f}  nonzero {np.mean(v > 0.01):.0%}")
    print(f"  priority distinct values (2 dp): {len(set(np.round(pr, 2)))}; std {pr.std():.2f}")
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    for ax, k in zip(axes.ravel(), ("protected", "encounter60", "productivity", "priority")):
        polys = [np.array(z["boundary"]) for z in zones]
        pc = PolyCollection(polys, array=np.array([z[k] for z in zones]), cmap="viridis", edgecolor="none")
        ax.add_collection(pc); fig.colorbar(pc, ax=ax, shrink=0.8)
        ax.set_xlim(C.LON_MIN, C.LON_MAX); ax.set_ylim(C.LAT_MIN, C.LAT_MAX)
        ax.set_aspect(1 / np.cos(np.radians(30))); ax.set_title(k)
    fig.suptitle("Zone priority = 1 + 2*protected + 2*encounter60 + 1*productivity (H3 res 3)")
    fig.tight_layout()
    out = C.ROOT / "docs" / "figures" / "priority.png"
    fig.savefig(out, dpi=100)
    print(f"wrote {ZONES_JSON.relative_to(C.ROOT)} and {out.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
