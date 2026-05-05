# Cleaning Tracker

A mobile-first Flask web app to track hours worked on cleaning jobs, log expenses and mileage, generate monthly reports and printable invoices, and produce tax year summaries (UK HMRC mileage allowance included).

## Stack

- **Backend**: Flask + Gunicorn, JSON file storage (no database)
- **Frontend**: Alpine.js + Tailwind CSS (precompiled), inline SVG icons, no build step at runtime
- **Compression**: gzip via `flask-compress`; static assets cached for 1 hour

## Features

- **Multiple clients** with default round-trip mileage per client
- **Log work** — date, start/end time, miles; auto-computes hours and amount
- **Log expenses** — cleaning supplies etc., grouped by client
- **Monthly reports** — hours, labour, expenses, mileage by client and month
- **Tax year summary** — full breakdown with HMRC-rate mileage allowance (45p/25p)
- **Printable invoices** — open as a standalone HTML page, print-ready A4
- **History** — browse and delete individual entries/expenses
- **Settings** — hourly rate, currency, tax year start, business details, payment info, client management

## Installation

Requires Python 3.10+ and Node.js (for the one-time CSS build).

```bash
# 1. Create a virtualenv and install Python deps
uv venv .venv               # or: python -m venv .venv
uv pip install -r requirements.txt   # or: .venv/bin/pip install -r requirements.txt

# 2. Build the Tailwind stylesheet (committed; only needed when classes change)
npm install
npm run build:css
```

## Running

```bash
./start.sh           # start gunicorn in the background on port 5001
./start.sh status    # check if it's running
./start.sh log       # tail the log
./start.sh stop      # stop it
```

Then open `http://localhost:5001`.

For development with hot CSS reloading:

```bash
npm run watch:css     # in one terminal
.venv/bin/python webapp.py    # in another (Flask dev server on :5001)
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
  tailwind.css         Built stylesheet (commit; rebuild via npm run build:css)
  app.js               Alpine app code + icon SVGs
  favicon.svg          App icon
  vendor/alpine.min.js Alpine.js 3.14.9 (self-hosted)
  src/input.css        Tailwind entry point
data/                  JSON data files (gitignored)
tailwind.config.js     Tailwind content-scanning config
package.json           CSS build scripts
requirements.txt       Python deps
start.sh               Gunicorn process manager
backup.sh              Data backup script
```

## API

JSON endpoints (all return `application/json`):

- `GET /api/bootstrap` — config + clients + entries + expenses in one call (used on initial page load)
- `GET|POST|DELETE /api/entries` (`?client_id=…`) and `DELETE /api/entries/<id>`
- `GET|POST|DELETE /api/expenses` and `DELETE /api/expenses/<id>`
- `GET|POST|PUT|DELETE /api/clients` and `<id>` variants
- `GET|PUT /api/config`
- `GET /api/reports/monthly?client_id=&year=&month=`
- `GET /api/reports/taxyear?client_id=&tax_year=`
- `GET /invoice?client_id=&year=&month=` — full HTML invoice page
