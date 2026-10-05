const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
let opened;
const context = { URLSearchParams, window: { open: url => { opened = url; } } };
vm.createContext(context);
vm.runInContext(readFileSync('static/app.js', 'utf8'), context);

(async () => {
  const app = context.app();
  app.reportMode = 'range';
  app.reportClientId = 'client & one';
  app.rangeStart = '2025-12-31';
  app.rangeEnd = '2026-01-01';
  app.api = async url => {
    const query = new URLSearchParams(url.split('?')[1]);
    assert.equal(query.get('client_id'), 'client & one');
    assert.equal(query.get('start_date'), '2025-12-31');
    assert.equal(query.get('end_date'), '2026-01-01');
    return { sessions: 2 };
  };
  await app.loadReport();
  assert.equal(app.rangeReady, true);
  app.openInvoice();
  assert.equal(new URLSearchParams(opened.split('?')[1]).get('end_date'), '2026-01-01');
  assert.equal(app.periodData.sessions, 2);

  app.rangeStart = '2026-01-02';
  opened = null;
  app.openInvoice();
  assert.equal(opened, null, 'Changed dates must not print stale report');
  await app.loadRange();
  assert.match(app.rangeError, /on or after/);
  assert.equal(app.rangeReady, false);
  app.rangeStart = '';
  await app.loadRange();
  assert.match(app.rangeError, /Select/);

  app.rangeStart = '2025-12-31';
  app.api = async () => { throw new Error('Network unavailable'); };
  await app.loadRange();
  assert.equal(app.rangeError, 'Network unavailable');
  assert.equal(app.rangeLoading, false);
  assert.equal(app.rangeReady, false);

  let finishOld, finishNew;
  app.api = () => new Promise(resolve => { finishOld = resolve; });
  const oldRequest = app.loadRange();
  app.rangeEnd = '2026-02-01';
  app.api = () => new Promise(resolve => { finishNew = resolve; });
  const newRequest = app.loadRange();
  finishNew({ sessions: 4 });
  await newRequest;
  finishOld({ sessions: 2 });
  await oldRequest;
  assert.equal(app.rangeReady, true);
  assert.equal(app.periodData.sessions, 4, 'Late responses must not replace newer results');

  app.reportMode = 'monthly';
  app.selectedMonth = '2026-1';
  app.openInvoice();
  const monthly = new URLSearchParams(opened.split('?')[1]);
  assert.equal(monthly.get('year'), '2026');
  assert.equal(monthly.get('month'), '1');
  assert.equal(monthly.has('start_date'), false);
  console.log('Report validation, retry, stale response and invoice checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
