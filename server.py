import os
import queue
import re
import threading
import traceback
import logging

import flask
from flask import Blueprint, request
from striprtf.striprtf import rtf_to_text
from werkzeug.utils import secure_filename

from clipboard import ClipboardType, ClipboardUtil
from config import Config
from notifier import INotifier
from result import Result
import utils

try:
    from waitress import serve as waitress_serve
except Exception:
    waitress_serve = None


def get_clipboard_dto(clipboard_type: ClipboardType, data: str):
    return {
        'type': clipboard_type.value,
        'data': data,
    }


class Server:
    READ_AHEAD_BYTES = 64 * 1024
    STREAM_CHUNK_BYTES = 512 * 1024
    MAX_CLIPBOARD_UPLOAD_BYTES = 2 * 1024 * 1024
    MAX_NOTIFY_TEXT_LENGTH = 240

    def __init__(self, config: Config, notifier: INotifier):
        self.config = config
        self.notifier = notifier
        self.is_en = str(getattr(config, 'language', 'zh')).lower().startswith('en')

        self._notify_queue: queue.Queue = queue.Queue(maxsize=200)
        self._notify_thread = threading.Thread(
            target=self._notify_worker,
            name='AirDropPlus-Notifier',
            daemon=True,
        )
        self._notify_thread.start()

        self.blueprint = Blueprint('server', __name__)
        self.register_routes()
        self.app = flask.Flask(__name__)
        self.app.register_blueprint(self.blueprint)

    def _t(self, zh: str, en: str) -> str:
        return en if self.is_en else zh

    @staticmethod
    def _short_text(value, max_length: int) -> str:
        text = '' if value is None else str(value)
        text = text.replace('\r\n', '\n').strip()
        if text == '':
            return ''
        if len(text) <= max_length:
            return text
        return text[: max_length - 1] + '…'

    def _notify_worker(self):
        while True:
            callback, args, kwargs = self._notify_queue.get()
            try:
                callback(*args, **kwargs)
            except Exception:
                traceback.print_exc()
            finally:
                self._notify_queue.task_done()

    def _submit_notify(self, callback, *args, **kwargs):
        try:
            self._notify_queue.put_nowait((callback, args, kwargs))
        except queue.Full:
            # Skip low-priority notifications when queue is full to avoid blocking transfer requests.
            pass

    def _notify(self, title_zh: str, msg_zh: str, title_en: str | None = None, msg_en: str | None = None):
        title_en = title_en if title_en is not None else title_zh
        msg_en = msg_en if msg_en is not None else msg_zh

        title = self._short_text(self._t(title_zh, title_en), 80)
        msg = self._short_text(self._t(msg_zh, msg_en), self.MAX_NOTIFY_TEXT_LENGTH)
        self._submit_notify(self.notifier.notify, title, msg)

    def _show_future_files(self, folder: str | None, filename_list: list[str], to_mobile: bool):
        self._submit_notify(self.notifier.show_future_files, folder, filename_list, to_mobile)

    def _show_received_file(self, folder: str, filename: str, ori_filename: str):
        self._submit_notify(self.notifier.show_received_file, folder, filename, ori_filename)

    def _show_received_files(self, folder: str, ori_filename_list: list[str]):
        self._submit_notify(self.notifier.show_received_files, folder, ori_filename_list)

    def _write_upload_stream(self, file_stream, file_path: str, head_bytes: bytes):
        with open(file_path, 'wb') as f:
            if head_bytes:
                f.write(head_bytes)

            while True:
                chunk = file_stream.read(self.STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                f.write(chunk)

    def run(self, host: str, port: int):
        """
        Prefer Waitress for better resilience under unstable/slow connections.
        Fallback to Flask dev server if Waitress is unavailable.
        """
        try:
            if waitress_serve is not None:
                waitress_serve(
                self.app,
                host=host,
                port=port,
                threads=16,
                connection_limit=256,
                channel_timeout=45,
                cleanup_interval=15,
                ident='AirDropPlus',
                )
                return
        except Exception as e:
            try:
                logging.exception('Failed to start Waitress, fallback to Flask server: %s', e)
            except Exception:
                pass

        self.app.run(host=host, port=port, threaded=True, use_reloader=False)

    @staticmethod
    def decode_text_bytes(raw: bytes):
        if not raw:
            return None

        if raw.startswith(b'\xef\xbb\xbf'):
            try:
                return raw.decode('utf-8-sig')
            except Exception:
                pass

        if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            for encoding in ('utf-16', 'utf-16-le', 'utf-16-be'):
                try:
                    return raw.decode(encoding)
                except Exception:
                    continue

        for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'utf-16-le', 'utf-16-be', 'gb18030'):
            try:
                text = raw.decode(encoding)
                if '\x00' in text:
                    continue
                return text
            except Exception:
                continue
        return None

    @staticmethod
    def is_probably_text_bytes(raw: bytes) -> bool:
        if not raw:
            return False
        if raw.startswith((b'\xff\xfe', b'\xfe\xff', b'\xef\xbb\xbf')):
            return True

        sample = raw[:4096]
        text = Server.decode_text_bytes(sample)
        if text is None:
            return False

        bad = sum(1 for ch in text if ord(ch) < 32 and ch not in ('\n', '\r', '\t'))
        return bad <= max(1, len(text) // 100)

    @staticmethod
    def rtf_to_plain_text(rtf_text: str) -> str:
        try:
            parsed = rtf_to_text(rtf_text).strip()
            if parsed != '':
                return parsed
        except Exception:
            pass

        def replace_hex(match):
            try:
                return bytes.fromhex(match.group(1)).decode('cp1252', errors='ignore')
            except Exception:
                return ''

        def replace_unicode(match):
            try:
                codepoint = int(match.group(1))
                if codepoint < 0:
                    codepoint += 65536
                return chr(codepoint)
            except Exception:
                return ''

        text = re.sub(r"\\'([0-9a-fA-F]{2})", replace_hex, rtf_text)
        text = re.sub(r'\\u(-?\d+)\??', replace_unicode, text)
        text = re.sub(r'\\par[d]? ?', '\n', text)
        text = re.sub(r'\\line ?', '\n', text)
        text = re.sub(r'\\tab ?', '\t', text)
        text = re.sub(r'\\[a-zA-Z]+-?\d* ?', '', text)
        text = text.replace(r'\\{', '{').replace(r'\\}', '}').replace(r'\\\\', '\\')
        text = text.replace('{', '').replace('}', '')
        text = text.replace('\r', '')
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def extract_upload_text(self, filename: str, raw: bytes):
        text = self.decode_text_bytes(raw)
        if text is None:
            return None
        stripped = text.strip('\ufeff').strip()
        if stripped == '':
            return None

        _, ext = os.path.splitext(filename.lower())
        if ext == '.rtf' or stripped.startswith('{\\rtf'):
            parsed = self.rtf_to_plain_text(stripped)
            return parsed if parsed != '' else None
        return stripped

    def should_convert_upload_to_clipboard(self, filename: str, content_type: str, head_bytes: bytes):
        _, ext = os.path.splitext(filename.lower())
        text_like_ext = {'', '.txt', '.text', '.rtf', '.md', '.csv', '.json', '.xml', '.yaml', '.yml', '.log'}
        if ext in text_like_ext:
            return True
        if content_type and content_type.lower().startswith('text/'):
            return True
        if b'{\\rtf' in head_bytes[:1024]:
            return True
        if self.is_probably_text_bytes(head_bytes):
            return True
        return False

    def register_routes(self):
        @self.blueprint.before_request
        def check_api_key():
            if request.path in ('/', '/device/info'):
                return

            auth_header = request.headers.get('Authorization')
            if auth_header != self.config.key:
                self._notify('错误', '密钥错误', 'Error', 'Key mismatch')
                return Result.error(msg=self._t('密钥错误', 'Key mismatch'), code=401)

            version = request.headers.get('ShortcutVersion')
            if version is None or version.strip() == '':
                return Result.error(msg=self._t('缺少 ShortcutVersion', 'Missing ShortcutVersion'), code=400)

            client_version = '.'.join(self.config.version.split('.')[:2])
            if '.'.join(version.split('.')[:2]) != client_version:
                zh_msg = f'版本不匹配\nWindows 版本: {self.config.version}\n快捷指令版本: {version}'
                en_msg = f'Version mismatch\nWindows version: {self.config.version}\nShortcut version: {version}'
                self._notify('错误', zh_msg, 'Error', en_msg)
                return Result.error(msg=self._t(zh_msg, en_msg), code=400)

        @self.blueprint.errorhandler(Exception)
        def handle_all_exceptions(error):
            traceback.print_exc()
            msg = str(error)
            self._notify('错误', msg, 'Error', msg)
            return Result.error(msg, 500)

        @self.blueprint.route('/')
        def test():
            return 'Hello world!'

        @self.blueprint.route('/device/info')
        def device_info():
            return Result.success(data={'device_id': self.config.device_id, 'version': self.config.version})

        @self.blueprint.route('/file/send/list', methods=['POST'])
        def send_file_list():
            filename_list = request.form['file_list'].splitlines()
            self._show_future_files(self.config.save_path, filename_list, to_mobile=False)
            return Result.success(msg=self._t('发送成功', 'Sent successfully'))

        @self.blueprint.route('/file/send', methods=['POST'])
        def send_file():
            if 'file' not in request.files:
                return Result.error(msg=self._t('文件不存在', 'File is missing'))

            file = request.files['file']
            filename = secure_filename(file.filename or '')
            if filename == '':
                filename = 'untitled.bin'

            notify_content = request.form.get('notify_content', '')
            content_type = getattr(file, 'content_type', '')
            head_bytes = file.stream.read(self.READ_AHEAD_BYTES)
            buffered_bytes = head_bytes

            if self.should_convert_upload_to_clipboard(filename, content_type, head_bytes):
                max_extra = max(0, self.MAX_CLIPBOARD_UPLOAD_BYTES - len(head_bytes))
                probe_bytes = file.stream.read(max_extra + 1)
                buffered_bytes = head_bytes + probe_bytes

                if len(buffered_bytes) <= self.MAX_CLIPBOARD_UPLOAD_BYTES:
                    text = self.extract_upload_text(filename, buffered_bytes)
                    if text is not None:
                        success, msg = ClipboardUtil.set_text(text)
                        if success:
                            self._notify('设置剪贴板文本', text, 'Clipboard text set', text)
                            return Result.success(msg=self._t('发送成功', 'Sent successfully'))
                        self._notify('设置剪贴板出错', msg, 'Failed to set clipboard', msg)
                        return Result.error(msg=msg)

            new_filename = utils.avoid_duplicate_filename(self.config.save_path, filename)
            file_path = os.path.join(self.config.save_path, new_filename)
            self._write_upload_stream(file.stream, file_path, buffered_bytes)

            if notify_content != '':
                ori_filename_list = notify_content.splitlines()
                if len(ori_filename_list) == 1:
                    self._show_received_file(self.config.save_path, new_filename, filename)
                else:
                    self._show_received_files(self.config.save_path, ori_filename_list)

            return Result.success(msg=self._t('发送成功', 'Sent successfully'))

        @self.blueprint.route('/file/receive', methods=['POST'])
        def receive_file():
            path = (request.form.get('path') or '').strip()
            if path == '':
                return Result.error(msg=self._t('缺少 path', 'Missing path'))
            if not os.path.isfile(path):
                return Result.error(msg=self._t('文件不存在', 'File not found'), code=404)

            file_name = os.path.basename(path)
            return flask.send_file(path, as_attachment=True, download_name=file_name)

        @self.blueprint.route('/clipboard/receive')
        def receive_clipboard():
            success, res = ClipboardUtil.get_text()
            if success:
                dto = get_clipboard_dto(ClipboardType.TEXT, res)
                self._notify('发送剪贴板文本', res, 'Sent clipboard text', res)
                return Result.success(data=dto)

            success, res = ClipboardUtil.get_files()
            if success:
                dto = get_clipboard_dto(ClipboardType.FILE, res)
                file_names = [os.path.basename(path) for path in res]
                self._show_future_files(None, file_names, to_mobile=True)
                return Result.success(data=dto)

            success, res = ClipboardUtil.get_img_base64()
            if success:
                dto = get_clipboard_dto(ClipboardType.IMG, res)
                self._notify('发送剪贴板图片', '', 'Sent clipboard image', '')
                return Result.success(data=dto)

            msg = self._t('Windows 剪贴板为空', 'Windows clipboard is empty')
            self._notify('发送剪贴板出错', msg, 'Clipboard send error', msg)
            return Result.error(msg=msg)

        @self.blueprint.route('/clipboard/send', methods=['POST'])
        def send_clipboard():
            text = request.form.get('clipboard')
            if text is None and request.is_json:
                body = request.get_json(silent=True) or {}
                text = body.get('clipboard') or body.get('text')
            if text is None:
                raw_text = request.get_data(cache=False, as_text=True)
                if raw_text is not None and raw_text.strip() != '':
                    text = raw_text

            if text is None or text == '':
                msg = self._t('iPhone 剪贴板为空', 'iPhone clipboard is empty')
                self._notify('设置剪贴板出错', msg, 'Failed to set clipboard', msg)
                return Result.error(msg=msg)

            text = str(text)
            success, msg = ClipboardUtil.set_text(text)
            if success:
                self._notify('设置剪贴板文本', text, 'Clipboard text set', text)
                return Result.success(msg=self._t('发送成功', 'Sent successfully'))

            self._notify('设置剪贴板出错', msg, 'Failed to set clipboard', msg)
            return Result.error(msg=msg)
