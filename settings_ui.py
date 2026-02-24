import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser

import customtkinter as ctk

from config import Config
from notifier import INotifier
from startup import set_startup_enabled


GITHUB_URL = "https://github.com/Ilikectrlmusic/Airdrop-Plus"

WINDOW_WIDTH = 700
WINDOW_HEIGHT = 540

COLOR_WINDOW_BG = "#f3f5f9"
COLOR_SIDEBAR_BG = "#eceff5"
COLOR_MAIN_BG = "#f3f5f9"
COLOR_TEXT = "#1f2a37"
COLOR_MUTED = "#5f6c80"
COLOR_LINE = "#d9deea"
COLOR_BLUE = "#4c5cf0"
COLOR_BLUE_DARK = "#3f4fe2"
COLOR_NAV_HOVER = "#e4e9f7"
COLOR_NAV_SELECTED = "#dfe6ff"
COLOR_INPUT_BG = "#edf1f8"
COLOR_INPUT_BORDER = "#c7cfdd"

FONT_NAV_TITLE = ("Microsoft YaHei UI", 26, "bold")
FONT_NAV_BUTTON = ("Microsoft YaHei UI", 14)
FONT_SECTION_TITLE = ("Microsoft YaHei UI", 20, "bold")
FONT_LABEL = ("Microsoft YaHei UI", 14)
FONT_VALUE = ("Microsoft YaHei UI", 14)
FONT_ENTRY = ("Microsoft YaHei UI", 13)
FONT_BUTTON = ("Microsoft YaHei UI", 13)
FONT_LINK = ("Microsoft YaHei UI", 14, "underline")
FONT_DEVICE_CODE = ("Consolas", 22, "bold")

TEXTS = {
    "zh": {
        "window_title": "AirDrop Plus 设置",
        "sidebar_title": "设置",
        "menu_transfer": "传输",
        "menu_general": "通用",
        "menu_notify": "通知",
        "menu_about": "关于",
        "section_transfer": "传输设置",
        "section_general": "通用设置",
        "section_notify": "通知设置",
        "section_about": "关于",
        "save_close": "保存并关闭",
        "cancel": "取消",
        "label_device_id": "设备码：",
        "label_shortcut": "重新安装快捷指令：",
        "get_qr": "获取二维码",
        "label_key": "密钥：",
        "label_port": "端口：",
        "label_save_path": "文件接受位置：",
        "browse": "浏览",
        "label_startup": "启动：",
        "auto_start": "开机自动启动",
        "label_startup_notify": "启动通知：",
        "startup_notify": "软件启动时通知",
        "label_version": "版本：",
        "label_github": "GitHub：",
        "github_link": "https://github.com/Ilikectrlmusic/Airdrop-Plus",
        "err_qr_not_found": "未找到二维码文件:\n{path}",
        "choose_save_path_title": "选择文件接收位置",
        "save_failed": "保存失败",
        "err_key_empty": "密钥不能为空",
        "err_port_empty": "端口不能为空",
        "err_port_range": "端口范围必须是 1-65535",
        "err_save_path_missing": "文件接收位置不存在，请重新选择",
        "saved_title": "设置已保存",
        "saved_message": "设置已保存，AirDrop Plus 将自动重启并应用新设置。",
        "restart_failed": "自动重启失败，请手动重启 AirDrop Plus。",
    },
    "en": {
        "window_title": "AirDrop Plus Settings",
        "sidebar_title": "Settings",
        "menu_transfer": "Transfer",
        "menu_general": "General",
        "menu_notify": "Notifications",
        "menu_about": "About",
        "section_transfer": "Transfer Settings",
        "section_general": "General Settings",
        "section_notify": "Notification Settings",
        "section_about": "About",
        "save_close": "Save & Close",
        "cancel": "Cancel",
        "label_device_id": "Device ID:",
        "label_shortcut": "Reinstall Shortcut:",
        "get_qr": "Get QR Code",
        "label_key": "Key:",
        "label_port": "Port:",
        "label_save_path": "Save Path:",
        "browse": "Browse",
        "label_startup": "Startup:",
        "auto_start": "Launch at startup",
        "label_startup_notify": "Startup Notification:",
        "startup_notify": "Notify when app starts",
        "label_version": "Version:",
        "label_github": "GitHub:",
        "github_link": "https://github.com/Ilikectrlmusic/Airdrop-Plus",
        "err_qr_not_found": "QR code file not found:\n{path}",
        "choose_save_path_title": "Choose save path",
        "save_failed": "Save Failed",
        "err_key_empty": "Key cannot be empty",
        "err_port_empty": "Port cannot be empty",
        "err_port_range": "Port must be in the range 1-65535",
        "err_save_path_missing": "Save path does not exist, please choose again",
        "saved_title": "Settings Saved",
        "saved_message": "Settings saved. AirDrop Plus will restart automatically to apply changes.",
        "restart_failed": "Automatic restart failed. Please restart AirDrop Plus manually.",
    },
}


