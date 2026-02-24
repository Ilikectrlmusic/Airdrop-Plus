import configparser
import locale
import os
import re
import secrets
import string
import tempfile

from win_elevate import TASK_WRITE_CONFIG, run_elevated_task


def write_config_content_from_file(source_path: str, destination_path: str):
    with open(source_path, 'rb') as source_file:
        content_bytes = source_file.read()
    with open(destination_path, 'wb') as destination_file:
        destination_file.write(content_bytes)


class Config:
    def __init__(self, config_path):
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding='utf-8')

        self.config_path = config_path
        self.key = self.config.get('config', 'key')
        self.save_path = self.config.get('config', 'save_path')
        if self.save_path == '' or self.save_path is None:
            self.save_path = os.path.join(os.path.expanduser('~'), 'Downloads')

        self.port = int(self.config.get('config', 'port'))
        self.basic_notifier = False if self.config.get('config', 'basic_notifier')=='0' else True
        self.startup_notify = self.config.get('config', 'startup_notify', fallback='1').strip() != '0'

        self.version = self.config.get('info', 'version')
        self.device_id = self._load_or_create_device_id()
        self.auto_start = self.config.get('config', 'auto_start', fallback='1').strip() != '0'
        self.language = self._load_or_init_language()
        self.is_first_run = self._first_run

    @staticmethod
    def _is_valid_device_id(value: str) -> bool:
        return bool(re.fullmatch(r'[a-z0-9]{6}', value))

    @staticmethod
    def _new_device_id() -> str:
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(6))

    def _load_or_create_device_id(self) -> str:
        raw = self.config.get('config', 'device_id', fallback='').strip().lower()
        if self._is_valid_device_id(raw):
            self._first_run = False
            return raw
        self._first_run = True
        device_id = self._new_device_id()
        try:
            self._persist_config_key('device_id', device_id)
        except PermissionError:
            # If config.ini is read-only, keep running with the generated ID in memory.
            pass
        return device_id

    @staticmethod
    def _normalize_language(value: str) -> str:
        raw = (value or '').strip().lower()
        if raw.startswith('en'):
            return 'en'
        if raw.startswith('zh'):
            return 'zh'
        return ''

    @staticmethod
    def _detect_default_language() -> str:
        candidates: list[str] = []
        default_locale = locale.getdefaultlocale()
        if isinstance(default_locale, tuple):
            if default_locale[0]:
                candidates.append(default_locale[0])
        current_locale = locale.getlocale()
        if isinstance(current_locale, tuple):
            if current_locale[0]:
                candidates.append(current_locale[0])
        for env_name in ('LANG', 'LC_ALL', 'LANGUAGE'):
            env_val = os.environ.get(env_name, '')
            if env_val:
                candidates.append(env_val)

        for candidate in candidates:
            normalized = candidate.replace('-', '_').lower()
            if normalized.startswith('en'):
                return 'en'
            if normalized.startswith('zh'):
                return 'zh'
        return 'zh'

    def _load_or_init_language(self) -> str:
        raw = self.config.get('config', 'language', fallback='')
        normalized = self._normalize_language(raw)
        if normalized == '':
            normalized = self._detect_default_language()
            try:
                self._persist_config_key('language', normalized)
            except PermissionError:
                pass
        return normalized

    def set_auto_start(self, enabled: bool):
        normalized = bool(enabled)
        self._persist_config_key('auto_start', '1' if normalized else '0')
        self.auto_start = normalized

    def set_startup_notify(self, enabled: bool):
        normalized = bool(enabled)
        self._persist_config_key('startup_notify', '1' if normalized else '0')
        self.startup_notify = normalized

    def set_language(self, language: str):
        normalized = self._normalize_language(language)
        if normalized == '':
            raise ValueError('language must be zh or en')
        self._persist_config_key('language', normalized)
        self.language = normalized

    def set_key(self, key: str):
        normalized = (key or '').strip()
        if normalized == '':
            raise ValueError('密钥不能为空')
        self._persist_config_key('key', normalized)
        self.key = normalized

    def set_port(self, port: int):
        value = int(port)
        if value < 1 or value > 65535:
            raise ValueError('端口范围必须为 1-65535')
        self._persist_config_key('port', str(value))
        self.port = value

    def set_save_path(self, path: str):
        default_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        normalized = (path or '').strip()
        if normalized == '' or os.path.normcase(normalized) == os.path.normcase(default_path):
            self._persist_config_key('save_path', '')
            self.save_path = default_path
            return
        self._persist_config_key('save_path', normalized)
        self.save_path = normalized

    def save_settings(
        self,
        key: str,
        port: int,
        save_path: str,
        auto_start: bool,
        startup_notify: bool | None = None,
        elevate: bool = False,
        persist_device_id: bool = False,
    ):
        normalized_key = (key or '').strip()
        if normalized_key == '':
            raise ValueError('key cannot be empty')

        normalized_port = int(port)
        if normalized_port < 1 or normalized_port > 65535:
            raise ValueError('port must be in range 1-65535')

        default_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        normalized_path = (save_path or '').strip()
        if normalized_path == '' or os.path.normcase(normalized_path) == os.path.normcase(default_path):
            final_save_path = default_path
            save_path_value = ''
        else:
            final_save_path = normalized_path
            save_path_value = normalized_path

        normalized_auto_start = bool(auto_start)
        normalized_startup_notify = self.startup_notify if startup_notify is None else bool(startup_notify)

        updates = {
            'key': normalized_key,
            'port': str(normalized_port),
            'save_path': save_path_value,
            'auto_start': '1' if normalized_auto_start else '0',
            'startup_notify': '1' if normalized_startup_notify else '0',
        }
        normalized_language = self._normalize_language(self.language)
        if normalized_language == '':
            normalized_language = self._detect_default_language()
        updates['language'] = normalized_language
        if persist_device_id:
            updates['device_id'] = self.device_id
        self._persist_config_updates(updates, elevate=elevate)
        self.key = normalized_key
        self.port = normalized_port
        self.save_path = final_save_path
        self.auto_start = normalized_auto_start
        self.startup_notify = normalized_startup_notify
        self.language = normalized_language

    def _persist_config_key(self, key: str, value: str, elevate: bool = False):
        self._persist_config_updates({key: value}, elevate=elevate)

    def _persist_config_updates(self, updates: dict[str, str], elevate: bool = False):
        if not updates:
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            content = ''

        new_content = self._build_updated_config_content(content, updates)
        self._write_config_content(new_content, elevate=elevate)
        if not self.config.has_section('config'):
            self.config.add_section('config')
        for update_key, update_value in updates.items():
            self.config.set('config', update_key, update_value)

    def _build_updated_config_content(self, content: str, updates: dict[str, str]) -> str:
        newline = '\r\n' if '\r\n' in content else '\n'
        lines = content.splitlines()
        in_config_section = False
        config_section_found = False
        key_written = {update_key: False for update_key in updates}
        key_patterns = {
            update_key: re.compile(rf'^\s*{re.escape(update_key)}\s*=', re.IGNORECASE)
            for update_key in updates
        }
        out_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[') and stripped.endswith(']'):
                if in_config_section:
                    for update_key, update_value in updates.items():
                        if not key_written[update_key]:
                            out_lines.append(f'{update_key} = {update_value}')
                            key_written[update_key] = True
                in_config_section = stripped.lower() == '[config]'
                if in_config_section:
                    config_section_found = True
                out_lines.append(line)
                continue

            if in_config_section:
                replaced = False
                for update_key, key_pattern in key_patterns.items():
                    if key_pattern.match(line):
                        if not key_written[update_key]:
                            out_lines.append(f'{update_key} = {updates[update_key]}')
                            key_written[update_key] = True
                        replaced = True
                        break
                if replaced:
                    continue
            out_lines.append(line)

        if not config_section_found:
            if out_lines and out_lines[-1].strip() != '':
                out_lines.append('')
            out_lines.append('[config]')
            for update_key, update_value in updates.items():
                out_lines.append(f'{update_key} = {update_value}')
                key_written[update_key] = True
        elif in_config_section:
            for update_key, update_value in updates.items():
                if not key_written[update_key]:
                    out_lines.append(f'{update_key} = {update_value}')
                    key_written[update_key] = True

        if not out_lines:
            out_lines = ['[config]']
            for update_key, update_value in updates.items():
                out_lines.append(f'{update_key} = {update_value}')

        new_content = newline.join(out_lines)
        if out_lines and content.endswith(('\n', '\r\n')):
            new_content += newline
        return new_content

    def _write_config_content(self, new_content: str, elevate: bool = False):
        try:
            with open(self.config_path, 'w', encoding='utf-8', newline='') as f:
                f.write(new_content)
                return
        except PermissionError:
            if not elevate:
                raise
        if os.name != 'nt':
            raise PermissionError(f'Permission denied while writing: {self.config_path}')
        self._write_config_content_with_elevation(new_content)

    def _write_config_content_with_elevation(self, new_content: str):
        content_file = ''
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, newline='') as temp_content:
                temp_content.write(new_content)
                content_file = temp_content.name

            exit_code = run_elevated_task(TASK_WRITE_CONFIG, content_file, self.config_path)
            if exit_code != 0:
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as check_file:
                        if check_file.read() == new_content:
                            return
                except Exception:
                    pass
                raise PermissionError(
                    f'Failed to write config.ini with administrator rights (exit code {exit_code}).'
                )
        finally:
            for temp_path in (content_file,):
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
