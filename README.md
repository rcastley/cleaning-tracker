# Cleaning Tracker

A mobile-first Flask web app to track hours worked on cleaning jobs, log expenses and mileage, generate monthly and custom date range reports and printable invoices, and produce tax year summaries (UK HMRC mileage allowance included).

## Stack

- **Backend**: Flask + Gunicorn, JSON file storage (no database)
- **Frontend**: Alpine.js + Bootstrap 5.3.8 (self-hosted), inline SVG icons, no build step at runtime
- **Compression**: gzip via `flask-compress`; static assets cached for 1 hour

## Features

- **Multiple clients** with default round-trip mileage per client
- **Log work** — date, start/end time, miles; auto-computes hours and amount
- **Log expenses** — cleaning supplies etc., grouped by client
- **Reports** — hours, labour, expenses and mileage by client, month or custom date range (both dates included)
- **Tax year summary** — full breakdown with HMRC-rate mileage allowance (45p/25p)
- **Printable invoices** — open as a standalone HTML page, print-ready A4
- **History** — browse, edit and delete individual entries/expenses
- **Settings** — hourly rate, currency, tax year start, business details, payment info, client management

## Installation

Requires Python 3.10+. No Node.js, npm install, or CSS build is needed.

```bash
# 1. Create a virtualenv and install Python deps
uv venv .venv               # or: python -m venv .venv
uv pip install -r requirements.txt   # or: .venv/bin/pip install -r requirements.txt
```

## Proxmox LXC installation and updates

Use a Debian 12+ or Ubuntu 22.04+ LXC with systemd and Python 3.10+. Run the
following **inside the LXC as root**. For a new installation:

```bash
apt-get update
apt-get install -y git
git clone https://github.com/rcastley/cleaning-tracker.git /opt/cleaning-tracker
cd /opt/cleaning-tracker
./install.sh
```

For an existing installation, keep the existing checkout and its `data/` directory
together. Stop the manually started app with `./start.sh stop` before installing
the service. If the checkout is under `/root` or `/home`, move it to an unused path
under `/opt` or `/srv` first. The installer deliberately refuses those private home
locations rather than changing their permissions. Do not clone over existing data.
The Git checkout must be clean, including untracked files; `.venv/`, `.runtime/`,
`data/*.json`, and `backups/` are ignored and preserved.

`install.sh` installs OS/Python dependencies, creates a dedicated `cleaning-tracker`
system account, backs up existing data, and installs/enables
`cleaning-tracker.service`. Gunicorn runs in the foreground with one worker, restarts
after a crash, and writes logs to the journal. The service can write only to the
app's `data/` directory (plus its private temporary directory). The installer can
be rerun; it does not reset entries, clients, expenses, or settings. It refuses to
replace an unrelated systemd unit or one with custom overrides.

The app listens on port **5001**, preserving the existing reverse-proxy setup.
Installation does not configure authentication, TLS, the firewall, or a reverse
proxy. In Proxmox, also enable **Container → Options → Start at boot** to start the
LXC after the host reboots; systemd starts the app whenever the LXC starts.

```bash
systemctl status cleaning-tracker
systemctl restart cleaning-tracker
journalctl -u cleaning-tracker -f
```

For later updates:

```bash
cd /opt/cleaning-tracker
./update.sh
```

The updater uses the current branch's configured upstream. Git access must work for
the account running the script (root); private repositories need that account's
credentials. It fetches while the app is still running and refuses dirty, detached,
locally ahead, or divergent checkouts. If no new commit exists it leaves the service
alone. Otherwise it:

1. Stops the service and creates a private `backups/pre-deploy-*.tar.gz` snapshot,
   with the previous commit recorded alongside it.
2. Runs `git pull --ff-only --no-rebase . <fetched-commit>` to apply the exact remote
   revision already fetched and checked. Using the local fetched commit avoids a
   second remote fetch introducing an unchecked revision.
3. Creates a fresh Python environment under `.runtime/`, installs requirements,
   and checks dependency compatibility.
4. Switches the environment, starts the service, and checks both the main page and
   `/api/bootstrap` over localhost.
5. On failure, restores the previous commit and environment and tries to restart
   the previous app. The command still exits with an error and reports recovery
   status. Failed first-time installations leave the service stopped for repair.

Data is never automatically rolled back, since doing so could discard new records.
These scripts perform no data migrations. A future release that changes the data
format needs a separately reviewed migration/recovery procedure. Backups and old
environments are retained for recovery; review disk usage and remove old copies
only after confirming a successful deployment. Do not manually edit the checkout
or run `start.sh` while a deployment is in progress. Updates keep the installed unit;
rerun `install.sh` when a release requires changes to its systemd configuration.

Deployment tests use real temporary Git repositories, backups, and symlinks, with
systemd, package installation, and HTTP responses simulated. Run them with
`.venv/bin/python -m unittest discover -s tests -p test_deployment.py`.
The first real installation must still be validated inside the target LXC.

## Running locally

```bash
./start.sh           # start gunicorn in the background on port 5001
./start.sh status    # check if it's running
./start.sh log       # tail the log
./start.sh stop      # stop it
```

Then open `http://localhost:5001`.

For development, edit `static/app.css` directly and refresh the browser:

```bash
.venv/bin/python webapp.py    # Flask dev server on :5001
```

## Data storage

JSON files in `./data/` (created on first save):

- `entries.json` — work entries
- `expenses.json` — expenses
- `clients.json` — client list
- `config.json` — app settings

