#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="$ROOT/.dev"
LOCK_DIR="$DEV_DIR/lock"
NEXT_ENTRY="$ROOT/frontend/node_modules/next/dist/bin/next"

mkdir -p "$DEV_DIR"

acquire_lock() {
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Another dev service command is running: $LOCK_DIR"
    exit 1
  fi
  trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
}

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

stop_service() {
  local name="$1"
  local pid_file="$2"
  local matcher="$3"

  if [[ ! -f "$pid_file" ]]; then
    echo "$name is not managed by $pid_file"
    return
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"

  if [[ -z "$pid" ]] || ! kill -0 "$pid" 2>/dev/null; then
    echo "$name is not running; removing stale $pid_file"
    rm -f "$pid_file"
    return
  fi

  if ! "$matcher" "$pid"; then
    echo "$name pid file points to a different process: pid $pid"
    echo "Refusing to stop it automatically. Inspect $pid_file."
    return 1
  fi

  echo "Stopping $name with TERM: pid $pid"
  kill "$pid" 2>/dev/null || true

  for _ in {1..20}; do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pid_file"
      echo "$name stopped"
      return
    fi
    sleep 0.5
  done

  echo "$name did not stop after TERM; sending KILL"
  kill -KILL "$pid" 2>/dev/null || true
  rm -f "$pid_file"
  echo "$name stopped"
}

acquire_lock
stop_service "Frontend" "$DEV_DIR/frontend.pid" is_frontend_process
stop_service "Backend" "$DEV_DIR/backend.pid" is_backend_process
