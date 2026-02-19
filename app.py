import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date, time
from urllib.parse import quote

from helpers import (
    ENTRIES_FILE, CONFIG_FILE, EXPENSES_FILE, CLIENTS_FILE,
    DEFAULT_CLIENTS,
    load_json, save_json, load_config,
    get_client_by_id, get_client_names,
    calculate_hours, get_tax_year, get_tax_year_label,
    format_hours, generate_invoice_number, generate_invoice_html,
)


def client_filter(clients, entries, expenses, key=None):
    """Render a client filter selectbox and return (selected_id, filtered_entries, filtered_expenses)."""
    client_names = get_client_names(clients)
    client_options = {"All Clients": None, **client_names}
    selected_name = st.selectbox("Client", list(client_options.keys()), key=key)
    selected_id = client_options[selected_name]

    if selected_id:
        filtered_entries = [e for e in entries if e.get('client_id') == selected_id]
        filtered_expenses = [e for e in expenses if e.get('client_id') == selected_id]
    else:
        filtered_entries = entries
        filtered_expenses = expenses

    return selected_id, filtered_entries, filtered_expenses


# Page configuration
st.set_page_config(
    page_title="Cleaning Tracker",
    page_icon=":material/mop:",
    layout="centered"
)

# Load data
config = load_config()
entries = load_json(ENTRIES_FILE, [])
expenses = load_json(EXPENSES_FILE, [])
clients = load_json(CLIENTS_FILE, DEFAULT_CLIENTS)

# Sidebar navigation
st.sidebar.title(":material/mop: Tracker")
page = st.sidebar.radio(
    "Menu",
    ["Log Entry", "Log Expense", "Monthly Report", "Tax Year", "View All", "Settings"],
    label_visibility="collapsed"
)

st.sidebar.divider()
st.sidebar.metric("Current Rate", f"{config['currency_symbol']}{config['hourly_rate']:.2f}/hr")

# ============== LOG ENTRY PAGE ==============
if page == "Log Entry":
    st.subheader(":material/edit_note: Log Work")

    # Client selector
    client_names = get_client_names(clients)
    if len(client_names) > 1:
        selected_client_name = st.selectbox("Client", list(client_names.keys()))
        selected_client_id = client_names[selected_client_name]
    else:
        selected_client_id = list(client_names.values())[0] if client_names else "default"

    work_date = st.date_input("Date", value=date.today(), format="DD/MM/YYYY")

    col1, col2 = st.columns(2)
    with col1:
        start_time = st.time_input("Start", value=time(9, 0))
    with col2:
        end_time = st.time_input("End", value=time(12, 0))

    # Calculate
    hours = calculate_hours(start_time, end_time)
    amount = hours * config['hourly_rate']

    # Compact summary line
    st.markdown(f"**{format_hours(hours)}** @ {config['currency_symbol']}{config['hourly_rate']:.2f} = **{config['currency_symbol']}{amount:.2f}**")

    if st.button("Save Entry", type="primary", width="stretch", icon=":material/save:"):
        entry = {
            "id": datetime.now().isoformat(),
            "client_id": selected_client_id,
            "date": work_date.isoformat(),
            "start_time": start_time.strftime("%H:%M"),
            "end_time": end_time.strftime("%H:%M"),
            "hours": round(hours, 2),
            "hourly_rate": config['hourly_rate'],
            "amount": round(amount, 2)
        }
        entries.append(entry)
        save_json(ENTRIES_FILE, entries)
        st.success(f"Saved! {format_hours(hours)} on {work_date.strftime('%d/%m/%Y')}", icon=":material/check_circle:")
        st.balloons()

