function app() {
  const localDate = date => [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-');
  const today = localDate(new Date());

  const ICONS = {
    chevron_left: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg>',
    chevron_right: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg>',
    edit: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a.996.996 0 000-1.41l-2.34-2.34a.996.996 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>',
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
      { id: 'log', label: 'Add entry', icon: 'edit_note' },
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
    bootLoading: true,
    bootError: '',
    logError: '',
    lastSaved: null,
    historyLoading: false,
    historyError: '',
    historySearch: '',
    historyClientId: '',
    historyMonth: today.slice(0, 7),
    historyPage: 1,
    historyPageSize: 10,
    reportLoading: false,
    reportError: '',
    reportRequest: 0,
    deleteBusy: false,
    deleteError: '',

    get pageTitle() { return { log: 'Add an entry', reports: 'Reports & invoices', history: 'Your history', settings: 'Settings' }[this.tab]; },
    get pageDescription() { return { log: 'Keep your hours and expenses up to date.', reports: 'Choose a period. Check your totals. Create an invoice.', history: 'Find, review and update your saved records.', settings: 'Manage your business, clients and payment details.' }[this.tab]; },
    get historySearching() { return !!this.historySearch.trim(); },
    get historyClientRecords() {
      const records = this.historyMode === 'work' ? this.sortedEntries : this.sortedExpenses;
      return records.filter(e => !this.historyClientId || e.client_id === this.historyClientId);
    },
    get latestHistoryMonth() { return this.historyClientRecords[0]?.date.slice(0, 7) || ''; },
    get historyMonthLabel() {
      return new Date(this.historyMonth + '-01T12:00:00').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
    },
    get filteredHistory() {
      const query = this.historySearch.trim().toLowerCase();
      return this.historyClientRecords.filter(e => query
        ? [this.clientName(e.client_id), e.date, this.fullDate(e.date), e.description || '', String(e.amount)]
          .join(' ').toLowerCase().includes(query)
        : e.date.slice(0, 7) === this.historyMonth);
    },
    get historyTotal() { return this.filteredHistory.reduce((total, e) => total + e.amount, 0); },
    get historyPageCount() { return Math.max(1, Math.ceil(this.filteredHistory.length / this.historyPageSize)); },
    get currentHistoryPage() { return Math.min(Math.max(1, this.historyPage), this.historyPageCount); },
    get historyResultLabel() {
      const count = this.filteredHistory.length;
      if (!count) return '0 records';
      const first = (this.currentHistoryPage - 1) * this.historyPageSize + 1;
      return first + '–' + Math.min(first + this.historyPageSize - 1, count) + ' of ' + count + ' records';
    },
    get visibleHistory() {
      const start = (this.currentHistoryPage - 1) * this.historyPageSize;
      return this.filteredHistory.slice(start, start + this.historyPageSize);
    },
    setHistoryMonth(value) {
      if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value)) return;
      this.historyMonth = value;
      this.historyPage = 1;
    },
    shiftHistoryMonth(direction) {
      const [year, month] = this.historyMonth.split('-').map(Number);
      const index = year * 12 + month - 1 + direction;
      if (index < 12 || index >= 120000) return;
      this.setHistoryMonth(String(Math.floor(index / 12)).padStart(4, '0') + '-' + String(index % 12 + 1).padStart(2, '0'));
    },
    currentHistoryMonth() { this.setHistoryMonth(localDate(new Date()).slice(0, 7)); },
    changeHistoryPage(direction) {
      this.historyPage = Math.min(Math.max(1, this.currentHistoryPage + direction), this.historyPageCount);
      this.$nextTick(() => {
        this.$refs.historyResults.scrollIntoView({ block: 'start' });
        this.$refs.historyResults.focus({ preventScroll: true });
      });
    },
    get canInvoice() {
      return !!this.reportClientId && !this.reportLoading && !this.reportError &&
        (this.reportMode === 'range' ? this.rangeReady : !!this.selectedMonth) &&
        (this.periodData.sessions > 0 || this.periodData.expenses.length > 0);
    },
    get invoiceHint() {
      if (!this.reportClientId) return 'Select one client to create an invoice.';
      if (this.rangeLoading || this.reportLoading) return 'Your report is loading…';
      if (this.reportError || (this.reportMode === 'range' && !this.rangeReady)) return 'Choose a valid period and load your report first.';
      if (!this.canInvoice) return 'No work or expenses to invoice for this period.';
      return 'Review and issue a draft, or reprint the saved invoice.';
    },
    fullDate(iso) {
      if (!iso) return '';
      return new Date(iso.slice(0, 10) + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    },
    setLogDate(offset) {
      const date = new Date();
      date.setDate(date.getDate() + offset);
      this[this.logMode === 'work' ? 'workDate' : 'expDate'] = localDate(date);
    },
    setRangePreset(preset) {
      const end = new Date(), start = new Date(end);
      if (preset === 'week') start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
      if (preset === 'month') start.setDate(1);
      if (preset === 'lastmonth') {
        start.setDate(1);
        start.setMonth(start.getMonth() - 1);
        end.setDate(0);
      }
      this.rangeStart = localDate(start);
      this.rangeEnd = localDate(end);
      return this.loadRange();
    },
    async loadHistory() {
      this.historyLoading = true;
      this.historyError = '';
      try {
        const [entries, expenses] = await Promise.all([this.api('/api/entries'), this.api('/api/expenses')]);
        this.entries = entries;
        this.expenses = expenses;
        this.historyPage = this.currentHistoryPage;
      } catch (error) { this.historyError = 'Unable to refresh history. Please try again.'; }
      finally { this.historyLoading = false; }
    },
    viewSaved() {
      this.historyMode = this.lastSaved.kind === 'work' ? 'work' : 'expenses';
      this.historyClientId = this.lastSaved.client_id;
      this.historySearch = '';
      this.setHistoryMonth(this.lastSaved.date.slice(0, 7));
      const index = this.filteredHistory.findIndex(e => e.id === this.lastSaved.id);
      this.historyPage = Math.floor(Math.max(0, index) / this.historyPageSize) + 1;
      this.tab = 'history';
      this.onTabSwitch('history');
    },

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
    rangeLoadFailed: false,
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
        this.historyPage = this.currentHistoryPage;
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
    backupBusy: false,
    backupError: '',
    backupStatus: '',
    deleteConfirm: { show: false, type: '', action: () => {} },

    toast: { show: false, msg: '', type: 'success' },

    monthNames: ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],

    get previewHours() {
      return this.fmtHours(this.calcHours(this.workStart, this.workEnd));
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
      this.bootLoading = true;
      this.bootError = '';
      try {
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
      } catch (error) { this.bootError = 'Unable to load your data. Check your connection and try again.'; }
      finally { this.bootLoading = false; }
    },

    async loadConfig() { this.config = await this.api('/api/config'); },
    async loadClients() { this.clients = await this.api('/api/clients'); },
    async loadEntries() { this.entries = await this.api('/api/entries'); },
    async loadExpenses() { this.expenses = await this.api('/api/expenses'); },

    onTabSwitch(id) {
      document.body.scrollTop = 0;
      document.documentElement.scrollTop = 0;
      if (id === 'reports') {
        this.loadReport();
      } else if (id === 'history') {
        this.loadHistory();
      }
    },

    async saveWork() {
      if (this.saving) return;
      this.logError = '';
      if (!this.logClientId || !this.workDate || !this.workStart || !this.workEnd || this.workStart === this.workEnd || !Number.isFinite(Number(this.workMiles)) || Number(this.workMiles) < 0) {
        this.logError = 'Choose a client and date, different start and end times, and miles of zero or more.';
        return;
      }
      this.saving = true;
      try {
        const clientId = this.clients.length === 1 ? this.clients[0].id : this.logClientId;
        const saved = await this.api('/api/entries', 'POST', {
          client_id: clientId,
          date: this.workDate,
          start_time: this.workStart,
          end_time: this.workEnd,
          miles: this.workMiles,
        });
        this.entries.push(saved);
        this.lastSaved = { ...saved, kind: 'work' };
        this.showToast('Work entry saved', 'success');
      } catch (e) {
        this.logError = e.message || 'Unable to save. Your entry is still here; please try again.';
      }
      this.saving = false;
    },

    async saveExpense() {
      if (this.saving) return;
      this.logError = '';
      if (!this.logClientId || !this.expDate || !Number.isFinite(Number(this.expAmount)) || Number(this.expAmount) <= 0) {
        this.logError = 'Choose a client and date, and enter an amount greater than zero.';
        return;
      }
      this.saving = true;
      try {
        const clientId = this.clients.length === 1 ? this.clients[0].id : this.logClientId;
        const saved = await this.api('/api/expenses', 'POST', {
          client_id: clientId,
          date: this.expDate,
          amount: this.expAmount,
          description: this.expDesc,
        });
        this.expenses.push(saved);
        this.lastSaved = { ...saved, kind: 'expense' };
        this.showToast('Expense saved', 'success');
        this.expAmount = 0;
        this.expDesc = 'Cleaning supplies';
      } catch (e) {
        this.logError = e.message || 'Unable to save. Your entry is still here; please try again.';
      }
      this.saving = false;
    },

    loadReport() {
      if (this.reportMode === 'range') return this.loadRange();
      if (this.reportMode === 'monthly') return this.loadMonthly();
      return this.loadTaxYear();
    },

    async loadRange() {
      ++this.reportRequest;
      this.reportLoading = false;
      const request = ++this.rangeRequest;
      const key = this.rangeKey;
      this.rangeError = '';
      this.rangeLoadFailed = false;
      this.reportError = '';
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
          this.rangeLoadFailed = true;
        }
      } finally {
        if (request === this.rangeRequest) this.rangeLoading = false;
      }
    },

    loadMonthly() { return this.loadStandardReport('monthly'); },
    loadTaxYear() { return this.loadStandardReport('taxyear'); },
    async loadStandardReport(mode) {
      const request = ++this.reportRequest;
      const client = this.reportClientId;
      const monthly = mode === 'monthly';
      const selection = monthly ? 'selectedMonth' : 'selectedTaxYear';
      const property = monthly ? 'monthlyData' : 'taxYearData';
      const available = monthly ? 'available_months' : 'available_tax_years';
      const key = item => monthly ? item.year + '-' + item.month : String(item.year);
      const params = new URLSearchParams();
      if (client) params.set('client_id', client);
      const fetchPeriod = async value => {
        if (value) {
          if (monthly) {
            const [year, month] = value.split('-');
            params.set('year', year); params.set('month', month);
          } else params.set('tax_year', value);
        }
        return this.api('/api/reports/' + mode + '?' + params);
      };
      this.reportLoading = true;
      this.reportError = '';
      try {
        let value = this[selection];
        let data = await fetchPeriod(value);
        if (data[available].length && !data[available].some(item => key(item) === value)) {
          value = key(data[available][0]);
          data = await fetchPeriod(value);
        }
        if (request !== this.reportRequest || client !== this.reportClientId || mode !== this.reportMode) return;
        this[selection] = data[available].length ? value : '';
        this[property] = data;
      } catch (error) {
        if (request === this.reportRequest && mode === this.reportMode) this.reportError = 'Unable to load this report. Please try again.';
      } finally { if (request === this.reportRequest) this.reportLoading = false; }
    },

    openInvoice() {
      if (!this.reportClientId || this.reportLoading || this.reportError) return;
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

    async confirmDelete() {
      if (this.deleteBusy) return;
      this.deleteBusy = true;
      this.deleteError = '';
      try {
        await this.deleteConfirm.action();
        this.deleteConfirm.show = false;
      } catch (error) { this.deleteError = 'Unable to delete. Please try again.'; }
      finally { this.deleteBusy = false; }
    },

    deleteEntry(id) {
      this.deleteError = '';
      this.deleteConfirm = {
        show: true, type: 'entry',
        action: async () => {
          await this.api('/api/entries/' + encodeURIComponent(id), 'DELETE');
          this.showToast('Entry deleted', 'success');
          this.entries = this.entries.filter(e => e.id !== id);
          this.historyPage = this.currentHistoryPage;
        }
      };
    },
    deleteExpense(id) {
      this.deleteError = '';
      this.deleteConfirm = {
        show: true, type: 'expense',
        action: async () => {
          await this.api('/api/expenses/' + encodeURIComponent(id), 'DELETE');
          this.showToast('Expense deleted', 'success');
          this.expenses = this.expenses.filter(e => e.id !== id);
          this.historyPage = this.currentHistoryPage;
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
      this.deleteError = '';
      this.deleteConfirm = {
        show: true, type: 'client',
        action: async () => {
          await this.api('/api/clients/' + encodeURIComponent(id), 'DELETE');
          this.showToast('Client deleted', 'success');
          this.loadClients();
        }
      };
    },

    async downloadBackup() {
      if (this.backupBusy) return;
      this.backupBusy = true;
      this.backupError = '';
      this.backupStatus = '';
      let url;
      try {
        const response = await fetch('/api/backup', { cache: 'no-store' });
        if (!response.ok) throw new Error('Unable to create your backup. Please try again.');
        const blob = await response.blob();
        url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        const disposition = response.headers.get('Content-Disposition') || '';
        link.download = disposition.match(/filename="?([^";]+)"?/)?.[1] || 'cleaning-tracker-backup.zip';
        document.body.appendChild(link);
        link.click();
        link.remove();
        this.backupStatus = 'Backup download started. Check your Files or Downloads folder to confirm it was saved.';
      } catch (error) {
        this.backupError = 'Unable to download your backup. Check your connection and try again.';
      } finally {
        // Give mobile browsers time to hand off the file to their download manager.
        if (url) setTimeout(() => URL.revokeObjectURL(url), 60000);
        this.backupBusy = false;
      }
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
      const minutes = Math.round(h * 60);
      const hr = Math.floor(minutes / 60);
      const mn = minutes % 60;
      return hr + 'h ' + mn + 'm';
    },

    entryHours(entry) {
      if (entry.minutes != null) return entry.minutes / 60;
      if (entry.start_time && entry.end_time) return this.calcHours(entry.start_time, entry.end_time);
      return entry.hours;
    },

    clientName(id) {
      const c = this.clients.find(c => c.id === id);
      return c ? c.name : 'Unknown';
    },

    showToast(msg, type) {
      this.toast = { show: true, msg, type };
      clearTimeout(this.toastTimer);
      this.toastTimer = setTimeout(() => this.toast.show = false, 4000);
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
