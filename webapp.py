"""Flask web app — mobile-first UI for Cleaning Tracker."""

from datetime import datetime, timezone
import math
import hashlib
import io
import json
import zipfile
from pathlib import Path
import re
from flask import Flask, jsonify, request, render_template, abort, send_file
from flask_compress import Compress

from helpers import (
    ENTRIES_FILE, EXPENSES_FILE, CONFIG_FILE, CLIENTS_FILE,
    DEFAULT_CONFIG, DEFAULT_CLIENTS,
    load_json, save_json, load_config,
    get_client_by_id,
    calculate_hours, get_tax_year, get_tax_year_label,
    format_hours, generate_invoice_html,
    calculate_hmrc_mileage_allowance,
)

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 3600  # 1 hour cache for /static
Compress(app)


@app.after_request
def _enable_static_compression(response):
    # flask-compress skips direct_passthrough responses (used by send_from_directory).
    # Force the body to materialise so the next after_request (flask-compress) can gzip it.
    if response.direct_passthrough and response.mimetype in ("text/css", "text/javascript"):
        response.direct_passthrough = False
        response.set_data(response.get_data())
    return response


def _filter_by_client(items, client_id):
    """Filter a list of entries/expenses by client_id (no-op if None/empty)."""
    if not client_id:
        return items
    return [e for e in items if e.get("client_id") == client_id]


def _requested_date_range():
    dates = []
    for field in ("start_date", "end_date"):
        value = request.args.get(field, "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Enter a valid start and end date (YYYY-MM-DD).")
        try:
            dates.append(datetime.strptime(value, "%Y-%m-%d").date())
        except ValueError:
            raise ValueError("Enter a valid start and end date (YYYY-MM-DD).") from None
    if dates[0] > dates[1]:
        raise ValueError("End date must be on or after start date.")
    return dates


def _filter_by_dates(items, start, end):
    return [e for e in items if start <= datetime.fromisoformat(e["date"]).date() <= end]


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    # Keep markup and assets in sync after deployment, even with browser caching.
    versions = {name: hashlib.sha256((Path(app.static_folder) / name).read_bytes()).hexdigest()[:12]
                for name in ("app.js", "tailwind.css")}
    return render_template("index.html", asset_versions=versions)


@app.route("/api/bootstrap")
def bootstrap():
    """Single-shot endpoint that returns everything needed for initial UI render."""
    return jsonify({
        "config": load_config(),
        "clients": load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS)),
        "entries": load_json(ENTRIES_FILE, []),
        "expenses": load_json(EXPENSES_FILE, []),
    })


@app.route("/api/backup")
def download_backup():
    """Download a portable copy of saved data without changing any records."""
    created = datetime.now(timezone.utc)
    files = {
        "entries.json": load_json(ENTRIES_FILE, []),
        "expenses.json": load_json(EXPENSES_FILE, []),
        "clients.json": load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS)),
        "config.json": load_config(),
        "backup-info.json": {
            "application": "Cleaning Tracker",
            "format_version": 1,
            "created_at": created.isoformat(),
        },
    }
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as backup:
        for name, data in files.items():
            backup.writestr(name, json.dumps(data, ensure_ascii=False, indent=2))
        backup.writestr("README.txt", (
            "Cleaning Tracker backup\n\n"
            "Includes saved work entries, expenses, clients and settings.\n"
            "Settings include business and payment details. Keep this file private.\n\n"
            "To restore: stop the application, keep a copy of its current data folder,\n"
            "then copy entries.json, expenses.json, clients.json and config.json\n"
            "from this archive into the application's data folder and restart it.\n"
            "Restoring replaces the current records; it does not merge them.\n"
            "Ask the person who manages the application to do this if needed.\n"
        ))
    archive.seek(0)
    response = send_file(archive, mimetype="application/zip", as_attachment=True,
                         download_name=created.strftime("cleaning-tracker-backup-%Y-%m-%d-%H%M%S.zip"),
                         max_age=0)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/invoice")
