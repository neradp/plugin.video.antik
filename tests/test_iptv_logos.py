import html
import importlib.util
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch


LIB = Path(__file__).resolve().parents[1] / 'resources' / 'lib'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CapturedFile:
    def __init__(self):
        self.content = bytearray()

    def write(self, data):
        self.content.extend(data)

    def close(self):
        pass


class IptvLogoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='antik & ')
        self.addCleanup(self.temp.cleanup)
        self.addon_path = Path(self.temp.name)
        logos = self.addon_path / 'resources' / 'stations' / 'png'
        logos.mkdir(parents=True)
        self.local_logo = logos / 'wau.png'
        self.local_logo.write_bytes(b'png')
        self.channel = {'id': 'wau', 'name': 'JOJ Krimi', 'logo': 'https://example.test/old.svg',
                        'archive': True}
        self.settings = {'output_dir': 'output', 'use_picons_server': 'false',
                         'catchup_mode': 'default', 'isa': 'false', 'all_channels': 'false',
                         'picons_server_ip': '127.0.0.1', 'picons_server_port': '8000'}
        self.addon = MagicMock()
        self.addon.getSetting.side_effect = self.settings.get
        self.addon.getAddonInfo.return_value = str(self.addon_path)
        self.channels = MagicMock()
        self.channels.get_channels_list.side_effect = lambda key, **kwargs: (
            {1: self.channel} if key == 'channel_number' else {'wau': self.channel})
        self.files = {}
        def open_file(name, mode):
            self.files[name] = CapturedFile()
            return self.files[name]
        self.vfs = types.SimpleNamespace(translatePath=lambda path: path, File=open_file)
        self.gui = MagicMock()
        modules = {
            'xbmc': MagicMock(), 'xbmcgui': self.gui,
            'xbmcaddon': types.SimpleNamespace(Addon=lambda: self.addon),
            'xbmcvfs': self.vfs,
            'resources.lib.channels': types.SimpleNamespace(Channels=lambda: self.channels),
            'resources.lib.utils': types.SimpleNamespace(
                plugin_id='plugin.video.antik', replace_by_html_entity=html.escape),
            'resources.lib.epg': types.SimpleNamespace(get_channels_epg=lambda **kwargs: [{
                'channel_id': 'wau', 'title': 'Film & more', 'description': 'Description',
                'genres': ['Drama'], 'startts': 1700000000, 'endts': 1700003600,
            }]),
        }
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        sys.modules['resources.lib.station_logos'] = load_module('test_station_logos', LIB / 'station_logos.py')
        self.iptv = load_module('test_iptvsc', LIB / 'iptvsc.py')
        self.iptv.save_file_test = lambda: 1

    def generate(self):
        self.iptv.generate_playlist('playlist')
        self.iptv.generate_epg('epg', show_progress=False)
        playlist = self.files['playlist'].content.decode('utf-8')
        xml = self.files['epg'].content.decode('utf-8')
        self.assertIn('catchup-days="7"', playlist)
        self.assertIn('plugin://plugin.video.antik/?action=iptsc_play_stream&id=' + self.channel['id'], playlist)
        root = ET.fromstring(xml)
        self.assertEqual(root.find('programme/title').text, 'Film & more')
        return playlist, root.find('channel/icon').attrib['src']

    def test_local_logo_and_xml_escaping(self):
        playlist, icon = self.generate()
        self.assertIn('tvg-logo="' + str(self.local_logo) + '"', playlist)
        self.assertEqual(icon, str(self.local_logo))

    def test_picons_has_priority(self):
        self.settings['use_picons_server'] = 'true'
        playlist, icon = self.generate()
        expected = 'http://127.0.0.1:8000/picons/JOJ%20Krimi'
        self.assertIn('tvg-logo="' + expected + '"', playlist)
        self.assertEqual(icon, expected)

    def test_missing_local_logo_uses_original_url_or_empty(self):
        self.channel['id'] = 'missing'
        playlist, icon = self.generate()
        self.assertIn('tvg-logo="https://example.test/old.svg"', playlist)
        self.assertEqual(icon, 'https://example.test/old.svg')
        self.channel['logo'] = None
        playlist, icon = self.generate()
        self.assertIn('tvg-logo=""', playlist)
        self.assertEqual(icon, '')


if __name__ == '__main__':
    unittest.main()
