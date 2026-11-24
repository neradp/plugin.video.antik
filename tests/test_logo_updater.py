import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


LIB = Path(__file__).resolve().parents[1] / 'resources' / 'lib'
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'
PNG = b'\x89PNG\r\n\x1a\n' + b'test'


class LogoUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.addon = MagicMock()
        self.addon.getLocalizedString.side_effect = lambda value: {
            30056: 'Updated: {0}, errors: {1}', 30057: 'Canceled: {0}, errors: {1}',
        }.get(value, str(value))
        self.gui = MagicMock()
        self.gui.DialogProgress.return_value.iscanceled.return_value = False
        self.channels = MagicMock()
        self.requests = MagicMock()
        self.requests.RequestException = type('RequestException', (Exception,), {})
        modules = {
            'requests': self.requests, 'xbmc': MagicMock(), 'xbmcgui': self.gui,
            'xbmcaddon': types.SimpleNamespace(Addon=lambda: self.addon),
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda path: path),
            'resources.lib.channels': types.SimpleNamespace(Channels=lambda: self.channels),
        }
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        spec = importlib.util.spec_from_file_location('test_logo_update_module', LIB / 'logo_updater.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addon_path = Path(self.temp.name)
        self.channel = {'id': 'wau', 'name': 'JOJ Krimi', 'logo': 'https://example.test/logo.svg'}
        self.response = self.requests.get.return_value.__enter__.return_value
        self.response.url = self.channel['logo']
        self.response.iter_content.return_value = [SVG]

    def test_download_validation(self):
        self.assertEqual(self.module.download_svg(self.channel['logo']), SVG)
        for data in (b'not svg', b'<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>',
                     b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/a"/></svg>'):
            self.response.iter_content.return_value = [data]
            with self.assertRaises((ValueError, self.module.ET.ParseError)):
                self.module.download_svg(self.channel['logo'])

    def test_converts_and_retains_original_on_failure(self):
        def convert(command, **kwargs):
            Path(command[-1][len('PNG32:'):]).write_bytes(PNG)
        with patch.object(self.module.subprocess, 'run', side_effect=convert):
            self.module.update_logo(self.channel, str(self.addon_path), 'magick')
        png = self.addon_path / 'resources' / 'stations' / 'png' / 'wau.png'
        svg = self.addon_path / 'resources' / 'stations' / 'svg' / 'wau.svg'
        self.assertEqual(png.read_bytes(), PNG)
        self.assertEqual(svg.read_bytes(), SVG)
        with patch.object(self.module.subprocess, 'run', side_effect=self.module.subprocess.TimeoutExpired('magick', 60)):
            with self.assertRaises(self.module.subprocess.TimeoutExpired):
                self.module.update_logo(self.channel, str(self.addon_path), 'magick')
        self.assertEqual(png.read_bytes(), PNG)
        self.assertEqual(svg.read_bytes(), SVG)

    def test_bad_id_never_downloads(self):
        self.channel['id'] = '../other'
        with self.assertRaises(ValueError):
            self.module.update_logo(self.channel, str(self.addon_path), 'magick')
        self.requests.get.assert_not_called()

    def test_update_reports_partial_failures_and_closes_progress(self):
        self.channels.get_channels.return_value = {'a': self.channel, 'b': dict(self.channel, id='bad')}
        self.addon.getAddonInfo.return_value = str(self.addon_path)
        with patch.object(self.module, 'find_magick', return_value='magick'), \
             patch.object(self.module, 'update_logo', side_effect=[None, ValueError('failed')]):
            self.module.update_station_logos()
        self.gui.DialogProgress.return_value.close.assert_called_once()
        self.assertEqual(self.gui.Dialog.return_value.notification.call_args.args[1], 'Updated: 1, errors: 1')

    def test_missing_magick_is_reported_without_requesting_channels(self):
        with patch.object(self.module, 'find_magick', return_value=None):
            self.module.update_station_logos()
        self.channels.get_channels.assert_not_called()
        self.assertEqual(self.gui.Dialog.return_value.notification.call_args.args[1], '30055')


if __name__ == '__main__':
    unittest.main()
