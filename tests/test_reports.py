import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import webapp
from helpers import DEFAULT_CONFIG, save_json


class ReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name in ('ENTRIES_FILE', 'EXPENSES_FILE', 'CLIENTS_FILE'):
            patcher = patch.object(webapp, name, Path(temp.name) / name)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(webapp, 'load_config', return_value=DEFAULT_CONFIG.copy())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = webapp.app.test_client()
        work = dict(client_id='a', start_time='09:00', end_time='10:30',
                    hours=1.5, hourly_rate=15, amount=22.5, miles=4)
        dates = ['2025-12-30', '2025-12-31', '2026-01-01', '2026-01-02']
        save_json(webapp.ENTRIES_FILE, [dict(work, id=str(i), date=d) for i, d in enumerate(dates)] +
                  [dict(work, id='other', client_id='b', date='2026-01-01')])
        save_json(webapp.EXPENSES_FILE, [dict(id=str(i), client_id='a', date=d, amount=3.49,
                                           description='Supplies ' + d) for i, d in enumerate(dates)])
        save_json(webapp.CLIENTS_FILE, [dict(id='a', name='Client A', address=''),
                                       dict(id='b', name='Client B', address='')])

    def test_page_uses_content_versioned_assets(self):
        import hashlib
        from pathlib import Path
        html = self.client.get('/').get_data(as_text=True)
        for name in ('app.js', 'app.css', 'vendor/bootstrap.min.css'):
            version = hashlib.sha256((Path(webapp.app.static_folder) / name).read_bytes()).hexdigest()[:12]
            self.assertIn(name + '?v=' + version, html)

    def test_inclusive_cross_year_range_and_client_filter(self):
        query = '?start_date=2025-12-31&end_date=2026-01-01'
        report = self.client.get('/api/reports/range' + query + '&client_id=a').get_json()
        self.assertEqual([e['date'] for e in report['entries']], ['2025-12-31', '2026-01-01'])
        self.assertEqual([e['date'] for e in report['expenses']], ['2025-12-31', '2026-01-01'])
        for key, value in dict(sessions=2, total_hours=3, total_labour=45,
                               total_expenses=6.98, total_amount=51.98, total_miles=8).items():
            self.assertEqual(report[key], value)
        self.assertEqual(self.client.get('/api/reports/range' + query).get_json()['sessions'], 3)

    def test_same_day_empty_and_expense_only(self):
        query = '?start_date=2026-01-01&end_date=2026-01-01&client_id=a'
        self.assertEqual(self.client.get('/api/reports/range' + query).get_json()['sessions'], 1)
        save_json(webapp.ENTRIES_FILE, [])
        report = self.client.get('/api/reports/range' + query).get_json()
        self.assertEqual((report['sessions'], report['total_amount']), (0, 3.49))
        self.assertIn(b'3.49', self.client.get('/invoice' + query).data)
        report = self.client.get('/api/reports/range?start_date=2024-02-29&end_date=2024-02-29').get_json()
        self.assertEqual((report['entries'], report['expenses'], report['total_amount']), ([], [], 0))

    def test_invalid_dates(self):
        for query in ('', 'start_date=2026-01-01', 'end_date=2026-01-01',
                      'start_date=&end_date=2026-01-01',
                      'start_date=2026-02-29&end_date=2026-03-01',
                      'start_date=2026-1-1&end_date=2026-01-02',
                      'start_date=2026-01-02&end_date=2026-01-01'):
            for endpoint in ('/api/reports/range?', '/invoice?client_id=a&'):
                with self.subTest(endpoint=endpoint, query=query):
                    self.assertEqual(self.client.get(endpoint + query).status_code, 400)

    def test_invoice_matches_range_and_monthly_still_works(self):
        response = self.client.get('/invoice?client_id=a&start_date=2025-12-31&end_date=2026-01-01')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('31/12/2025 – 01/01/2026', html)
        self.assertIn(DEFAULT_CONFIG['invoice_prefix'] + '-20251231-20260101', html)
        self.assertIn('51.98', html)
        self.assertNotIn('30/12/2025', html)
        self.assertNotIn('02/01/2026', html)
        report = self.client.get('/api/reports/monthly?client_id=a&year=2026&month=1').get_json()
        self.assertEqual(report['sessions'], 2)
        self.assertEqual(report['total_amount'], 51.98)
        html = self.client.get('/invoice?client_id=a&year=2026&month=1').get_data(as_text=True)
        self.assertIn('January 2026', html)
        self.assertIn(DEFAULT_CONFIG['invoice_prefix'] + '-202601', html)
        self.assertEqual(self.client.get('/api/reports/taxyear?tax_year=2025').status_code, 200)


if __name__ == '__main__':
    unittest.main()
