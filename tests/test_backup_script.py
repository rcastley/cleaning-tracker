import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('backup_data', ROOT / 'scripts/backup_data.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupScriptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'data').mkdir()
        (self.root / 'scripts').mkdir()
        for name in ('backup.sh', 'scripts/backup_data.py'):
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.entries = self.root / 'data/entries.json'
        self.entries.write_text('[{"id":"current"}]')
        patcher = patch.object(backup, 'ROOT', self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def archive(self, name, members):
        path = self.root / name
        with tarfile.open(path, 'w:gz') as archive:
            for member, content in members.items():
                info = tarfile.TarInfo(member)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        return path

    def run_script(self, *args, answer='y\n'):
        return subprocess.run(['bash', str(self.root / 'backup.sh'), *map(str, args)],
                              input=answer, capture_output=True, text=True)

    def test_legacy_and_deployment_archives_restore_to_active_directory(self):
        for prefix in ('', 'data/'):
            with self.subTest(prefix=prefix):
                self.entries.write_text('[{"id":"current"}]')
                archive = self.archive('restore.tar.gz', {prefix + 'entries.json': b'[{"id":"restored"}]'})
                result = self.run_script('restore', archive, '--offline')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.entries.read_text()), [{'id': 'restored'}])
                self.assertFalse((self.root / 'data/data').exists())
                self.assertEqual(self.entries.stat().st_mode & 0o777, 0o600)
                safety = sorted((self.root / 'backups').glob('pre-restore-*.tar.gz'))[-1]
                self.assertEqual(backup.read_archive(safety)['entries.json'], b'[{"id":"current"}]')

    def test_rejects_unsafe_invalid_and_duplicate_members_before_any_changes(self):
        original = self.entries.read_bytes()
        for members in ({'../entries.json': b'[]'}, {'data/entries.json': b'invalid'},
                        {'entries.json': b'[]', 'data/entries.json': b'[]'},
                        {'entries.json': b'{}'}, {'expenses.json': b'[NaN]'}):
            archive = self.archive('bad.tar.gz', members)
            result = self.run_script('restore', archive, '--offline')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.entries.read_bytes(), original)
            self.assertFalse((self.root / 'backups').exists())

    def test_restore_can_replace_corrupt_data_and_preserves_missing_invoice_history(self):
        self.entries.write_text('corrupt')
        invoices = self.root / 'data/invoices.json'
        invoices.write_text('[{"id":"issued"}]')
        archive = self.archive('old.tar.gz', {'entries.json': b'[]'})
        result = self.run_script('restore', archive, '--offline')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.entries.read_text(), '[]')
        self.assertEqual(invoices.read_text(), '[{"id":"issued"}]')
        self.assertIn('existing files preserved', result.stdout)

    def test_backup_permissions_listing_and_scheduled_retention(self):
        directory = self.root / 'backups'
        directory.mkdir()
        for i in range(32):
            (directory / f'scheduled-20000101{i:02d}.tar.gz').write_bytes(b'old')
        manual = directory / 'backup_manual.tar.gz'
        deployment = directory / 'pre-deploy-old.tar.gz'
        for path in (manual, deployment):
            path.write_bytes(b'keep')
        result = self.run_script('scheduled', '--offline')
        self.assertEqual(result.returncode, 0, result.stderr)
        scheduled = sorted(directory.glob('scheduled-*.tar.gz'))
        self.assertEqual(len(scheduled), 30)
        self.assertEqual(backup.read_archive(scheduled[-1])['entries.json'], self.entries.read_bytes())
        self.assertEqual(scheduled[-1].stat().st_mode & 0o777, 0o600)
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        listed = self.run_script('list').stdout
        self.assertIn(manual.name, listed)
        self.assertIn(deployment.name, listed)

    def test_failed_backup_does_not_expire_existing_archives(self):
        directory = self.root / 'backups'
        directory.mkdir()
        for i in range(31):
            (directory / f'scheduled-{i:03d}.tar.gz').write_bytes(b'keep')
        self.entries.write_text('corrupt')
        result = self.run_script('scheduled', '--offline')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(list(directory.glob('*.tar.gz'))), 31)

    def test_managed_service_restarts_even_if_backup_fails(self):
        unit = self.root / 'unit'
        unit.write_text(f'# Managed by Cleaning Tracker install.sh\nWorkingDirectory={self.root}\n')
        for state in ('active', 'inactive'):
            with patch.object(backup, 'UNIT', unit), patch.object(backup, 'LOCK', self.root / 'lock'), \
                    patch.object(backup.os, 'geteuid', return_value=0), \
                    patch.object(backup, 'systemctl') as service:
                service.return_value.stdout = state
                with self.assertRaisesRegex(ValueError, 'simulated failure'):
                    with backup.stopped():
                        raise ValueError('simulated failure')
                calls = [call.args[0] for call in service.call_args_list]
                self.assertIn('stop', calls)
                self.assertEqual('start' in calls, state == 'active')

    def test_restore_write_failure_rolls_back_changed_files(self):
        original = self.entries.read_bytes()
        actual_write = backup.write_record
        attempts = 0

        def fail_second_write(path, content):
            nonlocal attempts
            attempts += 1
            if attempts == 2:
                raise OSError('simulated disk error')
            actual_write(path, content)

        with patch.object(backup, 'write_record', side_effect=fail_second_write), \
                patch('builtins.print'):
            with self.assertRaises(OSError):
                backup.restore({'entries.json': b'[]', 'expenses.json': b'[]'})
        self.assertEqual(self.entries.read_bytes(), original)
        self.assertFalse((self.root / 'data/expenses.json').exists())


if __name__ == '__main__':
    unittest.main()
