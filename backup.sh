#!/usr/bin/env bash
# Back up, list or restore application data (legacy and deployment archives).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/scripts/backup_data.py" "$@"
