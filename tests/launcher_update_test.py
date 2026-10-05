import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from launcher_update import apply_and_restart, check_for_update, download_update, extract_launcher_exe, write_replace_script  # noqa: E402
import launcher_update  # noqa: E402


class LauncherUpdateTests(unittest.TestCase):
    def test_extracts_named_launcher_exe(self):
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, 'w') as archive:
            archive.writestr('other.exe', b'nope')
            archive.writestr('Happy Wheels Mod Launcher.exe', b'legacy')
            archive.writestr('JHWML - Mod Launcher.exe', b'ok-launcher')
        with tempfile.TemporaryDirectory() as temp:
            path = extract_launcher_exe(blob.getvalue(), pathlib.Path(temp) / 'out')
            self.assertEqual(path.name, 'JHWML - Mod Launcher.exe')
            self.assertEqual(path.read_bytes(), b'ok-launcher')

    def test_rejects_bad_checksum(self):
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, 'w') as archive:
            archive.writestr('JHWML - Mod Launcher.exe', b'ok-launcher')
        with tempfile.TemporaryDirectory() as temp:
            os.environ['HW_MOD_CACHE'] = temp
            self.addCleanup(lambda: os.environ.pop('HW_MOD_CACHE', None))
            original = launcher_update._read_url
            launcher_update._read_url = lambda _url: blob.getvalue()
            self.addCleanup(lambda: setattr(launcher_update, '_read_url', original))
            with self.assertRaises(ValueError):
                download_update({
                    'version': '0.1.8',
                    'file': 'https://example.com/launcher.zip',
                    'sha256': '0' * 64,
                })

    def test_relative_zip_resolves_against_jhwml_manifest(self):
        blob = io.BytesIO()
        with zipfile.ZipFile(blob, 'w') as archive:
            archive.writestr('JHWML - Mod Launcher.exe', b'ok-launcher')
        payload = blob.getvalue()
        seen = []

        def fake_read(url):
            seen.append(url)
            return payload

        with tempfile.TemporaryDirectory() as temp:
            os.environ['HW_MOD_CACHE'] = temp
            self.addCleanup(lambda: os.environ.pop('HW_MOD_CACHE', None))
            original = launcher_update._read_url
            launcher_update._read_url = fake_read
            self.addCleanup(lambda: setattr(launcher_update, '_read_url', original))
            download_update({
                'version': '0.1.9',
                'file': 'zips/JHWML-Mod-Launcher-0.1.9.zip',
                'sha256': '',
            })
        self.assertEqual(
            seen,
            ['https://raw.githubusercontent.com/MathewRegier/jhwml/main/mod-store/zips/JHWML-Mod-Launcher-0.1.9.zip'],
        )
        self.assertIn('MathewRegier/jhwml', launcher_update.DEFAULT_LAUNCHER_URL)
        self.assertTrue(launcher_update.DEFAULT_LAUNCHER_URL.endswith('/mod-store/launcher.json'))
        self.assertNotIn('happy-wheels-ghost-relay', launcher_update.DEFAULT_LAUNCHER_URL)
        self.assertEqual(
            launcher_update.launcher_manifest_url(),
            launcher_update.DEFAULT_LAUNCHER_URL,
        )

    def test_check_for_update_detects_newer(self):
        original = launcher_update.fetch_launcher_manifest
        launcher_update.fetch_launcher_manifest = lambda _url=None: {
            'version': '0.1.9',
            'file': 'zips/JHWML-Mod-Launcher-0.1.9.zip',
            'sha256': '',
            'notes': '',
            'name': 'JHWML - Mod Launcher',
        }
        self.addCleanup(lambda: setattr(launcher_update, 'fetch_launcher_manifest', original))
        info = check_for_update('0.1.8')
        self.assertEqual(info['version'], '0.1.9')
        self.assertIsNone(check_for_update('0.1.9'))

    def test_writes_replace_script_and_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            os.environ['HW_MOD_CACHE'] = temp
            os.environ['HW_LAUNCHER_DRY_RUN'] = '1'
            self.addCleanup(lambda: os.environ.pop('HW_MOD_CACHE', None))
            self.addCleanup(lambda: os.environ.pop('HW_LAUNCHER_DRY_RUN', None))
            current = pathlib.Path(temp) / 'current.exe'
            newest = pathlib.Path(temp) / 'new.exe'
            current.write_bytes(b'old')
            newest.write_bytes(b'new')
            script = apply_and_restart(newest, current)
            self.assertTrue(script.is_file())
            self.assertEqual(script.suffix, '.vbs')
            text = script.read_text(encoding='utf-8')
            self.assertIn('Win32_Process', text)
            self.assertIn('CopyFile', text)
            self.assertIn('PYINSTALLER_RESET_ENVIRONMENT', text)
            self.assertIn('_PYI_APPLICATION_HOME_DIR', text)
            self.assertNotIn('cmd.exe', text)
            self.assertNotIn('start ""', text)


if __name__ == '__main__':
    unittest.main()
