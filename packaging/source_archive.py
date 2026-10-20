#!/usr/bin/env python3
"""Archive complete build sources, including vendored Cargo dependencies."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Patched upstream source used for the package')
    args = parser.parse_args()
    source = args.source.resolve()
    version = (ROOT / 'VERSION').read_text().strip()
    destination = ROOT / 'dist' / f'cosmic-monitor-graphs-{version}-source.tar.xz'
    destination.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='graphs-source-') as temporary:
        tree = Path(temporary) / f'cosmic-monitor-graphs-{version}'
        upstream = tree / 'upstream'
        shutil.copytree(source, upstream, ignore=shutil.ignore_patterns('.git', 'target', 'vendor'))
        result = subprocess.run(['cargo', 'vendor', '--locked', '--versioned-dirs', str(upstream / 'vendor')],
                                cwd=source, check=True, text=True, stdout=subprocess.PIPE)
        config = upstream / '.cargo/config.toml'
        config.parent.mkdir(exist_ok=True)
        config.write_text(result.stdout.replace(str(upstream / 'vendor'), 'vendor'))
        overlay = tree / 'overlay'
        overlay.mkdir()
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        for name in filter(None, tracked):
            path = ROOT / name
            if path.is_file():
                target = overlay / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        (tree / 'BUILDING.txt').write_text(
            'COSMIC Monitor Graphs ' + version + '\n\n'
            'Complete patched upstream source and Cargo dependencies are in upstream/.\n'
            'Overlay, package tooling and documentation are in overlay/.\n'
            'On Pop!_OS/Ubuntu 24.04 install Rust >= 1.95, pkg-config, libxkbcommon-dev,\n'
            'libwayland-dev, libudev-dev, libfontconfig1-dev and libegl1-mesa-dev.\n'
            'Then: cd upstream && cargo build --release --locked --offline\n'
            'For the exact package build flags, see overlay/packaging/build_deb.py.\n'
            'Source and license notices for dependencies are retained inside vendor/.\n')
        # Validate that vendoring is sufficient for Cargo to resolve the locked graph offline.
        subprocess.run(['cargo', 'metadata', '--locked', '--offline', '--format-version=1'],
                       cwd=upstream, check=True, stdout=subprocess.DEVNULL)
        with tarfile.open(destination, 'w:xz', preset=3) as archive:
            def normalize(info):
                info.uid = info.gid = 0
                info.uname = info.gname = 'root'
                info.mode = 0o755 if info.isdir() or info.mode & 0o111 else 0o644
                return info
            archive.add(tree, arcname=tree.name, filter=normalize)
    print(destination)


if __name__ == '__main__':
    main()