The `data/*.json` files are gitignored. Use `./backup.sh` to snapshot the `data/` folder into `./backups/`.

## Configuration

Configurable from the in-app **Settings** tab. Defaults:

- Hourly rate: £15.00
- Currency: £ (GBP)
- Tax year starts: April (UK)
- Payment terms: 14 days

## Project layout

```
webapp.py              Flask routes (page + JSON API)
helpers.py             Business logic + invoice template rendering
templates/
  index.html           Single-page app shell
  invoice.html         Printable invoice template
static/
  app.css              App styles; edit directly, no build step
  vendor/bootstrap.min.css Bootstrap 5.3.8 compiled CSS (MIT)
  app.js               Alpine app code + icon SVGs
  favicon.svg          App icon
  vendor/alpine.min.js Alpine.js 3.14.9 (self-hosted)
data/                  JSON data files (gitignored)
requirements.txt       Python deps
start.sh               Gunicorn process manager
install.sh             LXC installation and systemd setup
update.sh              Fast-forward update, backup, health check and rollback
scripts/service-common.sh Shared deployment functions
backup.sh              Data backup script
```

## API

JSON endpoints (all return `application/json`):

- `GET /api/bootstrap` — config + clients + entries + expenses in one call (used on initial page load)
- `GET|POST /api/entries` (`?client_id=…`) and `PUT|DELETE /api/entries/<id>`
- `GET|POST /api/expenses` and `PUT|DELETE /api/expenses/<id>`
- `GET|POST|PUT|DELETE /api/clients` and `<id>` variants
- `GET|PUT /api/config`
- `GET /api/reports/monthly?client_id=&year=&month=`
- `GET /api/reports/range?client_id=&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- `GET /api/reports/taxyear?client_id=&tax_year=`
- `GET /invoice?client_id=&year=&month=` — full HTML invoice page
- `GET /invoice?client_id=&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — custom period invoice

### Editing records

History provides an Edit action for work and expenses. Work edits retain the original
hourly rate and recalculate hours and earnings. Earlier end times indicate overnight
work. Cancel or Escape asks before discarding changed drafts; failed saves retain them.
Reports and newly generated invoices use the saved corrections.

Update requests require client_id and date, plus start_time, end_time and miles for
work, or amount and description for expenses. IDs and work rates cannot be changed.
Validation failures return HTTP 400 with `error` and field-keyed `errors`; missing
records return HTTP 404.

Run edit regression tests with `.venv/bin/python -m unittest discover -s tests`
and `node tests/test_editor.cjs`.

### Custom date reports

In **Reports → Custom dates**, select the start and end dates. Reports update when
those dates or the client change. **Try again** appears only if loading fails.
Both dates are included, and ranges can span months or years. Select a client and
choose **View Invoice** to print or save as PDF using your browser. Expense-only
periods can also be invoiced. Custom invoice references use
`PREFIX-YYYYMMDD-YYYYMMDD`; monthly invoice references are unchanged.

Run report checks with `.venv/bin/python -m unittest discover -s tests`
and `node tests/test_reports.cjs`.

### Mobile usability

- **Add entry** has today/yesterday shortcuts, side-by-side time fields, overnight
  guidance, penny-precision expenses and a saved-entry confirmation. Failed saves
  retain the draft and repeated taps cannot submit a second request while saving.
- **History** supports search by client, date, description or amount, a client
  filter, matching totals and 10 records per page. History opens on the current
  month, with previous/next month controls and a month/year picker. Search covers
  all dates; clearing it returns to the selected month. Empty months offer a
  shortcut to the latest records for the selected client and entry type. Cards show full dates and keep
  edit/delete targets separate from the record details.
- **Reports** offer this-week/this-month/last-month shortcuts, a compact totals
  panel, loading/retry states and a prominent invoice action with guidance.
- **Invoices** have a Print / Save PDF button, a phone-friendly preview and
  repeating table headers for longer printed reports.
- Larger touch targets, labelled fields, visible keyboard focus, a mobile edit
  sheet and a reachable settings-save button support small-screen use.
- App JavaScript and CSS URLs include content versions to avoid stale assets
  after deployment.

Additional interaction checks: `node tests/test_mobile_ux.cjs`.

### Phone backups

Go to **Settings → Back up your data → Download backup**. The browser downloads
`cleaning-tracker-backup-YYYY-MM-DD-HHMMSS.zip` (UTC timestamp). Check Files or
Downloads to confirm it was saved; you can move it to your preferred backup location.
The ZIP contains `entries.json`, `expenses.json`, `clients.json`, `config.json`,
version/timestamp metadata and restore instructions. Only saved data is included.
Keep the backup private: settings contain business and payment details.

`GET /api/backup` is read-only and returns a ZIP attachment with `Cache-Control: no-store`.
Bulk-clear controls and the collection DELETE endpoints have been removed.
Individual record deletion remains available in History with confirmation.

There is no in-app restore button. To restore, stop the app, preserve the current
`data/` folder, extract the four data JSON files into `data/`, then restart.
Restoration replaces existing data; it does not merge records. The existing
server-side `backup.sh` remains available.

Bootstrap CSS is vendored from https://getbootstrap.com/ (5.3.8). Alpine handles interactions, so Bootstrap JavaScript is not required. The standalone invoice retains its print-specific CSS. Existing `.cjs` interaction tests optionally use Node’s built-in test utilities; they require no npm dependencies and are not part of installation or deployment.
