#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="${1:-/var/log/ufw.log}"
exec tail -F "$LOG_FILE"
