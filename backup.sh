#!/usr/bin/env bash
#
# Backup and restore script for cleaning-tracker data files.
#
# Usage:
#   ./backup.sh backup              Create a timestamped backup
#   ./backup.sh restore <file>      Restore from a backup archive
#   ./backup.sh list                List available backups
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
BACKUP_DIR="$SCRIPT_DIR/backups"
DATA_FILES=("config.json" "entries.json" "expenses.json" "clients.json")

do_backup() {
    mkdir -p "$BACKUP_DIR"

    # Collect files that actually exist
    local files_to_backup=()
    for f in "${DATA_FILES[@]}"; do
        if [[ -f "$DATA_DIR/$f" ]]; then
            files_to_backup+=("$f")
        fi
    done

    if [[ ${#files_to_backup[@]} -eq 0 ]]; then
        echo "No data files found in $DATA_DIR — nothing to back up."
        exit 1
    fi

    local timestamp
    timestamp="$(date +%Y%m%d_%H%M%S)"
    local archive="$BACKUP_DIR/backup_${timestamp}.tar.gz"

    tar -czf "$archive" -C "$DATA_DIR" "${files_to_backup[@]}"
    echo "Backup created: $archive"
    echo "Files: ${files_to_backup[*]}"
}

do_restore() {
    local archive="$1"

    if [[ ! -f "$archive" ]]; then
        # Check if it's a relative name in the backups dir
        if [[ -f "$BACKUP_DIR/$archive" ]]; then
            archive="$BACKUP_DIR/$archive"
        else
            echo "Error: File not found: $archive"
            exit 1
        fi
    fi

    mkdir -p "$DATA_DIR"

    echo "Restoring from: $archive"
    echo "This will overwrite existing data files. Continue? [y/N]"
    read -r confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Cancelled."
        exit 0
    fi

    tar -xzf "$archive" -C "$DATA_DIR"
    echo "Restore complete. Files extracted to $DATA_DIR/"
}

do_list() {
    mkdir -p "$BACKUP_DIR"
    local count
    count=$(find "$BACKUP_DIR" -name "backup_*.tar.gz" 2>/dev/null | wc -l | tr -d ' ')

    if [[ "$count" -eq 0 ]]; then
        echo "No backups found in $BACKUP_DIR/"
        exit 0
    fi

    echo "Available backups:"
    for f in "$BACKUP_DIR"/backup_*.tar.gz; do
        local size
        size=$(du -h "$f" | cut -f1)
        echo "  $(basename "$f")  ($size)"
    done
}

case "${1:-}" in
    backup)
        do_backup
        ;;
    restore)
        if [[ -z "${2:-}" ]]; then
            echo "Usage: $0 restore <backup-file>"
            echo "Run '$0 list' to see available backups."
            exit 1
        fi
        do_restore "$2"
        ;;
    list)
        do_list
        ;;
    *)
        echo "Usage: $0 {backup|restore <file>|list}"
        exit 1
        ;;
esac