# ============== LOG EXPENSE PAGE ==============
elif page == "Log Expense":
    st.subheader(":material/receipt_long: Log Expense")

    # Client selector
    client_names = get_client_names(clients)
    if len(client_names) > 1:
        selected_client_name = st.selectbox("Client", list(client_names.keys()), key="exp_client")
        selected_client_id = client_names[selected_client_name]
    else:
        selected_client_id = list(client_names.values())[0] if client_names else "default"

    col1, col2 = st.columns(2)
    with col1:
        expense_date = st.date_input("Date", value=date.today(), format="DD/MM/YYYY", key="expense_date")
    with col2:
        expense_amount = st.number_input(f"Amount ({config['currency_symbol']})", min_value=0.0, value=0.0, step=0.50, format="%.2f")

    expense_description = st.text_input("Description", value="Cleaning supplies")

    if st.button("Save Expense", type="primary", width="stretch", icon=":material/save:"):
        if expense_amount > 0:
            expense = {
                "id": datetime.now().isoformat(),
                "client_id": selected_client_id,
                "date": expense_date.isoformat(),
                "amount": round(expense_amount, 2),
                "description": expense_description
            }
            expenses.append(expense)
            save_json(EXPENSES_FILE, expenses)
            st.success(f"Saved! {config['currency_symbol']}{expense_amount:.2f}", icon=":material/check_circle:")
            st.balloons()
        else:
            st.error("Please enter an amount greater than zero.")

    # Show recent expenses
    if expenses:
        st.divider()
        st.caption("**Recent Expenses**")
        recent_expenses = sorted(expenses, key=lambda x: x['date'], reverse=True)[:5]
        recent_data = []
        for exp in recent_expenses:
            exp_date = datetime.fromisoformat(exp['date'])
            client = get_client_by_id(clients, exp.get('client_id', 'default'))
            recent_data.append({
                "Date": exp_date.strftime('%d/%m'),
                "Client": client['name'][:10],
                "Amount": f"{config['currency_symbol']}{exp['amount']:.2f}"
            })
        st.dataframe(pd.DataFrame(recent_data), hide_index=True, width='stretch')

# ============== MONTHLY REPORT PAGE ==============
elif page == "Monthly Report":
    st.subheader(":material/bar_chart: Monthly Report")

    if not entries and not expenses:
        st.info("No entries logged yet. Start by logging your first work entry!")
    else:
        selected_filter_id, filtered_entries, filtered_expenses = client_filter(clients, entries, expenses)

        # Get available months from filtered entries and expenses
        entry_dates = [datetime.fromisoformat(e['date']) for e in filtered_entries]
        expense_dates = [datetime.fromisoformat(e['date']) for e in filtered_expenses]
        all_dates = entry_dates + expense_dates
        available_months = sorted(set((d.year, d.month) for d in all_dates), reverse=True)

        if available_months:
            month_options = {
                f"{datetime(y, m, 1).strftime('%B %Y')}": (y, m)
                for y, m in available_months
            }

            selected_month_label = st.selectbox("Month", list(month_options.keys()))
            selected_year, selected_month = month_options[selected_month_label]

            # Filter entries for selected month
            month_entries = [
                e for e in filtered_entries
                if datetime.fromisoformat(e['date']).year == selected_year
                and datetime.fromisoformat(e['date']).month == selected_month
            ]

            # Filter expenses for selected month
            month_expenses = [
                e for e in filtered_expenses
                if datetime.fromisoformat(e['date']).year == selected_year
                and datetime.fromisoformat(e['date']).month == selected_month
            ]

            # Calculate totals
            total_hours = sum(e['hours'] for e in month_entries)
            total_labour = sum(e['amount'] for e in month_entries)
            total_expenses = sum(e['amount'] for e in month_expenses)
            total_amount = total_labour + total_expenses

            # Compact metrics in 2x2 grid
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Sessions", len(month_entries))
                st.metric("Expenses", f"{config['currency_symbol']}{total_expenses:.2f}")
            with col2:
                st.metric("Hours", format_hours(total_hours))
                st.metric("Total", f"{config['currency_symbol']}{total_amount:.2f}")

            # Sessions table
            if month_entries:
                st.divider()
                st.caption("**Sessions**")
                sessions_data = []
                for entry in sorted(month_entries, key=lambda x: x['date']):
                    entry_date = datetime.fromisoformat(entry['date'])
                    sessions_data.append({
                        "Date": entry_date.strftime('%d/%m'),
                        "Time": f"{entry['start_time']}-{entry['end_time']}",
                        "Hours": format_hours(entry['hours']),
                        "Amount": f"{config['currency_symbol']}{entry['amount']:.2f}"
                    })
                st.dataframe(pd.DataFrame(sessions_data), hide_index=True, width='stretch')

            # Expenses table
            if month_expenses:
                st.caption("**Expenses**")
                expenses_data = []
                for exp in sorted(month_expenses, key=lambda x: x['date']):
                    exp_date = datetime.fromisoformat(exp['date'])
                    expenses_data.append({
                        "Date": exp_date.strftime('%d/%m'),
                        "Description": exp.get('description', 'Supplies'),
                        "Amount": f"{config['currency_symbol']}{exp['amount']:.2f}"
                    })
                st.dataframe(pd.DataFrame(expenses_data), hide_index=True, width='stretch')

            # Invoice section - only show if a specific client is selected
            st.divider()
            st.subheader(":material/print: Invoice")

            if selected_filter_id:
                client = get_client_by_id(clients, selected_filter_id)
                invoice_num = generate_invoice_number(selected_year, selected_month, config)
                st.caption(f"**{invoice_num}** | {config['business_name']} → {client['name']} | {config['payment_terms']} days")

                # Generate the invoice HTML
                invoice_html = generate_invoice_html(
                    month_entries,
                    month_expenses,
                    selected_year,
                    selected_month,
                    config,
                    client
                )

                # Encode HTML for data URI - use URL encoding for proper UTF-8 support
                invoice_encoded = quote(invoice_html, safe='')

                # Create a button that opens invoice in new tab using data URI
                open_invoice_js = f"""
                    <script>
                        function openInvoice() {{
                            var html = decodeURIComponent('{invoice_encoded}');
                            var win = window.open('', '_blank');
                            win.document.write(html);
                            win.document.close();
                        }}
                    </script>
                    <button onclick="openInvoice()" style="
                        background-color: #FF4B4B;
                        color: white;
                        padding: 0.75rem 1.5rem;
                        font-size: 16px;
                        font-weight: 600;
                        border: none;
                        border-radius: 8px;
                        cursor: pointer;
                        width: 100%;
                        margin-top: 10px;
                    ">
                        Print Invoice
                    </button>
                """

                components.html(open_invoice_js, height=70)

                st.caption("Opens in new tab for printing")
            else:
                st.info("Select a specific client to generate an invoice.")
        else:
            st.info("No entries found for the selected client.")

