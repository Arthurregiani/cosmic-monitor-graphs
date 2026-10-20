import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).resolve().parents[1] / 'monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='monitor graphs ')
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir()
        self.environment = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home / 'data with spaces')})
        self.environment.start()
        self.source = Path(self.temp.name) / 'checkout'
        self.source.mkdir()
        self.binary = self.source / 'cosmic-monitor'

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def binary_version(self, version):
        self.binary.write_text('#!/bin/sh\nprintf "%s\\n" ' + version + '\n')
        self.binary.chmod(0o755)

    def launch(self):
        return subprocess.check_output([str(monitor.paths()[1])], text=True).strip()

    def test_move_checkout_update_and_rollback(self):
        self.binary_version('first')
        monitor.install(self.binary, 'first-ref')
        self.source.rename(self.source.with_name('moved checkout'))
        self.assertEqual(self.launch(), 'first')
        self.source.mkdir()
        self.binary_version('second')
        monitor.install(self.binary, 'second-ref')
        self.assertEqual(self.launch(), 'second')
        monitor.rollback()
        self.assertEqual(self.launch(), 'first')
        monitor.rollback()
        self.assertEqual(self.launch(), 'second')
        desktop = monitor.paths()[2]
        if shutil.which('desktop-file-validate'):
            subprocess.run(['desktop-file-validate', str(desktop)], check=True)

    def test_build_or_patch_failure_preserves_install(self):
        self.binary_version('working')
        monitor.install(self.binary, 'working-ref')
        with patch.object(monitor, 'ROOT', Path(self.temp.name)):
            with patch.object(monitor, 'prepare', side_effect=ValueError('Patch incompatible')):
                with self.assertRaises(ValueError):
                    monitor.build_and_install(latest=True)
            with patch.object(monitor, 'prepare', return_value=(self.source, 'candidate')):
                with patch.object(monitor, 'run', side_effect=subprocess.CalledProcessError(1, 'cargo')):
                    with self.assertRaises(subprocess.CalledProcessError):
                        monitor.build_and_install(latest=True)
        self.assertEqual(self.launch(), 'working')

    def test_preserves_original_shortcut(self):
        desktop = monitor.paths()[2]
        desktop.parent.mkdir(parents=True)
        desktop.write_text('original shortcut\n')
        self.binary_version('first')
        monitor.install(self.binary, 'first')
        monitor.install(self.binary, 'first')
        self.assertEqual(desktop.with_suffix('.desktop.backup').read_text(), 'original shortcut\n')
        self.assertFalse((monitor.paths()[0] / 'previous').exists())

    def test_missing_binary_does_not_change_install(self):
        self.binary_version('working')
        monitor.install(self.binary, 'working')
        with self.assertRaises(FileNotFoundError):
            monitor.install(self.binary.with_name('absent'), 'bad')
        self.assertEqual(self.launch(), 'working')


if __name__ == '__main__':
    unittest.main()
