"""Shared paths and parameters. Longitudes are 0-360 everywhere in this project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ENV = DATA / "env"
DERIVED = DATA / "derived"
RUNTIME = ROOT / "runtime"          # SQLite, evidence photos, chain deployment info (gitignored)
CURRENTS_NC = DATA / "currents.nc"
CURRENTS_NPZ = DERIVED / "currents_region.npz"

# Demo region: North Pacific, 15-45N, 170E-130W (0-360 longitudes 170-230).
LAT_MIN, LAT_MAX = 15.0, 45.0
LON_MIN, LON_MAX = 170.0, 230.0

# Usable currents: the 300 contiguous days 2021-03-07 .. 2021-12-31 (file index 15..314).
TIME_START_INDEX = 15

# Drift model (see docs/TECHNICAL_PROPOSAL.md section 4.2).
DT_HOURS = 3.0
DIFFUSIVITY_M2S = 100.0          # random-walk stand-in for sub-grid eddies (tunable)
SPEED_PERTURBATION = 0.15        # per-particle multiplicative speed spread (windage / net type)
START_SIGMA_KM = 5.0             # uncertainty of the reported loss position
HORIZON_DAYS = 120

# Zones and priority (section 4.5).
H3_RES = 3
NEAR_SHORE_KM = 25.0
ENCOUNTER_DAYS = 60
W_PROTECTED, W_ENCOUNTER, W_PRODUCTIVITY = 2.0, 2.0, 1.0

# Pricing (section 4.7). Amounts are whole dUSD; on-chain they use 18 decimals.
DEPOSIT = 200
COOLING_DAYS = 3
LAMBDA_CAP = 400
BUDGET_FRACTION = 0.8
SPONSOR_SEED = 250_000
