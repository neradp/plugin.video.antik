import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

LIB = Path(__file__).resolve().parents[1] / 'resources' / 'lib'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, 'argv', ['plugin://plugin.video.antik', '1']):
        spec.loader.exec_module(module)
    return module


class ArchiveSearchTests(unittest.TestCase):
    def setUp(self):
        self.api = MagicMock()
        self.modules = {
            'xbmc': MagicMock(),
            'xbmcaddon': MagicMock(),
            'resources.lib.api': types.SimpleNamespace(API=lambda: self.api),
            'resources.lib.session': types.SimpleNamespace(Session=lambda: MagicMock()),
            'resources.lib.channels': types.SimpleNamespace(Channels=MagicMock()),
            'resources.lib.utils': types.SimpleNamespace(get_kodi_version=lambda: 20),
        }
        self.modules_patch = patch.dict(sys.modules, self.modules)
        self.modules_patch.start()
        self.epg = load_module('test_epg', LIB / 'epg.py')
        self.now = datetime(2026, 11, 23, 16, 0)

    def tearDown(self):
        self.modules_patch.stop()

    def item(self, channel, title, end):
        return {
            'SeriesID': 'series', 'Title': title, 'Channel': channel,
            'Description': 'description', 'Genres': [],
            'Start': (end - timedelta(hours=1)).isoformat(), 'Stop': end.isoformat(),
        }

    def test_per_channel_archive_days_and_playable_time(self):
        recent = self.item('a', 'Život dnes', self.now - timedelta(hours=1))
        future = self.item('a', 'Život neskôr', self.now + timedelta(hours=1))
        old_a = self.item('a', 'Život včera', self.now - timedelta(days=1, hours=1))
        old_b = self.item('b', 'ŽIVOT včera', self.now - timedelta(days=1, hours=1))
        def response(**kwargs):
            day = kwargs['data']['date']
            if day == self.now.date().isoformat():
                return [{'epg': [recent, recent, future]}]
            if day == (self.now.date() - timedelta(days=1)).isoformat():
                return [{'epg': [old_a, old_b]}]
            return []
        self.api.call_api.side_effect = response
        channels = {'a': {'archive_days': 0}, 'b': {'archive_days': 2}}
        result = self.epg.search_archive_epg(channels, 'život', self.now.timestamp())
        self.assertEqual([item['title'] for item in result], ['Život dnes', 'ŽIVOT včera'])
        calls = self.api.call_api.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].kwargs['data']['filter'], ['a', 'b'])
        self.assertEqual(calls[1].kwargs['data']['filter'], ['b'])
        self.assertEqual(calls[2].kwargs['data']['filter'], ['b'])

    def test_fallback_days_batches_and_error(self):
        channels = {str(i): {} for i in range(51)}
        self.api.call_api.return_value = []
        self.assertEqual(self.epg.search_archive_epg(channels, 'x', self.now.timestamp()), [])
        self.assertEqual(self.api.call_api.call_count, 30)
        self.assertEqual(len(self.api.call_api.call_args_list[0].kwargs['data']['filter']), 50)
        self.assertEqual(len(self.api.call_api.call_args_list[1].kwargs['data']['filter']), 1)
        self.api.call_api.return_value = {'err': 'unavailable'}
        with self.assertRaises(ValueError):
            self.epg.search_archive_epg(channels, 'x', self.now.timestamp())

    def test_fourteen_day_boundary(self):
        inside = self.item('a', 'Film', self.now - timedelta(days=14) + timedelta(minutes=1))
        outside = self.item('a', 'Film', self.now - timedelta(days=14, minutes=1))
        def response(**kwargs):
            if kwargs['data']['date'] == (self.now.date() - timedelta(days=14)).isoformat():
                return [{'epg': [inside, outside]}]
            return []
        self.api.call_api.side_effect = response
        result = self.epg.search_archive_epg({'a': {}}, 'film', self.now.timestamp())
        self.assertEqual([item['stop'] for item in result], [inside['Stop']])
        self.assertEqual(self.api.call_api.call_count, 15)

    def test_numeric_and_invalid_titles(self):
        numeric = self.item('a', 12345, self.now - timedelta(hours=1))
        invalid = self.item('a', None, self.now - timedelta(hours=1))
        self.api.call_api.return_value = [{'epg': [numeric, invalid]}]
        result = self.epg.search_archive_epg({'a': {'archive_days': 0}}, '234', self.now.timestamp())
        self.assertEqual([item['title'] for item in result], ['12345'])
        self.modules['xbmc'].log.assert_called_once()


