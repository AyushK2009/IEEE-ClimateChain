"""Ensemble drift forecast on OSCAR 2021 currents (docs/TECHNICAL_PROPOSAL.md section 4.2).

Particles move with RK4 steps through currents interpolated bilinearly in space and linearly
in time, plus a random walk (sub-grid eddies) and a per-particle speed factor (unknown windage
and net type). A particle that steps into a land cell is beached; one that leaves the region
is out of area. Both stop moving; nothing else ever freezes a particle.
"""
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import numpy as np
from scipy.ndimage import gaussian_filter

from engine import config as C

M_PER_DEG = 111_195.0
DRIFTING, BEACHED, OUT = 0, 1, 2


class Currents:
    def __init__(self, path=C.CURRENTS_NPZ):
        z = np.load(path)
        self.lat, self.lon = z["lat"], z["lon"]
        self.dates = [date.fromisoformat(d) for d in z["dates"]]
        self.land = z["land"]
        self.u = np.nan_to_num(z["u"], nan=0.0)      # land counts as zero current when blending
        self.v = np.nan_to_num(z["v"], nan=0.0)
        self.nt, self.ny, self.nx = self.u.shape
        self.lat0, self.lon0 = float(self.lat[0]), float(self.lon[0])
        self.d = float(self.lat[1] - self.lat[0])

    def day_index(self, d: date) -> float:
        return float((d - self.dates[0]).days)

    def date_of(self, t: float) -> date:
        return self.dates[min(int(t), self.nt - 1)]

    def velocity(self, lat, lon, t):
        """Bilinear in space, linear in time. lat/lon arrays, t scalar (days since first date)."""
        fy = np.clip((lat - self.lat0) / self.d, 0, self.ny - 1.001)
        fx = np.clip((lon - self.lon0) / self.d, 0, self.nx - 1.001)
        iy, ix = fy.astype(int), fx.astype(int)
        wy, wx = fy - iy, fx - ix
        t = min(max(t, 0.0), self.nt - 1.001)
        it, wt = int(t), t - int(t)
        out = []
        for f in (self.u, self.v):
            def at(k):
                g = f[k]
                return ((1 - wy) * ((1 - wx) * g[iy, ix] + wx * g[iy, ix + 1])
                        + wy * ((1 - wx) * g[iy + 1, ix] + wx * g[iy + 1, ix + 1]))
            out.append((1 - wt) * at(it) + wt * at(it + 1))
        return out[0], out[1]

    def is_land(self, lat, lon):
        iy = np.clip(np.rint((lat - self.lat0) / self.d).astype(int), 0, self.ny - 1)
        ix = np.clip(np.rint((lon - self.lon0) / self.d).astype(int), 0, self.nx - 1)
        return self.land[iy, ix]


@lru_cache(maxsize=1)
def currents() -> Currents:
    return Currents()


@dataclass
class Ensemble:
    start_day: float            # days since the first data date
    lat: np.ndarray             # (days+1, n) daily snapshots
    lon: np.ndarray
    status: np.ndarray          # (days+1, n) DRIFTING / BEACHED / OUT

    @property
    def days(self):
        return self.lat.shape[0] - 1