# ============== TAX YEAR PAGE ==============
elif page == "Tax Year":
    st.subheader(":material/calendar_month: Tax Year")

    if not entries and not expenses:
        st.info("No entries logged yet. Start by logging your first work entry!")
    else:
        selected_filter_id, filtered_entries, filtered_expenses = client_filter(clients, entries, expenses, key="ty_client")

        # Get available tax years from filtered entries and expenses
        all_dates = []
        for e in filtered_entries:
            all_dates.append(datetime.fromisoformat(e['date']).date())
        for e in filtered_expenses:
            all_dates.append(datetime.fromisoformat(e['date']).date())

        tax_years = sorted(set(
            get_tax_year(d, config['tax_year_start_month'])
            for d in all_dates
        ), reverse=True)

        if tax_years:
            tax_year_options = {
                get_tax_year_label(ty, config['tax_year_start_month']): ty
                for ty in tax_years
            }

            selected_ty_label = st.selectbox("Tax Year", list(tax_year_options.keys()))
            selected_tax_year = tax_year_options[selected_ty_label]

            # Filter entries for selected tax year
            ty_entries = [
                e for e in filtered_entries
                if get_tax_year(datetime.fromisoformat(e['date']).date(), config['tax_year_start_month']) == selected_tax_year
            ]

            # Filter expenses for selected tax year
            ty_expenses = [
                e for e in filtered_expenses
                if get_tax_year(datetime.fromisoformat(e['date']).date(), config['tax_year_start_month']) == selected_tax_year
            ]

            # Calculate totals
            total_hours = sum(e['hours'] for e in ty_entries)
            total_labour = sum(e['amount'] for e in ty_entries)
            total_expenses = sum(e['amount'] for e in ty_expenses)
            total_income = total_labour + total_expenses

            # Compact 2x2 metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Sessions", len(ty_entries))
                st.metric("Expenses", f"{config['currency_symbol']}{total_expenses:.2f}")
            with col2:
                st.metric("Hours", format_hours(total_hours))
                st.metric("Total", f"{config['currency_symbol']}{total_income:.2f}")

            # Monthly breakdown table
            st.divider()
            st.caption("**Monthly Breakdown**")

            # Group by month
            monthly_data = {}
            for entry in ty_entries:
                entry_date = datetime.fromisoformat(entry['date'])
                month_key = (entry_date.year, entry_date.month)
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'hours': 0, 'labour': 0, 'expenses': 0, 'sessions': 0}
                monthly_data[month_key]['hours'] += entry['hours']
                monthly_data[month_key]['labour'] += entry['amount']
                monthly_data[month_key]['sessions'] += 1

            for expense in ty_expenses:
                expense_date = datetime.fromisoformat(expense['date'])
                month_key = (expense_date.year, expense_date.month)
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'hours': 0, 'labour': 0, 'expenses': 0, 'sessions': 0}
                monthly_data[month_key]['expenses'] += expense['amount']

            # Build table data
            breakdown_data = []
            for (year, month), data in sorted(monthly_data.items()):
                month_name = datetime(year, month, 1).strftime('%b %Y')
                month_total = data['labour'] + data['expenses']
                breakdown_data.append({
                    "Month": month_name,
                    "Sessions": data['sessions'],
                    "Hours": format_hours(data['hours']),
                    "Expenses": f"{config['currency_symbol']}{data['expenses']:.2f}" if data['expenses'] > 0 else "-",
                    "Total": f"{config['currency_symbol']}{month_total:.2f}"
                })
            st.dataframe(pd.DataFrame(breakdown_data), hide_index=True, width='stretch')

