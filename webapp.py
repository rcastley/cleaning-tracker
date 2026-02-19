"""Flask web app — mobile-first UI for Cleaning Tracker."""

from datetime import datetime
from flask import Flask, jsonify, request, render_template, abort

from helpers import (
    ENTRIES_FILE, EXPENSES_FILE, CONFIG_FILE, CLIENTS_FILE,
    DEFAULT_CONFIG, DEFAULT_CLIENTS,
    load_json, save_json, load_config,
    get_client_by_id,
    calculate_hours, get_tax_year, get_tax_year_label,
    format_hours, generate_invoice_html,
)

app = Flask(__name__)


def _filter_by_client(items, client_id):
    """Filter a list of entries/expenses by client_id (no-op if None/empty)."""
    if not client_id:
        return items
    return [e for e in items if e.get("client_id") == client_id]


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/invoice")
def invoice():
    """Render an invoice as a standalone HTML page."""
    client_id = request.args.get("client_id")
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not client_id or not year or not month:
        abort(400, "client_id, year, and month are required")

    config = load_config()
    clients = load_json(CLIENTS_FILE, list(DEFAULT_CLIENTS))
    entries = load_json(ENTRIES_FILE, [])
    expenses = load_json(EXPENSES_FILE, [])

    client = get_client_by_id(clients, client_id)
    entries = _filter_by_client(entries, client_id)
    expenses = _filter_by_client(expenses, client_id)

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

    html = generate_invoice_html(month_entries, month_expenses, year, month, config, client)
    return html


# ---------------------------------------------------------------------------
# Entries API
# ---------------------------------------------------------------------------

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


@app.route("/api/entries", methods=["DELETE"])
def clear_entries():
    if request.args.get("confirm") != "true":
        abort(400, "Pass ?confirm=true to clear all entries")
    save_json(ENTRIES_FILE, [])
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


@app.route("/api/expenses", methods=["DELETE"])
def clear_expenses():
    if request.args.get("confirm") != "true":
        abort(400, "Pass ?confirm=true to clear all expenses")
    save_json(EXPENSES_FILE, [])
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
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "name": data["name"],
        "address": data.get("address", ""),
    }
    clients.append(client)
    save_json(CLIENTS_FILE, clients)
    return jsonify(client), 201


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

    total_hours = sum(e["hours"] for e in month_entries)
    total_labour = sum(e["amount"] for e in month_entries)
    total_expenses = sum(e["amount"] for e in month_expenses)

    return jsonify({
        "available_months": [{"year": y, "month": m, "label": datetime(y, m, 1).strftime("%B %Y")} for y, m in available_months],
        "sessions": len(month_entries),
        "total_hours": round(total_hours, 2),
        "total_hours_fmt": format_hours(total_hours),
        "total_labour": round(total_labour, 2),
        "total_expenses": round(total_expenses, 2),
        "total_amount": round(total_labour + total_expenses, 2),
        "entries": sorted(month_entries, key=lambda x: x["date"]),
        "expenses": sorted(month_expenses, key=lambda x: x["date"]),
        "currency": config["currency_symbol"],
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

    # Monthly breakdown
    monthly = {}
    for e in ty_entries:
        d = datetime.fromisoformat(e["date"])
        key = f"{d.year}-{d.month:02d}"
        if key not in monthly:
            monthly[key] = {"year": d.year, "month": d.month, "hours": 0, "labour": 0, "expenses": 0, "sessions": 0}
        monthly[key]["hours"] += e["hours"]
        monthly[key]["labour"] += e["amount"]
        monthly[key]["sessions"] += 1
    for e in ty_expenses:
        d = datetime.fromisoformat(e["date"])
        key = f"{d.year}-{d.month:02d}"
        if key not in monthly:
            monthly[key] = {"year": d.year, "month": d.month, "hours": 0, "labour": 0, "expenses": 0, "sessions": 0}
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
        })

    return jsonify({
        "available_tax_years": [{"year": ty, "label": get_tax_year_label(ty, tsm)} for ty in tax_years],
        "sessions": len(ty_entries),
        "total_hours": round(total_hours, 2),
        "total_hours_fmt": format_hours(total_hours),
        "total_labour": round(total_labour, 2),
        "total_expenses": round(total_expenses_val, 2),
        "total_amount": round(total_labour + total_expenses_val, 2),
        "breakdown": breakdown,
        "currency": config["currency_symbol"],
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
