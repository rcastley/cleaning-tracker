"""One-time migration: backfill miles on existing entries from client defaults.

Run this AFTER setting default_miles on each client via the Settings UI.

Usage:
    python backfill_miles.py          # dry-run (shows what would change)
    python backfill_miles.py --apply  # apply changes
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CLIENTS_FILE = DATA_DIR / "clients.json"
ENTRIES_FILE = DATA_DIR / "entries.json"


def main():
    apply = "--apply" in sys.argv

    with open(CLIENTS_FILE) as f:
        clients = json.load(f)
    with open(ENTRIES_FILE) as f:
        entries = json.load(f)

    client_miles = {c["id"]: c.get("default_miles", 0) for c in clients}
    updated = 0

    for entry in entries:
        current = entry.get("miles", 0)
        default = client_miles.get(entry.get("client_id"), 0)
        if current == 0 and default > 0:
            if apply:
                entry["miles"] = default
            updated += 1
            print(f"  {entry['date']}  {entry.get('start_time','')}-{entry.get('end_time','')}  -> {default} mi")

    if updated == 0:
        print("No entries need updating.")
        return

    print(f"\n{updated} entries {'updated' if apply else 'would be updated'}.")

    if apply:
        with open(ENTRIES_FILE, "w") as f:
            json.dump(entries, f, indent=2)
        print("Saved to", ENTRIES_FILE)
    else:
        print("Run with --apply to save changes.")


if __name__ == "__main__":
    main()