# ============== VIEW ALL PAGE ==============
elif page == "View All":
    st.subheader(":material/list_alt: All Entries")

    tab1, tab2 = st.tabs([":material/mop: Work", ":material/receipt_long: Expenses"])

    with tab1:
        if not entries:
            st.info("No work entries logged yet.")
        else:
            sorted_entries = sorted(entries, key=lambda x: x['date'], reverse=True)

            # Display as table
            work_data = []
            for entry in sorted_entries:
                entry_date = datetime.fromisoformat(entry['date'])
                client = get_client_by_id(clients, entry.get('client_id', 'default'))
                work_data.append({
                    "Date": entry_date.strftime('%d/%m'),
                    "Client": client['name'][:12],
                    "Time": f"{entry['start_time']}-{entry['end_time']}",
                    "Amount": f"{config['currency_symbol']}{entry['amount']:.2f}"
                })
            st.dataframe(pd.DataFrame(work_data), hide_index=True, width='stretch')

            # Delete section
            st.caption("**Delete Entry**")
            delete_options = {
                f"{datetime.fromisoformat(e['date']).strftime('%d/%m')} {e['start_time']}-{e['end_time']} [{e['id'][:10]}]": e
                for e in sorted_entries
            }
            selected_entry = st.selectbox("Select entry to delete", list(delete_options.keys()), key="del_work")
            if st.button("Delete Selected", key="del_work_btn", icon=":material/delete:"):
                entries.remove(delete_options[selected_entry])
                save_json(ENTRIES_FILE, entries)
                st.rerun()

    with tab2:
        if not expenses:
            st.info("No expenses logged yet.")
        else:
            sorted_expenses = sorted(expenses, key=lambda x: x['date'], reverse=True)

            # Display as table
            exp_data = []
            for exp in sorted_expenses:
                exp_date = datetime.fromisoformat(exp['date'])
                client = get_client_by_id(clients, exp.get('client_id', 'default'))
                exp_data.append({
                    "Date": exp_date.strftime('%d/%m'),
                    "Client": client['name'][:12],
                    "Description": exp.get('description', 'Supplies')[:15],
                    "Amount": f"{config['currency_symbol']}{exp['amount']:.2f}"
                })
            st.dataframe(pd.DataFrame(exp_data), hide_index=True, width='stretch')

            # Delete section
            st.caption("**Delete Expense**")
            delete_exp_options = {
                f"{datetime.fromisoformat(e['date']).strftime('%d/%m')} {e.get('description', 'Supplies')} {config['currency_symbol']}{e['amount']:.2f} [{e['id'][:10]}]": e
                for e in sorted_expenses
            }
            selected_exp = st.selectbox("Select expense to delete", list(delete_exp_options.keys()), key="del_exp")
            if st.button("Delete Selected", key="del_exp_btn", icon=":material/delete:"):
                expenses.remove(delete_exp_options[selected_exp])
                save_json(EXPENSES_FILE, expenses)
                st.rerun()

