import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from helpers import load_json, save_json


class EditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        for name in ('ENTRIES_FILE', 'EXPENSES_FILE', 'CLIENTS_FILE'):
            patcher = patch.object(webapp, name, root / (name + '.json'))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = webapp.app.test_client()
        self.work = dict(id='work-1', client_id='a', date='2026-09-20',
                         start_time='09:00', end_time='12:00', miles=4,
                         hours=3, hourly_rate=15, amount=45)
        self.expense = dict(id='expense-1', client_id='a', date='2026-09-20',
                            amount=5, description='Supplies')
        save_json(webapp.CLIENTS_FILE, [dict(id='a', name='A'), dict(id='b', name='B')])
        save_json(webapp.ENTRIES_FILE, [self.work, dict(self.work, id='work-2')])
        save_json(webapp.EXPENSES_FILE, [self.expense])

    def test_work_preserves_identity_rate_and_other_records(self):
        with patch.object(webapp, 'load_config', return_value=dict(hourly_rate=99)):
            response = self.client.put('/api/entries/work-1', json=dict(
                self.work, id='tampered', hourly_rate=99, amount=999,
                client_id='b', start_time='22:00', end_time='01:30', miles=7))
        self.assertEqual(response.status_code, 200)
        saved = response.get_json()
        self.assertEqual((saved['id'], saved['hourly_rate'], saved['hours'], saved['amount']),
                         ('work-1', 15, 3.5, 52.5))
        self.assertEqual(saved['client_id'], 'b')
        self.assertEqual(load_json(webapp.ENTRIES_FILE, [])[1], dict(self.work, id='work-2'))
        report = self.client.get('/api/reports/monthly?client_id=b&year=2026&month=9').get_json()
        self.assertEqual(report['total_labour'], 52.5)
        self.assertEqual(report['total_miles'], 7)
        invoice = self.client.get('/invoice?client_id=b&year=2026&month=9')
        self.assertEqual(invoice.status_code, 200)
        self.assertIn(b'52.50', invoice.data)

    def test_expense_accepts_pennies_and_updates_report(self):
        response = self.client.put('/api/expenses/expense-1', json=dict(
            self.expense, amount=3.49, description='Cloths', date='2026-08-01'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['amount'], 3.49)
        report = self.client.get('/api/reports/monthly?year=2026&month=8').get_json()
        self.assertEqual(report['total_expenses'], 3.49)
        self.assertEqual(len(load_json(webapp.EXPENSES_FILE, [])), 1)

    def test_invalid_work_does_not_mutate_storage(self):
        for field, value in [('date', '2026-02-30'), ('client_id', 'missing'),
                             ('start_time', '25:00'), ('end_time', '09:00'),
                             ('miles', -1), ('miles', 'NaN'), ('miles', True)]:
            with self.subTest(field=field, value=value):
                response = self.client.put('/api/entries/work-1', json=dict(self.work, **{field: value}))
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.get_json()['errors'])
                self.assertEqual(load_json(webapp.ENTRIES_FILE, [])[0], self.work)

    def test_invalid_expense_and_missing_records(self):
        for value in (0, 0.001, -1, '', 'Infinity', None):
            response = self.client.put('/api/expenses/expense-1', json=dict(self.expense, amount=value))
            self.assertEqual(response.status_code, 400)
            self.assertEqual(load_json(webapp.EXPENSES_FILE, [])[0], self.expense)
        for endpoint in ('entries', 'expenses'):
            self.assertEqual(self.client.put('/api/' + endpoint + '/missing', json={}).status_code, 404)
            record_id = 'work-1' if endpoint == 'entries' else 'expense-1'
            for body in ([], None, {}):
                self.assertEqual(self.client.put('/api/' + endpoint + '/' + record_id, json=body).status_code, 400)


if __name__ == '__main__':
    unittest.main()
