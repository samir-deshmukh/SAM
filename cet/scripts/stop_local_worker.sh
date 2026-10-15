#!/usr/bin/env bash
set -euo pipefail
PID_FILE="$HOME/.local/state/capfind-local-worker/worker.pid"
if [[ ! -f "$PID_FILE" ]]; then
  echo "No CAPFind local worker PID file found."
  exit 0
fi
PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
fi
rm -f "$PID_FILE"
echo "CAPFind local worker stop requested."