class ArchiveSearchUiTests(unittest.TestCase):
    def setUp(self):
        self.xbmc, self.gui, self.plugin, self.addon = (MagicMock() for _ in range(4))
        self.addon.Addon.return_value.getLocalizedString.side_effect = str
        self.channels, self.search = MagicMock(), MagicMock()
        modules = {
            'xbmc': self.xbmc, 'xbmcgui': self.gui, 'xbmcplugin': self.plugin,
            'xbmcaddon': self.addon,
            'resources.lib.utils': types.SimpleNamespace(
                get_url=lambda **kwargs: kwargs, day_translation={},
                day_translation_short={str(i): str(i) for i in range(7)}),
            'resources.lib.channels': types.SimpleNamespace(Channels=lambda: self.channels),
            'resources.lib.epg': types.SimpleNamespace(
                get_channel_epg=MagicMock(),
                epg_listitem=lambda item, epg, logo: item,
                search_archive_epg=self.search),
        }
        self.modules_patch = patch.dict(sys.modules, modules)
        self.modules_patch.start()
        self.archive = load_module('test_archive', LIB / 'archive.py')
        self.archive._handle = 1

    def tearDown(self):
        self.modules_patch.stop()

    def test_playable_results_and_existing_channel_rules(self):
        keyboard = self.xbmc.Keyboard.return_value
        keyboard.isConfirmed.return_value = True
        keyboard.getText.return_value = ' film '
        self.channels.get_channels_list.return_value = {
            '1': {'id': '1', 'name': 'One', 'archive': False, 'archive_days': 2},
            '2': {'id': '2', 'name': 'Two', 'archive': False, 'archive_days': 0},
        }
        self.search.return_value = [{
            'channel_id': '1', 'title': 'Film', 'startts': 1000000000,
            'endts': 1000003600, 'start': 'start', 'stop': 'stop',
        }]
        self.archive.search_archive('Archive')
        self.assertEqual(list(self.search.call_args.args[0]), ['1'])
        self.assertEqual(self.search.call_args.args[1], 'film')
        args = self.plugin.addDirectoryItem.call_args.args
        self.assertEqual(args[1], {'action': 'play_archive', 'id': '1', 'start': 'start', 'stop': 'stop'})
        self.assertFalse(args[3])
        args[2].setProperty.assert_called_with('IsPlayable', 'true')

    def test_cancel_and_errors(self):
        self.xbmc.Keyboard.return_value.isConfirmed.return_value = False
        self.archive.search_archive('Archive')
        self.search.assert_not_called()
        self.assertFalse(self.plugin.endOfDirectory.call_args.kwargs['succeeded'])
        self.xbmc.Keyboard.return_value.isConfirmed.return_value = True
        self.xbmc.Keyboard.return_value.getText.return_value = 'film'
        self.channels.get_channels_list.return_value = {}
        self.search.side_effect = ValueError('bad response')
        self.archive.search_archive('Archive')
        self.gui.Dialog.return_value.notification.assert_called_once()
        self.assertFalse(self.plugin.endOfDirectory.call_args.kwargs['succeeded'])

    def test_remote_query_skips_keyboard_and_empty_query_fails(self):
        self.channels.get_channels_list.return_value = {}
        self.search.return_value = []
        self.archive.search_archive('Archive', query=' Film ')
        self.xbmc.Keyboard.assert_not_called()
        self.assertEqual(self.search.call_args.args[1], 'Film')
        self.search.reset_mock()
        self.archive.search_archive('Archive', query='  ')
        self.xbmc.Keyboard.assert_not_called()
        self.search.assert_not_called()
        self.gui.Dialog.return_value.notification.assert_called_once()
        self.assertFalse(self.plugin.endOfDirectory.call_args.kwargs['succeeded'])


class ArchiveSearchRouterTests(unittest.TestCase):
    def test_remote_query_and_empty_query_reach_search(self):
        archive = MagicMock()
        addon = MagicMock()
        addon.Addon.return_value.getLocalizedString.return_value = 'Search'
        modules = {
            'xbmcgui': MagicMock(), 'xbmcplugin': MagicMock(), 'xbmcaddon': addon,
            'resources.lib.utils': MagicMock(), 'resources.lib.session': MagicMock(),
            'resources.lib.channels': MagicMock(), 'resources.lib.live': MagicMock(),
            'resources.lib.archive': archive, 'resources.lib.stream': MagicMock(),
            'resources.lib.settings': MagicMock(), 'resources.lib.iptvsc': MagicMock(),
        }
        with patch.dict(sys.modules, modules):
            main = load_module('test_main', LIB.parents[1] / 'main.py')
            main.router('action=search_archive&query=%C5%BDivot')
            archive.search_archive.assert_called_with(label='Search', query='Život')
            main.router('action=search_archive&query=')
            archive.search_archive.assert_called_with(label='Search', query='')
            main.router('action=search_archive&label=Archive')
            archive.search_archive.assert_called_with(label='Archive', query=None)


if __name__ == '__main__':
    unittest.main()
