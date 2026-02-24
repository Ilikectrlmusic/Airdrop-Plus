import os
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk


GUIDE_TEXTS = {
    "zh": {
        "title": "AirDrop Plus 使用引导",
        "page": "第 {page} / 4 页",
        "next": "下一步",
        "prev": "上一步",
        "done": "完成",
        "missing_file": "未找到 {file_name}",
        "page1_desc": "扫描二维码以添加快捷指令",
        "page2_note": "123456 只是示例，请填入右侧设备码",
        "page2_desc": "点击快捷指令右上角的 3 个小圆点，填入以下设备码",
        "page3_left": "添加到主屏幕",
        "page3_right": "设置双击手机背面来运行(iPhone 8+)",
        "page3_note": "后续可在设置中修改",
        "page3_auto_start": "开机自启动",
        "page3_save_path": "传输文件保存位置",
        "browse": "浏览",
        "choose_save_path_title": "选择文件保存位置",
    },
    "en": {
        "title": "AirDrop Plus Setup Guide",
        "page": "Page {page} / 4",
        "next": "Next",
        "prev": "Back",
        "done": "Finish",
        "missing_file": "{file_name} not found",
        "page1_desc": "Scan the QR code to install the shortcut",
        "page2_note": "abcdef is only an example.\nEnter the one shown on the right.",
        "page2_desc": "Tap the three dots in the shortcut's top-right corner, then enter the DeviceID below.",
        "page3_left": "Add to Home Screen",
        "page3_right": "Set Double Back Tap to run (iPhone 8+)",
        "page3_note": "You can change later in Settings",
        "page3_auto_start": "Launch at startup",
        "page3_save_path": "Save location for received files",
        "browse": "Browse",
        "choose_save_path_title": "Choose save location",
    },
}

GUIDE_ASSETS = {
    "zh": {
        "qr": "QR_code.PNG",
        "device_gif": "DeviceID.GIF",
        "home_gif": "Home_screen.GIF",
        "double_tap_gif": "Double_tap.GIF",
        "open_setting_gif": "open_setting.GIF",
    },
    "en": {
        "qr": "QR_code_en.PNG",
        "device_gif": "DeviceID_en.GIF",
        "home_gif": "Home_screen_en.GIF",
        "double_tap_gif": "Double_tap_en.GIF",
        "open_setting_gif": "open_setting_en.GIF",
    },
}


