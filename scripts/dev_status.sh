#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="$ROOT/.dev"
PORTS_FILE="$DEV_DIR/ports.env"
NEXT_ENTRY="$ROOT/frontend/node_modules/next/dist/bin/next"

if [[ ! -f "$PORTS_FILE" ]]; then
  echo "Dev services are not initialized: missing $PORTS_FILE"
  echo "Run ./scripts/dev_up.sh to reserve ports and start services."
  exit 0
fi

# shellcheck disable=SC1090
source "$PORTS_FILE"

process_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

is_backend_process() {
  local pid="$1"
  local command
  command="$(process_command "$pid")"
  [[ "$command" == *"$ROOT"* && "$command" == *"uvicorn"* && "$command" == *"app.main:app"* ]]
}

is_frontend_process() {
  local pid="$1"
  local command
  command="$(process_command "$pid")"
  [[ "$command" == *"$NEXT_ENTRY"* || "$command" == next-server* ]]
}

pid_status() {
  local name="$1"
  local pid_file="$2"
  local url="$3"
  local method="$4"
  local matcher="$5"

  local pid=""
  if [[ -f "$pid_file" ]]; then
    pid="$(tr -d '[:space:]' < "$pid_file")"
  fi

  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    if "$matcher" "$pid"; then
      echo "$name: running (pid $pid, managed)"
    else
      echo "$name: running (pid $pid, not this project)"
    fi
  elif [[ -n "$pid" ]]; then
    echo "$name: stopped (stale pid $pid)"
  else
    echo "$name: no managed pid"
  fi

  if [[ "$method" == "HEAD" ]]; then
    if curl --noproxy '*' -fsS -I "$url" >/dev/null 2>&1; then
      echo "$name URL: responding ($url)"
    else
      echo "$name URL: not responding ($url)"
    fi
  else
    if curl --noproxy '*' -fsS "$url" >/dev/null 2>&1; then
      echo "$name URL: responding ($url)"
    else
      echo "$name URL: not responding ($url)"
    fi
  fi
}

pid_status "Backend" "$DEV_DIR/backend.pid" "http://127.0.0.1:${API_PORT}/health" "GET" is_backend_process
pid_status "Frontend" "$DEV_DIR/frontend.pid" "http://127.0.0.1:${WEB_PORT}" "HEAD" is_frontend_process