def simulate(lat0, lon0, start_day, n=300, horizon_days=C.HORIZON_DAYS, seed=0,
             start_sigma_km=C.START_SIGMA_KM, cur: Currents | None = None) -> Ensemble:
    """lat0/lon0 may be scalars (one net) or arrays of length n (one particle each)."""
    cur = cur or currents()
    rng = np.random.default_rng(seed)
    horizon_days = int(min(horizon_days, cur.nt - 1 - start_day))
    lat = np.broadcast_to(np.asarray(lat0, float), (n,)).copy()
    lon = np.broadcast_to(np.asarray(lon0, float), (n,)).copy()
    if start_sigma_km > 0:
        lat += rng.normal(0, start_sigma_km * 1000 / M_PER_DEG, n)
        lon += rng.normal(0, start_sigma_km * 1000 / M_PER_DEG, n) / np.cos(np.radians(lat))
    factor = np.clip(rng.normal(1.0, C.SPEED_PERTURBATION, n), 0.5, 1.5)
    status = np.zeros(n, np.int8)
    status[cur.is_land(lat, lon)] = BEACHED
    dt = C.DT_HOURS * 3600.0
    dt_days = C.DT_HOURS / 24.0
    steps_per_day = int(round(24 / C.DT_HOURS))
    sigma = np.sqrt(2 * C.DIFFUSIVITY_M2S * dt)

    def rate(la, lo, t, f):
        u, v = cur.velocity(la, lo, t)
        return (v * f / M_PER_DEG, u * f / (M_PER_DEG * np.cos(np.radians(la))))

    snaps_lat, snaps_lon, snaps_st = [lat.copy()], [lon.copy()], [status.copy()]
    t = float(start_day)
    for _ in range(horizon_days):
        for _ in range(steps_per_day):
            m = status == DRIFTING
            if not m.any():
                break
            la, lo, f = lat[m], lon[m], factor[m]
            k1 = rate(la, lo, t, f)
            k2 = rate(la + 0.5 * dt * k1[0], lo + 0.5 * dt * k1[1], t + 0.5 * dt_days, f)
            k3 = rate(la + 0.5 * dt * k2[0], lo + 0.5 * dt * k2[1], t + 0.5 * dt_days, f)
            k4 = rate(la + dt * k3[0], lo + dt * k3[1], t + dt_days, f)
            nla = la + dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
            nlo = lo + dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
            nla += rng.normal(0, sigma, nla.size) / M_PER_DEG
            nlo += rng.normal(0, sigma, nlo.size) / (M_PER_DEG * np.cos(np.radians(nla)))
            st = np.zeros(nla.size, np.int8)
            st[cur.is_land(nla, nlo)] = BEACHED
            out = (nla < C.LAT_MIN) | (nla > C.LAT_MAX) | (nlo < C.LON_MIN) | (nlo > C.LON_MAX)
            st[out] = OUT
            keep = st != DRIFTING
            nla[keep], nlo[keep] = la[keep], lo[keep]      # stop at the last valid position
            lat[m], lon[m], status[m] = nla, nlo, st
            t += dt_days
        snaps_lat.append(lat.copy()); snaps_lon.append(lon.copy()); snaps_st.append(status.copy())
    return Ensemble(float(start_day), np.array(snaps_lat), np.array(snaps_lon), np.array(snaps_st))


def density(lat, lon, res=0.1, smooth_cells=1.5):
    """Smoothed probability grid on the region; returns (grid, lat_edges, lon_edges)."""
    ny = int(round((C.LAT_MAX - C.LAT_MIN) / res)); nx = int(round((C.LON_MAX - C.LON_MIN) / res))
    h, ye, xe = np.histogram2d(lat, lon, bins=[ny, nx], range=[[C.LAT_MIN, C.LAT_MAX], [C.LON_MIN, C.LON_MAX]])
    h = gaussian_filter(h, smooth_cells)
    s = h.sum()
    return (h / s if s > 0 else h), ye, xe


def hdr_thresholds(grid, levels=(0.5, 0.9)):
    """Density values whose super-level sets hold the given probability mass."""
    v = np.sort(grid.ravel())[::-1]
    c = np.cumsum(v)
    return [float(v[min(np.searchsorted(c, q), v.size - 1)]) for q in levels]


def hdr_level_of_point(grid, ye, xe, lat, lon):
    """Probability mass of the smallest high-density region containing the point (0..1).
    0.3 means the point is inside the 30% cloud; 1.0 means outside the cloud entirely."""
    iy = np.searchsorted(ye, lat) - 1; ix = np.searchsorted(xe, lon) - 1
    if not (0 <= iy < grid.shape[0] and 0 <= ix < grid.shape[1]):
        return 1.0
    d = grid[iy, ix]
    if d <= 0:
        return 1.0
    return float(grid[grid >= d].sum())


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))
