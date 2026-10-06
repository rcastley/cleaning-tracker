#!/usr/bin/env bash
# Safely fast-forward the installed checkout and restart its systemd service.
set -euo pipefail
umask 022
source "$(dirname "${BASH_SOURCE[0]}")/scripts/service-common.sh"

main() {
    if [[ ${1:-} == --help ]]; then
        echo "Usage: sudo ./update.sh (uses the current branch's configured upstream)"
        return
    fi
    [[ $# == 0 ]] || die "Usage: sudo ./update.sh"
    preflight
    check_checkout
    check_managed_unit
    repo_git symbolic-ref --quiet HEAD >/dev/null || die "Detached HEAD. Check out the deployment branch first."
    local upstream remote target
    upstream=$(repo_git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}') || die "Configure an upstream branch first."
    remote=$(repo_git config --get "branch.$(repo_git branch --show-current).remote")
    [[ "$remote" != . ]] || die "The deployment branch must track a remote repository."
    # Fetch while the app is still available; authentication/network failure causes no downtime.
    repo_git fetch "$remote"
    target=$(repo_git rev-parse "$upstream")
    repo_git merge-base --is-ancestor HEAD "$upstream" || die "Local branch is ahead of or diverged from $upstream. Resolve it manually."
    [[ -z "$(repo_git ls-tree -r --name-only "$target" -- data .runtime backups)" ]] || die "New release attempts to track deployment data."
    if [[ "$OLD_COMMIT" == "$target" ]]; then
        echo "Already up to date. Service was not restarted."
        return
    fi
    prepare_runtime
    [[ -n "$OLD_ENV" && -x "$OLD_ENV/bin/gunicorn" ]] || die "Previous environment is missing; run install.sh first."
    [[ -d "$APP_DIR/data" ]] || die "Data directory is missing. Investigate before updating."
    arm_recovery
    systemctl stop "$SERVICE"
    backup_data
    RESTORE_CODE=1
    # Main and recovery functions are already loaded, even if this pull updates these scripts.
    # Pull the exact revision just fetched and checked, rather than racing a second remote fetch.
    repo_git pull --ff-only --no-rebase . "$target"
    # Future releases must keep persistent data outside Git as well.
    [[ -z "$(repo_git ls-files data .runtime backups)" ]] || die "New release attempts to track deployment data."
    build_environment
    activate_environment
    systemctl reset-failed "$SERVICE"
    systemctl start "$SERVICE"
    healthy || die "Updated app failed its startup check."
    ROLLBACK_NEEDED=0
    echo "Updated to $(repo_git rev-parse --short HEAD). Service is healthy."
    echo "Previous environment retained at $OLD_ENV; backup at $BACKUP."
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then main "$@"; fi
