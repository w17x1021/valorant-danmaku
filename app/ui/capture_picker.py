"""截图选区域：把整屏拍下来，在桌面上拖框选。

用途：游戏开成「独占全屏」时，任何覆盖层都盖不上去（连框选遮罩都看不到）。
这个方式不需要覆盖游戏——先截一张图，再在截图窗口里框，坐标照样映射回屏幕。
"""
from __future__ import annotations

import ctypes
import tkinter as tk
from tkinter import messagebox

import numpy as np
from PIL import Image, ImageGrab, ImageTk

from .theme import BORDER, CARD, FONT, TEXT

u32 = ctypes.windll.user32


class CapturePicker:
    def __init__(self, root: tk.Tk, on_done, delay_s: int = 3):
        self.root = root
        self.on_done = on_done
        self.delay = max(1, int(delay_s))
        self._toast: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self.top: tk.Toplevel | None = None
        self._photo = None
        self._img: Image.Image | None = None
        self._scale = 1.0
        self._origin = (0, 0)
        self._start = None
        self._rect = None
        self._size_id = None
        self._begin()

    # ------------------------------------------------------------------
    def _begin(self) -> None:
        vx = u32.GetSystemMetrics(76)
        vy = u32.GetSystemMetrics(77)
        self._toast = tk.Toplevel(self.root)
        self._toast.overrideredirect(True)
        self._toast.attributes("-topmost", True)
        self._toast.configure(bg=CARD)
        self._label = tk.Label(self._toast, text="", bg=CARD, fg=TEXT,
                               font=(FONT, 11, "bold"), padx=18, pady=12)
        self._label.pack()
        self._toast.update_idletasks()
        w, h = self._toast.winfo_width(), self._toast.winfo_height()
        sw = u32.GetSystemMetrics(0)
        self._toast.geometry(f"+{vx + (sw - w) // 2}+{vy + 60}")
        self._tick(self.delay)

    def _tick(self, n: int) -> None:
        if n <= 0:
            if self._toast is not None:
                self._toast.destroy()
                self._toast = None
            self.root.after(120, self._capture)
            return
        if self._label is not None:
            self._label.configure(text=f"{n} 秒后截屏 · 现在切回游戏画面")
        self.root.after(1000, lambda: self._tick(n - 1))

    # ------------------------------------------------------------------
    def _capture(self) -> None:
        try:
            img = ImageGrab.grab(all_screens=True)
        except OSError as exc:
            self._fail(f"截屏失败：{exc}")
            return
        arr = np.asarray(img.convert("L"), dtype=np.uint8)
        if float(arr.mean()) < 8:
            self._fail("抓到的是全黑画面。\n\n说明游戏还在「独占全屏」，"
                       "任何工具都截不到。\n请到游戏设置 → 视频 → 显示模式，"
                       "改成「窗口化全屏」，再用这个功能。")
            return
        self._img = img
        self._origin = (u32.GetSystemMetrics(76), u32.GetSystemMetrics(77))
        self._show(img)

    def _fail(self, msg: str) -> None:
        messagebox.showwarning("截图选区域", msg, parent=self.root)
        self._finish(None)

    def _finish(self, region) -> None:
        if self.top is not None:
            try:
                self.top.destroy()
            except tk.TclError:
                pass
            self.top = None
        self.on_done(region)

    # ------------------------------------------------------------------
    def _show(self, img: Image.Image) -> None:
        sw = u32.GetSystemMetrics(0)
        sh = u32.GetSystemMetrics(1)
        self._scale = min(1.0, sw / img.width, sh / img.height)
        w = int(img.width * self._scale)
        h = int(img.height * self._scale)
        shown = img.resize((w, h), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(shown)

        self.top = tk.Toplevel(self.root)
        self.top.title("在截图上拖拽，框住游戏聊天区域（Esc 取消）")
        self.top.attributes("-topmost", True)
        self.top.geometry(f"{w}x{h}+{self._origin[0]}+{self._origin[1]}")
        self.top.configure(bg="black")
        self.canvas = tk.Canvas(self.top, width=w, height=h, bg="black",
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas.create_text(
            w // 2, 26, text="拖拽框住聊天文字区域 · Esc 取消",
            fill="#ffffff", font=(FONT, 13, "bold"))

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.top.bind("<Escape>", lambda e: self._finish(None))
        self.top.focus_force()

    def _press(self, ev) -> None:
        self._start = (ev.x, ev.y)
        if self._rect:
            self.canvas.delete(self._rect)
        self._rect = self.canvas.create_rectangle(ev.x, ev.y, ev.x, ev.y,
                                                  outline="#3b82f6", width=3)
        self._size_id = self.canvas.create_text(
            ev.x + 10, ev.y - 16, text="", anchor="w", fill="#3b82f6",
            font=(FONT, 11, "bold"))

    def _drag(self, ev) -> None:
        if not self._start:
            return
        x0, y0 = self._start
        self.canvas.coords(self._rect, x0, y0, ev.x, ev.y)
        self.canvas.coords(self._size_id, min(x0, ev.x) + 10, min(y0, ev.y) - 16)
        s = self._scale or 1.0
        self.canvas.itemconfigure(
            self._size_id, text=f"{int(abs(ev.x - x0) / s)} × {int(abs(ev.y - y0) / s)}")

    def _release(self, ev) -> None:
        if not self._start:
            return self._finish(None)
        x0, y0 = self._start
        s = self._scale or 1.0
        x = min(x0, ev.x) / s + self._origin[0]
        y = min(y0, ev.y) / s + self._origin[1]
        w = abs(ev.x - x0) / s
        h = abs(ev.y - y0) / s
        if w < 40 or h < 20:
            return self._finish(None)
        self._finish([int(x), int(y), int(w), int(h)])
