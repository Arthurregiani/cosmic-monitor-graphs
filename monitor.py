#!/usr/bin/env python3
"""Build and install the graphs-only overlay without modifying the system monitor."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
APP_ID = 'org.local.CosmicMonitorGraphs'


def run(*args, cwd=None, capture=False, env=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None, env=env)


def atomic_write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_link(path, target):
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    os.close(fd)
    os.unlink(name)
    try:
        os.symlink(target, name)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def paths():
    home = Path.home()
    data = Path(os.environ.get('XDG_DATA_HOME', home / '.local/share'))
    return data / 'cosmic-monitor-graphs', home / '.local/bin/cosmic-monitor-graphs', data / 'applications' / (APP_ID + '.desktop')


@contextmanager
def install_lock():
    data, _, _ = paths()
    data.mkdir(parents=True, exist_ok=True)
    with (data / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def desktop_quote(value):
    # Exec quoting plus the desktop-entry string escaping layer.
    value = str(value).replace('%', '%%')
    value = ''.join('\\' + c if c in '\\"`$' else c for c in value)
    return '"' + value.replace('\\', '\\\\') + '"'


def install(binary, revision):
    binary = Path(binary).resolve(strict=True)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError('Binary must be an executable file')
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    data, launcher, desktop = paths()
    with install_lock():
        release = data / 'releases' / digest
        release.mkdir(parents=True, exist_ok=True)
        destination = release / 'cosmic-monitor'
        if not destination.exists():
            fd, temporary = tempfile.mkstemp(dir=release)
            os.close(fd)
            try:
                shutil.copyfile(binary, temporary)
                os.chmod(temporary, 0o755)
                os.replace(temporary, destination)
            finally:
                Path(temporary).unlink(missing_ok=True)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise ValueError('Installed binary checksum mismatch')
        atomic_write(release / 'build.json', json.dumps({'upstream': revision, 'sha256': digest}, indent=2) + '\n')
        current = data / 'current'
        old = os.readlink(current) if current.is_symlink() else None
        target = str(destination.relative_to(data))
        # Write the launcher before switching the executable. It is independent of the checkout.
        atomic_write(launcher, '#!/bin/sh\nexec ' + shlex.quote(str(current)) + ' "$@"\n', 0o755)
        entry = ('[Desktop Entry]\nType=Application\nName=COSMIC Monitor (Graphs)\n'
                 'Name[pt_BR]=Monitor COSMIC (Gráficos)\n'
                 'Comment=System monitor with a graphs-only dashboard\n'
                 'Exec=' + desktop_quote(launcher) + '\n'
                 'Icon=com.system76.CosmicMonitor\nTerminal=false\nCategories=System;Monitor;\n'
                 'Keywords=CPU;GPU;RAM;Graphs;Performance;\nStartupNotify=true\n')
        backup = desktop.with_suffix('.desktop.backup')
        if desktop.exists() and not backup.exists():
            shutil.copy2(desktop, backup)
        atomic_write(desktop, entry)
        if old and old != target:
            atomic_link(data / 'previous', old)
        atomic_link(current, target)
    if shutil.which('update-desktop-database'):
        run('update-desktop-database', str(desktop.parent))
    print('Installed:', launcher)
    print('Upstream:', revision, '\nSHA256:', digest)


def rollback():
    with install_lock():
        data, _, _ = paths()
        previous, current = data / 'previous', data / 'current'
        if not previous.is_symlink() or not previous.exists():
            raise ValueError('No previous installation available')
        old, target = os.readlink(current), os.readlink(previous)
        atomic_link(current, target)
        atomic_link(previous, old)
    print('Restored previous binary. Close and reopen the application.')


def prepare(latest=False):
    spec = json.loads((ROOT / 'upstream.json').read_text())
    build = ROOT / '.build'
    build.mkdir(exist_ok=True)
    mirror = build / 'upstream.git'
    if not mirror.exists():
        run('git', 'clone', '--mirror', spec['repository'], str(mirror))
    else:
        run('git', 'fetch', '--prune', 'origin', cwd=mirror)
    ref = spec['branch'] if latest else spec['ref']
    revision = run('git', 'rev-parse', '--verify', ref + '^{commit}', cwd=mirror, capture=True).stdout.strip()
    source = build / ('source-' + revision)
    # This directory is generated, never a developer's checkout.
    if source.exists():
        shutil.rmtree(source)
    run('git', 'clone', '--no-hardlinks', str(mirror), str(source))
    run('git', 'checkout', '--detach', revision, cwd=source)
    run('git', 'apply', '--check', str(ROOT / 'patches/graphs-only.patch'), cwd=source)
    run('git', 'apply', str(ROOT / 'patches/graphs-only.patch'), cwd=source)
    return source, revision


def build_and_install(latest=False, check_only=False):
    with (ROOT / '.build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        source, revision = prepare(latest)
        env = os.environ.copy()
        target = Path(env.get('CARGO_TARGET_DIR', ROOT / '.build/target')).resolve()
        env['CARGO_TARGET_DIR'] = str(target)
        run('cargo', 'build', '--release', '--locked', cwd=source, env=env)
        if check_only:
            print('Compatibility build passed:', revision)
        else:
            install(target / 'release/cosmic-monitor', revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('install', 'check'):
        p = sub.add_parser(command)
        p.add_argument('--latest', action='store_true', help='Try upstream master instead of the tested revision')
    sub.add_parser('rollback')
    sub.add_parser('status')
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as your normal user, without sudo')
    if args.command in ('install', 'check'):
        build_and_install(args.latest, args.command == 'check')
    elif args.command == 'rollback':
        rollback()
    else:
        data, launcher, desktop = paths()
        print('Launcher:', launcher, '\nDesktop:', desktop)
        if (data / 'current').exists():
            print(((data / 'current').resolve().parent / 'build.json').read_text())
        else:
            print('Not installed')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        print('An existing installed binary is preserved if preparation or compilation fails.', file=sys.stderr)
        raise SystemExit(1)
