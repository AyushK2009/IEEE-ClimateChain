"""HTTP API for the web app.

    uvicorn engine.api:app --port 8000          (needs a running chain: anvil --accounts 12)
    RESEED=1 uvicorn engine.api:app ...         (force a fresh deployment and scenario)
"""
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import config as C
from engine import zones as Z
from engine.world import World

world = World()


@asynccontextmanager
async def lifespan(app):
    how = world.start(reseed=os.environ.get("RESEED") == "1")
    print(f"[world] {how}; today = {world.date_of(world.today)}; contract {world.chain.escrow.address}")
    yield


app = FastAPI(title="Ghost Gear Recovery API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except ValueError as e:
        raise HTTPException(400, str(e))


class Checkout(BaseModel):
    org: str
    count: int = 12
    product: str = "Gillnet panel, 50 m"


class Loss(BaseModel):
    lat: float
    lon: float


class Advance(BaseModel):
    days: int = 1


class Sponsor(BaseModel):
    amount: int = 25_000


@app.get("/api/state")
def state():
    return world.state()


_zones_cache = None


@app.get("/api/zones")
def zones():
    global _zones_cache
    if _zones_cache is None:
        _zones_cache = json.loads((C.DERIVED / "zones.json").read_text())
    return _zones_cache


_mpa_cache = None


@app.get("/api/layers/mpa")
def mpa():
    """Protected-area outlines (0-360 longitudes), simplified for drawing."""
    global _mpa_cache
    if _mpa_cache is None:
        import shapely
        geom, _ = Z.layers()
        polys = [g for g in getattr(shapely.simplify(geom, 0.01), "geoms", [shapely.simplify(geom, 0.01)])]
        _mpa_cache = [[[round(x, 3), round(y, 3)] for x, y in p.exterior.coords] for p in polys if p.area > 0.001]
    return _mpa_cache


@app.get("/api/market")
def market():
    return world.market()


@app.get("/api/nets/{net_id}")
def net(net_id: int):
    return _guard(world.net_detail, net_id)


@app.get("/api/nets/{net_id}/forecast")
def forecast(net_id: int):
    return _guard(world.net_forecast, net_id)


@app.get("/api/nets/{net_id}/tag.png")
def tag(net_id: int):
    return Response(_guard(world.tag_png, net_id), media_type="image/png")


@app.get("/api/nets/{net_id}/staged-photo")
def staged(net_id: int, variant: str = "recovered", seed: int = 0):
    return Response(_guard(world.staged_photo, net_id, variant, seed), media_type="image/jpeg")


@app.get("/api/orgs/{org}/nets")
def org_nets(org: str):
    return world.nets_of(org)


@app.get("/api/ledger")
def ledger(since: int = 0, limit: int = 200):
    return world.ledger(since, limit)


@app.post("/api/checkout")
def checkout(body: Checkout):
    return _guard(world.checkout, body.org, body.count, body.product)


@app.post("/api/nets/{net_id}/loss")
def loss(net_id: int, body: Loss):
    return _guard(world.report_loss, net_id, body.lat, body.lon)


@app.post("/api/nets/{net_id}/return")
def return_net(net_id: int):
    return _guard(world.return_net, net_id)


_story = None


@app.get("/api/story")
def story():
    global _story
    if _story is None:
        from engine import story as ST
        _story = ST.load()
    return _story


@app.post("/api/clock/advance")
def advance(body: Advance):
    return world.advance(body.days)


@app.post("/api/sponsor")
def sponsor(body: Sponsor):
    return world.sponsor(body.amount)


@app.post("/api/claims")
async def claim(photo: UploadFile = File(...), claimant: str = Form("crew_a"), lat: float = Form(...), lon: float = Form(...)):
    data = await photo.read()
    return world.claim(data, claimant, lat, lon)


@app.post("/api/identify")
async def identify(photo: UploadFile = File(...)):
    return world.identify(await photo.read())


@app.get("/api/demo/scenario")
def demo_scenario():
    return world.scenario()


@app.post("/api/demo/start")
def demo_start():
    return world.start_demo()


_priority_layer = None


@app.get("/api/layers/priority")
def priority_layer():
    """Ecological priority as smooth contour bands (high >= 2.5, very high >= 4) instead of hexagons."""
    global _priority_layer
    if _priority_layer is None:
        import contourpy
        import numpy as np
        from scipy.ndimage import gaussian_filter
        zs = Z.load()
        step = 0.2
        lats = np.arange(C.LAT_MIN + step / 2, C.LAT_MAX, step); lons = np.arange(C.LON_MIN + step / 2, C.LON_MAX, step)
        LO, LA = np.meshgrid(lons, lats)
        cells = Z.cell_of(LA.ravel(), LO.ravel())
        g = np.array([zs[c]["priority"] if c in zs else 1.0 for c in cells]).reshape(LA.shape)
        g = gaussian_filter(g, 1.2)
        gen = contourpy.contour_generator(lons, lats, g, fill_type=contourpy.FillType.OuterOffset)
        out = {}
        for name, lo_, hi_ in (("high", 2.5, 4.0), ("veryHigh", 4.0, 99.0)):
            polys, offs = gen.filled(lo_, hi_)
            out[name] = [[np.round(p[a:b], 3).tolist() for a, b in zip(o[:-1], o[1:])] for p, o in zip(polys, offs) if len(p) >= 4]
        _priority_layer = out
    return _priority_layer


@app.get("/api/areas")
def areas():
    from engine import regions as R
    return list(R.static().values())


@app.get("/api/claims/{claim_id}/photo")
def claim_photo(claim_id: int):
    r = world.con.execute("SELECT photo FROM claims WHERE id=?", (claim_id,)).fetchone()
    if not r:
        raise HTTPException(404)
    return Response((C.RUNTIME / "evidence" / r["photo"]).read_bytes(), media_type="image/jpeg")


@app.post("/api/reset")
def reset():
    world.reset()
    return world.state()


_dist = C.ROOT / "web" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
