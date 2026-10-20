#!/usr/bin/env python3
"""Build a Debian package from the pinned upstream plus the graphs-only overlay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import monitor

NAME = 'cosmic-monitor-graphs'
APP_ID = 'org.local.CosmicMonitorGraphs'


def stage_file(root, name, content, mode=0o644):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)
    path.chmod(mode)
    return path


def package(binary, source, output):
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid VERSION')
    revision = json.loads((ROOT / 'upstream.json').read_text())['ref']
    actual_revision = monitor.run('git', 'rev-parse', 'HEAD', cwd=source, capture=True).stdout.strip()
    actual_patch = monitor.run('git', 'diff', 'HEAD', cwd=source, capture=True).stdout
    if actual_revision != revision or actual_patch != (ROOT / 'patches/graphs-only.patch').read_text():
        raise ValueError('Source does not match pinned revision and overlay')
    architecture = monitor.run('dpkg', '--print-architecture', capture=True).stdout.strip()
    elf = monitor.run('readelf', '-h', str(binary), capture=True).stdout
    expected = {'amd64': 'Advanced Micro Devices X86-64', 'arm64': 'AArch64'}
    if architecture not in expected or expected[architecture] not in elf:
        raise ValueError('Native ELF architecture mismatch or unsupported architecture')
    if (str(Path.home()) + '/').encode() in binary.read_bytes():
        raise ValueError('Personal build paths remain in binary; rebuild with path remapping')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='graphs-deb-') as temporary:
        stage = Path(temporary) / NAME
        stage.mkdir()
        executable = stage_file(stage, 'usr/bin/' + NAME, binary.read_bytes(), 0o755)
        monitor.run('strip', '--strip-unneeded', str(executable))
        stage_file(stage, 'usr/share/applications/' + APP_ID + '.desktop',
                   '[Desktop Entry]\nType=Application\nName=COSMIC Monitor (Graphs)\n'
                   'Name[pt_BR]=Monitor COSMIC (Gráficos)\n'
                   'Comment=System monitor with a graphs-only dashboard\n'
                   'Exec=cosmic-monitor-graphs\nIcon=' + APP_ID + '\n'
                   'Terminal=false\nCategories=System;Monitor;\n'
                   'Keywords=CPU;GPU;RAM;Graphs;Performance;\nStartupNotify=true\n')
        for icon in sorted((source / 'res/icons/hicolor').glob('*/apps/com.system76.CosmicMonitor.svg')):
            stage_file(stage, 'usr/share/icons/hicolor/' + icon.parent.parent.name + '/apps/' + APP_ID + '.svg', icon.read_bytes())
        docs = 'usr/share/doc/' + NAME + '/'
        for name in ('README.md', 'CHANGELOG.md', 'LICENSE'):
            stage_file(stage, docs + name, (ROOT / name).read_bytes())
        stage_file(stage, docs + 'copyright',
                   'Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n'
                   'Upstream-Name: COSMIC Monitor (Graphs)\n'
                   'Source: https://github.com/Arthurregiani/cosmic-monitor-graphs\n\n'
                   'Files: *\nCopyright: Jeremy Soller, System76 and upstream contributors; Arthur Regiani\n'
                   'License: GPL-3.0-only\n See LICENSE in this directory for the full license.\n')
        stage_file(stage, docs + 'build.json', json.dumps({
            'version': version, 'upstream': revision, 'architecture': architecture,
            'binary_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        }, indent=2) + '\n')
        # dpkg-shlibdeps reads package metadata from its working directory.
        debian = Path(temporary) / 'debian'
        debian.mkdir()
        (debian / 'control').write_text('Source: ' + NAME + '\n\nPackage: ' + NAME + '\nArchitecture: any\nDescription: COSMIC graphs dashboard\n')
        dependencies = monitor.run('dpkg-shlibdeps', '-O', str(executable), cwd=temporary, capture=True).stdout.strip()
        if not dependencies.startswith('shlibs:Depends='):
            raise ValueError('Could not determine ELF runtime dependencies')
        dependencies = dependencies.split('=', 1)[1]
        # These libraries are loaded dynamically, so ELF dependency scanning cannot see them.
        dynamic = 'libwayland-client0, libwayland-cursor0, libwayland-egl1, libegl1, libvulkan1, libx11-6, libxcursor1, libxi6, libxrandr2, libxkbcommon-x11-0'
        size = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()) // 1024 + 1
        stage_file(stage, 'DEBIAN/control', f'Package: {NAME}\nVersion: {version}\nSection: utils\nPriority: optional\nArchitecture: {architecture}\nMaintainer: Arthur Regiani <Arthurregiani@users.noreply.github.com>\nInstalled-Size: {size}\nDepends: {dependencies}, {dynamic}\nRecommends: xdg-utils, mesa-vulkan-drivers | vulkan-icd\nHomepage: https://github.com/Arthurregiani/cosmic-monitor-graphs\nDescription: COSMIC System Monitor with a graphs-only dashboard\n Separate community build with persistent graphs-only mode.\n Does not replace the distribution system monitor.\n')
        lines = []
        for path in sorted(stage.rglob('*')):
            if path.is_file() and path.relative_to(stage).parts[0] != 'DEBIAN':
                lines.append(hashlib.md5(path.read_bytes()).hexdigest() + '  ' + str(path.relative_to(stage)))
        stage_file(stage, 'DEBIAN/md5sums', '\n'.join(lines) + '\n')
        # Explicit permissions are required even when the builder uses umask 077.
        for path in [stage, *stage.rglob('*')]:
            if path.is_dir():
                path.chmod(0o755)
        monitor.run('desktop-file-validate', str(stage / 'usr/share/applications' / (APP_ID + '.desktop')))
        destination = output / f'{NAME}_{version}_{architecture}.deb'
        monitor.run('dpkg-deb', '--root-owner-group', '--build', str(stage), str(destination))
    print(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, help='Package an already built, remapped ELF')
    parser.add_argument('--source', type=Path, help='Matching patched upstream checkout')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if bool(args.binary) != bool(args.source):
        parser.error('--binary and --source must be used together')
    if args.binary:
        binary, source = args.binary.resolve(), args.source.resolve()
    else:
        source, _ = monitor.prepare()
        env = os.environ.copy()
        target = ROOT / '.build/package-target'
        env['CARGO_TARGET_DIR'] = str(target)
        env['CARGO_PROFILE_RELEASE_STRIP'] = 'symbols'
        env['RUSTFLAGS'] = env.get('RUSTFLAGS', '') + ' --remap-path-prefix=' + str(Path.home()) + '=/usr/src/build'
        monitor.run('cargo', 'build', '--release', '--locked', cwd=source, env=env)
        binary = target / 'release/cosmic-monitor'
    package(binary, source, args.output.resolve())


if __name__ == '__main__':
    main()
