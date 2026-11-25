import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'resources' / 'lib'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, 'argv', ['plugin://plugin.video.antik', '1']):
        spec.loader.exec_module(module)
    return module


class SessionTimeoutTests(unittest.TestCase):
    def run_get_token(self, login_status):
        addon = MagicMock()
        addon.getSetting.side_effect = lambda name: {'username': 'user', 'password': 'pass'}.get(name, '')
        gui = MagicMock()
        requests_session = MagicMock()
        requests_session.get.return_value.status_code = 204
        requests_session.post.return_value.status_code = login_status
        requests_session.cookies.get_dict.return_value = {'session_id': 'sid', 'XSRF-TOKEN': 'csrf'}
        modules = {
            'xbmcaddon': types.SimpleNamespace(Addon=lambda: addon),
            'xbmcgui': gui,
            'requests': types.SimpleNamespace(Session=lambda: requests_session),
            'resources.lib.api': types.SimpleNamespace(API=lambda: types.SimpleNamespace(headers={})),
            'resources.lib.utils': types.SimpleNamespace(
                get_api_url=lambda: 'https://example.test/',
                get_session_cookie=lambda: 'session_id'),
        }
        with patch.dict(sys.modules, modules):
            module = load_module('test_session_timeouts', LIB / 'session.py')
            session = object.__new__(module.Session)
            session.save_session = MagicMock()
            session.register_device = MagicMock()
            if login_status not in [200, 201, 204]:
                with self.assertRaises(SystemExit):
                    session.get_token()
            else:
                session.get_token()
            return requests_session, session

    def test_auth_requests_use_timeout_and_login_status_is_checked(self):
        request_session, session = self.run_get_token(401)
        request_session.get.assert_called_once_with(
            'https://example.test/sanctum/csrf-cookie', headers={}, timeout=30)
        request_session.post.assert_called_once_with(
            'https://example.test/login',
            json={'login': 'user', 'password': 'pass'}, headers={}, timeout=30)
        session.save_session.assert_not_called()

    def test_successful_login_saves_session(self):
        _, session = self.run_get_token(204)
        session.save_session.assert_called_once()
        session.register_device.assert_called_once()


class ChannelManagementTests(unittest.TestCase):
    def load_channels(self):
        modules = {
            'xbmc': MagicMock(),
            'xbmcgui': MagicMock(),
            'xbmcaddon': MagicMock(),
            'xbmcplugin': MagicMock(),
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda path: path),
            'resources.lib.settings': types.SimpleNamespace(Settings=MagicMock()),
            'resources.lib.api': types.SimpleNamespace(API=MagicMock()),
            'resources.lib.session': types.SimpleNamespace(Session=MagicMock()),
            'resources.lib.utils': types.SimpleNamespace(get_url=MagicMock(), plugin_id='plugin.video.antik'),
        }
        with patch.dict(sys.modules, modules):
            return load_module('test_channels_alignment', LIB / 'channels.py')

    def test_decreasing_channels_rejects_collision_and_underflow(self):
        module = self.load_channels()
        channels = MagicMock()
        channels.get_channels_list.return_value = {1: {'name': 'One'}, 2: {'name': 'Two'}}
        with patch.object(module, 'Channels', return_value=channels):
            module.xbmcgui.Dialog.return_value.numeric.return_value = '1'
            module.change_channels_numbers(3, 'decrease')
            channels.change_channels_numbers.assert_not_called()

            channels.get_channels_list.return_value = {}
            module.change_channels_numbers(1, 'decrease')
            channels.change_channels_numbers.assert_not_called()
        self.assertEqual(module.xbmcgui.Dialog.return_value.notification.call_count, 2)

    def test_channel_group_saves_visibility_once_after_batch(self):
        module = self.load_channels()
        channels = MagicMock()
        channels.get_channels_list.return_value = {
            'a': {'name': 'A'},
            'b': {'name': 'B'},
        }
        group = object.__new__(module.Channels_groups)
        group.selected = None
        group.channels = {'Favorites': ['A']}
        group.save_channels_groups = MagicMock()
        with patch.object(module, 'Channels', return_value=channels):
            group.select_group('Favorites')
        channels.set_visibility.assert_has_calls([
            call('a', True, save=False),
            call('b', False, save=False),
        ])
        channels.save_channels.assert_called_once()
        group.save_channels_groups.assert_called_once()

    def test_set_visibility_can_defer_saving(self):
        module = self.load_channels()
        channels = object.__new__(module.Channels)
        channels.channels = {'a': {'visible': True}}
        channels.save_channels = MagicMock()
        channels.set_visibility('a', False, save=False)
        self.assertFalse(channels.channels['a']['visible'])
        channels.save_channels.assert_not_called()
        channels.set_visibility('a', True)
        channels.save_channels.assert_called_once()


class MainMenuArtworkTests(unittest.TestCase):
    def test_main_menu_items_have_icons_and_fanart(self):
        plugin = MagicMock()
        list_items = [MagicMock() for _ in range(3)]
        gui = MagicMock()
        gui.ListItem.side_effect = list_items
        addon = MagicMock()
        addon.Addon.return_value.getAddonInfo.return_value = 'addon-path'
        addon.Addon.return_value.getSetting.return_value = 'false'
        modules = {
            'xbmcgui': gui,
            'xbmcplugin': plugin,
            'xbmcaddon': addon,
            'resources.lib.utils': types.SimpleNamespace(get_url=MagicMock(), check_settings=MagicMock()),
            'resources.lib.session': MagicMock(),
            'resources.lib.channels': MagicMock(),
            'resources.lib.live': MagicMock(),
            'resources.lib.archive': MagicMock(),
            'resources.lib.stream': MagicMock(),
            'resources.lib.settings': MagicMock(),
            'resources.lib.iptvsc': MagicMock(),
            'resources.lib.logo_updater': MagicMock(),
        }
        with patch.dict(sys.modules, modules):
            module = load_module('test_main_menu_artwork', ROOT / 'main.py')
        module._handle = 1
        module.router('')
        plugin.setPluginFanart.assert_called_once_with(
            1, str(Path('addon-path') / 'fanart.jpg'))
        items = [entry.args[2] for entry in plugin.addDirectoryItem.call_args_list]
        self.assertEqual(len(items), 3)
        for item, name in zip(items, ('livetv.png', 'archive.png', 'settings.png')):
            path = str(Path('addon-path') / 'resources' / 'images' / name)
            item.setArt.assert_called_once_with({
                'thumb': path,
                'icon': path,
                'fanart': str(Path('addon-path') / 'fanart.jpg'),
            })
        for query, filename in (
                ('action=list_live&label=Live', 'live_fanart.jpg'),
                ('action=list_archive&label=Archive', 'archive_fanart.jpg'),
                ('action=list_archive_days&id=1&days=1&label=Archive', 'archive_fanart.jpg'),
                ('action=list_program&id=1&day_min=0&label=Archive', 'archive_fanart.jpg'),
                ('action=search_archive&label=Archive', 'archive_fanart.jpg')):
            with self.subTest(query=query):
                plugin.setPluginFanart.reset_mock()
                module.router(query)
                expected = str(Path('addon-path') / 'resources' / 'images' / filename)
                plugin.setPluginFanart.assert_called_once_with(1, expected)
