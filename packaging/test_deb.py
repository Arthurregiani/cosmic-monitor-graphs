#!/usr/bin/env python3
"""Install/remove package in an isolated dpkg root, without changing the host."""
from pathlib import Path
import argparse
import hashlib
import subprocess
import tempfile


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    with tempfile.TemporaryDirectory(prefix='graphs-dpkg-') as temporary:
        root = Path(temporary) / 'root'
        (root / 'var/lib/dpkg').mkdir(parents=True)
        (root / 'var/lib/dpkg/status').touch()
        (root / 'var/log').mkdir(parents=True)
        log = '--log=' + str(root / 'var/log/dpkg.log')
        # No maintainer scripts are shipped; dpkg's install/remove only touches this root.
        control = Path(temporary) / 'control'
        run('dpkg-deb', '-e', str(package), str(control))
        assert {p.name for p in control.iterdir()} == {'control', 'md5sums'}
        run('fakeroot', 'dpkg', '--root=' + str(root), log, '--force-depends', '-i', str(package))
        binary = root / 'usr/bin/cosmic-monitor-graphs'
        assert binary.is_file() and binary.stat().st_mode & 0o777 == 0o755
        desktop = root / 'usr/share/applications/org.local.CosmicMonitorGraphs.desktop'
        assert desktop.stat().st_mode & 0o777 == 0o644
        run('desktop-file-validate', str(desktop))
        for line in (control / 'md5sums').read_text().splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.md5((root / name).read_bytes()).hexdigest() == digest
        assert not (root / 'usr/bin/cosmic-monitor').exists()
        listing = run('dpkg-deb', '-c', str(package), stdout=subprocess.PIPE).stdout
        assert all('root/root' in line for line in listing.splitlines())
        run('fakeroot', 'dpkg', '--root=' + str(root), log, '--remove', 'cosmic-monitor-graphs')
        assert not binary.exists() and not desktop.exists()
        print('PASS: isolated dpkg install, payload checksums, permissions, ownership and removal')
    # This asks APT to resolve real runtime dependencies but does not install anything.
    run('apt-get', '--simulate', 'install', str(package))


if __name__ == '__main__':
    main()
