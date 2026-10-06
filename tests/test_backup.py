import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import webapp
from helpers import DEFAULT_CONFIG, save_json


class BackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name in ('ENTRIES_FILE', 'EXPENSES_FILE', 'CLIENTS_FILE', 'CONFIG_FILE', 'INVOICES_FILE'):
            patcher = patch.object(webapp, name, self.root / name)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config = dict(DEFAULT_CONFIG, business_name='Saved business', account_number='12345678')
        patcher = patch.object(webapp, 'load_config', return_value=self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = webapp.app.test_client()

    def test_backup_contains_all_saved_data_without_mutating_it(self):
        expected = {
            'entries.json': [{'id': 'work', 'client_id': 'a', 'date': '2026-10-01', 'hours': 2, 'amount': 30}],
            'expenses.json': [{'id': 'expense', 'client_id': 'a', 'amount': 3.49, 'description': 'Cloths £3.49'}],
            'clients.json': [{'id': 'a', 'name': 'Zoë', 'address': 'Saved address'}],
            'config.json': self.config,
            'invoices.json': [{'id': 'issued', 'html': '<html>Saved invoice</html>'}],
        }
        for filename, value in expected.items():
            save_json(getattr(webapp, filename.split('.')[0].upper() + '_FILE'), value)
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        response = self.client.get('/api/backup')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertRegex(response.headers['Content-Disposition'], r'attachment; filename=cleaning-tracker-backup-\d{4}-\d{2}-\d{2}-\d{6}\.zip')
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), set(expected) | {'backup-info.json', 'README.txt'})
            for name, value in expected.items():
                self.assertEqual(json.loads(archive.read(name)), value)
            self.assertEqual(json.loads(archive.read('backup-info.json'))['format_version'], 1)
            self.assertIn(b'Restoring replaces', archive.read('README.txt'))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_empty_install_can_be_backed_up(self):
        response = self.client.get('/api/backup')
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(json.loads(archive.read('entries.json')), [])
            self.assertEqual(json.loads(archive.read('expenses.json')), [])
            self.assertEqual(json.loads(archive.read('clients.json')), webapp.DEFAULT_CLIENTS)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bulk_delete_is_no_longer_available(self):
        for name in ('entries', 'expenses'):
            path = getattr(webapp, name.upper() + '_FILE')
            save_json(path, [{'id': 'keep'}])
            response = self.client.delete('/api/' + name + '?confirm=true')
            self.assertEqual(response.status_code, 405)
            self.assertEqual(json.loads(path.read_text()), [{'id': 'keep'}])


if __name__ == '__main__':
    unittest.main()
