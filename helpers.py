"""Shared business logic for Cleaning Tracker — zero Streamlit dependencies."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
ENTRIES_FILE = DATA_DIR / "entries.json"
CONFIG_FILE = DATA_DIR / "config.json"
EXPENSES_FILE = DATA_DIR / "expenses.json"
CLIENTS_FILE = DATA_DIR / "clients.json"
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Jinja2 setup
# ---------------------------------------------------------------------------
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
jinja_env.filters["nl2br"] = lambda val: escape(val).replace("\n", Markup("<br>"))

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "hourly_rate": 15.00,
    "tax_year_start_month": 4,
    "currency_symbol": "\u00a3",
    "business_name": "Your Name",
    "business_address": "Your Address\nCity, Postcode",
    "business_email": "your.email@example.com",
    "business_phone": "07xxx xxxxxx",
    "payment_terms": 14,
    "bank_name": "Your Bank",
    "account_name": "Your Name",
    "sort_code": "00-00-00",
    "account_number": "00000000",
    "invoice_prefix": "INV",
}

DEFAULT_CLIENTS = [
    {"id": "client_1", "name": "Client 1", "address": "Address\nCity, Postcode", "default_miles": 0}
]

# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------

def load_json(path, default):
    """Load data from a JSON file, returning *default* if it doesn't exist."""
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return default() if callable(default) else default


def save_json(path, data):
    """Save data to a JSON file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_config():
    """Load configuration, merging with defaults for forward-compatibility."""
    return {**DEFAULT_CONFIG, **load_json(CONFIG_FILE, {})}


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

def get_client_by_id(clients, client_id):
    """Get a client by ID."""
    for client in clients:
        if client["id"] == client_id:
            return client
    return clients[0] if clients else {"id": "default", "name": "Unknown", "address": ""}


def get_client_names(clients):
    """Get dict of client names to IDs for dropdown."""
    return {client["name"]: client["id"] for client in clients}


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def calculate_hours(start_time, end_time):
    """Calculate hours between two times, handling overnight shifts.

    Accepts both ``datetime.time`` objects and ``"HH:MM"`` strings.
    """
    def _to_minutes(t):
        if isinstance(t, str):
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        return t.hour * 60 + t.minute

    start_minutes = _to_minutes(start_time)
    end_minutes = _to_minutes(end_time)

    if end_minutes < start_minutes:
        diff_minutes = (24 * 60 - start_minutes) + end_minutes
    else:
        diff_minutes = end_minutes - start_minutes

    return diff_minutes / 60


def get_tax_year(work_date, tax_year_start_month):
    """Get the tax year for a given date (returns the year the tax year started)."""
    if work_date.month >= tax_year_start_month:
        return work_date.year
    return work_date.year - 1


def get_tax_year_label(tax_year, tax_year_start_month):
    """Get a human-readable tax year label."""
    start_month_name = datetime(2000, tax_year_start_month, 1).strftime("%B")
    end_month = tax_year_start_month - 1 or 12
    end_month_name = datetime(2000, end_month, 1).strftime("%B")
    return f"{tax_year}/{tax_year + 1} ({start_month_name} {tax_year} - {end_month_name} {tax_year + 1})"


def format_hours(hours):
    """Format hours as hours and minutes."""
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m}m"


def generate_invoice_number(year, month, config):
    """Generate an invoice number based on year and month."""
    return f"{config['invoice_prefix']}-{year}{month:02d}"


def calculate_hmrc_mileage_allowance(total_miles):
    """Calculate HMRC approved mileage allowance for a tax year.

    45p/mile for first 10,000 miles, 25p/mile thereafter.
    Returns allowance in pounds.
    """
    if total_miles <= 10000:
        return round(total_miles * 0.45, 2)
    return round(10000 * 0.45 + (total_miles - 10000) * 0.25, 2)


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

def generate_invoice_html(month_entries, month_expenses, selected_year, selected_month, config, client):
    """Generate a printable HTML invoice optimized for single A4 page."""
    total_hours = sum(e["hours"] for e in month_entries)
    total_labour = sum(e["amount"] for e in month_entries)
    total_expenses = sum(e["amount"] for e in month_expenses)
    currency = config["currency_symbol"]

    entries_data = []
    for e in sorted(month_entries, key=lambda x: x["date"]):
        entries_data.append(
            {
                "date": datetime.fromisoformat(e["date"]).strftime("%d/%m/%Y"),
                "start_time": e["start_time"],
                "end_time": e["end_time"],
                "hours": e["hours"],
                "hourly_rate": e["hourly_rate"],
                "amount": e["amount"],
            }
        )

    expenses_data = []
    for e in sorted(month_expenses, key=lambda x: x["date"]):
        expenses_data.append(
            {
                "date": datetime.fromisoformat(e["date"]).strftime("%d/%m/%Y"),
                "description": e.get("description", "Cleaning supplies"),
                "amount": e["amount"],
            }
        )

    class Config:
        def __init__(self, d):
            self.__dict__.update(d)

    template = jinja_env.get_template("invoice.html")
    return template.render(
        config=Config(config),
        client=Config(client),
        invoice_number=generate_invoice_number(selected_year, selected_month, config),
        invoice_date=datetime.now().strftime("%d/%m/%Y"),
        due_date=(datetime.now() + timedelta(days=config["payment_terms"])).strftime("%d/%m/%Y"),
        month_name=datetime(selected_year, selected_month, 1).strftime("%B %Y"),
        currency=currency,
        entries=entries_data,
        expenses=expenses_data,
        total_hours=total_hours,
        total_labour=total_labour,
        total_expenses=total_expenses,
        total_amount=total_labour + total_expenses,
    )
