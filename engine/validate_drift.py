"""Sanity checks for the drift engine. Writes figures to docs/figures/ and prints the numbers.

    python -m engine.validate_drift
"""
import json
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from engine import config as C
from engine import drift as D

FIG = C.ROOT / "docs" / "figures"


def land_outlines():
    rings = []
    for name in ("ne_10m_land", "ne_10m_minor_islands"):
        for f in json.load(open(C.ENV / f"{name}.geojson"))["features"]:
            g = f["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for p in polys:
                r = np.array(p[0]); r[:, 0] %= 360
                if ((r[:, 0] > C.LON_MIN - 1) & (r[:, 0] < C.LON_MAX + 1) & (r[:, 1] > C.LAT_MIN - 1) & (r[:, 1] < C.LAT_MAX + 1)).any():
                    rings.append(r)
    return rings


def cloud_area_km2(grid, ye, xe, thr):
    cell = (ye[1] - ye[0]) * (xe[1] - xe[0]) * 111.2 ** 2
    lat_c = 0.5 * (ye[:-1] + ye[1:])
    return float(((grid >= thr) * np.cos(np.radians(lat_c))[:, None]).sum() * cell)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    cur = D.currents()
    rings = land_outlines()

    # 1. One featured net: 1,000 particles, 90 days.
    start = cur.day_index(date(2021, 4, 1))
    e = D.simulate(35.0, 200.0, start, n=1000, horizon_days=90, seed=1, cur=cur)
    print("Featured net from 35.0N 200.0E (160W) on 2021-04-01, 1000 particles")
    for d in (1, 7, 30, 60, 90):
        disp = D.haversine_km(35.0, 200.0, e.lat[d], e.lon[d])
        g, ye, xe = D.density(e.lat[d], e.lon[d])
        t50, t90 = D.hdr_thresholds(g)
        print(f"  day {d:2d}: median displacement {np.median(disp):6.0f} km, max {disp.max():6.0f} km, "
              f"50% cloud {cloud_area_km2(g, ye, xe, t50):9.0f} km2, 90% cloud {cloud_area_km2(g, ye, xe, t90):9.0f} km2, "
              f"drifting {np.mean(e.status[d] == D.DRIFTING):.0%}")
    moving = e.status[-1] == D.DRIFTING
    still = D.haversine_km(e.lat[-8], e.lon[-8], e.lat[-1], e.lon[-1])[moving]
    print(f"  drifting particles that moved < 1 km in the last 7 days: {(still < 1).sum()} (should be 0)")

    # 2. Time-step convergence: deterministic run at 3 h vs 1 h steps.
    saved = (C.DT_HOURS, C.DIFFUSIVITY_M2S, C.SPEED_PERTURBATION)
    C.DIFFUSIVITY_M2S, C.SPEED_PERTURBATION = 0.0, 0.0
    lats = np.linspace(20, 42, 12); lons = np.linspace(180, 225, 12)
    LA, LO = [a.ravel() for a in np.meshgrid(lats, lons)]
    runs = {}
    for dt in (3.0, 1.0):
        C.DT_HOURS = dt
        runs[dt] = D.simulate(LA, LO, start, n=LA.size, horizon_days=30, seed=2, start_sigma_km=0, cur=cur)
    C.DT_HOURS, C.DIFFUSIVITY_M2S, C.SPEED_PERTURBATION = saved
    gap = D.haversine_km(runs[3.0].lat[-1], runs[3.0].lon[-1], runs[1.0].lat[-1], runs[1.0].lon[-1])
    travel = D.haversine_km(LA, LO, runs[1.0].lat[-1], runs[1.0].lon[-1])
    print(f"Time-step check (30 days, no randomness): 3 h vs 1 h steps differ by median {np.median(gap):.2f} km, "
          f"p95 {np.percentile(gap, 95):.2f} km, vs median travel {np.median(travel):.0f} km")

    # 3. Accumulation: uniform seeding over the region, run all 299 days.
    glat, glon = np.meshgrid(np.arange(15.5, 45, 0.5), np.arange(170.5, 230, 0.5))
    acc = D.simulate(glat.ravel(), glon.ravel(), 0, n=glat.size, horizon_days=299, seed=3, start_sigma_km=0, cur=cur)
    inside = acc.status[-1] == D.DRIFTING
    box = lambda la, lo: (la >= 27) & (la <= 38) & (lo >= 205) & (lo <= 225)
    share0 = box(acc.lat[0], acc.lon[0]).mean()
    share1 = box(acc.lat[-1][inside], acc.lon[-1][inside]).mean()
    print(f"Accumulation (uniform start 2021-03-07 -> 2021-12-31): {inside.mean():.0%} still in region; "
          f"share inside garbage-patch box 27-38N 135-155W: {share0:.1%} at start -> {share1:.1%} at end")

    # Figures
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    ax = axes[0]
    for r in rings:
        ax.fill(r[:, 0], r[:, 1], color="#999", lw=0)
    for k in range(0, 1000, 25):
        ax.plot(e.lon[:, k], e.lat[:, k], lw=0.4, color="#3a7bd5", alpha=0.5)
    colors = {10: "#2ca02c", 30: "#ff7f0e", 60: "#d62728", 90: "#9467bd"}
    for d, c in colors.items():
        g, ye, xe = D.density(e.lat[d], e.lon[d])
        t50, t90 = D.hdr_thresholds(g)
        xc, yc = 0.5 * (xe[:-1] + xe[1:]), 0.5 * (ye[:-1] + ye[1:])
        ax.contour(xc, yc, g, levels=[t90, t50], colors=[c, c], linestyles=["--", "-"], linewidths=1.4)
        ax.plot([], [], color=c, label=f"day {d}: 50% (solid) / 90% (dashed) cloud")
    ax.plot(200, 35, "k*", ms=12, label="reported loss point")
    ax.set_xlim(185, 225); ax.set_ylim(22, 45); ax.set_aspect(1 / np.cos(np.radians(33)))
    ax.set_title("One lost net: 1,000 virtual copies, OSCAR 2021 currents (historical replay)")
    ax.set_xlabel("longitude (0-360)"); ax.set_ylabel("latitude"); ax.legend(fontsize=8, loc="lower left")
    ax = axes[1]
    for r in rings:
        ax.fill(r[:, 0], r[:, 1], color="#999", lw=0)
    ax.scatter(acc.lon[-1][inside], acc.lat[-1][inside], s=1, color="#d62728", alpha=0.4, label="after 299 days")
    ax.add_patch(plt.Rectangle((205, 27), 20, 11, fill=False, ec="k", ls="--", label="garbage-patch box"))
    ax.set_xlim(C.LON_MIN, C.LON_MAX); ax.set_ylim(C.LAT_MIN, C.LAT_MAX); ax.set_aspect(1 / np.cos(np.radians(30)))
    ax.set_title(f"Particles seeded evenly every 0.5° on 2021-03-07: positions on 2021-12-31\n"
                 f"share in box {share0:.0%} -> {share1:.0%}")
    ax.set_xlabel("longitude (0-360)"); ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout(); fig.savefig(FIG / "drift_validation.png", dpi=110)
    print(f"wrote {(FIG / 'drift_validation.png').relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()
