#!/usr/bin/env bash
set -euo pipefail

for port in 3000 5001; do
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN || true)"
  if [[ -n "$pids" ]]; then
    echo "Stopping processes on :$port"
    kill $pids
  fi
done