def invoice():
    """Render an invoice as a standalone HTML page."""
    client_id = request.args.get("client_id")
    start = end = None
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not client_id:
        abort(400, "client_id is required")
    if "start_date" in request.args or "end_date" in request.args:
        try:
            start, end = _requested_date_range()
        except ValueError as error:
            return jsonify(error=str(error)), 400
    else:
        try:
            datetime(year, month, 1)
        except (ValueError, TypeError):
            abort(400, "A valid year and month are required")

    config = load_config()
    clients = load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS))
    entries = load_json(ENTRIES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])

    client = get_client_by_id(clients, client_id)
    entries = _filter_by_client(entries, client_id)
    expenses = _filter_by_client(expenses, client_id)

    if start is not None:
        month_entries = _filter_by_dates(entries, start, end)
        month_expenses = _filter_by_dates(expenses, start, end)
    else:
        month_entries = [
            e for e in entries
            if datetime.fromisoformat(e["date"]).year == year
            and datetime.fromisoformat(e["date"]).month == month
        ]
        month_expenses = [
            e for e in expenses
            if datetime.fromisoformat(e["date"]).year == year
            and datetime.fromisoformat(e["date"]).month == month
        ]

    html = generate_invoice_html(month_entries, month_expenses, year, month, config, client,
                                 start_date=start, end_date=end)
    return html


# ---------------------------------------------------------------------------
# Entries API
# ---------------------------------------------------------------------------

def _validate_edit(data, work=False):
    """Validate editable fields without accepting derived values from the browser."""
    errors = {}
    clients = load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS))
    if not any(c['id'] == data.get('client_id') for c in clients):
        errors['client_id'] = 'Select an existing client.'
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(data.get('date', ''))):
            raise ValueError
        datetime.strptime(data['date'], '%Y-%m-%d')
    except (ValueError, TypeError):
        errors['date'] = 'Enter a valid date.'
    numeric = 'miles' if work else 'amount'
    try:
        value = float(data.get(numeric, ''))
        if isinstance(data.get(numeric), bool) or not math.isfinite(value) or value < 0 or (not work and round(value, 2) <= 0):
            raise ValueError
        data[numeric] = value
    except (ValueError, TypeError, OverflowError):
        errors[numeric] = 'Enter miles of zero or more.' if work else 'Enter an amount greater than zero.'
    if work:
        for field in ('start_time', 'end_time'):
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', str(data.get(field, ''))):
                errors[field] = 'Enter a valid time.'
        if not errors.get('start_time') and not errors.get('end_time') and data['start_time'] == data['end_time']:
            errors['end_time'] = 'End time must differ from start time.'
    elif not isinstance(data.get('description'), str):
        errors['description'] = 'Enter a description (or leave it blank).'
    return errors


@app.route('/api/entries/<entry_id>', methods=['PUT'])
def update_entry(entry_id):
    return _update_record(ENTRIES_FILE, entry_id, work=True)


@app.route('/api/expenses/<expense_id>', methods=['PUT'])
def update_expense(expense_id):
    return _update_record(EXPENSES_FILE, expense_id)


def _update_record(path, record_id, work=False):
    records = load_json(path, [])
    record = next((r for r in records if r['id'] == record_id), None)
    if record is None:
        return jsonify(error='This record no longer exists.'), 404
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Send a JSON object.'), 400
    errors = _validate_edit(data, work)
    if errors:
        return jsonify(error='Please check the highlighted fields.', errors=errors), 400
    fields = ('client_id', 'date', 'start_time', 'end_time', 'miles') if work else ('client_id', 'date', 'amount', 'description')
    updated = {**record, **{field: data[field] for field in fields}}
    if work:
        hours = calculate_hours(updated['start_time'], updated['end_time'])
        updated['hours'] = round(hours, 2)
        updated['amount'] = round(hours * record['hourly_rate'], 2)
    else:
        updated['amount'] = round(updated['amount'], 2)
    records[records.index(record)] = updated
    save_json(path, records)
    return jsonify(updated)

@app.route("/api/entries", methods=["GET"])
def list_entries():
    entries = load_json(ENTRIES_FILE, [])
    return jsonify(_filter_by_client(entries, request.args.get("client_id")))


@app.route("/api/entries", methods=["POST"])
def create_entry():
    data = request.get_json(force=True)
    for field in ("client_id", "date", "start_time", "end_time"):
        if field not in data:
            abort(400, f"Missing required field: {field}")
    config = load_config()
    entries = load_json(ENTRIES_FILE, [])

    hours = calculate_hours(data["start_time"], data["end_time"])
    rate = config["hourly_rate"]
    entry = {
        "id": datetime.now().isoformat(),
        "client_id": data["client_id"],
        "date": data["date"],
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "hours": round(hours, 2),
        "hourly_rate": rate,
        "amount": round(hours * rate, 2),
        "miles": float(data.get("miles", 0)),
    }
    entries.append(entry)
    save_json(ENTRIES_FILE, entries)
    return jsonify(entry), 201


