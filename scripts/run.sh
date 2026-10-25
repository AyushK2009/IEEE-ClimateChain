#!/usr/bin/env bash
# Start the local chain, the vision model server and the app, then open http://127.0.0.1:8000
#   scripts/run.sh            reuse the existing world if the chain is still running
#   RESEED=1 scripts/run.sh   deploy fresh contracts and re-seed the simulated world
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.foundry/bin"
mkdir -p runtime
(cd contracts && forge build -q)
if ! curl -s -o /dev/null -X POST -H 'Content-Type: application/json' --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId"}' http://127.0.0.1:8545; then
  echo "starting local chain (anvil)"; anvil --accounts 12 --silent > runtime/anvil.log 2>&1 &
  sleep 2
fi
if ! curl -s -o /dev/null http://127.0.0.1:11434; then
  echo "starting ollama"; ollama serve > runtime/ollama.log 2>&1 &
  sleep 2
fi
[ -d web/dist ] || (cd web && npm run build)
echo "App: http://127.0.0.1:8000   (first start seeds the world and runs ~360 forecasts: about 2 minutes)"
exec .venv/bin/uvicorn engine.api:app --host 127.0.0.1 --port 8000
