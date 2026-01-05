# Cleaning Job Time Tracker

A simple Streamlit application to track hours worked for cleaning jobs, generate monthly reports, and manage tax year summaries.

## Features

- **Multiple Clients**: Add and manage multiple clients, select client when logging entries
- **Log Entries**: Record date, start time, and end time for each cleaning session
- **Log Expenses**: Track expenses for cleaning products (receipts attached to printed invoice)
- **Monthly Reports**: View hours, expenses and amounts by month, filtered by client
- **Printable Invoices**: Generate professional A4 invoices per client that open in a new tab for printing
- **Tax Year Summary**: Track earnings and expenses across the full tax year with monthly breakdown
- **View All Entries**: Browse and delete individual entries and expenses
- **Settings**: Configure hourly rate, currency, tax year start month, and invoice details

## Installation

1. Make sure you have Python 3.8+ installed

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   streamlit run app.py
   ```

4. Open your browser to `http://localhost:8501`

## Data Storage

The app stores data in JSON files in a `data` folder:
- `entries.json` - All your logged work entries
- `expenses.json` - All your logged expenses
- `clients.json` - Your client list
- `config.json` - Your settings (hourly rate, currency, invoice details, etc.)

These files are created automatically when you first save data.

## Backup

To backup your data, simply copy the `data` folder. To restore, replace the `data` folder with your backup.

## Configuration

Default settings (can be changed in the Settings page):
- Hourly rate: £15.00
- Currency: £ (GBP)
- Tax year starts: April (UK tax year)
- Payment terms: 14 days