@app.route("/api/entries/<entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    entries = load_json(ENTRIES_FILE, [])
    entries = [e for e in entries if e["id"] != entry_id]
    save_json(ENTRIES_FILE, entries)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Expenses API
# ---------------------------------------------------------------------------

@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    expenses = load_json(EXPENSES_FILE, [])
    return jsonify(_filter_by_client(expenses, request.args.get("client_id")))


@app.route("/api/expenses", methods=["POST"])
def create_expense():
    data = request.get_json(force=True)
    for field in ("client_id", "date", "amount"):
        if field not in data:
            abort(400, f"Missing required field: {field}")
    expenses = load_json(EXPENSES_FILE, [])

    expense = {
        "id": datetime.now().isoformat(),
        "client_id": data["client_id"],
        "date": data["date"],
        "amount": round(float(data["amount"]), 2),
        "description": data.get("description", "Cleaning supplies"),
    }
    expenses.append(expense)
    save_json(EXPENSES_FILE, expenses)
    return jsonify(expense), 201


@app.route("/api/expenses/<expense_id>", methods=["DELETE"])
def delete_expense(expense_id):
    expenses = load_json(EXPENSES_FILE, [])
    expenses = [e for e in expenses if e["id"] != expense_id]
    save_json(EXPENSES_FILE, expenses)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Config API
# ---------------------------------------------------------------------------

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["PUT"])
def update_config():
    data = request.get_json(force=True)
    config = load_config()
    for key in data:
        if key in DEFAULT_CONFIG:
            config[key] = data[key]
    save_json(CONFIG_FILE, config)
    return jsonify(config)


# ---------------------------------------------------------------------------
# Clients API
# ---------------------------------------------------------------------------

@app.route("/api/clients", methods=["GET"])
def list_clients():
    return jsonify(load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS)))


@app.route("/api/clients", methods=["POST"])
def create_client():
    data = request.get_json(force=True)
    if "name" not in data or not data["name"].strip():
        abort(400, "Missing required field: name")
    clients = load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS))

    client = {
        "id": datetime.now().isoformat(),
        "name": data["name"],
        "address": data.get("address", ""),
        "default_miles": float(data.get("default_miles", 0)),
    }
    clients.append(client)
    save_json(CLIENTS_FILE, clients)
    return jsonify(client), 201


@app.route("/api/clients/<client_id>", methods=["PUT"])
def update_client(client_id):
    data = request.get_json(force=True)
    clients = load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS))
    for c in clients:
        if c["id"] == client_id:
            if "name" in data:
                c["name"] = data["name"]
            if "address" in data:
                c["address"] = data["address"]
            if "default_miles" in data:
                c["default_miles"] = float(data["default_miles"])
            save_json(CLIENTS_FILE, clients)
            return jsonify(c)
    abort(404, "Client not found")


@app.route("/api/clients/<client_id>", methods=["DELETE"])
def delete_client(client_id):
    clients = load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS))
    clients = [c for c in clients if c["id"] != client_id]
    save_json(CLIENTS_FILE, clients)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Reports API (computed, read-only)
# ---------------------------------------------------------------------------

@app.route("/api/reports/monthly")
def monthly_report():
    config = load_config()
    entries = load_json(ENTRIES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])

    client_id = request.args.get("client_id")
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    entries = _filter_by_client(entries, client_id)
    expenses = _filter_by_client(expenses, client_id)

    # Determine available months
    all_dates = (
        [datetime.fromisoformat(e["date"]) for e in entries]
        + [datetime.fromisoformat(e["date"]) for e in expenses]
    )
    available_months = sorted(set((d.year, d.month) for d in all_dates), reverse=True)

    if year and month:
        month_entries = [
            e for e in entries
            if datetime.fromisoformat(e["date"]).year == year
            and datetime.fromisoformat(e["date"]).month == month
        ]
        month_expenses = [
            e for e in expenses
            if datetime.fromisoformat(e["date"]).year == year
            and datetime.fromisoformat(e["date"]).month == month
        ]
    else:
        month_entries = []
        month_expenses = []

    return jsonify({
        **_report_totals(month_entries, month_expenses, config),
        "available_months": [{"year": y, "month": m, "label": datetime(y, m, 1).strftime("%B %Y")} for y, m in available_months],
    })


