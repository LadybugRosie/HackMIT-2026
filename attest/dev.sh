#!/bin/bash
# attest dev stack — API (8090), web (9100), hardware witness (8093) — in one place.
#
#   ./dev.sh up        kill anything on the three ports, start all three, tail the logs
#   ./dev.sh down      stop everything this script (or anyone) left on those ports
#   ./dev.sh restart   down + up
#   ./dev.sh status    who is listening where
#   ./dev.sh logs      tail all three logs (Ctrl+C to stop tailing; servers keep running)
#   ./dev.sh reset     down, wipe the database (keeps the issuer key), re-seed demo data, up
#   ./dev.sh seed      (re)run the demo seed against the running database
#
# First run installs what is missing (python venv, node modules, helper build).
# Logs: .run/api.log .run/web.log .run/hid.log
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(pwd)
RUN="$ROOT/.run"; mkdir -p "$RUN"
API_PORT=${API_PORT:-8090}; WEB_PORT=${WEB_PORT:-9100}; HID_PORT=${HID_PORT:-8093}
PY="$ROOT/server/.venv/bin/python"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
dim()  { printf '\033[2m%s\033[0m\n' "$*"; }
pids_on() { lsof -t -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null || true; }

kill_port() {
  local port=$1 name=$2 pids
  pids=$(pids_on "$port")
  if [ -n "$pids" ]; then
    dim "stopping $name on :$port (pid $(echo $pids | tr '\n' ' '))"
    kill $pids 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do [ -z "$(pids_on "$port")" ] && break; sleep 0.3; done
    pids=$(pids_on "$port")
    if [ -n "$pids" ]; then dim "  still up — force"; kill -9 $pids 2>/dev/null || true; sleep 0.3; fi
  fi
  return 0
}

ensure_deps() {
  if [ ! -x "$PY" ]; then
    say "creating python venv and installing server deps…"
    (cd server && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]")
  fi
  if [ ! -d web/node_modules ]; then
    say "installing web deps…"
    (cd web && (command -v pnpm >/dev/null && pnpm install --silent || npm install --silent --legacy-peer-deps))
  fi
  if [ ! -x native/attest-hid/.build/release/attest-hid ] && command -v swift >/dev/null; then
    say "building the hardware witness helper…"
    (cd native/attest-hid && swift build -c release 2>&1 | grep -E "error|Compiling" || true)
  fi
}

down() {
  kill_port "$API_PORT" api
  kill_port "$WEB_PORT" web
  kill_port "$HID_PORT" hid
  pkill -f "attest-hid" 2>/dev/null || true       # a helper that never bound (port clash) has no listener
  pkill -f "uvicorn classroom.app:app" 2>/dev/null || true
  say "down."
}

up() {
  ensure_deps
  kill_port "$API_PORT" api; kill_port "$WEB_PORT" web; kill_port "$HID_PORT" hid
  pkill -f "uvicorn classroom.app:app" 2>/dev/null || true
  pkill -f "attest-hid" 2>/dev/null || true

  say "starting API on :$API_PORT"
  (cd server && nohup "$PY" -m uvicorn classroom.app:app --port "$API_PORT" --reload < /dev/null > "$RUN/api.log" 2>&1 &)
  say "starting web on :$WEB_PORT"
  if command -v pnpm >/dev/null; then
    (cd web && nohup pnpm dev --port "$WEB_PORT" < /dev/null > "$RUN/web.log" 2>&1 &)
  else
    (cd web && nohup npx vite --port "$WEB_PORT" < /dev/null > "$RUN/web.log" 2>&1 &)
  fi
  if [ -x native/attest-hid/.build/release/attest-hid ]; then
    say "starting hardware witness on :$HID_PORT"
    (nohup native/attest-hid/.build/release/attest-hid --port "$HID_PORT" < /dev/null > "$RUN/hid.log" 2>&1 &)
  else
    dim "helper not built (no swift?) — L3 unavailable; L1/L2 still work"
  fi

  for _ in $(seq 1 40); do
    [ -n "$(pids_on "$API_PORT")" ] && [ -n "$(pids_on "$WEB_PORT")" ] && break; sleep 0.25
  done
  echo; status
  echo
  if grep -q "input-monitoring=granted" "$RUN/hid.log" 2>/dev/null; then dim "witness: Input Monitoring granted";
  elif [ -f "$RUN/hid.log" ]; then printf '\033[33m%s\033[0m\n' "witness: Input Monitoring NOT granted — System Settings → Privacy & Security → Input Monitoring → enable the app that launched it (Terminal), then ./dev.sh restart"; fi
  if ! "$PY" -c "import sqlite3,sys; c=sqlite3.connect('server/data/classroom.db'); sys.exit(0 if c.execute(\"select count(*) from users where email='prof@demo.edu'\").fetchone()[0] else 1)" 2>/dev/null; then
    dim "no demo accounts yet — run: ./dev.sh seed"
  fi
  say "open http://localhost:$WEB_PORT   (teacher prof@demo.edu · students ana@/ben@/cara@demo.edu · password Passw0rd!x)"
  dim "logs: ./dev.sh logs"
}

status() {
  for pair in "$API_PORT api" "$WEB_PORT web" "$HID_PORT hid"; do
    set -- $pair
    pids=$(pids_on "$1")
    if [ -n "$pids" ]; then printf '  \033[32m●\033[0m %-4s :%s  pid %s\n' "$2" "$1" "$(echo $pids | tr '\n' ' ')"
    else printf '  \033[31m○\033[0m %-4s :%s  not running\n' "$2" "$1"; fi
  done
}

logs() { tail -n 20 -F "$RUN"/api.log "$RUN"/web.log "$RUN"/hid.log 2>/dev/null; }

seed() { (cd server && "$PY" -m classroom.seed 2>&1 | grep -v -i warning); }

reset() {
  down
  say "wiping database (issuer key kept so old certificates still verify as ours)…"
  rm -f server/data/classroom.db server/data/classroom.db-wal server/data/classroom.db-shm
  up
  sleep 2
  seed
}

case "${1:-up}" in
  up) up ;;
  down) down ;;
  restart) down; up ;;
  status) status ;;
  logs) logs ;;
  seed) seed ;;
  reset) reset ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
