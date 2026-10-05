const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
let clicks = 0, removed = 0, appended = 0, revoked = 0, cleanup;
const link = { click() { clicks++; }, remove() { removed++; } };
const context = {
  URL: { createObjectURL: () => 'blob:backup', revokeObjectURL: () => revoked++ },
  setTimeout(fn) { cleanup = fn; },
  document: { createElement: () => link, body: { appendChild() { appended++; } } },
};
vm.createContext(context);
vm.runInContext(readFileSync('static/app.js', 'utf8'), context);
(async () => {
  const app = context.app();
  let resolve, calls = 0;
  context.fetch = () => { calls++; return new Promise(done => { resolve = done; }); };
  const pending = app.downloadBackup();
  await app.downloadBackup();
  assert.equal(calls, 1);
  assert.equal(app.backupBusy, true);
  resolve({ ok: true, blob: async () => ({}), headers: { get: () => 'attachment; filename=cleaning-tracker-backup-2026-10-05-123456.zip' } });
  await pending;
  assert.equal(link.download, 'cleaning-tracker-backup-2026-10-05-123456.zip');
  assert.equal(link.href, 'blob:backup');
  assert.equal(clicks, 1);
  assert.equal(removed, 1);
  assert.equal(appended, 1);
  assert.equal(app.backupBusy, false);
  assert.match(app.backupStatus, /download started/);
  assert.equal(revoked, 0);
  cleanup();
  assert.equal(revoked, 1);
  for (const fetch of [async () => ({ ok: false }), async () => { throw new Error('Offline'); }]) {
    context.fetch = fetch;
    await app.downloadBackup();
    assert.match(app.backupError, /try again/);
    assert.equal(app.backupStatus, '');
    assert.equal(app.backupBusy, false);
    assert.equal(clicks, 1);
  }
  console.log('Backup download, duplicate tap, cleanup and failure checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
