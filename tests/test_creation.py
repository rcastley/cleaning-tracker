import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from helpers import DEFAULT_CONFIG, load_json, save_json


class CreationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for name in ('ENTRIES_FILE', 'EXPENSES_FILE', 'CLIENTS_FILE'):
            patcher = patch.object(webapp, name, Path(temporary.name) / name)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(webapp, 'load_config', return_value=DEFAULT_CONFIG.copy())
        patcher.start()
        self.addCleanup(patcher.stop)
        save_json(webapp.CLIENTS_FILE, [dict(id='a', name='Client A')])
        save_json(webapp.ENTRIES_FILE, [])
        save_json(webapp.EXPENSES_FILE, [])
        self.client = webapp.app.test_client()
        self.work = dict(client_id='a', date='2026-10-06', start_time='09:00', end_time='10:00')
        self.expense = dict(client_id='a', date='2026-10-06', amount=3.49)

    def test_invalid_records_never_reach_storage_or_break_reports(self):
        shared = [('date', 'bad-date'), ('date', '2026-02-29'), ('date', '2026-1-1'),
                  ('date', None), ('client_id', 'missing'), ('client_id', None)]
        work = [('start_time', '25:00'), ('end_time', '09:00'), ('start_time', None)]
        work += [('miles', value) for value in (-1, 'NaN', 'Infinity', True, None, {}, [])]
        expenses = [('amount', value) for value in (0, 0.001, -1, 'NaN', 'Infinity', True, None, {}, [])]
        expenses += [('description', value) for value in (None, [], {})]
        for endpoint, valid, invalid, path in (
                ('entries', self.work, shared + work, webapp.ENTRIES_FILE),
                ('expenses', self.expense, shared + expenses, webapp.EXPENSES_FILE)):
            before = path.read_bytes()
            for field, value in invalid:
                with self.subTest(endpoint=endpoint, field=field, value=value):
                    response = self.client.post('/api/' + endpoint, json={**valid, field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.get_json()['errors'])
                    self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.client.get('/api/bootstrap').status_code, 200)
        self.assertEqual(self.client.get('/api/reports/monthly?year=2026&month=10').status_code, 200)

    def test_missing_fields_and_malformed_bodies_return_json_errors(self):
        for endpoint, valid in (('entries', self.work), ('expenses', self.expense)):
            for field in valid:
                body = {key: value for key, value in valid.items() if key != field}
                response = self.client.post('/api/' + endpoint, json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.get_json()['errors'])
            for body in ('null', '[]', 'true', '42', '"text"', '{'):
                response = self.client.post('/api/' + endpoint, data=body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.get_json())

    def test_valid_defaults_and_server_derived_fields(self):
        response = self.client.post('/api/entries', json={**self.work,
            'start_time': '23:30', 'end_time': '00:30',
            'hours': 99, 'minutes': 999, 'amount': 999, 'hourly_rate': 999})
        self.assertEqual(response.status_code, 201)
        record = response.get_json()
        self.assertEqual((record['minutes'], record['hours'], record['amount'], record['miles']),
                         (60, 1, 15, 0))
        response = self.client.post('/api/expenses', json=self.expense)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()['description'], 'Cleaning supplies')
        self.assertEqual(load_json(webapp.EXPENSES_FILE, [])[0]['amount'], 3.49)


if __name__ == '__main__':
    unittest.main()