# ============== SETTINGS PAGE ==============
elif page == "Settings":
    st.subheader(":material/settings: Settings")

    tab1, tab2, tab3, tab4 = st.tabs([":material/payments: Rates", ":material/person: You", ":material/group: Clients", ":material/credit_card: Payment"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            new_rate = st.number_input(
                "Hourly Rate",
                min_value=0.0,
                value=float(config['hourly_rate']),
                step=0.50,
                format="%.2f"
            )
        with col2:
            currency_options = ["\u00a3", "$", "\u20ac"]
            current_currency_index = currency_options.index(config['currency_symbol']) if config['currency_symbol'] in currency_options else 0
            new_currency = st.selectbox("Currency", currency_options, index=current_currency_index)

        col1, col2 = st.columns(2)
        with col1:
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            new_tax_month = st.selectbox(
                "Tax Year Starts",
                range(1, 13),
                index=config['tax_year_start_month'] - 1,
                format_func=lambda x: month_names[x - 1]
            )
        with col2:
            new_invoice_prefix = st.text_input(
                "Invoice Prefix",
                value=config.get('invoice_prefix', 'INV')
            )

    with tab2:
        new_business_name = st.text_input("Your Name", value=config.get('business_name', ''))
        new_business_address = st.text_area("Address", value=config.get('business_address', ''), height=80)
        col1, col2 = st.columns(2)
        with col1:
            new_business_email = st.text_input("Email", value=config.get('business_email', ''))
        with col2:
            new_business_phone = st.text_input("Phone", value=config.get('business_phone', ''))

    with tab3:
        st.caption("**Manage Clients**")

        # Show existing clients
        if clients:
            client_data = []
            for c in clients:
                addr_short = c['address'].replace('\n', ', ')
                client_data.append({
                    "Name": c['name'],
                    "Address": addr_short[:30] + "..." if len(addr_short) > 30 else addr_short
                })
            st.dataframe(pd.DataFrame(client_data), hide_index=True, width='stretch')

            # Delete client
            if len(clients) > 1:
                del_client_names = {c['name']: c['id'] for c in clients}
                del_selected = st.selectbox("Select client to delete", list(del_client_names.keys()), key="del_client")
                if st.button("Delete Client", icon=":material/delete:"):
                    updated_clients = [c for c in clients if c['id'] != del_client_names[del_selected]]
                    save_json(CLIENTS_FILE, updated_clients)
                    st.rerun()

        st.divider()
        st.caption("**Add New Client**")
        new_client_name = st.text_input("Client Name", key="new_client_name")
        new_client_address = st.text_area("Client Address", height=80, key="new_client_addr")

        if st.button("Add Client", icon=":material/add:"):
            if new_client_name:
                new_client = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "name": new_client_name,
                    "address": new_client_address
                }
                clients.append(new_client)
                save_json(CLIENTS_FILE, clients)
                st.success(f"Added {new_client_name}", icon=":material/check_circle:")
                st.rerun()
            else:
                st.error("Please enter a client name")

    with tab4:
        st.caption("**Payment Details**")
        col1, col2 = st.columns(2)
        with col1:
            new_bank_name = st.text_input("Bank", value=config.get('bank_name', ''))
            new_sort_code = st.text_input("Sort Code", value=config.get('sort_code', ''))
        with col2:
            new_account_name = st.text_input("Account Name", value=config.get('account_name', ''))
            new_account_number = st.text_input("Account No", value=config.get('account_number', ''))

        new_payment_terms = st.number_input("Payment Terms (days)", min_value=0, max_value=90, value=config.get('payment_terms', 14))

    if st.button("Save Settings", type="primary", width="stretch", icon=":material/save:"):
        config['hourly_rate'] = new_rate
        config['currency_symbol'] = new_currency
        config['tax_year_start_month'] = new_tax_month
        config['invoice_prefix'] = new_invoice_prefix
        config['business_name'] = new_business_name
        config['business_address'] = new_business_address
        config['business_email'] = new_business_email
        config['business_phone'] = new_business_phone
        config['bank_name'] = new_bank_name
        config['account_name'] = new_account_name
        config['sort_code'] = new_sort_code
        config['account_number'] = new_account_number
        config['payment_terms'] = new_payment_terms
        save_json(CONFIG_FILE, config)
        st.success("Saved!", icon=":material/check_circle:")
        st.rerun()

    st.divider()
    st.caption("**Data Management**")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear Entries", icon=":material/delete:"):
            st.session_state.confirm_delete = "entries"
    with col2:
        if st.button("Clear Expenses", icon=":material/delete:"):
            st.session_state.confirm_delete = "expenses"

    if st.session_state.get('confirm_delete') == "entries":
        st.error("Delete all work entries?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes", type="primary", key="yes_entries"):
                save_json(ENTRIES_FILE, [])
                st.session_state.confirm_delete = None
                st.rerun()
        with col2:
            if st.button("No", key="no_entries"):
                st.session_state.confirm_delete = None
                st.rerun()

    if st.session_state.get('confirm_delete') == "expenses":
        st.error("Delete all expenses?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes", type="primary", key="yes_expenses"):
                save_json(EXPENSES_FILE, [])
                st.session_state.confirm_delete = None
                st.rerun()
        with col2:
            if st.button("No", key="no_expenses"):
                st.session_state.confirm_delete = None
                st.rerun()

# Footer
st.sidebar.divider()
st.sidebar.caption(f"Clients: {len(clients)} | Entries: {len(entries)} | Expenses: {len(expenses)}")
