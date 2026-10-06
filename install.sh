#!/usr/bin/env bash
# Install this checkout as a systemd service inside a Debian/Ubuntu LXC.
set -euo pipefail
umask 022
source "$(dirname "${BASH_SOURCE[0]}")/scripts/service-common.sh"

main() {
    if [[ ${1:-} == --help ]]; then
        echo "Usage: sudo ./install.sh (from a clean Git checkout under /opt or /srv)"
        return
    fi
    [[ $# == 0 ]] || die "Usage: sudo ./install.sh"
    preflight
    command -v git >/dev/null || die "Install git first: apt-get install git"
    check_checkout
    if [[ -e "$UNIT_FILE" ]]; then
        check_managed_unit
    elif systemctl cat "$SERVICE" >/dev/null 2>&1; then
        die "A service with this name already exists outside $UNIT_FILE."
    fi

    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip curl ca-certificates iproute2
    python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
    if ! systemctl is-active --quiet "$SERVICE" && [[ -n "$(ss -H -ltn 'sport = :5001')" ]]; then
        die "Port 5001 is in use. Stop the existing app with ./start.sh stop, then rerun this installer."
    fi
    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        useradd --system --user-group --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$SERVICE_USER"
    fi
    runuser -u "$SERVICE_USER" -- test -r "$APP_DIR/webapp.py" || die "The service account cannot read this checkout. Check directory permissions."
    prepare_runtime
    build_environment
    runuser -u "$SERVICE_USER" -- test -x "$NEW_ENV/bin/gunicorn" || die "The service account cannot execute the new environment."
    if [[ -f "$UNIT_FILE" ]]; then
        OLD_UNIT="$RUNTIME/service-before-$RUN_ID"
        cp "$UNIT_FILE" "$OLD_UNIT"
    fi
    arm_recovery
    systemctl stop "$SERVICE" 2>/dev/null || [[ ! -f "$UNIT_FILE" ]]
    install -d -m 700 "$APP_DIR/data"
    backup_data
    chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/data"
    chmod -R u+rwX,go-rwx "$APP_DIR/data"
    activate_environment
    RESTORE_UNIT=1
    write_unit
    systemctl daemon-reload
    # A new unit may not be loaded yet. Clearing an old failure is best-effort;
    # enable/restart and the health check below remain mandatory.
    systemctl reset-failed "$SERVICE" 2>/dev/null || true
    systemctl enable "$SERVICE"
    systemctl restart "$SERVICE"
    healthy || die "Startup check failed. See journalctl -u $SERVICE -n 80."
    configure_backup_cron
    ROLLBACK_NEEDED=0
    echo "Installed and running on port 5001. The app will start when this LXC starts."
    echo "Also enable Start at boot in Proxmox if the LXC should start with its host."
}

# Defining main before invoking it keeps an in-progress deployment in memory.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
