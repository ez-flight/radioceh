#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export LD_LIBRARY_PATH="$ROOT/.pg/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$ROOT/.pg/usr/lib/postgresql/18/bin:$PATH"
export PGDATA="${PGDATA:-$ROOT/.pgdata}"
export PGHOST="${PGHOST:-127.0.0.1}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-radiotsekh}"

cmd="${1:-status}"

start() {
  if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
    echo "PostgreSQL already running"
    return
  fi
  pg_ctl -D "$PGDATA" -l "$PGDATA/logfile" start
  for _ in $(seq 1 20); do
    pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" && return
    sleep 0.3
  done
  echo "PostgreSQL did not become ready" >&2
  exit 1
}

case "$cmd" in
  start) start ;;
  stop) pg_ctl -D "$PGDATA" stop ;;
  status) pg_ctl -D "$PGDATA" status ;;
  psql) shift; exec psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d radiotsekh "$@" ;;
  *)
    echo "Usage: $0 {start|stop|status|psql}" >&2
    exit 1
    ;;
esac