def _report_totals(entries, expenses, config):
    total_hours = sum(e["hours"] for e in entries)
    total_labour = sum(e["amount"] for e in entries)
    total_expenses = sum(e["amount"] for e in expenses)
    return {
        "sessions": len(entries),
        "total_hours": round(total_hours, 2),
        "total_hours_fmt": format_hours(total_hours),
        "total_labour": round(total_labour, 2),
        "total_expenses": round(total_expenses, 2),
        "total_amount": round(total_labour + total_expenses, 2),
        "total_miles": round(sum(e.get("miles", 0) for e in entries), 1),
        "entries": sorted(entries, key=lambda x: x["date"]),
        "expenses": sorted(expenses, key=lambda x: x["date"]),
        "currency": config["currency_symbol"],
    }


@app.route("/api/reports/range")
def date_range_report():
    try:
        start, end = _requested_date_range()
    except ValueError as error:
        return jsonify(error=str(error)), 400
    client_id = request.args.get("client_id")
    entries = _filter_by_dates(_filter_by_client(load_json(ENTRIES_FILE, []), client_id), start, end)
    expenses = _filter_by_dates(_filter_by_client(load_json(EXPENSES_FILE, []), client_id), start, end)
    return jsonify({
        **_report_totals(entries, expenses, load_config()),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    })


@app.route("/api/reports/taxyear")
def taxyear_report():
    config = load_config()
    entries = load_json(ENTRIES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])
    tsm = config["tax_year_start_month"]

    client_id = request.args.get("client_id")
    entries = _filter_by_client(entries, client_id)
    expenses = _filter_by_client(expenses, client_id)

    # Determine available tax years
    all_dates = (
        [datetime.fromisoformat(e["date"]).date() for e in entries]
        + [datetime.fromisoformat(e["date"]).date() for e in expenses]
    )
    tax_years = sorted(set(get_tax_year(d, tsm) for d in all_dates), reverse=True) if all_dates else []

    selected_ty = request.args.get("tax_year", type=int)

    if selected_ty is not None:
        ty_entries = [
            e for e in entries
            if get_tax_year(datetime.fromisoformat(e["date"]).date(), tsm) == selected_ty
        ]
        ty_expenses = [
            e for e in expenses
            if get_tax_year(datetime.fromisoformat(e["date"]).date(), tsm) == selected_ty
        ]
    else:
        ty_entries = []
        ty_expenses = []

    total_hours = sum(e["hours"] for e in ty_entries)
    total_labour = sum(e["amount"] for e in ty_entries)
    total_expenses_val = sum(e["amount"] for e in ty_expenses)
    total_miles = sum(e.get("miles", 0) for e in ty_entries)
    mileage_allowance = calculate_hmrc_mileage_allowance(total_miles)

    # Monthly breakdown
    monthly = {}
    for e in ty_entries:
        d = datetime.fromisoformat(e["date"])
        key = f"{d.year}-{d.month:02d}"
        if key not in monthly:
            monthly[key] = {"year": d.year, "month": d.month, "hours": 0, "labour": 0, "expenses": 0, "sessions": 0, "miles": 0}
        monthly[key]["hours"] += e["hours"]
        monthly[key]["labour"] += e["amount"]
        monthly[key]["sessions"] += 1
        monthly[key]["miles"] += e.get("miles", 0)
    for e in ty_expenses:
        d = datetime.fromisoformat(e["date"])
        key = f"{d.year}-{d.month:02d}"
        if key not in monthly:
            monthly[key] = {"year": d.year, "month": d.month, "hours": 0, "labour": 0, "expenses": 0, "sessions": 0, "miles": 0}
        monthly[key]["expenses"] += e["amount"]

    breakdown = []
    for key in sorted(monthly):
        m = monthly[key]
        breakdown.append({
            "label": datetime(m["year"], m["month"], 1).strftime("%b %Y"),
            "sessions": m["sessions"],
            "hours": round(m["hours"], 2),
            "hours_fmt": format_hours(m["hours"]),
            "labour": round(m["labour"], 2),
            "expenses": round(m["expenses"], 2),
            "total": round(m["labour"] + m["expenses"], 2),
            "miles": round(m["miles"], 1),
        })

    return jsonify({
        "available_tax_years": [{"year": ty, "label": get_tax_year_label(ty, tsm)} for ty in tax_years],
        "sessions": len(ty_entries),
        "total_hours": round(total_hours, 2),
        "total_hours_fmt": format_hours(total_hours),
        "total_labour": round(total_labour, 2),
        "total_expenses": round(total_expenses_val, 2),
        "total_amount": round(total_labour + total_expenses_val, 2),
        "total_miles": round(total_miles, 1),
        "mileage_allowance": mileage_allowance,
        "breakdown": breakdown,
        "currency": config["currency_symbol"],
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
