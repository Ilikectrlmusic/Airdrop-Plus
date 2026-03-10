import os
import subprocess
import threading
from abc import ABC, abstractmethod
from typing import Optional

from win10toast import ToastNotifier
from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastActivatedEventArgs,
    ToastButton,
    ToastDisplayImage,
)

import utils


class INotifier(ABC):
    @abstractmethod
    def notify(self, title: str, msg: str):
        pass

    @abstractmethod
    def show_received_file(self, folder: str, filename: str, ori_filename: str) -> None:
        pass

    @abstractmethod
    def show_received_files(self, folder: str, ori_filename_list: list):
        pass

    @abstractmethod
    def show_future_files(self, folder: Optional[str], filename_list: list, to_mobile: bool):
        pass


class _LangMixin:
    def __init__(self, language: str = "zh"):
        self.language = "en" if str(language).lower().startswith("en") else "zh"

    def _t(self, zh: str, en: str) -> str:
        return en if self.language == "en" else zh


class BasicNotifier(_LangMixin, INotifier):
    def __init__(self, language: str = "zh"):
        super().__init__(language=language)
        self.notifier = ToastNotifier()

    def notify(self, title: str, msg: str):
        self.notifier.show_toast(str(title), str(msg), threaded=True)

    def show_received_file(self, folder: str, filename: str, ori_filename: str) -> None:
        self.notify(self._t("收到文件", "Received File"), ori_filename)

    def show_received_files(self, folder: str, ori_filename_list: list):
        num_files = len(ori_filename_list)
        if num_files == 0:
            raise ValueError(self._t("文件数量不能为空", "File list cannot be empty"))
        msg = ", ".join(ori_filename_list)
        title = self._t(f"收到 {num_files} 个文件", f"Received {num_files} files")
        self.notify(title, msg)

    def show_future_files(self, folder: Optional[str], filename_list: list, to_mobile: bool):
        num_files = len(filename_list)
        if num_files == 0:
            raise ValueError(self._t("文件数量不能为空", "File list cannot be empty"))
        msg = ", ".join(filename_list)
        action = self._t("发送", "sending") if to_mobile else self._t("接收", "receiving")
        title = self._t(f"开始{action} {num_files} 个文件", f"Start {action} {num_files} files")
        self.notify(title, msg)


class Notifier(_LangMixin, INotifier):
    def __init__(self, language: str = "zh"):
        super().__init__(language=language)
        self._toaster_local = threading.local()

    def _get_toaster(self) -> InteractableWindowsToaster:
        toaster = getattr(self._toaster_local, "toaster", None)
        if toaster is None:
            toaster = InteractableWindowsToaster("", "Microsoft.Windows.Explorer")
            self._toaster_local.toaster = toaster
        return toaster

    @staticmethod
    def _normalize_path(path: str) -> str:
        raw = str(path or "").strip()
        if raw == "":
            return ""
        return os.path.normpath(os.path.abspath(os.path.expandvars(os.path.expanduser(raw))))

    @classmethod
    def _open_folder_path(cls, path: str) -> None:
        folder_path = cls._normalize_path(path)
        if folder_path == "":
            return

        target_path = folder_path
        if not os.path.isdir(target_path) and os.path.isfile(target_path):
            target_path = os.path.dirname(target_path)

        if target_path == "":
            return

        os.startfile(target_path)

    @classmethod
    def _select_path(cls, path: str) -> None:
        target_path = cls._normalize_path(path)
        if target_path == "":
            return

        if os.path.exists(target_path):
            subprocess.Popen(["explorer", "/select,", target_path])
            return

        parent_dir = os.path.dirname(target_path)
        if parent_dir and os.path.isdir(parent_dir):
            os.startfile(parent_dir)

    @staticmethod
    def _button_callback(args: ToastActivatedEventArgs):
        if "=" not in args.arguments:
            return
        action, arg = args.arguments.split("=", 1)
        if action == "select":
            Notifier._select_path(arg)
        elif action == "open":
            Notifier._open_folder_path(arg)

    def notify(self, title: str, msg: str):
        self.clear_toasts()
        toast = Toast([str(title), str(msg)])
        self._get_toaster().show_toast(toast)

    def clear_toasts(self):
        toaster = self._get_toaster()
        toaster.clear_scheduled_toasts()
        toaster.clear_toasts()

    def show_received_file(self, folder: str, filename: str, ori_filename: str):
        self.clear_toasts()
        toast = Toast([f"{self._t('收到文件', 'Received File')}: {ori_filename}"])
        file_path = os.path.join(folder, filename)
        if utils.is_image_file(file_path):
            toast.AddImage(ToastDisplayImage.fromPath(file_path))
        toast.AddAction(ToastButton(self._t("打开文件夹", "Open Folder"), arguments=f"select={file_path}"))
        toast.AddAction(ToastButton(self._t("关闭", "Close"), arguments="ignore="))
        toast.on_activated = self._button_callback
        self._get_toaster().show_toast(toast)

    def show_received_files(self, folder: str, ori_filename_list: list):
        self.clear_toasts()
        num_files = len(ori_filename_list)
        if num_files == 0:
            raise ValueError(self._t("文件数量不能为空", "File list cannot be empty"))
        title = self._t(f"收到 {num_files} 个文件", f"Received {num_files} files")
        content = [title, ", ".join(ori_filename_list)]
        toast = Toast(content)
        toast.AddAction(ToastButton(self._t("打开文件夹", "Open Folder"), arguments=f"open={folder}"))
        toast.AddAction(ToastButton(self._t("关闭", "Close"), arguments="ignore="))
        toast.on_activated = self._button_callback
        self._get_toaster().show_toast(toast)

    def show_future_files(self, folder: Optional[str], filename_list: list, to_mobile: bool):
        self.clear_toasts()
        num_files = len(filename_list)
        if num_files == 0:
            raise ValueError(self._t("文件数量不能为空", "File list cannot be empty"))
        if to_mobile:
            title = self._t(f"开始发送 {num_files} 个文件", f"Start sending {num_files} files")
        else:
            title = self._t(f"开始接收 {num_files} 个文件", f"Start receiving {num_files} files")
        toast = Toast([title, ", ".join(filename_list)])
        if not to_mobile and folder:
            toast.AddAction(ToastButton(self._t("打开文件夹", "Open Folder"), arguments=f"open={folder}"))
            toast.AddAction(ToastButton(self._t("关闭", "Close"), arguments="ignore="))
            toast.on_activated = self._button_callback
        self._get_toaster().show_toast(toast)


def create_notifier(basic: bool = True, language: str = "zh") -> INotifier:
    return BasicNotifier(language=language) if basic else Notifier(language=language)
