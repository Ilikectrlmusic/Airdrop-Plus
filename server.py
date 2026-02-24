import io
import os
import re
import traceback

import flask
from flask import Blueprint, stream_with_context, request
from striprtf.striprtf import rtf_to_text
from werkzeug.utils import secure_filename

from clipboard import ClipboardType, ClipboardUtil
from config import Config
from notifier import INotifier
from result import Result
import utils


def get_clipboard_dto(clipboard_type: ClipboardType, data: str):
    return {
        'type': clipboard_type.value,
        'data': data,
    }


class Server:
    def __init__(self, config: Config, notifier: INotifier):
        self.config = config
        self.notifier = notifier
        self.is_en = str(getattr(config, 'language', 'zh')).lower().startswith('en')

        self.blueprint = Blueprint('server', __name__)
        self.register_routes()
        self.app = flask.Flask(__name__)
        self.app.register_blueprint(self.blueprint)

    def _t(self, zh: str, en: str) -> str:
        return en if self.is_en else zh

    def _notify(self, title_zh: str, msg_zh: str, title_en: str | None = None, msg_en: str | None = None):
        title_en = title_en if title_en is not None else title_zh
        msg_en = msg_en if msg_en is not None else msg_zh
        self.notifier.notify(self._t(title_zh, title_en), self._t(msg_zh, msg_en))

    def run(self, host: str, port: int):
        self.app.run(host=host, port=port)

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
        if b'\x00' in sample:
            return False

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
        text = text.replace(r'\{', '{').replace(r'\}', '}').replace(r'\\', '\\')
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
            self.notifier.show_future_files(self.config.save_path, filename_list, to_mobile=False)
            return Result.success(msg=self._t('发送成功', 'Sent successfully'))

        @self.blueprint.route('/file/send', methods=['POST'])
        def send_file():
            if 'file' not in request.files:
                return Result.error(msg=self._t('文件不存在', 'File is missing'))

            file = request.files['file']
            filename = secure_filename(file.filename)
            notify_content = request.form.get('notify_content', '')
            content_type = getattr(file, 'content_type', '')
            head_bytes = file.stream.read(1024 * 64)

            if self.should_convert_upload_to_clipboard(filename, content_type, head_bytes):
                raw = head_bytes + file.stream.read()
                text = self.extract_upload_text(filename, raw)
                if text is not None:
                    success, msg = ClipboardUtil.set_text(text)
                    if success:
                        self._notify('设置剪贴板文本', text, 'Clipboard text set', text)
                        return Result.success(msg=self._t('发送成功', 'Sent successfully'))
                    self._notify('设置剪贴板出错', msg, 'Failed to set clipboard', msg)
                    return Result.error(msg=msg)

            new_filename = utils.avoid_duplicate_filename(self.config.save_path, filename)
            file_path = os.path.join(self.config.save_path, new_filename)
            with open(file_path, 'wb') as f:
                if head_bytes:
                    f.write(head_bytes)
                for chunk in stream_with_context(file.stream):
                    if chunk:
                        f.write(chunk)

            if notify_content != '':
                ori_filename_list = notify_content.splitlines()
                if len(ori_filename_list) == 1:
                    self.notifier.show_received_file(self.config.save_path, new_filename, filename)
                else:
                    self.notifier.show_received_files(self.config.save_path, ori_filename_list)

            return Result.success(msg=self._t('发送成功', 'Sent successfully'))

        @self.blueprint.route('/file/receive', methods=['POST'])
        def receive_file():
            path = request.form.get('path')
            file_name = os.path.basename(path)
            with open(path, 'rb') as f:
                file_content = f.read()
            return flask.send_file(io.BytesIO(file_content), as_attachment=True, download_name=file_name)

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
                self.notifier.show_future_files(None, file_names, to_mobile=True)
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
