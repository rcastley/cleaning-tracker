function app() {
  const today = new Date().toISOString().slice(0, 10);

  const ICONS = {
    delete: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M9 3v1H4v2h1v13a2 2 0 002 2h10a2 2 0 002-2V6h1V4h-5V3H9zm-2 3h10v13H7V6zm2 2v9h2V8H9zm4 0v9h2V8h-2z"/></svg>',
    expand_more: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/></svg>',
    edit_note: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M3 10h11v2H3v-2zm0-2h11V6H3v2zm0 8h7v-2H3v2zm15.01-3.13l.71-.71a.996.996 0 011.41 0l.71.71c.39.39.39 1.02 0 1.41l-.71.71-2.12-2.12zm-.71.71l-5.3 5.3V21h2.12l5.3-5.3-2.12-2.12z"/></svg>',
    bar_chart: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M5 9.2h3V19H5V9.2zM10.6 5h2.8v14h-2.8V5zm5.6 8H19v6h-2.8v-6z"/></svg>',
    list_alt: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M19 5v14H5V5h14m0-2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-2 4h-7v2h7V7zm0 4h-7v2h7v-2zm0 4h-7v2h7v-2zM7 7h2v2H7V7zm0 4h2v2H7v-2zm0 4h2v2H7v-2z"/></svg>',
    settings: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84a.484.484 0 00-.48.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 00-.59.22L2.74 8.87a.49.49 0 00.12.61l2.03 1.58c-.05.3-.07.62-.07.94 0 .32.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.39.31.61.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.25.41.48.41h3.84c.24 0 .44-.17.48-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.09.49 0 .61-.22l1.92-3.32c.12-.22.07-.49-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1112 8.4a3.6 3.6 0 010 7.2z"/></svg>',
  };

  return {
    icons: ICONS,

    tabs: [
      { id: 'log', label: 'Log', icon: 'edit_note' },
      { id: 'reports', label: 'Reports', icon: 'bar_chart' },
      { id: 'history', label: 'History', icon: 'list_alt' },
      { id: 'settings', label: 'Settings', icon: 'settings' },
    ],
    tab: 'log',

    config: {},
    clients: [],
    entries: [],
    expenses: [],
    saving: false,

    logMode: 'work',
    logClientId: '',
    workDate: today,
    workStart: '09:00',
    workEnd: '12:00',
    workMiles: 0,
    expDate: today,
    expAmount: 0,
    expDesc: 'Cleaning supplies',

    reportMode: 'monthly',
    reportClientId: '',
    selectedMonth: '',
    selectedTaxYear: '',
    rangeStart: today.slice(0, 8) + '01',
    rangeEnd: today,
    rangeData: null,
    rangeLoadedKey: '',
    rangeRequest: 0,
    rangeLoading: false,
    rangeError: '',
    get rangeKey() { return JSON.stringify([this.reportClientId, this.rangeStart, this.rangeEnd]); },
    get rangeReady() { return !!this.rangeData && this.rangeLoadedKey === this.rangeKey && !this.rangeLoading && !this.rangeError; },
    get periodData() { return this.reportMode === 'range' && this.rangeData ? this.rangeData : this.monthlyData; },
    monthlyData: { available_months: [], sessions: 0, total_hours: 0, total_hours_fmt: '0h 0m', total_labour: 0, total_expenses: 0, total_amount: 0, total_miles: 0, entries: [], expenses: [], currency: '£' },
    taxYearData: { available_tax_years: [], sessions: 0, total_hours: 0, total_hours_fmt: '0h 0m', total_labour: 0, total_expenses: 0, total_amount: 0, total_miles: 0, mileage_allowance: 0, breakdown: [], currency: '£' },

    historyMode: 'work',
    editor: { open: false, kind: 'work', draft: {}, original: '', errors: {}, error: '', saving: false },

    openEditor(kind, record, trigger) {
      this.editTrigger = trigger;
      this.editor = { open: true, kind, draft: { ...record }, original: JSON.stringify(record), errors: {}, error: '', saving: false };
      this.$nextTick(() => this.$refs.editClient.focus());
    },

    closeEditor() {
      if (this.editor.saving) return;
      if (JSON.stringify(this.editor.draft) !== this.editor.original && !window.confirm('Discard your unsaved changes?')) return;
      this.finishEditing();
    },

    finishEditing() {
      this.editor.open = false;
      this.$nextTick(() => this.editTrigger?.focus({ preventScroll: true }));
    },

    editorKeydown(event) {
      if (event.key === 'Escape') { event.preventDefault(); this.closeEditor(); }
      if (event.key !== 'Tab') return;
      const items = [...this.$refs.editDialog.querySelectorAll('button, input, select, textarea')]
        .filter(el => !el.disabled && el.getClientRects().length);
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    },

    async saveEdit() {
      if (this.editor.saving) return;
      this.editor.saving = true;
      this.editor.errors = {};
      this.editor.error = '';
      const work = this.editor.kind === 'work';
      try {
        const updated = await this.api('/api/' + (work ? 'entries' : 'expenses') + '/' + encodeURIComponent(this.editor.draft.id), 'PUT', this.editor.draft);
        const records = work ? this.entries : this.expenses;
        const index = records.findIndex(r => r.id === updated.id);
        if (index >= 0) records.splice(index, 1, updated);
        this.finishEditing();
        this.showToast(work ? 'Entry updated' : 'Expense updated', 'success');
        // Reports fetch current data whenever opened; invoices are rendered from saved records.
      } catch (error) {
        this.editor.errors = error.fields || {};
        this.editor.error = error.message || 'Unable to save. Please try again.';
        this.$nextTick(() => this.$refs.editDialog.querySelector('[aria-invalid="true"]')?.focus());
      } finally {
        this.editor.saving = false;
      }
    },

    newClientName: '',
    newClientAddress: '',
    newClientMiles: 0,
    confirmAction: null,
    deleteConfirm: { show: false, type: '', action: () => {} },

    toast: { show: false, msg: '', type: 'success' },

    monthNames: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],

    get previewHours() {
      const h = this.calcHours(this.workStart, this.workEnd);
      const hr = Math.floor(h);
      const mn = Math.round((h - hr) * 60);
      return hr + 'h ' + mn + 'm';
    },
    get previewAmount() {
      return (this.calcHours(this.workStart, this.workEnd) * (this.config.hourly_rate || 0)).toFixed(2);
    },
    get sortedEntries() {
      return [...this.entries].sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
    },
    get sortedExpenses() {
      return [...this.expenses].sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
    },

    async init() {
      const data = await this.api('/api/bootstrap');
      this.config = data.config;
      this.clients = data.clients;
      this.entries = data.entries;
      this.expenses = data.expenses;
      if (this.clients.length) {
        this.logClientId = this.clients[0].id;
        this.workMiles = this.clients[0].default_miles || 0;
        if (this.clients.length === 1) this.reportClientId = this.clients[0].id;
      }
    },

    async loadConfig() { this.config = await this.api('/api/config'); },
    async loadClients() { this.clients = await this.api('/api/clients'); },
    async loadEntries() { this.entries = await this.api('/api/entries'); },
    async loadExpenses() { this.expenses = await this.api('/api/expenses'); },

    onTabSwitch(id) {
      if (id === 'reports') {
        this.loadReport();
      } else if (id === 'history') {
        this.loadEntries();
        this.loadExpenses();
      }
    },

    async saveWork() {
      this.saving = true;
      try {
        const clientId = this.clients.length === 1 ? this.clients[0].id : this.logClientId;
        await this.api('/api/entries', 'POST', {
          client_id: clientId,
          date: this.workDate,
          start_time: this.workStart,
          end_time: this.workEnd,
          miles: this.workMiles,
        });
        this.showToast('Entry saved!', 'success');
        this.workDate = today;
        this.updateMilesFromClient();
        this.loadEntries();
      } catch (e) {
        this.showToast('Failed to save', 'error');
      }
      this.saving = false;
    },

    async saveExpense() {
      this.saving = true;
      try {
        const clientId = this.clients.length === 1 ? this.clients[0].id : this.logClientId;
        await this.api('/api/expenses', 'POST', {
          client_id: clientId,
          date: this.expDate,
          amount: this.expAmount,
          description: this.expDesc,
        });
        this.showToast('Expense saved!', 'success');
        this.expAmount = 0;
        this.expDesc = 'Cleaning supplies';
        this.loadExpenses();
      } catch (e) {
        this.showToast('Failed to save', 'error');
      }
      this.saving = false;
    },

    loadReport() {
      if (this.reportMode === 'range') return this.loadRange();
      if (this.reportMode === 'monthly') return this.loadMonthly();
      return this.loadTaxYear();
    },

    async loadRange() {
      const request = ++this.rangeRequest;
      const key = this.rangeKey;
      this.rangeError = '';
      this.rangeLoadedKey = '';
      this.rangeLoading = false;
      if (!this.rangeStart || !this.rangeEnd) {
        this.rangeError = 'Select a start and end date.';
        return;
      }
      if (this.rangeStart > this.rangeEnd) {
        this.rangeError = 'End date must be on or after start date.';
        return;
      }
      this.rangeLoading = true;
      const params = new URLSearchParams({ start_date: this.rangeStart, end_date: this.rangeEnd });
      if (this.reportClientId) params.set('client_id', this.reportClientId);
      try {
        const data = await this.api('/api/reports/range?' + params);
        if (request !== this.rangeRequest || key !== this.rangeKey) return;
        this.rangeData = data;
        this.rangeLoadedKey = key;
      } catch (error) {
        if (request === this.rangeRequest && key === this.rangeKey) {
          this.rangeError = error.message || 'Unable to load report. Please try again.';
        }
      } finally {
        if (request === this.rangeRequest) this.rangeLoading = false;
      }
    },

    async loadMonthly() {
      let url = '/api/reports/monthly?';
      if (this.reportClientId) url += 'client_id=' + this.reportClientId + '&';
      if (this.selectedMonth) {
        const [y, m] = this.selectedMonth.split('-');
        url += 'year=' + y + '&month=' + m;
      }
      const data = await this.api(url);
      const prevMonth = this.selectedMonth;
      this.monthlyData = data;
      if (!prevMonth && data.available_months.length) {
        this.selectedMonth = data.available_months[0].year + '-' + data.available_months[0].month;
        await this.loadMonthly();
        return;
      }
      const valid = data.available_months.some(m => m.year + '-' + m.month === prevMonth);
      if (!valid && data.available_months.length) {
        this.selectedMonth = data.available_months[0].year + '-' + data.available_months[0].month;
        await this.loadMonthly();
      }
    },

    async loadTaxYear() {
      let url = '/api/reports/taxyear?';
      if (this.reportClientId) url += 'client_id=' + this.reportClientId + '&';
      if (this.selectedTaxYear) url += 'tax_year=' + this.selectedTaxYear;
      const data = await this.api(url);
      const prev = this.selectedTaxYear;
      this.taxYearData = data;
      if (!prev && data.available_tax_years.length) {
        this.selectedTaxYear = String(data.available_tax_years[0].year);
        await this.loadTaxYear();
        return;
      }
      const valid = data.available_tax_years.some(ty => String(ty.year) === String(prev));
      if (!valid && data.available_tax_years.length) {
        this.selectedTaxYear = String(data.available_tax_years[0].year);
        await this.loadTaxYear();
      }
    },

    openInvoice() {
      if (!this.reportClientId) return;
      const params = new URLSearchParams({ client_id: this.reportClientId });
      if (this.reportMode === 'range') {
        if (!this.rangeReady) return;
        params.set('start_date', this.rangeStart);
        params.set('end_date', this.rangeEnd);
      } else {
        if (!this.selectedMonth) return;
        const [y, m] = this.selectedMonth.split('-');
        params.set('year', y);
        params.set('month', m);
      }
      window.open('/invoice?' + params, '_blank');
    },

    deleteEntry(id) {
      this.deleteConfirm = {
        show: true, type: 'entry',
        action: async () => {
          await this.api('/api/entries/' + encodeURIComponent(id), 'DELETE');
          this.showToast('Entry deleted', 'success');
          this.loadEntries();
        }
      };
    },
    deleteExpense(id) {
      this.deleteConfirm = {
        show: true, type: 'expense',
        action: async () => {
          await this.api('/api/expenses/' + encodeURIComponent(id), 'DELETE');
          this.showToast('Expense deleted', 'success');
          this.loadExpenses();
        }
      };
    },

    async saveConfig() {
      this.saving = true;
      try {
        this.config = await this.api('/api/config', 'PUT', this.config);
        this.showToast('Settings saved!', 'success');
      } catch (e) {
        this.showToast('Failed to save', 'error');
      }
      this.saving = false;
    },

    async addClient() {
      if (!this.newClientName.trim()) return;
      await this.api('/api/clients', 'POST', { name: this.newClientName, address: this.newClientAddress, default_miles: this.newClientMiles });
      this.newClientName = '';
      this.newClientAddress = '';
      this.newClientMiles = 0;
      this.showToast('Client added!', 'success');
      this.loadClients();
    },

    deleteClient(id) {
      this.deleteConfirm = {
        show: true, type: 'client',
        action: async () => {
          await this.api('/api/clients/' + encodeURIComponent(id), 'DELETE');
          this.showToast('Client deleted', 'success');
          this.loadClients();
        }
      };
    },

    async clearData(type) {
      await this.api('/api/' + type + '?confirm=true', 'DELETE');
      this.showToast('All ' + type + ' cleared', 'success');
      if (type === 'entries') this.loadEntries();
      else this.loadExpenses();
    },

    updateMilesFromClient() {
      const client = this.clients.find(c => c.id === this.logClientId);
      this.workMiles = client ? (client.default_miles || 0) : 0;
    },

    async updateClientMiles(clientId, miles) {
      await this.api('/api/clients/' + encodeURIComponent(clientId), 'PUT', { default_miles: parseFloat(miles) || 0 });
      this.showToast('Miles updated', 'success');
      this.loadClients();
    },

    calcHours(start, end) {
      if (!start || !end) return 0;
      const [sh, sm] = start.split(':').map(Number);
      const [eh, em] = end.split(':').map(Number);
      let diff = (eh * 60 + em) - (sh * 60 + sm);
      if (diff < 0) diff += 24 * 60;
      return diff / 60;
    },

    fmtDate(iso) {
      if (!iso) return '';
      const [y, m, d] = iso.split('-');
      return d + '/' + m;
    },

    fmtHours(h) {
      const hr = Math.floor(h);
      const mn = Math.round((h - hr) * 60);
      return hr + 'h ' + mn + 'm';
    },

    clientName(id) {
      const c = this.clients.find(c => c.id === id);
      return c ? c.name : 'Unknown';
    },

    showToast(msg, type) {
      this.toast = { show: true, msg, type };
      setTimeout(() => this.toast.show = false, 2500);
    },

    async api(url, method = 'GET', body = null) {
      const opts = { method, headers: {} };
      if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
      }
      const res = await fetch(url, opts);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const error = new Error(data.error || 'Unable to complete the request. Please try again.');
        error.fields = data.errors || {};
        throw error;
      }
      return res.json();
    },
  };
}
