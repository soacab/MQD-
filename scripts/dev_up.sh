#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="$ROOT/.dev"
LOCK_DIR="$DEV_DIR/lock"

mkdir -p "$DEV_DIR"

API_PORT="$(codex-port reserve "$ROOT/backend" api)"
WEB_PORT="$(codex-port reserve "$ROOT/frontend" dev)"

API_PID_FILE="$DEV_DIR/backend.pid"
WEB_PID_FILE="$DEV_DIR/frontend.pid"
PORTS_FILE="$DEV_DIR/ports.env"
API_LOG="$DEV_DIR/backend.log"
WEB_LOG="$DEV_DIR/frontend.log"
UVICORN_BIN="$ROOT/.venv/bin/uvicorn"
NODE_BIN="$(command -v node)"
NEXT_ENTRY="$ROOT/frontend/node_modules/next/dist/bin/next"
STARTED_API_PID=""
STARTED_WEB_PID=""
STARTUP_COMPLETE=0

acquire_lock() {
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "Another dev service command is running: $LOCK_DIR"
    exit 1
  fi
  trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
}

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

pid_from_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    tr -d '[:space:]' < "$file"
  fi
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

url_ok() {
  local url="$1"
  curl --noproxy '*' -fsS "$url" >/dev/null 2>&1
}

url_head_ok() {
  local url="$1"
  curl --noproxy '*' -fsS -I "$url" >/dev/null 2>&1
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local method="$3"

  for _ in {1..120}; do
    if [[ "$method" == "HEAD" ]]; then
      url_head_ok "$url" && return 0
    else
      url_ok "$url" && return 0
    fi
    sleep 0.5
  done

  echo "$name did not become ready: $url"
  return 1
}

write_ports_file() {
  {
    echo "API_PORT=$API_PORT"
    echo "WEB_PORT=$WEB_PORT"
  } > "$PORTS_FILE"
}

terminate_started_process() {
  local name="$1"
  local pid="$2"
  local pid_file="$3"
  local matcher="$4"

  if ! is_pid_running "$pid"; then
    rm -f "$pid_file"
    return
  fi

  if ! "$matcher" "$pid"; then
    echo "$name pid $pid no longer matches this project; not stopping it automatically."
    return 1
  fi

  kill "$pid" 2>/dev/null || true
  for _ in {1..20}; do
    if ! is_pid_running "$pid"; then
      rm -f "$pid_file"
      return
    fi
    sleep 0.5
  done

  kill -KILL "$pid" 2>/dev/null || true
  rm -f "$pid_file"
}

cleanup_started_processes() {
  if [[ -n "$STARTED_WEB_PID" ]]; then
    terminate_started_process "Frontend" "$STARTED_WEB_PID" "$WEB_PID_FILE" is_frontend_process || true
  fi

  if [[ -n "$STARTED_API_PID" ]]; then
    terminate_started_process "Backend" "$STARTED_API_PID" "$API_PID_FILE" is_backend_process || true
  fi
}

handle_startup_error() {
  local exit_code=$?
  if [[ "$STARTUP_COMPLETE" != "1" ]]; then
    echo "Startup failed; cleaning up newly started services."
    cleanup_started_processes
  fi
  exit "$exit_code"
}

start_backend() {
  local pid
  pid="$(pid_from_file "$API_PID_FILE")"

  if is_pid_running "$pid"; then
    if ! is_backend_process "$pid"; then
      echo "Backend pid file points to a different process: pid $pid"
      echo "Refusing to continue. Inspect $API_PID_FILE before retrying."
      return 1
    fi

    if url_ok "http://127.0.0.1:${API_PORT}/health"; then
      echo "Backend already running: pid $pid, port $API_PORT"
      return
    fi

    echo "Backend pid $pid is managed by this project, but health check failed. Run ./scripts/dev_down.sh before retrying."
    return 1
  fi

  if [[ -n "$pid" ]]; then
    rm -f "$API_PID_FILE"
  fi

  if url_ok "http://127.0.0.1:${API_PORT}/health"; then
    echo "Backend port $API_PORT is already responding, but it is not managed by $API_PID_FILE."
    return 1
  fi

  : > "$API_LOG"
  (
    cd "$ROOT"
    nohup "$UVICORN_BIN" app.main:app --app-dir backend --reload --reload-dir backend --host 127.0.0.1 --port "$API_PORT" >> "$API_LOG" 2>&1 &
    echo $! > "$API_PID_FILE"
  )

  pid="$(pid_from_file "$API_PID_FILE")"
  STARTED_API_PID="$pid"
  if ! wait_for_url "Backend" "http://127.0.0.1:${API_PORT}/health" "GET"; then
    terminate_started_process "Backend" "$pid" "$API_PID_FILE" is_backend_process
    STARTED_API_PID=""
    return 1
  fi
  echo "Started backend: pid $pid, port $API_PORT, log $API_LOG"
}

start_frontend() {
  local pid
  pid="$(pid_from_file "$WEB_PID_FILE")"

  if is_pid_running "$pid"; then
    if ! is_frontend_process "$pid"; then
      echo "Frontend pid file points to a different process: pid $pid"
      echo "Refusing to continue. Inspect $WEB_PID_FILE before retrying."
      return 1
    fi

    if url_head_ok "http://127.0.0.1:${WEB_PORT}"; then
      echo "Frontend already running: pid $pid, port $WEB_PORT"
      return
    fi

    echo "Frontend pid $pid is managed by this project, but health check failed. Run ./scripts/dev_down.sh before retrying."
    return 1
  fi

  if [[ -n "$pid" ]]; then
    rm -f "$WEB_PID_FILE"
  fi

  if url_head_ok "http://127.0.0.1:${WEB_PORT}"; then
    echo "Frontend port $WEB_PORT is already responding, but it is not managed by $WEB_PID_FILE."
    return 1
  fi

  : > "$WEB_LOG"
  (
    cd "$ROOT/frontend"
    export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:${API_PORT}"
    nohup "$NODE_BIN" "$NEXT_ENTRY" dev --webpack -H 127.0.0.1 -p "$WEB_PORT" >> "$WEB_LOG" 2>&1 &
    echo $! > "$WEB_PID_FILE"
  )

  pid="$(pid_from_file "$WEB_PID_FILE")"
  STARTED_WEB_PID="$pid"
  if ! wait_for_url "Frontend" "http://127.0.0.1:${WEB_PORT}" "HEAD"; then
    terminate_started_process "Frontend" "$pid" "$WEB_PID_FILE" is_frontend_process
    STARTED_WEB_PID=""
    return 1
  fi
  echo "Started frontend: pid $pid, port $WEB_PORT, log $WEB_LOG"
}

acquire_lock
trap handle_startup_error ERR
write_ports_file
start_backend
start_frontend
STARTUP_COMPLETE=1

echo "Dev services ready:"
echo "  Backend:  http://127.0.0.1:${API_PORT}"
echo "  Frontend: http://127.0.0.1:${WEB_PORT}"
