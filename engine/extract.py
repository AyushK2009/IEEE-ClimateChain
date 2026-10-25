"""Cut the demo region and the 300 contiguous days out of the 10 GB OSCAR file.

Reads only the needed hyperslab by variable name (the file stores blocks as v, vg, u, ug,
so never rely on block order). Land is stored as -999 and becomes NaN here.

    python -m engine.extract
"""
from datetime import date, timedelta

import h5py
import numpy as np

from engine import config as C


def main():
    with h5py.File(C.CURRENTS_NC, "r") as f:
        lat = f["lat"][:]
        lon = f["lon"][:]
        days = f["time"][:]
        i_lat = np.where((lat >= C.LAT_MIN) & (lat <= C.LAT_MAX))[0]
        i_lon = np.where((lon >= C.LON_MIN) & (lon <= C.LON_MAX))[0]
        t0 = C.TIME_START_INDEX
        assert np.all(np.diff(days[t0:]) == 1.0), "selected days must be contiguous"
        sl = (slice(t0, None), slice(i_lon[0], i_lon[-1] + 1), slice(i_lat[0], i_lat[-1] + 1))
        fields = {}
        for name in ("u", "v"):
            a = f[name][sl].astype(np.float32)          # (time, lon, lat)
            a[a <= -998] = np.nan
            fields[name] = np.ascontiguousarray(a.transpose(0, 2, 1))  # -> (time, lat, lon)

    land = np.all(np.isnan(fields["u"]), axis=0)
    origin = date(1990, 1, 1)
    dates = np.array([(origin + timedelta(days=float(d))).isoformat() for d in days[t0:]])
    C.DERIVED.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(C.CURRENTS_NPZ, u=fields["u"], v=fields["v"], lat=lat[i_lat], lon=lon[i_lon],
                        days=days[t0:], dates=dates, land=land)

    speed = np.hypot(fields["u"], fields["v"])
    print(f"saved {C.CURRENTS_NPZ.relative_to(C.ROOT)}: {fields['u'].shape} (time, lat, lon), "
          f"{dates[0]} .. {dates[-1]}")
    print(f"land cells: {land.sum()} of {land.size}; partially-missing ocean cells: "
          f"{int((np.isnan(fields['u']).any(axis=0) & ~land).sum())}")
    print(f"speed m/s: median {np.nanmedian(speed):.3f}, p99 {np.nanpercentile(speed, 99):.3f}, "
          f"max {np.nanmax(speed):.3f}")


if __name__ == "__main__":
    main()
