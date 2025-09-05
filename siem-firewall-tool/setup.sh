#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
LOG_DIR="$ROOT_DIR/logs"
DB_PATH="$ROOT_DIR/storage/firewall_logs.db"

mkdir -p "$LOG_DIR"

need_pkg() {
  if ! dpkg -s "$1" >/dev/null 2>&1; then
    echo "[*] Installing missing package: $1"
    sudo apt-get install -y "$1"
  fi
}

echo "[*] Checking required system packages..."
need_pkg sqlite3
need_pkg rsyslog
need_pkg python3-gi
need_pkg gir1.2-notify-0.7
need_pkg python3-venv

echo "[*] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
$PIP install --upgrade pip >/dev/null 2>&1 || true
$PIP install -r "$ROOT_DIR/requirements.txt"

echo "[*] Initializing database..."
PYTHONPATH="$ROOT_DIR" DB_PATH="$DB_PATH" "$PY" - <<'PYCODE'
from storage.db_handler import init_db
init_db()
print("[✓] Database initialized")
PYCODE

start_services() {
  export PYTHONPATH="$ROOT_DIR"
  export DB_PATH="$DB_PATH"
  export LOG_FILE="${LOG_FILE:-/var/log/ufw.log}"
  export HOST="0.0.0.0"
  export PORT="${PORT:-5000}"

  echo "[*] Starting services..."
  "$PY" "$ROOT_DIR/parser/firewall_parser.py" >>"$LOG_DIR/parser.log" 2>&1 &
  echo $! > "$LOG_DIR/parser.log.pid"

  "$PY" "$ROOT_DIR/alerts/alert_engine.py" >>"$LOG_DIR/alerts.log" 2>&1 &
  echo $! > "$LOG_DIR/alerts.log.pid"

  "$PY" "$ROOT_DIR/dashboard/app.py" >>"$LOG_DIR/dashboard.log" 2>&1 &
  echo $! > "$LOG_DIR/dashboard.log.pid"

  echo "[✓] Services started successfully"
  echo "   - Parser PID:   $(cat "$LOG_DIR/parser.log.pid") (logs/parser.log)"
  echo "   - Alert Engine: $(cat "$LOG_DIR/alerts.log.pid") (logs/alerts.log)"
  echo "   - Dashboard:    $(cat "$LOG_DIR/dashboard.log.pid") (logs/dashboard.log)"
  echo
  echo "Dashboard available at: http://127.0.0.1:${PORT}"
  echo "Use './setup.sh stop' to stop services."
}

stop_services() {
  echo "[*] Stopping services..."
  for name in parser alerts dashboard; do
    PID_FILE="$LOG_DIR/${name}.log.pid"
    if [ -f "$PID_FILE" ]; then
      PID="$(cat "$PID_FILE" || true)"
      if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        echo "   - $name (pid $PID) stopped"
      else
        echo "   - $name not running"
      fi
      rm -f "$PID_FILE"
    else
      echo "   - $name not running"
    fi
  done
  echo "[✓] All services stopped"
}

status_services() {
  echo "[*] Service status:"
  for name in parser alerts dashboard; do
    PID_FILE="$LOG_DIR/${name}.log.pid"
    if [ -f "$PID_FILE" ]; then
      PID="$(cat "$PID_FILE" 2>/dev/null || true)"
      if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
        echo "   - $name: running (pid $PID)"
      else
        echo "   - $name: not running (stale PID file)"
      fi
    else
      echo "   - $name: not running"
    fi
  done
}

case "${1:-run}" in
  run) start_services; trap 'stop_services; exit 0' INT TERM; wait ;;
  start) nohup bash "$0" run >/dev/null 2>&1 & echo "[✓] Daemonized. Use ./setup.sh status or ./setup.sh stop" ;;
  stop) stop_services ;;
  status) status_services ;;
  restart) stop_services; sleep 1; bash "$0" run ;;
  *) echo "Usage: ./setup.sh [run|start|stop|status|restart]"; exit 1 ;;
esac
