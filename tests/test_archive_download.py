import base64
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs


LIB = Path(__file__).resolve().parents[1] / 'resources' / 'lib'


class ArchiveDownloadTests(unittest.TestCase):
    def setUp(self):
        self.xbmc, self.gui, self.plugin, self.addons = (MagicMock() for _ in range(4))
        self.session = MagicMock()
        self.session.get_cookies.return_value = {'session': 'fake-cookie', 'XSRF-TOKEN': 'fake-xsrf'}
        self.api = MagicMock()
        self.api.call_api.return_value = {'showIdentifier': 'fake-show'}
        channels = MagicMock()
        channels.get_channels_list.return_value = {'channel': {'radio': 0}}
        modules = {
            'xbmc': self.xbmc, 'xbmcgui': self.gui, 'xbmcplugin': self.plugin, 'xbmcaddon': self.addons,
            'resources.lib.api': types.SimpleNamespace(API=lambda: self.api),
            'resources.lib.session': types.SimpleNamespace(Session=lambda: self.session),
            'resources.lib.channels': types.SimpleNamespace(Channels=lambda: channels),
            'resources.lib.epg': types.SimpleNamespace(get_channel_epg=MagicMock()),
            'resources.lib.quality': types.SimpleNamespace(apply_to_listitem=MagicMock()),
            'resources.lib.utils': types.SimpleNamespace(
                get_api_url=lambda: 'https://example.test/', get_isa_version=lambda: 22,
                get_kodi_version=lambda: 22, ua='fake-agent'),
        }
        self.modules_patch = patch.dict(sys.modules, modules)
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)
        spec = importlib.util.spec_from_file_location('test_archive_stream', LIB / 'stream.py')
        self.stream = importlib.util.module_from_spec(spec)
        with patch.object(sys, 'argv', ['plugin://plugin.video.antik', '1']):
            spec.loader.exec_module(self.stream)

    def test_download_handoff_contains_verified_url_headers_and_title(self):
        title = 'Film, (Život) & spol.'
        self.stream.play_archive('channel', 'start', 'stop', download=True, title=title)
        self.api.call_api.assert_called_once_with(
            api='archive/verify', data={'channelIdentifier': 'channel', 'showStart': 'start', 'showStop': 'stop'},
            method='post', cookies=self.session.get_cookies.return_value)
        command = self.xbmc.executebuiltin.call_args.args[0]
        prefix = 'RunScript(script.stream.saver,add,'
        self.assertTrue(command.startswith(prefix) and command.endswith(')'))
        encoded = command[len(prefix):-1]
        payload = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        self.assertEqual(payload['title'], title)
        url, headers = payload['url'].split('|', 1)
        self.assertEqual(url, 'https://example.test/archive/playShow/fake-show')
        self.assertEqual(parse_qs(headers), {'Cookie': ['session=fake-cookie; XSRF-TOKEN=fake-xsrf'],
                                              'User-Agent': ['fake-agent'], 'Referer': ['https://webtv.tv']})
        self.plugin.endOfDirectory.assert_called_once_with(1, succeeded=True)
        self.plugin.setResolvedUrl.assert_not_called()

    def test_existing_playback_and_failed_verification(self):
        self.stream.play_archive('channel', 'start', 'stop')
        self.plugin.setResolvedUrl.assert_called_once()
        self.xbmc.executebuiltin.assert_not_called()
        self.api.call_api.return_value = {}
        self.stream.play_archive('channel', 'start', 'stop', download=True)
        self.xbmc.executebuiltin.assert_not_called()
        self.plugin.endOfDirectory.assert_called_once_with(1, succeeded=False)
        self.gui.Dialog.return_value.notification.assert_called_once()


if __name__ == '__main__':
    unittest.main()
