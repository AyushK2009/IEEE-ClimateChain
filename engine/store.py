"""Off-chain records (SQLite). Money and net status live on-chain; this holds what the chain does not:
loss coordinates, forecasts' metadata, price lists with proofs, claims' evidence and reports, the demo clock."""
import json
import shutil
import sqlite3

from engine import config as C

DB = C.RUNTIME / "world.sqlite"
SEED_DB = C.RUNTIME / "world_seed.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS nets (id INTEGER PRIMARY KEY, owner TEXT, product TEXT, registered_day INTEGER,
    loss_day INTEGER, loss_lat REAL, loss_lon REAL, loss_salt TEXT, featured INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS epochs (epoch INTEGER PRIMARY KEY, day INTEGER, root TEXT, total REAL, lambda REAL,
    sponsor_available REAL, board TEXT, tx TEXT);
CREATE TABLE IF NOT EXISTS prices (net_id INTEGER, epoch INTEGER, day INTEGER, bounty REAL, PRIMARY KEY (net_id, epoch));
CREATE TABLE IF NOT EXISTS claims (id INTEGER PRIMARY KEY, net_id INTEGER, claimant TEXT, day INTEGER, lat REAL, lon REAL,
    photo TEXT, photo_hash TEXT, bounty REAL, epoch INTEGER, outcome TEXT, report TEXT, tx_submit TEXT, tx_resolve TEXT);
CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY AUTOINCREMENT, day INTEGER, tx TEXT, block INTEGER,
    actor TEXT, label TEXT, gas INTEGER, events TEXT);
"""


def connect():
    C.RUNTIME.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def fresh():
    for p in (DB, SEED_DB):
        p.unlink(missing_ok=True)
    return connect()


def save_seed(con):
    con.commit()
    shutil.copyfile(DB, SEED_DB)


def restore_seed():
    shutil.copyfile(SEED_DB, DB)
    return connect()


def get(con, key, default=None):
    r = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def put(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, json.dumps(value)))
