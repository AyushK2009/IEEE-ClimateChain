"""Human-readable locations: '210 km NW of Laysan Island'. Longitudes are 0-360."""
import math

LANDMARKS = [
    ("Kure Atoll", 28.42, 181.67), ("Midway Atoll", 28.21, 182.63), ("Pearl and Hermes Atoll", 27.85, 184.17),
    ("Lisianski Island", 26.06, 186.04), ("Laysan Island", 25.77, 188.27), ("French Frigate Shoals", 23.75, 193.83),
    ("Necker Island", 23.58, 195.30), ("Nihoa", 23.06, 198.08), ("Kauaʻi", 22.05, 200.48), ("Oʻahu", 21.47, 202.02),
    ("Maui", 20.80, 203.70), ("Hawaiʻi Island", 19.60, 204.50), ("the Great Pacific Garbage Patch", 32.0, 215.0),
]
DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _dist_bearing(lat1, lon1, lat2, lon2):
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 6371 * 2 * math.asin(math.sqrt(a))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


def describe(lat, lon):
    """Position relative to the nearest landmark, e.g. '210 km NW of Laysan Island'."""
    best = min(LANDMARKS, key=lambda p: _dist_bearing(p[1], p[2], lat, lon)[0])
    d, b = _dist_bearing(best[1], best[2], lat, lon)
    if d < 30:
        return f"near {best[0]}"
    if d > 1000:
        w = lon > 180
        return f"open ocean at {abs(lat):.0f}°N {abs(360 - lon if w else lon):.0f}°{'W' if w else 'E'}"
    return f"{round(d, -1):,.0f} km {DIRS[int((b + 22.5) // 45) % 8]} of {best[0]}"
