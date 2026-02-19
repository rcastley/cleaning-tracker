#!/usr/bin/env bash
#
# Start/stop the Cleaning Tracker Flask app via gunicorn.
#
# Usage:
#   ./start.sh          Start the app (background, port 5001)
#   ./start.sh stop     Stop the running app
#   ./start.sh status   Check if the app is running
#   ./start.sh log      Tail the log file
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"
PIDFILE="$SCRIPT_DIR/gunicorn.pid"
LOGFILE="$SCRIPT_DIR/gunicorn.log"
BIND="0.0.0.0:5001"
WORKERS=1

do_start() {
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Already running (PID $(cat "$PIDFILE"))"
        echo "  http://localhost:5001"
        exit 0
    fi

    if [[ ! -d "$VENV" ]]; then
        echo "Error: virtualenv not found at $VENV"
        echo "Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
        exit 1
    fi

    "$VENV/bin/gunicorn" webapp:app \
        --bind "$BIND" \
        --workers "$WORKERS" \
        --pid "$PIDFILE" \
        --access-logfile "$LOGFILE" \
        --error-logfile "$LOGFILE" \
        --daemon \
        --chdir "$SCRIPT_DIR"

    sleep 1
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Started (PID $(cat "$PIDFILE"))"
        echo "  http://localhost:5001"
    else
        echo "Failed to start. Check $LOGFILE"
        exit 1
    fi
}

do_stop() {
    if [[ ! -f "$PIDFILE" ]]; then
        echo "Not running (no PID file)"
        exit 0
    fi

    local pid
    pid="$(cat "$PIDFILE")"
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "Stopped (PID $pid)"
    else
        echo "Not running (stale PID file)"
    fi
    rm -f "$PIDFILE"
}

do_status() {
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "Running (PID $(cat "$PIDFILE"))"
        echo "  http://localhost:5001"
    else
        echo "Not running"
    fi
}

do_log() {
    if [[ -f "$LOGFILE" ]]; then
        tail -f "$LOGFILE"
    else
        echo "No log file yet"
    fi
}

case "${1:-}" in
    stop)    do_stop ;;
    status)  do_status ;;
    log)     do_log ;;
    start|"") do_start ;;
    *)
        echo "Usage: $0 {start|stop|status|log}"
        exit 1
        ;;
esac
