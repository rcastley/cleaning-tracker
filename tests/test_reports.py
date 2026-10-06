import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import webapp
from helpers import DEFAULT_CONFIG, save_json, get_tax_year, get_tax_year_label, format_hours


class ReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        for name in ('ENTRIES_FILE', 'EXPENSES_FILE', 'CLIENTS_FILE', 'INVOICES_FILE'):
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

    def test_exact_minutes_in_new_and_legacy_reports_and_invoices(self):
        save_json(webapp.ENTRIES_FILE, [])
        save_json(webapp.EXPENSES_FILE, [])
        entries = []
        for _ in range(3):
            response = self.client.post('/api/entries', json=dict(
                client_id='a', date='2026-06-01', start_time='09:00', end_time='09:20'))
            self.assertEqual(response.status_code, 201)
            entry = response.get_json()
            self.assertEqual((entry['minutes'], entry['amount']), (20, 5))
            entries.append(entry)
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                if legacy:
                    for entry in entries:
                        entry.pop('minutes')
                    save_json(webapp.ENTRIES_FILE, entries)
                for query in ('monthly?year=2026&month=6',
                              'range?start_date=2026-06-01&end_date=2026-06-01',
                              'taxyear?tax_year=2026'):
                    report = self.client.get('/api/reports/' + query).get_json()
                    self.assertEqual(report['total_hours'], 1)
                    self.assertEqual(report['total_hours_fmt'], '1h 0m')
                    self.assertEqual(report['total_labour'], 15)
                    if 'breakdown' in report:
                        self.assertEqual(report['breakdown'][0]['hours_fmt'], '1h 0m')
                html = self.client.get('/invoice?client_id=a&year=2026&month=6').get_data(as_text=True)
                self.assertIn('Labour (1.00 hrs)', html)

    def test_minutes_survive_edit_and_overnight_work(self):
        save_json(webapp.ENTRIES_FILE, [])
        save_json(webapp.EXPENSES_FILE, [])
        fields = dict(client_id='a', date='2026-06-01', start_time='23:59', end_time='00:01', miles=0)
        entry = self.client.post('/api/entries', json=fields).get_json()
        self.assertEqual(entry['minutes'], 2)
        report = self.client.get('/api/reports/monthly?year=2026&month=6').get_json()
        self.assertEqual(report['total_hours_fmt'], '0h 2m')
        response = self.client.put('/api/entries/' + entry['id'], json={**fields, 'end_time': '01:00'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['minutes'], 61)
        report = self.client.get('/api/reports/monthly?year=2026&month=6').get_json()
        self.assertEqual(report['total_hours_fmt'], '1h 1m')
        self.assertEqual(format_hours(1.999), '2h 0m')

    def test_uk_tax_year_boundaries_and_labels(self):
        for value, expected in [('2026-04-01', 2025), ('2026-04-05', 2025),
                                ('2026-04-06', 2026), ('2027-04-05', 2026),
                                ('2027-04-06', 2027), ('2024-02-29', 2023)]:
            with self.subTest(date=value):
                self.assertEqual(get_tax_year(date.fromisoformat(value), 4), expected)
        self.assertEqual(get_tax_year_label(2026, 4),
                         '2026/2027 (6 April 2026 - 5 April 2027)')

    def test_other_tax_year_months_keep_first_day_boundary(self):
        self.assertEqual(get_tax_year(date(2026, 6, 30), 7), 2025)
        self.assertEqual(get_tax_year(date(2026, 7, 1), 7), 2026)
        self.assertEqual(get_tax_year_label(2026, 7),
                         '2026/2027 (1 July 2026 - 30 June 2027)')
        self.assertEqual(get_tax_year(date(2026, 1, 1), 1), 2026)
        self.assertEqual(get_tax_year_label(2026, 1),
                         '2026 (1 January 2026 - 31 December 2026)')

    def test_tax_report_splits_work_expenses_and_mileage_at_six_april(self):
        dates = ['2026-04-05', '2026-04-06', '2027-04-05', '2027-04-06']
        save_json(webapp.ENTRIES_FILE, [
            dict(id=str(i), client_id='a', date=d, hours=1, amount=15, miles=10)
            for i, d in enumerate(dates)
        ] + [dict(id='other', client_id='b', date='2026-04-06',
                  hours=2, amount=30, miles=20)])
        save_json(webapp.EXPENSES_FILE, [
            dict(id=str(i), client_id='a', date=d, amount=i + 1)
            for i, d in enumerate(dates)
        ])
        for year, sessions, expenses in [(2025, 1, 1), (2026, 2, 5), (2027, 1, 4)]:
            with self.subTest(year=year):
                response = self.client.get(f'/api/reports/taxyear?tax_year={year}&client_id=a')
                self.assertEqual(response.status_code, 200)
                report = response.get_json()
                self.assertEqual(report['sessions'], sessions)
                self.assertEqual(report['total_labour'], sessions * 15)
                self.assertEqual(report['total_expenses'], expenses)
                self.assertEqual(report['total_miles'], sessions * 10)
                self.assertEqual(report['mileage_allowance'], sessions * 4.5)
                self.assertEqual(sum(m['expenses'] for m in report['breakdown']), expenses)
                self.assertIn({'year': 2026, 'label': '2026/2027 (6 April 2026 - 5 April 2027)'},
                              report['available_tax_years'])

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
        self.assertIn('DRAFT', html)
        self.assertIn('51.98', html)
        self.assertNotIn('30/12/2025', html)
        self.assertNotIn('02/01/2026', html)
        report = self.client.get('/api/reports/monthly?client_id=a&year=2026&month=1').get_json()
        self.assertEqual(report['sessions'], 2)
        self.assertEqual(report['total_amount'], 51.98)
        html = self.client.get('/invoice?client_id=a&year=2026&month=1').get_data(as_text=True)
        self.assertIn('January 2026', html)
        self.assertIn('Issue invoice', html)
        self.assertEqual(self.client.get('/api/reports/taxyear?tax_year=2025').status_code, 200)


if __name__ == '__main__':
    unittest.main()