class SettingsWindow:
    def __init__(self, config: Config, notifier: INotifier, script_dir: str, entry_script: str, language: str = "zh"):
        self.config = config
        self.notifier = notifier
        self.script_dir = script_dir
        self.entry_script = entry_script

        self.language = "en" if str(language).lower().startswith("en") else "zh"
        self.t = TEXTS[self.language]
        self.qr_file_name = "QR_code_en.PNG" if self.language == "en" else "QR_code.PNG"

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk(fg_color=COLOR_WINDOW_BG)
        self.root.title(self.t["window_title"])
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.key_var = tk.StringVar(value=self.config.key)
        self.port_var = tk.StringVar(value=str(self.config.port))
        self.save_path_var = tk.StringVar(value=self.config.save_path)
        self.auto_start_var = tk.BooleanVar(value=self.config.auto_start)
        self.startup_notify_var = tk.BooleanVar(value=self.config.startup_notify)

        self.menu_items = ["transfer", "general", "notify", "about"]
        self.menu_texts = {
            "transfer": self.t["menu_transfer"],
            "general": self.t["menu_general"],
            "notify": self.t["menu_notify"],
            "about": self.t["menu_about"],
        }
        self.section_titles = {
            "transfer": self.t["section_transfer"],
            "general": self.t["section_general"],
            "notify": self.t["section_notify"],
            "about": self.t["section_about"],
        }

        self.menu_buttons: dict[str, ctk.CTkButton] = {}
        self.content_panel: ctk.CTkFrame | None = None
        self.section_title_label: ctk.CTkLabel | None = None
        self.current_menu = ""

        self._build_layout()
        self.select_menu("transfer")

    def _build_layout(self):
        layout = ctk.CTkFrame(self.root, fg_color="transparent")
        layout.pack(fill=tk.BOTH, expand=True)

        sidebar = ctk.CTkFrame(layout, width=180, corner_radius=0, fg_color=COLOR_SIDEBAR_BG)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text=self.t["sidebar_title"],
            font=FONT_NAV_TITLE,
            text_color=COLOR_TEXT,
            anchor="w",
        ).pack(fill=tk.X, padx=24, pady=(24, 12))

        nav_list = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_list.pack(fill=tk.X, padx=16, pady=(0, 0))

        for item in self.menu_items:
            button = ctk.CTkButton(
                nav_list,
                text=self.menu_texts[item],
                font=FONT_NAV_BUTTON,
                anchor="w",
                corner_radius=10,
                height=46,
                fg_color="transparent",
                hover_color=COLOR_NAV_HOVER,
                text_color=COLOR_MUTED,
                command=lambda name=item: self.select_menu(name),
            )
            button.pack(fill=tk.X, pady=4)
            self.menu_buttons[item] = button

        main = ctk.CTkFrame(layout, corner_radius=0, fg_color=COLOR_MAIN_BG)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(24, 10))

        self.section_title_label = ctk.CTkLabel(
            header,
            text="",
            font=FONT_SECTION_TITLE,
            text_color=COLOR_TEXT,
            anchor="w",
        )
        self.section_title_label.pack(anchor="w")

        ctk.CTkFrame(header, fg_color=COLOR_LINE, height=1, corner_radius=0).pack(fill=tk.X, pady=(14, 0))

        self.content_panel = ctk.CTkFrame(main, fg_color="transparent")
        self.content_panel.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 6))

        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 18))

        ctk.CTkButton(
            footer,
            text=self.t["save_close"],
            width=90,
            height=35,
            corner_radius=8,
            font=FONT_BUTTON,
            fg_color=COLOR_BLUE,
            hover_color=COLOR_BLUE_DARK,
            text_color="white",
            command=self.save_and_close,
        ).pack(side=tk.LEFT)

        ctk.CTkButton(
            footer,
            text=self.t["cancel"],
            width=60,
            height=35,
            corner_radius=8,
            font=FONT_BUTTON,
            fg_color=COLOR_INPUT_BG,
            hover_color="#e3e8f3",
            text_color=COLOR_MUTED,
            border_width=1,
            border_color=COLOR_INPUT_BORDER,
            command=self.root.destroy,
        ).pack(side=tk.LEFT, padx=(12, 0))

    def _style_entry(self, entry: ctk.CTkEntry):
        entry.configure(
            fg_color=COLOR_INPUT_BG,
            border_color=COLOR_INPUT_BORDER,
            text_color=COLOR_TEXT,
            corner_radius=8,
        )

    def _style_checkbox(self, checkbox: ctk.CTkCheckBox):
        checkbox.configure(
            fg_color=COLOR_BLUE,
            hover_color=COLOR_BLUE_DARK,
            border_color=COLOR_INPUT_BORDER,
            text_color=COLOR_TEXT,
            checkmark_color="white",
        )

    def _new_content_inner(self):
        panel = ctk.CTkFrame(self.content_panel, fg_color="transparent")
        panel.pack(fill=tk.BOTH, expand=True, padx=(6, 10), pady=(2, 6))
        panel.grid_columnconfigure(0, minsize=150)
        panel.grid_columnconfigure(1, weight=1)
        return panel

    def _make_row_label(self, panel: ctk.CTkFrame, row: int, text: str, pady: int):
        ctk.CTkLabel(panel, text=text, font=FONT_LABEL, text_color=COLOR_MUTED).grid(
            row=row, column=0, sticky="ne", pady=(0, pady), padx=(0, 16)
        )

    def select_menu(self, name: str):
        self.current_menu = name

        for menu_name, button in self.menu_buttons.items():
            if menu_name == name:
                button.configure(fg_color=COLOR_NAV_SELECTED, text_color=COLOR_BLUE)
            else:
                button.configure(fg_color="transparent", text_color=COLOR_MUTED)

        self.render_content(name)

    def clear_content(self):
        if self.content_panel is None:
            return
        for widget in self.content_panel.winfo_children():
            widget.destroy()

    def render_content(self, menu_name: str):
        self.clear_content()

        if self.section_title_label is not None:
            self.section_title_label.configure(text=self.section_titles.get(menu_name, menu_name))

        if menu_name == "transfer":
            self.render_transfer()
        elif menu_name == "general":
            self.render_general()
        elif menu_name == "notify":
            self.render_notify()
        else:
            self.render_about()

    def render_transfer(self):
        panel = self._new_content_inner()
        row_gap = 20

        self._make_row_label(panel, 0, self.t["label_device_id"], row_gap)
        ctk.CTkLabel(
            panel,
            text=self.config.device_id,
            font=FONT_DEVICE_CODE,
            text_color=COLOR_BLUE,
            anchor="w",
        ).grid(row=0, column=1, sticky="w", pady=(0, row_gap))

        self._make_row_label(panel, 1, self.t["label_shortcut"], row_gap)
        ctk.CTkButton(
            panel,
            text=self.t["get_qr"],
            width=90,
            height=30,
            corner_radius=8,
            font=FONT_BUTTON,
            fg_color=COLOR_BLUE,
            hover_color=COLOR_BLUE_DARK,
            command=self.open_shortcut_qr,
        ).grid(row=1, column=1, sticky="w", pady=(0, row_gap))

        self._make_row_label(panel, 2, self.t["label_key"], row_gap)
        key_entry = ctk.CTkEntry(panel, textvariable=self.key_var, width=80, height=30, font=FONT_ENTRY)
        self._style_entry(key_entry)
        key_entry.grid(row=2, column=1, sticky="w", pady=(0, row_gap))

        self._make_row_label(panel, 3, self.t["label_port"], row_gap)
        port_entry = ctk.CTkEntry(panel, textvariable=self.port_var, width=80, height=30, font=FONT_ENTRY)
        self._style_entry(port_entry)
        port_entry.grid(row=3, column=1, sticky="w", pady=(0, row_gap))

        panel.grid_rowconfigure(99, weight=1)

    def render_general(self):
        panel = self._new_content_inner()
        row_gap = 20

        self._make_row_label(panel, 0, self.t["label_save_path"], row_gap)
        path_row = ctk.CTkFrame(panel, fg_color="transparent")
        path_row.grid(row=0, column=1, sticky="ew", pady=(0, row_gap))
        path_row.grid_columnconfigure(0, weight=1)

        path_entry = ctk.CTkEntry(path_row, textvariable=self.save_path_var, height=30, font=FONT_ENTRY)
        self._style_entry(path_entry)
        path_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            path_row,
            text=self.t["browse"],
            width=55,
            height=30,
            corner_radius=8,
            font=FONT_BUTTON,
            fg_color=COLOR_BLUE,
            hover_color=COLOR_BLUE_DARK,
            border_width=0,
            text_color="white",
            command=self.choose_save_path,
        ).grid(row=0, column=1, padx=(10, 0))

        self._make_row_label(panel, 1, self.t["label_startup"], row_gap)
        auto_start_checkbox = ctk.CTkCheckBox(
            panel,
            text=self.t["auto_start"],
            variable=self.auto_start_var,
            font=FONT_LABEL,
        )
        self._style_checkbox(auto_start_checkbox)
        auto_start_checkbox.grid(row=1, column=1, sticky="w", pady=(0, row_gap))

        panel.grid_rowconfigure(99, weight=1)

    def render_about(self):
        panel = self._new_content_inner()
        row_gap = 20

        self._make_row_label(panel, 0, self.t["label_version"], row_gap)
        ctk.CTkLabel(panel, text=self.config.version, font=FONT_VALUE, text_color=COLOR_TEXT).grid(
            row=0, column=1, sticky="w", pady=(0, row_gap)
        )

        self._make_row_label(panel, 1, self.t["label_github"], row_gap)
        link = ctk.CTkLabel(panel, text=self.t["github_link"], font=FONT_LINK, text_color=COLOR_BLUE, cursor="hand2")
        link.grid(row=1, column=1, sticky="w", pady=(0, row_gap))
        link.bind("<Button-1>", lambda _e: webbrowser.open(GITHUB_URL))

        panel.grid_rowconfigure(99, weight=1)

    def render_notify(self):
        panel = self._new_content_inner()
        row_gap = 20

        self._make_row_label(panel, 0, self.t["label_startup_notify"], row_gap)
        startup_notify_checkbox = ctk.CTkCheckBox(
            panel,
            text=self.t["startup_notify"],
            variable=self.startup_notify_var,
            font=FONT_LABEL,
        )
        self._style_checkbox(startup_notify_checkbox)
        startup_notify_checkbox.grid(row=0, column=1, sticky="w", pady=(0, row_gap))

        panel.grid_rowconfigure(99, weight=1)

    def open_shortcut_qr(self):
        qr_path = os.path.join(self.script_dir, "static", self.qr_file_name)
        if not os.path.exists(qr_path):
            messagebox.showerror(self.t["save_failed"], self.t["err_qr_not_found"].format(path=qr_path))
            return
        os.startfile(qr_path)

    def choose_save_path(self):
        initial = self.save_path_var.get().strip()
        if initial == "" or not os.path.isdir(initial):
            initial = os.path.join(os.path.expanduser("~"), "Downloads")
        selected = filedialog.askdirectory(parent=self.root, title=self.t["choose_save_path_title"], initialdir=initial)
        if selected:
            self.save_path_var.set(selected)

    def _restart_application(self):
        if getattr(sys, "frozen", False):
            launch_cmd = [sys.executable]
        else:
            entry_script = self.entry_script
            if not os.path.isabs(entry_script):
                entry_script = os.path.join(self.script_dir, entry_script)
            launch_cmd = [sys.executable, entry_script]

        child_env = os.environ.copy()
        child_env["AIRDROPPLUS_RESTART_PARENT_PID"] = str(os.getpid())

        creationflags = 0
        if os.name == "nt":
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)

        subprocess.Popen(
            launch_cmd,
            cwd=self.script_dir,
            env=child_env,
            creationflags=creationflags,
        )

    def save_and_close(self):
        try:
            key = self.key_var.get().strip()
            port_text = self.port_var.get().strip()
            save_path = self.save_path_var.get().strip()
            auto_start = bool(self.auto_start_var.get())
            startup_notify = bool(self.startup_notify_var.get())

            if key == "":
                raise ValueError(self.t["err_key_empty"])
            if port_text == "":
                raise ValueError(self.t["err_port_empty"])

            port = int(port_text)
            if port < 1 or port > 65535:
                raise ValueError(self.t["err_port_range"])
            if save_path != "" and not os.path.isdir(save_path):
                raise ValueError(self.t["err_save_path_missing"])

            self.config.save_settings(
                key=key,
                port=port,
                save_path=save_path,
                auto_start=auto_start,
                startup_notify=startup_notify,
                elevate=True,
            )
            set_startup_enabled(auto_start, self.entry_script)
        except Exception as e:
            messagebox.showerror(self.t["save_failed"], str(e))
            return

        self.notifier.notify(self.t["saved_title"], self.t["saved_message"])
        try:
            self._restart_application()
        except Exception as e:
            messagebox.showerror(self.t["save_failed"], f'{self.t["restart_failed"]}\n{e}')
            return

        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


def show_settings_window(
    config: Config,
    notifier: INotifier,
    script_dir: str,
    entry_script: str,
    language: str = "zh",
):
    win = SettingsWindow(
        config=config,
        notifier=notifier,
        script_dir=script_dir,
        entry_script=entry_script,
        language=language,
    )
    win.run()
