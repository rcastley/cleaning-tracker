#!/usr/bin/env bash
# Shared implementation for install.sh and update.sh (Debian/Ubuntu + systemd).

SERVICE=cleaning-tracker.service
SERVICE_USER=cleaning-tracker
UNIT_FILE=/etc/systemd/system/cleaning-tracker.service
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
RUNTIME="$APP_DIR/.runtime"
ROLLBACK_NEEDED=0
RESTORE_CODE=0
RESTORE_UNIT=0
OLD_ENV=
OLD_COMMIT=
OLD_UNIT=

die() { echo "Error: $*" >&2; exit 1; }
repo_git() { git -c safe.directory="$APP_DIR" -C "$APP_DIR" "$@"; }

preflight() {
    [[ $(uname -s) == Linux ]] || die "Run this inside the Debian/Ubuntu LXC, not on your development computer."
    [[ $EUID -eq 0 ]] || die "Run as root (sudo $0)."
    [[ -d /run/systemd/system ]] || die "This container must run systemd."
    # shellcheck source=/dev/null
    source /etc/os-release
    case "$ID" in debian|ubuntu) ;; *) die "Supported systems: Debian and Ubuntu." ;; esac
    [[ "$APP_DIR" =~ ^/[a-zA-Z0-9_./-]+$ ]] || die "Use an installation path without spaces or special characters."
    case "$APP_DIR" in /opt/*|/srv/*) ;; *) die "Place this checkout under /opt or /srv first, preserving its data/ directory." ;; esac
    command -v flock >/dev/null || die "Install util-linux first."
    exec 9>/run/lock/cleaning-tracker-deploy.lock
    flock -n 9 || die "Another install or update is already running."
    cd "$APP_DIR"
}

check_checkout() {
    [[ "$(repo_git rev-parse --show-toplevel)" == "$APP_DIR" ]] || die "Run from the Cleaning Tracker Git checkout."
    [[ -z "$(repo_git status --porcelain --untracked-files=all)" ]] || die "Checkout has local changes or untracked files. Commit/stash them before deployment."
    [[ -z "$(repo_git ls-files data .runtime backups)" ]] || die "data/, backups/ and .runtime/ must not be tracked by Git."
    OLD_COMMIT=$(repo_git rev-parse HEAD)
}

check_managed_unit() {
    [[ -f "$UNIT_FILE" ]] || die "Service is not installed. Run ./install.sh first."
    grep -qx '# Managed by Cleaning Tracker install.sh' "$UNIT_FILE" || die "Existing service was not created by this installer; refusing to overwrite it."
    grep -qx "WorkingDirectory=$APP_DIR" "$UNIT_FILE" || die "Service belongs to a different checkout."
    [[ ! -d /etc/systemd/system/cleaning-tracker.service.d ]] || die "Service has custom overrides. Review these manually before using the deployment scripts."
}

prepare_runtime() {
    install -d -m 755 "$RUNTIME"
    OLD_ENV=$(readlink "$RUNTIME/current" || true)
    [[ ! -e "$RUNTIME/current" || -n "$OLD_ENV" ]] || die ".runtime/current must be a managed symlink."
    RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
    NEW_ENV="$RUNTIME/venv-$RUN_ID"
}

build_environment() {
    # Never mutate the environment used by the previous release.
    python3 -m venv "$NEW_ENV"
    "$NEW_ENV/bin/python" -m pip install --disable-pip-version-check -r "$APP_DIR/requirements.txt"
    "$NEW_ENV/bin/python" -m pip check
}

activate_environment() {
    ln -sfn "$NEW_ENV" "$RUNTIME/current.next"
    mv -Tf "$RUNTIME/current.next" "$RUNTIME/current"
}

backup_data() {
    install -d -m 700 "$APP_DIR/backups"
    BACKUP="$APP_DIR/backups/pre-deploy-$RUN_ID.tar.gz"
    # The service is stopped, so all JSON files belong to the same snapshot.
    (umask 077; tar -czf "$BACKUP" -C "$APP_DIR" data)
    tar -tzf "$BACKUP" >/dev/null
    printf '%s\n' "$OLD_COMMIT" > "$BACKUP.commit"
    chmod 600 "$BACKUP" "$BACKUP.commit"
    echo "Data backup: $BACKUP"
}

healthy() {
    local attempt
    for attempt in {1..15}; do
        if systemctl is-active --quiet "$SERVICE" &&
            curl --noproxy '*' --fail --silent --max-time 3 http://127.0.0.1:5001/ >/dev/null &&
            curl --noproxy '*' --fail --silent --max-time 3 http://127.0.0.1:5001/api/bootstrap >/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

recover_on_exit() {
    local result=$? recovered=1
    trap - EXIT INT TERM
    [[ $ROLLBACK_NEEDED == 1 ]] || return "$result"
    set +e
    echo "Deployment failed. Restoring the previous application; data will not be overwritten." >&2
    systemctl stop "$SERVICE" || recovered=0
    if [[ $RESTORE_CODE == 1 ]]; then
        # The checkout was verified clean before the update; no git clean is used.
        repo_git reset --hard "$OLD_COMMIT" || recovered=0
    fi
    if [[ -n "$OLD_ENV" ]]; then
        ln -sfn "$OLD_ENV" "$RUNTIME/current" || recovered=0
    else
        rm -f "$RUNTIME/current"
    fi
    if [[ $RESTORE_UNIT == 1 ]]; then
        if [[ -n "$OLD_UNIT" ]]; then
            cp "$OLD_UNIT" "$UNIT_FILE" || recovered=0
        else
            systemctl disable "$SERVICE"
            rm -f "$UNIT_FILE"
        fi
        systemctl daemon-reload || recovered=0
    fi
    if [[ -n "$OLD_ENV" && $recovered == 1 ]]; then
        systemctl reset-failed "$SERVICE" 2>/dev/null || true
        if systemctl start "$SERVICE" && healthy; then
            echo "Previous version is running again." >&2
        else
            echo "Recovery needs attention. Run: journalctl -u $SERVICE -n 80" >&2
        fi
    else
        echo "Service is stopped. Fix the error and rerun install.sh. Any backup remains in backups/." >&2
    fi
    [[ $result != 0 ]] || result=1
    exit "$result"
}

arm_recovery() {
    ROLLBACK_NEEDED=1
    trap recover_on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
}

write_unit() {
    cat > "$RUNTIME/service.next" <<EOF
# Managed by Cleaning Tracker install.sh
[Unit]
Description=Cleaning Tracker
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
ExecStart=$RUNTIME/current/bin/gunicorn webapp:app --bind 0.0.0.0:5001 --workers 1 --access-logfile - --error-logfile -
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=$APP_DIR/data

[Install]
WantedBy=multi-user.target
EOF
    install -m 644 "$RUNTIME/service.next" "$UNIT_FILE"
}
