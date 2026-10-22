import ast
import configparser
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from config import Config
from server import Server


class TrayConfigTests(unittest.TestCase):
    def load_config(self, setting):
        text = "[config]\nkey=test\nsave_path=\nport=53843\nbasic_notifier=0\ndevice_id=abc123\nlanguage=en\n"
        if setting is not None:
            text += f"show_icon={setting}\n"
        text += "[info]\nversion=1.7\n"
        def read(parser, *args, **kwargs):
            parser.read_string(text)
        with patch.object(configparser.ConfigParser, 'read', autospec=True, side_effect=read):
            return Config('unused.ini')

    def test_default_visible_for_existing_configs(self):
        self.assertTrue(self.load_config(None).show_icon)

    def test_explicit_visible(self):
        self.assertTrue(self.load_config('1').show_icon)

    def test_explicit_hidden(self):
        self.assertFalse(self.load_config(' 0 ').show_icon)

    def test_gui_save_preserves_config_only_setting(self):
        cfg = self.load_config('0')
        result = cfg._build_updated_config_content('[config]\nshow_icon = 0\nkey = old\n', {'key': 'new'})
        self.assertIn('show_icon = 0', result)
        self.assertIn('key = new', result)

    def main_loop(self, visible):
        tree = ast.parse(Path('AirDropPlus.py').read_text(encoding='utf-8-sig'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_main_loop')
        scope = {'config': SimpleNamespace(show_icon=visible), 'create_icon': Mock(), 'stop_event': Mock()}
        scope['stop_event'].wait.side_effect = [False, True]
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'AirDropPlus.py', 'exec'), scope)
        scope['run_main_loop']()
        return scope

    def test_visible_mode_runs_tray(self):
        scope = self.main_loop(True)
        scope['create_icon'].assert_called_once_with()
        scope['stop_event'].wait.assert_not_called()

    def test_hidden_mode_keeps_running_without_tray(self):
        scope = self.main_loop(False)
        scope['create_icon'].assert_not_called()
        self.assertEqual(scope['stop_event'].wait.call_count, 2)


class ShortcutCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cfg = SimpleNamespace(language='en', key='test', version='1.7', device_id='abc123', save_path='.')
        cls.server = Server(cfg, Mock())
        cls.server._submit_notify = Mock()
        cls.client = cls.server.app.test_client()

    def request(self, version, key='test'):
        return self.client.post('/file/send/list', data={'file_list': 'sample.png'},
                                headers={'Authorization': key, 'ShortcutVersion': version})

    def test_existing_and_current_shortcuts(self):
        for version in ['1.4', '1.5', '1.6', '1.7', '1.5.2', '1.7.0', ' 1.6 ']:
            with self.subTest(version=version):
                self.assertEqual(self.request(version).status_code, 200)

    def test_newer_minimum_rejected(self):
        for version in ['1.7.1', '1.8', '1.10', '2.0']:
            with self.subTest(version=version):
                self.assertEqual(self.request(version).status_code, 400)

    def test_malformed_version_rejected(self):
        for version in ['abc', '1..5', '-1.5', '1.5beta', '1.5.0.0.0']:
            with self.subTest(version=version):
                self.assertEqual(self.request(version).status_code, 400)

    def test_numeric_version_comparison(self):
        for current, minimum, expected in [('1.10', '1.9', True), ('1.9', '1.10', False),
                                           ('1.7', '1.7.0', True), ('1.7.0', '1.7', True),
                                           ('1.7.1', '1.7', True), ('1.7', '1.7.1', False)]:
            with self.subTest(current=current, minimum=minimum):
                stub = SimpleNamespace(config=SimpleNamespace(version=current), parse_version=Server.parse_version)
                self.assertEqual(Server.supports_shortcut(stub, minimum), expected)

    def test_bad_key_rejected(self):
        self.assertEqual(self.request('1.7', key='wrong').status_code, 401)

    def test_missing_version_rejected(self):
        self.assertEqual(self.request('').status_code, 400)


if __name__ == '__main__':
    unittest.main()
