"""Real Git/filesystem deployment tests; OS services and package installs are simulated."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.origin = self.root / 'origin'
        self.app = self.root / 'app'
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL='/dev/null',
                        GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                        GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid',
                        GIT_TERMINAL_PROMPT='0', TEST_ROOT=str(self.root),
                        PATH=f'{self.bin}:{os.environ["PATH"]}')
        self.git('init', '-b', 'main', str(self.origin))
        (self.origin / '.gitignore').write_text('data/\nbackups/\n.runtime/\n')
        (self.origin / 'webapp.py').write_text('# application\n')
        (self.origin / 'requirements.txt').write_text('old\n')
        self.git('-C', str(self.origin), 'add', '.')
        self.git('-C', str(self.origin), 'commit', '-m', 'initial')
        self.git('clone', str(self.origin), str(self.app))
        self.old = self.git('-C', str(self.app), 'rev-parse', 'HEAD').stdout.strip()
        self.runtime = self.app / '.runtime'
        self.old_env = self.runtime / 'venv-old'
        (self.old_env / 'bin').mkdir(parents=True)
        (self.old_env / 'bin/gunicorn').write_text('#!/bin/sh\nexit 0\n')
        (self.old_env / 'bin/gunicorn').chmod(0o755)
        (self.runtime / 'current').symlink_to(self.old_env)
        (self.app / 'data').mkdir()
        (self.app / 'data/entries.json').write_text('[{"id":"keep-me"}]')
        self.unit = self.root / 'service'
        self.unit.write_text(f'# Managed by Cleaning Tracker install.sh\nWorkingDirectory={self.app}\n')
        (self.root / 'state').write_text('running')
        self.command('systemctl', '''
echo "$*" >> "$TEST_ROOT/service.log"
case "$1" in
 is-active) test "$(cat "$TEST_ROOT/state")" = running ;;
 cat) test -f "$TEST_ROOT/service" ;;
 stop) echo stopped > "$TEST_ROOT/state" ;;
 start|restart) echo running > "$TEST_ROOT/state" ;;
 *) exit 0 ;;
esac
''')
        self.command('python3', '''
if [ "$1" = -c ]; then exit 0; fi
[ "$1" = -m ] && [ "$2" = venv ] || exit 1
mkdir -p "$3/bin"
cat > "$3/bin/python" <<'SH'
#!/bin/bash
if [[ "$*" == *"pip install"* && "${FAIL_PIP:-0}" == 1 ]]; then exit 1; fi
exit 0
SH
printf '#!/bin/sh\\nexit 0\\n' > "$3/bin/gunicorn"
chmod +x "$3/bin/python" "$3/bin/gunicorn"
''')
        self.command('curl', '''
if [[ ${FAIL_HEALTH:-0} == 1 && $(readlink "$TEST_APP/.runtime/current") != "$TEST_APP/.runtime/venv-old" ]]; then exit 1; fi
exit 0
''')
        self.command('sleep', 'exit 0\n')
        # macOS lacks GNU mv's -T. Simulate that one OS primitive, using a real rename.
        self.command('mv', f'exec {sys.executable} -c \'import os,sys; os.replace(sys.argv[1],sys.argv[2])\' "$2" "$3"\n')
        self.env['TEST_APP'] = str(self.app)

    def command(self, name, body):
        p = self.bin / name
        p.write_text('#!/bin/bash\nset -e\n' + body)
        p.chmod(0o755)

    def git(self, *args):
        return subprocess.run(['git', *args], env=self.env, text=True, capture_output=True, check=True)

    def new_release(self):
        (self.origin / 'requirements.txt').write_text('new\n')
        self.git('-C', str(self.origin), 'add', '.')
        self.git('-C', str(self.origin), 'commit', '-m', 'release')
        return self.git('-C', str(self.origin), 'rev-parse', 'HEAD').stdout.strip()

    def run_script(self, script='update.sh', overrides='', **env):
        harness = '''
source "$SCRIPT"
APP_DIR="$TEST_APP"
RUNTIME="$APP_DIR/.runtime"
UNIT_FILE="$TEST_ROOT/service"
preflight() { cd "$APP_DIR"; }
''' + overrides + '\nmain\n'
        return subprocess.run(['bash', '-c', harness], env=dict(self.env, SCRIPT=str(ROOT / script), **env),
                              text=True, capture_output=True)

    def assert_old_running(self):
        self.assertEqual(self.git('-C', str(self.app), 'rev-parse', 'HEAD').stdout.strip(), self.old)
        self.assertEqual((self.runtime / 'current').resolve(), self.old_env)
        self.assertEqual((self.root / 'state').read_text().strip(), 'running')
        self.assertEqual((self.app / 'data/entries.json').read_text(), '[{"id":"keep-me"}]')

    def test_successful_fast_forward_keeps_backup_and_old_environment(self):
        target = self.new_release()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git('-C', str(self.app), 'rev-parse', 'HEAD').stdout.strip(), target)
        self.assertNotEqual((self.runtime / 'current').resolve(), self.old_env)
        self.assertTrue(self.old_env.exists())
        archives = list((self.app / 'backups').glob('*.tar.gz'))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].stat().st_mode & 0o777, 0o600)
        import tarfile
        with tarfile.open(archives[0]) as archive:
            self.assertEqual(archive.extractfile('data/entries.json').read(), b'[{"id":"keep-me"}]')
        self.assertEqual((self.root / 'state').read_text().strip(), 'running')

    def test_dependency_failure_restores_code_and_environment(self):
        self.new_release()
        result = self.run_script(FAIL_PIP='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Previous version is running again', result.stderr)
        self.assert_old_running()

    def test_failed_health_check_restores_old_release(self):
        self.new_release()
        result = self.run_script(FAIL_HEALTH='1')
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_running()

    def test_backup_failure_does_not_change_code(self):
        self.new_release()
        result = self.run_script(overrides='backup_data() { return 1; }')
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_running()

    def test_dirty_checkout_refused_before_service_stop(self):
        self.new_release()
        (self.app / 'webapp.py').write_text('local edits')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('local changes', result.stderr)
        self.assertFalse((self.root / 'service.log').exists())
        self.assertEqual((self.app / 'webapp.py').read_text(), 'local edits')

    def test_diverged_branch_refused(self):
        self.new_release()
        (self.app / 'local.txt').write_text('local commit')
        self.git('-C', str(self.app), 'add', '.')
        self.git('-C', str(self.app), 'commit', '-m', 'local')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('diverged', result.stderr)
        self.assertFalse((self.root / 'service.log').exists())

    def test_new_release_cannot_overwrite_ignored_data(self):
        (self.origin / 'data').mkdir()
        (self.origin / 'data/entries.json').write_text('[]')
        self.git('-C', str(self.origin), 'add', '-f', 'data/entries.json')
        self.git('-C', str(self.origin), 'commit', '-m', 'bad release')
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('track deployment data', result.stderr)
        self.assert_old_running()
        self.assertFalse((self.root / 'service.log').exists())

    def test_no_change_does_not_restart(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Already up to date', result.stdout)
        self.assertFalse((self.root / 'service.log').exists())

    def test_fetch_failure_does_not_stop_service(self):
        self.git('-C', str(self.app), 'remote', 'set-url', 'origin', str(self.root / 'missing'))
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_running()
        self.assertFalse((self.root / 'service.log').exists())

    def prepare_install(self):
        for name in ('apt-get', 'chown', 'useradd', 'ss'):
            self.command(name, 'exit 0\n')
        self.command('runuser', 'shift 3\nexec "$@"\n')

    def test_install_creates_foreground_service_and_preserves_data(self):
        self.prepare_install()
        self.unit.unlink()
        (self.runtime / 'current').unlink()
        result = self.run_script('install.sh')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        content = self.unit.read_text()
        self.assertIn('--workers 1', content)
        self.assertIn('Restart=on-failure', content)
        self.assertNotIn('--daemon', content)
        self.assertIn('ReadWritePaths=' + str(self.app / 'data'), content)
        self.assertEqual((self.app / 'data/entries.json').read_text(), '[{"id":"keep-me"}]')
        self.assertIn('enable cleaning-tracker.service', (self.root / 'service.log').read_text())
        # Running the installer again is safe and does not reset saved data.
        result = self.run_script('install.sh')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.app / 'data/entries.json').read_text(), '[{"id":"keep-me"}]')

    def test_reinstall_failure_restores_previous_unit(self):
        self.prepare_install()
        original_unit = self.unit.read_text()
        result = self.run_script('install.sh', FAIL_HEALTH='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.unit.read_text(), original_unit)
        self.assert_old_running()


if __name__ == '__main__':
    unittest.main()
