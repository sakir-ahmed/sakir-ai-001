#!/usr/bin/env python3
"""Compare deployed core files with a Git revision, printing paths/status only.

Never traverses secrets, environment files, runtime state or customer knowledge.
Read-only: does not deploy, fetch, modify services or print file contents.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

CORE_DIRS = {'lib', 'scripts', 'systemd', 'hostops', 'services', 'tools', 'hermes', 'db', 'config'}
CORE_FILES = {'install.sh', 'compose.yml', 'versions.env'}
EXCLUDED = {'secrets', 'data', 'knowledge', 'backups', 'outbox', '.git', '__pycache__', '.pytest_cache', '.venv', 'venv', 'queue', 'done'}


def allowed(path):
    parts = Path(path).parts
    return bool(parts) and not any(x in EXCLUDED for x in parts) and not any(x.startswith('.env') for x in parts) and (parts[0] in CORE_DIRS or path in CORE_FILES) and not path.endswith(('.pyc', '.key', '.age', '.candidate')) and '.pre-' not in path


def audit(source, installed, revision):
    source, installed = source.resolve(), installed.resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args])
    commit = git('rev-parse', '--verify', revision + '^{commit}').decode().strip()
    entries = git('ls-tree', '-r', '--name-only', commit).decode().splitlines()
    tracked = {name for name in entries if allowed(name)}
    counts = {'MATCH': 0, 'MODIFIED': 0, 'MISSING': 0, 'EXTRA': 0, 'SYMLINK': 0}
    print('Reference commit:', commit)
    for name in sorted(tracked):
        path = installed / name
        if path.is_symlink() or any((installed / parent).is_symlink() for parent in Path(name).parents):
            status = 'SYMLINK'
        elif not path.is_file():
            status = 'MISSING'
        else:
            expected = hashlib.sha256(git('show', commit + ':' + name)).digest()
            status = 'MATCH' if hashlib.sha256(path.read_bytes()).digest() == expected else 'MODIFIED'
        counts[status] += 1
        if status != 'MATCH':
            print(status, name)
    # Prune runtime directories before descent; never follow symlink directories.
    for directory in sorted(CORE_DIRS):
        base = installed / directory
        if base.is_symlink():
            print('SYMLINK_DIRECTORY', directory)
            counts['SYMLINK'] += 1
            continue
        if not base.exists():
            continue
        for current, directories, files in os.walk(base, followlinks=False):
            directories[:] = [d for d in directories if d not in EXCLUDED and not d.startswith('.env')]
            for filename in files:
                path = Path(current) / filename
                name = path.relative_to(installed).as_posix()
                if allowed(name) and name not in tracked:
                    counts['EXTRA'] += 1
                    print('EXTRA', name)
    print('Summary:', ' '.join(f'{k}={v}' for k, v in counts.items()))
    print('Excluded: secrets, .env*, runtime data, knowledge, rollback/candidate files; contents never printed.')
    return int(any(counts[k] for k in counts if k != 'MATCH'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Existing Git checkout')
    parser.add_argument('--installed', type=Path, default=Path('/opt/sakir-ai'))
    parser.add_argument('--revision', default='HEAD')
    args = parser.parse_args()
    sys.exit(audit(args.source, args.installed, args.revision))