class FirstRunGuide:
    def __init__(
        self,
        device_id: str,
        static_dir: str,
        default_auto_start: bool = True,
        default_save_path: str | None = None,
        language: str = "zh",
    ):
        self.device_id = device_id
        self.static_dir = static_dir
        self.page_index = 0
        self.result_auto_start = default_auto_start
        self.result_save_path = default_save_path or os.path.join(os.path.expanduser("~"), "Downloads")

        self.language = "en" if str(language).lower().startswith("en") else "zh"
        self.texts = GUIDE_TEXTS[self.language]
        self.assets = GUIDE_ASSETS[self.language]

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title(self.texts["title"])
        self.root.geometry("648x414")
        self.root.minsize(612, 378)
        self.root.protocol("WM_DELETE_WINDOW", self.finish)

        self.auto_start_var = tk.BooleanVar(master=self.root, value=default_auto_start)
        self.save_path_var = tk.StringVar(master=self.root, value=self.result_save_path)

        self._gif_jobs: dict[tk.Label, str] = {}
        self._image_ref = None

        self._build_layout()
        self.render_page()

    def _build_layout(self):
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.content_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(50, 0))
        self.content_frame.grid_columnconfigure(0, weight=1, uniform="guide_cols")
        self.content_frame.grid_columnconfigure(1, weight=1, uniform="guide_cols")

        self.left_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.right_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        nav_frame = ctk.CTkFrame(container, fg_color="transparent")
        nav_frame.pack(fill=tk.X, pady=(16, 0))

        self.page_label = ctk.CTkLabel(nav_frame, text="", font=("Microsoft YaHei UI", 14))
        self.page_label.pack(side=tk.LEFT, padx=(8, 0))

        self.next_button = ctk.CTkButton(
            nav_frame,
            text=self.texts["next"],
            width=76,
            height=35,
            font=("Microsoft YaHei UI", 13),
            command=self.next_or_finish,
        )
        self.next_button.pack(side=tk.RIGHT)
        self.prev_button = ctk.CTkButton(
            nav_frame,
            text=self.texts["prev"],
            width=76,
            height=35,
            font=("Microsoft YaHei UI", 13),
            command=self.prev_page,
        )
        self.prev_button.pack(side=tk.RIGHT, padx=(0, 8))

    @staticmethod
    def _resample_filter():
        try:
            return Image.Resampling.LANCZOS
        except AttributeError:
            return Image.LANCZOS

    def _load_image(self, file_name: str, max_size=(360, 360)):
        path = os.path.join(self.static_dir, file_name)
        if not os.path.exists(path):
            return None
        with Image.open(path) as img:
            img = img.convert("RGBA")
            img.thumbnail(max_size, self._resample_filter())
            return ImageTk.PhotoImage(img)

    def _load_gif_frames(self, file_name: str, max_size=(360, 360)):
        path = os.path.join(self.static_dir, file_name)
        if not os.path.exists(path):
            return [], []
        frames = []
        durations = []
        with Image.open(path) as img:
            while True:
                frame = img.copy().convert("RGBA")
                frame.thumbnail(max_size, self._resample_filter())
                frames.append(ImageTk.PhotoImage(frame))
                durations.append(max(80, int(img.info.get("duration", 120))))
                try:
                    img.seek(img.tell() + 1)
                except EOFError:
                    break
        return frames, durations

    def _clear_content(self):
        for _, job_id in list(self._gif_jobs.items()):
            try:
                self.root.after_cancel(job_id)
            except Exception:
                pass
        self._gif_jobs.clear()
        self._image_ref = None
        for frame in (self.left_frame, self.right_frame):
            for child in frame.winfo_children():
                child.destroy()

    def _frame_bg(self, frame) -> str:
        color = frame.cget("fg_color")
        if color == "transparent":
            color = self.root.cget("fg_color")
        if isinstance(color, (tuple, list)):
            color = color[0]
        if not isinstance(color, str) or color == "transparent":
            return "#d9d9d9"
        return color

    def _animate_gif(self, label: tk.Label, frames: list[ImageTk.PhotoImage], durations: list[int], index: int = 0):
        if not frames:
            return
        if not label.winfo_exists():
            self._gif_jobs.pop(label, None)
            return
        label.configure(image=frames[index])
        next_index = (index + 1) % len(frames)
        next_delay = durations[index]
        self._gif_jobs[label] = self.root.after(
            next_delay,
            lambda: self._animate_gif(label, frames, durations, next_index),
        )

    def _set_gif_on_label(self, label: tk.Label, file_name: str, max_size=(360, 360)) -> bool:
        frames, durations = self._load_gif_frames(file_name, max_size=max_size)
        if not frames:
            return False
        # Keep references to avoid Tk image garbage collection.
        label._gif_frames = frames  # type: ignore[attr-defined]
        label._gif_durations = durations  # type: ignore[attr-defined]
        self._animate_gif(label, frames, durations, 0)
        return True

    def render_page(self):
        self._clear_content()
        if self.page_index == 2:
            # Keep nav area unchanged, move page-3 content up to make room for taller portrait GIFs.
            top_pady = 2
        elif self.page_index == 1:
            top_pady = 44
        elif self.page_index == 0:
            top_pady = 60
        else:
            top_pady = 50
        self.content_frame.pack_configure(pady=(top_pady, 0))
        if self.page_index == 3:
            # On page 4, allocate more width to the right side so save-path field can show more text.
            self.content_frame.grid_columnconfigure(0, weight=4, uniform="")
            self.content_frame.grid_columnconfigure(1, weight=16, uniform="")
            self.left_frame.grid_configure(padx=(0, 0))
            self.right_frame.grid_configure(padx=(0, 0))
        else:
            self.content_frame.grid_columnconfigure(0, weight=1, uniform="guide_cols")
            self.content_frame.grid_columnconfigure(1, weight=1, uniform="guide_cols")
            self.left_frame.grid_configure(padx=(0, 12))
            self.right_frame.grid_configure(padx=(12, 0))
        self.page_label.configure(text=self.texts["page"].format(page=self.page_index + 1))
        self.prev_button.configure(state=tk.NORMAL if self.page_index > 0 else tk.DISABLED)
        self.next_button.configure(text=self.texts["done"] if self.page_index == 3 else self.texts["next"])

        if self.page_index == 0:
            self._render_page_1()
        elif self.page_index == 1:
            self._render_page_2()
        elif self.page_index == 2:
            self._render_page_3()
        else:
            self._render_page_4()

    def _render_page_1(self):
        file_name = self.assets["qr"]
        image = self._load_image(file_name, max_size=(250, 250))
        if image is None:
            ctk.CTkLabel(
                self.left_frame,
                text=self.texts["missing_file"].format(file_name=file_name),
                font=("Microsoft YaHei UI", 14),
            ).pack(expand=True, pady=(112, 0))
        else:
            self._image_ref = image
            tk.Label(self.left_frame, image=image, bd=0, highlightthickness=0, bg=self._frame_bg(self.left_frame)).pack(
                expand=True, pady=(54, 0), padx=(50, 0)
            )

        ctk.CTkLabel(
            self.right_frame,
            text=self.texts["page1_desc"],
            font=("Microsoft YaHei UI", 17, "bold"),
            wraplength=320,
            anchor="center",
            justify="center",
        ).pack(expand=True, pady=(54, 0), padx=(0, 20))

    def _render_page_2(self):
        file_name = self.assets["device_gif"]
        left_note_wrap = 320 if self.language == "en" else 360
        left_note_padx = (8, 8) if self.language == "en" else (20, 20)
        right_desc_wrap = 270 if self.language == "en" else 320

        left_stack = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        left_stack.pack(fill=tk.BOTH, expand=True, anchor="n")

        gif_label = tk.Label(left_stack, bd=0, highlightthickness=0, bg=self._frame_bg(self.left_frame))
        gif_label.pack(anchor="n", padx=(24, 0), pady=(0, 0))
        if not self._set_gif_on_label(gif_label, file_name, max_size=(350, 350)):
            gif_label.configure(text=self.texts["missing_file"].format(file_name=file_name), font=("Microsoft YaHei UI", 14))

        ctk.CTkLabel(
            left_stack,
            text=self.texts["page2_note"],
            font=("Microsoft YaHei UI", 15),
            wraplength=left_note_wrap,
            justify="center",
            anchor="center",
        ).pack(pady=(14, 0), padx=left_note_padx)

        right_stack = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        right_stack.pack(fill=tk.X, anchor="n", pady=(30, 0))

        ctk.CTkLabel(
            right_stack,
            text=self.texts["page2_desc"],
            font=("Microsoft YaHei UI", 17, "bold"),
            wraplength=right_desc_wrap,
            justify="center",
            anchor="center",
        ).pack(pady=(26, 20), padx=(10, 10), anchor="center")
        ctk.CTkLabel(
            right_stack,
            text=self.device_id,
            font=("Consolas", 35, "bold"),
            text_color="#1b4d89",
        ).pack(anchor="center")

    def _render_page_3(self):
        left_file_name = self.assets["home_gif"]
        right_file_name = self.assets["double_tap_gif"]

        left_stack = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        left_stack.pack(fill=tk.BOTH, expand=True)

        left_label = tk.Label(left_stack, bd=0, highlightthickness=0, bg=self._frame_bg(self.left_frame))
        left_label.pack(anchor="n", pady=(0, 0))
        if not self._set_gif_on_label(left_label, left_file_name, max_size=(410, 410)):
            ctk.CTkLabel(
                left_stack,
                text=self.texts["missing_file"].format(file_name=left_file_name),
                font=("Microsoft YaHei UI", 14),
                justify="center",
            ).pack(expand=True, pady=(72, 0), padx=(10, 10))
            left_label.configure(image="", text="")

        ctk.CTkLabel(
            left_stack,
            text=self.texts["page3_left"],
            font=("Microsoft YaHei UI", 16, "bold"),
            justify="center",
            anchor="center",
            wraplength=240 if self.language == "en" else 220,
        ).pack(pady=(8, 0), padx=(8, 8))

        right_stack = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        right_stack.pack(fill=tk.BOTH, expand=True)

        right_label = tk.Label(right_stack, bd=0, highlightthickness=0, bg=self._frame_bg(self.right_frame))
        right_label.pack(anchor="n", pady=(0, 0))
        if not self._set_gif_on_label(right_label, right_file_name, max_size=(410, 410)):
            ctk.CTkLabel(
                right_stack,
                text=self.texts["missing_file"].format(file_name=right_file_name),
                font=("Microsoft YaHei UI", 14),
                justify="center",
            ).pack(expand=True, pady=(72, 0), padx=(10, 10))
            right_label.configure(image="", text="")

        ctk.CTkLabel(
            right_stack,
            text=self.texts["page3_right"],
            font=("Microsoft YaHei UI", 16, "bold"),
            justify="center",
            anchor="center",
            wraplength=280 if self.language == "en" else 250,
        ).pack(pady=(8, 0), padx=(8, 8))

    def _render_page_4(self):
        file_name = self.assets["open_setting_gif"]
        left_visual = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        left_visual.pack(fill=tk.BOTH, expand=True, padx=(0, 20))

        setting_gif_label = tk.Label(left_visual, bd=0, highlightthickness=0, bg=self._frame_bg(self.left_frame))
        setting_gif_label.pack(expand=True, anchor="center", padx=(0, 0), pady=(114, 18))
        if not self._set_gif_on_label(setting_gif_label, file_name, max_size=(170, 170)):
            setting_gif_label.configure(text=self.texts["missing_file"].format(file_name=file_name), font=("Microsoft YaHei UI", 15))

        ctk.CTkLabel(
            left_visual,
            text=self.texts["page3_note"],
            font=("Microsoft YaHei UI", 15),
            wraplength=230 if self.language == "en" else 320,
            justify="center",
            anchor="center",
        ).pack(pady=(8, 66), padx=(0, 0), anchor="center")

        right_container = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        right_pad = 0
        right_container.pack(expand=True, fill=tk.X, padx=(0, right_pad), pady=(0, 0))

        ctk.CTkCheckBox(
            right_container,
            text=self.texts["page3_auto_start"],
            variable=self.auto_start_var,
            font=("Microsoft YaHei UI", 14),
        ).pack(fill=tk.X, pady=(0, 24), anchor="w")

        ctk.CTkLabel(
            right_container,
            text=self.texts["page3_save_path"],
            font=("Microsoft YaHei UI", 14),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 0))

        path_row = ctk.CTkFrame(right_container, fg_color="transparent")
        path_row.pack(fill=tk.X, padx=(0, 0))
        ctk.CTkEntry(path_row, textvariable=self.save_path_var, height=20, font=("Microsoft YaHei UI", 14)).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ctk.CTkButton(
            path_row,
            text=self.texts["browse"],
            width=55,
            height=30,
            font=("Microsoft YaHei UI", 14),
            command=self.choose_save_path,
        ).pack(side=tk.LEFT, padx=(8, 0))

    def choose_save_path(self):
        initial_dir = self.save_path_var.get().strip()
        if initial_dir == "" or not os.path.isdir(initial_dir):
            initial_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        selected = filedialog.askdirectory(
            parent=self.root,
            title=self.texts["choose_save_path_title"],
            initialdir=initial_dir,
        )
        if selected:
            self.save_path_var.set(selected)

    def prev_page(self):
        if self.page_index == 0:
            return
        self.page_index -= 1
        self.render_page()

    def next_or_finish(self):
        if self.page_index >= 3:
            self.finish()
            return
        self.page_index += 1
        self.render_page()

    def finish(self):
        self.result_auto_start = bool(self.auto_start_var.get())
        self.result_save_path = self.save_path_var.get().strip() or os.path.join(os.path.expanduser("~"), "Downloads")
        self.root.destroy()

    def run(self) -> tuple[bool, str]:
        self.root.mainloop()
        return self.result_auto_start, self.result_save_path


def show_first_run_guide(
    device_id: str,
    static_dir: str,
    default_auto_start: bool = True,
    default_save_path: str | None = None,
    language: str = "zh",
) -> tuple[bool, str]:
    guide = FirstRunGuide(
        device_id=device_id,
        static_dir=static_dir,
        default_auto_start=default_auto_start,
        default_save_path=default_save_path,
        language=language,
    )
    return guide.run()
