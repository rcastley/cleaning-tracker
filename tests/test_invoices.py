import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import webapp
from helpers import DEFAULT_CONFIG, save_json


class InvoiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for name in ('ENTRIES_FILE', 'EXPENSES_FILE', 'CLIENTS_FILE', 'INVOICES_FILE'):
            patcher = patch.object(webapp, name, Path(temporary.name) / name)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config = dict(DEFAULT_CONFIG, business_name='Original business')
        patcher = patch.object(webapp, 'load_config', return_value=self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        save_json(webapp.CLIENTS_FILE, [dict(id=c, name='Client ' + c, address='') for c in ('a', 'b')])
        save_json(webapp.ENTRIES_FILE, [dict(id=c, client_id=c, date='2026-06-01',
                  start_time='09:00', end_time='10:00', hours=1, amount=15, hourly_rate=15)
                  for c in ('a', 'b')])
        self.client = webapp.app.test_client()
        self.query = '/invoice?client_id=a&year=2026&month=6'

    def test_preview_does_not_issue_and_clients_get_unique_references(self):
        response = self.client.get(self.query)
        self.assertIn(b'Issue invoice', response.data)
        self.assertIn(b'DRAFT', response.data)
        self.assertFalse(webapp.INVOICES_FILE.exists())
        for client in ('a', 'b'):
            response = self.client.post(self.query.replace('client_id=a', 'client_id=' + client))
            self.assertEqual(response.status_code, 303)
            self.assertIn(b'Print / Save PDF', self.client.get(response.location).data)
        saved = json.loads(webapp.INVOICES_FILE.read_text())
        self.assertNotEqual(saved[0]['number'], saved[1]['number'])

    def test_reprints_freeze_dates_and_details_and_retries_are_idempotent(self):
        with patch.object(webapp, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = datetime(2026, 6, 15)
            issued = self.client.post(self.query)
        original = self.client.get(issued.location).data
        self.assertIn(b'15/06/2026', original)
        self.assertIn(b'29/06/2026', original)
        save_json(webapp.ENTRIES_FILE, [])
        save_json(webapp.CLIENTS_FILE, [])
        self.config.update(payment_terms=90, business_name='Changed business')
        with patch.object(webapp, 'datetime', wraps=datetime) as clock:
            clock.now.return_value = datetime(2027, 1, 1)
            self.assertEqual(self.client.get(issued.location).data, original)
            for url in (self.query, '/invoice?client_id=a&start_date=2026-06-01&end_date=2026-06-30'):
                self.assertEqual(self.client.post(url).location, issued.location)
                self.assertEqual(self.client.get(url, follow_redirects=True).data, original)
        self.assertEqual(len(json.loads(webapp.INVOICES_FILE.read_text())), 1)

    def test_rejects_missing_client_empty_period_and_unknown_invoice(self):
        self.assertEqual(self.client.post(self.query.replace('client_id=a', 'client_id=missing')).status_code, 404)
        self.assertEqual(self.client.post(self.query.replace('month=6', 'month=7')).status_code, 400)
        self.assertEqual(self.client.get('/invoice?id=missing').status_code, 404)
        self.assertFalse(webapp.INVOICES_FILE.exists())

    def test_failed_write_preserves_previously_issued_invoices(self):
        self.client.post(self.query)
        original = webapp.INVOICES_FILE.read_bytes()
        with patch.object(webapp.os, 'replace', side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):
                with webapp.app.test_request_context(self.query.replace('client_id=a', 'client_id=b'), method='POST'):
                    webapp.invoice()
        self.assertEqual(webapp.INVOICES_FILE.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
