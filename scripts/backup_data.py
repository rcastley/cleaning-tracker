"""Private, consistent backups and validated restores for the managed service."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('config.json', 'entries.json', 'expenses.json', 'clients.json', 'invoices.json')
SERVICE = 'cleaning-tracker.service'
UNIT = Path('/etc/systemd/system') / SERVICE
LOCK = Path('/run/lock/cleaning-tracker-deploy.lock')


def systemctl(*args, check=True):
    return subprocess.run(['systemctl', *args], check=check, capture_output=True, text=True)


@contextmanager
def stopped(offline=False):
    if offline:
        yield
        return
    if os.geteuid() != 0:
        raise ValueError('Run with sudo for the managed service, or stop the app and use --offline.')
    unit = UNIT.read_text()
    if '# Managed by Cleaning Tracker install.sh' not in unit.splitlines() or f'WorkingDirectory={ROOT}' not in unit.splitlines():
        raise ValueError('Service does not belong to this checkout. Stop the app and use --offline.')
    with LOCK.open('a') as lock:
        # Share the deployment lock: cron never snapshots a partially deployed app.
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = systemctl('show', '--property=ActiveState', '--value', SERVICE).stdout.strip()
        if state not in ('active', 'inactive', 'failed'):
            raise ValueError(f'Service is transitioning ({state}); retry later.')
        restart = state == 'active'
        try:
            systemctl('stop', SERVICE)
            yield
        finally:
            if restart:
                systemctl('start', SERVICE)
                systemctl('is-active', '--quiet', SERVICE)


def private_backups():
    directory = ROOT / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    return directory


def snapshot(prefix='backup_', validate_data=True):
    directory = private_backups()
    destination = directory / (prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.tar.gz')
    payload = {name: (ROOT / 'data' / name).read_bytes() for name in FILES if (ROOT / 'data' / name).exists()}
    if validate_data and not payload:
        raise ValueError('No saved data files found; no backup created or expired.')
    if validate_data:
        for name, content in payload.items():
            validate(name, content)
    with tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
        temporary = Path(output.name)
    try:
        with tarfile.open(temporary, 'w:gz') as archive:
            for name, content in payload.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(content), 0o600
                archive.addfile(info, io.BytesIO(content))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Backup created: {destination}', flush=True)
    return destination


def validate(name, content):
    def invalid_constant(value):
        raise ValueError(f'Invalid number: {value}')
    value = json.loads(content, parse_constant=invalid_constant)
    if not isinstance(value, dict if name == 'config.json' else list):
        raise ValueError(f'Invalid data structure in {name}')


def read_archive(path):
    payload = {}
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive.getmembers():
            name = member.name.removeprefix('./')
            if member.isdir() and name.rstrip('/') in ('data', '.'):
                continue
            if not member.isfile() or name.startswith('/') or '..' in Path(name).parts:
                raise ValueError(f'Unsafe archive member: {member.name}')
            if name == 'data/invoices.lock':
                continue
            normalized = name.removeprefix('data/')
            if normalized not in FILES or normalized in payload:
                raise ValueError(f'Unexpected or duplicate archive member: {member.name}')
            content = archive.extractfile(member).read()
            validate(normalized, content)
            payload[normalized] = content
    if not payload:
        raise ValueError('Archive contains no recognised data files.')
    return payload


def write_record(path, content):
    owner = path.parent.stat()
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
            if os.geteuid() == 0:
                os.fchown(output.fileno(), owner.st_uid, owner.st_gid)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def restore(payload):
    data = ROOT / 'data'
    data.mkdir(mode=0o700, exist_ok=True)
    snapshot('pre-restore-', validate_data=False)
    original = {name: (data / name).read_bytes() if (data / name).exists() else None for name in payload}
    try:
        for name, content in payload.items():
            write_record(data / name, content)
    except Exception:
        for name, content in original.items():
            if content is None:
                (data / name).unlink(missing_ok=True)
            else:
                write_record(data / name, content)
        raise
    missing = sorted(set(FILES) - payload.keys())
    print('Restore complete: ' + ', '.join(sorted(payload)))
    if missing:
        print('Not present in this backup; existing files preserved: ' + ', '.join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('backup', 'scheduled', 'restore', 'list'))
    parser.add_argument('archive', nargs='?')
    parser.add_argument('--offline', action='store_true', help='App is already stopped (unmanaged/local installs).')
    args = parser.parse_args()
    if args.command == 'list':
        files = sorted((ROOT / 'backups').glob('*.tar.gz'))
        print('\n'.join(str(path) for path in files) if files else 'No backups found.')
        return
    payload = None
    if args.command == 'restore':
        if not args.archive:
            parser.error('restore requires an archive path or backup filename')
        path = Path(args.archive)
        if not path.is_file():
            path = ROOT / 'backups' / args.archive
        payload = read_archive(path)  # Validate before stopping or modifying anything.
        if input('Replace the matching data files with this backup? [y/N] ').lower() != 'y':
            print('Cancelled.')
            return
    with stopped(args.offline):
        if payload is not None:
            restore(payload)
        else:
            snapshot('scheduled-' if args.command == 'scheduled' else 'backup_')
            if args.command == 'scheduled':
                # Only scheduled archives expire, and only after a successful snapshot.
                for old in sorted((ROOT / 'backups').glob('scheduled-*.tar.gz'), reverse=True)[30:]:
                    old.unlink()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Backup operation failed: {error}')
