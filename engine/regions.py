"""Recovery areas: H3 resolution-2 cells (roughly 300 km across), each grouping ~7 resolution-3 pricing zones.

Pricing stays per zone (resolution 3). Areas exist so people can explore the map geographically:
'about 9 lost nets likely in this area, $12,400 in rewards, and here is why it matters'.
"""
from functools import lru_cache

import h3

from engine import places
from engine import zones as Z

RES = 2


def _why(protected, encounter, productivity):
    if protected >= 0.5:
        return "Protected marine area: coral reefs, monk seals and nesting seabirds"
    if encounter >= 0.3:
        return "Currents carry gear from here into protected reef waters"
    if productivity >= 0.55:
        return "Rich feeding waters for turtles, seabirds and tuna"
    return "Open ocean, lower ecological risk"


@lru_cache(maxsize=1)
def static():
    groups = {}
    for z in Z.load().values():
        groups.setdefault(h3.cell_to_parent(z["id"], RES), []).append(z)
    out = {}
    for rid, zs in groups.items():
        lat, lng = h3.cell_to_latlng(rid)
        mean = lambda k: sum(x[k] for x in zs) / len(zs)
        prot, enc, prod = mean("protected"), mean("encounter60"), mean("productivity")
        out[rid] = {"id": rid, "boundary": Z.boundary360(rid), "center": [round(lat, 3), round(lng % 360, 3)],
                    "priority": round(mean("priority"), 2), "name": places.describe(lat, lng % 360),
                    "why": _why(prot, enc, prod)}
    return out


def parent(zone_id):
    return h3.cell_to_parent(zone_id, RES)
