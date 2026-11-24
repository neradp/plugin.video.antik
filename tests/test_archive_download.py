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
        self.addons.Addon.return_value.getSettingBool.return_value = True
        self.xbmc.Monitor.return_value.waitForAbort.return_value = False
        self.players = []
        players = self.players

        class FakePlayer:
            def __init__(self):
                self.getPlayingFile = MagicMock(return_value='https://example.test/archive/playShow/fake-show|headers')
                self.getTotalTime = MagicMock(return_value=6570.0)
                self.seekTime = MagicMock()
                players.append(self)

        self.xbmc.Player = FakePlayer
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
            'resources.lib.epg': types.SimpleNamespace(get_channel_epg=MagicMock(), epg_listitem=MagicMock()),
            'resources.lib.quality': types.SimpleNamespace(apply_to_listitem=MagicMock()),
            'resources.lib.utils': types.SimpleNamespace(
                get_api_url=lambda: 'https://example.test/', get_isa_version=lambda: 22,
                get_kodi_version=lambda: 22, ua='fake-agent'),
        }
        self.modules_patch = patch.dict(sys.modules, modules)
        self.modules_patch.start()
        self.addCleanup(self.modules_patch.stop)
        epg_spec = importlib.util.spec_from_file_location('test_archive_epg', LIB / 'epg.py')
        self.epg = importlib.util.module_from_spec(epg_spec)
        epg_spec.loader.exec_module(self.epg)
        sys.modules['resources.lib.epg'].epg_listitem = self.epg.epg_listitem
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

    def test_archive_metadata_is_applied_to_the_resolved_item(self):
        metadata = {'title': 'Film & život', 'description': 'Popis relácie',
                    'genres': ['film', 'drama'], 'art': {'poster': 'https://example.test/cover.jpg'}}
        self.addons.Addon.return_value.getSettingBool.return_value = False
        self.stream.play_archive('channel', 'start', 'stop', metadata=json.dumps(metadata))
        item = self.gui.ListItem.return_value
        tag = item.getVideoInfoTag.return_value
        tag.setTitle.assert_called_once_with(metadata['title'])
        tag.setPlot.assert_called_once_with(metadata['description'])
        tag.setGenres.assert_called_once_with(metadata['genres'])
        item.setArt.assert_called_once_with(metadata['art'])
        self.plugin.setResolvedUrl.assert_called_once_with(1, True, item)

    def test_invalid_archive_metadata_is_logged_without_blocking_playback(self):
        self.addons.Addon.return_value.getSettingBool.return_value = False
        self.stream.play_archive('channel', 'start', 'stop', metadata='{"title": []}')
        self.xbmc.log.assert_called_once()
        self.gui.ListItem.return_value.getVideoInfoTag.assert_not_called()
        self.plugin.setResolvedUrl.assert_called_once()

    def test_archive_metadata_supports_older_kodi(self):
        self.stream.get_kodi_version = lambda: 19
        self.epg.get_kodi_version = lambda: 19
        self.addons.Addon.return_value.getSettingBool.return_value = False
        metadata = {'title': 'Film', 'description': 'Popis', 'genres': ['film'], 'art': {}}
        self.stream.play_archive('channel', 'start', 'stop', metadata=json.dumps(metadata))
        item = self.gui.ListItem.return_value
        item.setInfo.assert_any_call('video', {'title': 'Film'})
        item.setInfo.assert_any_call('video', {'plot': 'Popis'})
        item.setInfo.assert_any_call('video', {'genre': ['film']})
        item.setArt.assert_not_called()

    def test_long_archive_uses_stream_minus_epg_duration(self):
        with patch.object(self.stream.ArchiveStartPlayer, 'wait') as wait:
            self.stream.play_archive('channel', '2026-11-23T12:00:00+01:00', '2026-11-23T13:40:00+01:00')
        wait.assert_called_once()
        player = self.players[0]
        player.getTotalTime.side_effect = [0, 6570.0, 6570.0]
        player.seekTime.assert_not_called()
        player.onAVStarted()
        player.wait()
        player.seekTime.assert_called_once_with(570.0)
        self.plugin.setResolvedUrl.assert_called_once()

    def test_short_archive_uses_stream_minus_epg_duration(self):
        for minutes in (5, 15):
            with self.subTest(minutes=minutes):
                with patch.object(self.stream.ArchiveStartPlayer, 'wait'):
                    self.stream.play_archive('channel', '2026-11-23T12:00:00+01:00',
                                             '2026-11-23T12:{:02d}:00+01:00'.format(minutes))
                player = self.players[-1]
                player.getTotalTime.return_value = minutes * 60 + 570
                player.onAVStarted()
                player.wait()
                player.seekTime.assert_called_once_with(570)

    def test_disabled_setting_starts_at_beginning(self):
        self.addons.Addon.return_value.getSettingBool.return_value = False
        self.stream.play_archive('channel', '2026-11-23T12:00:00+01:00', '2026-11-23T13:00:00+01:00')
        self.assertEqual(self.players, [])

    def test_invalid_archive_duration_is_logged_and_starts_at_beginning(self):
        self.stream.play_archive('channel', 'not-a-date', '2026-11-23T13:00:00+01:00')
        self.xbmc.log.assert_called_once()
        self.assertEqual(self.players, [])

    def test_older_kodi_seeks_after_playback_starts(self):
        self.stream.get_kodi_version = lambda: 20
        with patch.object(self.stream.ArchiveStartPlayer, 'wait'):
            self.stream.play_archive('channel', '2026-11-23T12:00:00Z', '2026-11-23T13:00:00Z')
        self.players[0].onAVStarted()
        self.players[0].wait()
        self.players[0].seekTime.assert_called_once_with(2970.0)

    def test_does_not_seek_a_different_item(self):
        player = self.stream.ArchiveStartPlayer('https://example.test/archive/playShow/fake-show', 6000)
        player.getPlayingFile.return_value = 'https://example.test/other-video'
        player.onAVStarted()
        player.wait()
        player.seekTime.assert_not_called()
        self.xbmc.log.assert_called_once()

    def test_does_not_seek_when_stream_is_not_longer_than_epg(self):
        player = self.stream.ArchiveStartPlayer('https://example.test/archive/playShow/fake-show', 6000)
        player.getTotalTime.return_value = 5900
        player.onAVStarted()
        player.wait()
        player.seekTime.assert_not_called()

    def test_does_not_seek_when_duration_never_becomes_available(self):
        player = self.stream.ArchiveStartPlayer('https://example.test/archive/playShow/fake-show', 6000)
        player.getTotalTime.return_value = 0
        player.onAVStarted()
        with patch.object(self.stream.time, 'monotonic', side_effect=[0, 0, 31]):
            player.wait()
        player.seekTime.assert_not_called()
        self.xbmc.log.assert_called_once()

    def test_download_is_not_offset(self):
        self.stream.play_archive('channel', '2026-11-23T12:00:00+01:00', '2026-11-23T13:00:00+01:00',
                                 download=True)
        self.gui.ListItem.assert_not_called()
        self.addons.Addon.return_value.getSettingBool.assert_not_called()


if __name__ == '__main__':
    unittest.main()
