#!/usr/bin/env bash
# One-time setup. Needs: Python 3.13, Node 18+, Foundry (forge/anvil) and Ollama. The ocean-current subset ships in
# data/derived/ (62 MB); the full 10 GB OSCAR file (data/currents.nc) is only needed to rebuild it.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.foundry/bin"

echo "== Python environment"
[ -d .venv ] || python3.13 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "== Smart contracts (OpenZeppelin v5.4.0, forge-std)"
cd contracts
[ -d lib/openzeppelin-contracts ] || forge install OpenZeppelin/openzeppelin-contracts@v5.4.0 --no-git
[ -d lib/forge-std ] || forge install foundry-rs/forge-std --no-git
forge build -q && forge test -q
cd ..

echo "== Data: region subset of the OSCAR file + environmental layers -> zone priorities"
[ -f data/derived/currents_region.npz ] || .venv/bin/python -m engine.extract
[ -f data/derived/zones.json ] || .venv/bin/python -m engine.zones

echo "== Web app"
(cd web && npm install --no-audit --no-fund && npm run build)

echo "== Local vision model (free, offline)"
ollama list | grep -q "qwen2.5vl:3b" || ollama pull qwen2.5vl:3b

echo "Setup complete. Start the demo with: scripts/run.sh"
