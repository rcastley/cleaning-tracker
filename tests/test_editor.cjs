const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const context = { setTimeout, window: { confirm: () => false } };
vm.createContext(context);
vm.runInContext(readFileSync('static/app.js', 'utf8'), context);

(async () => {
  const app = context.app();
  app.$nextTick = fn => fn();
  app.$refs = { editClient: { focus() {} }, editDialog: { querySelector() { return null; } } };
  app.showToast = () => {};
  let focused = false;
  const trigger = { focus() { focused = true; } };
  const work = { id: 'one', date: '2026-01-01', hourly_rate: 12, miles: 4, start_time: '09:00', end_time: '12:00' };
  app.entries = [work];
  app.openEditor('work', work, trigger);
  app.editor.draft.miles = '8';
  assert.equal(work.miles, 4, 'Draft must not mutate saved record');
  app.closeEditor();
  assert.equal(app.editor.open, true, 'Declining discard keeps draft');
  context.window.confirm = () => true;
  app.closeEditor();
  assert.equal(app.editor.open, false);
  assert.equal(focused, true);

  app.openEditor('work', work, trigger);
  app.editor.draft.miles = '-1';
  app.api = async () => { const error = new Error('Check miles'); error.fields = { miles: 'Invalid miles' }; throw error; };
  await app.saveEdit();
  assert.equal(app.editor.open, true);
  assert.equal(app.editor.draft.miles, '-1');
  assert.equal(app.editor.errors.miles, 'Invalid miles');
  assert.equal(app.editor.saving, false);
  assert.equal(work.miles, 4);

  app.editor.draft.miles = '8';
  let calls = 0;
  let resolve;
  app.api = () => { calls++; return new Promise(done => { resolve = done; }); };
  const save = app.saveEdit();
  await app.saveEdit();
  assert.equal(calls, 1, 'Repeated submission must be ignored');
  resolve({ ...work, miles: 8 });
  await save;
  assert.equal(app.entries.length, 1);
  assert.equal(app.entries[0].miles, 8);
  assert.equal(app.entries[0].hourly_rate, 12);
  assert.equal(app.editor.open, false);

  const expense = { id: 'expense', date: '2026-01-01', amount: 5, description: 'Supplies' };
  app.expenses = [expense];
  app.openEditor('expense', expense, trigger);
  app.editor.draft.amount = '3.49';
  app.api = async (url, method, draft) => {
    assert.equal(url, '/api/expenses/expense');
    assert.equal(method, 'PUT');
    return { ...draft, amount: 3.49 };
  };
  await app.saveEdit();
  assert.equal(app.expenses[0].amount, 3.49);
  assert.equal(app.expenses.length, 1);
  console.log('Editor draft, cancel, failure, retry, duplicate-save and expense checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
