"""弹幕浮层：透明、置顶、鼠标穿透的全屏文字层。

实现要点：
* Tk 的 ``-transparentcolor`` 把某个颜色挖成完全透明，配合 ``WS_EX_LAYERED |
  WS_EX_TRANSPARENT`` 让整层鼠标穿透，游戏照常操作；
* 每条弹幕用一组同 tag 的 canvas item（描边 + 正文），移动时按 tag 批量移动；
* 轨道分配看每条轨道最右侧那条弹幕的右边缘，避免叠字。
"""
from __future__ import annotations

import ctypes
import time
import tkinter as tk
from dataclasses import dataclass

import tkinter.font as tkfont

from ..config import Config

MAGIC = "#010203"
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

u32 = ctypes.windll.user32


def set_click_through(hwnd: int) -> None:
    style = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    u32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


@dataclass
class DanmakuItem:
    tag: str
    x: float
    w: float
    lane: int
    born: float


class DanmakuOverlay:
    def __init__(self, root: tk.Tk, cfg: Config):
        self.cfg = cfg
        self.visible = True
        self.items: list[DanmakuItem] = []
        self._seq = 0
        self._last = time.perf_counter()
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=MAGIC)
        self.canvas = tk.Canvas(self.win, bg=MAGIC, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._hwnd = 0
        self.apply_region()
        self.win.deiconify()
        self.win.update_idletasks()
        hwnd = u32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        self._hwnd = hwnd
        try:
            self.win.attributes("-transparentcolor", MAGIC)
            set_click_through(hwnd)
        except tk.TclError:
            pass
        self._keep_topmost()
        self.tick()

    # ------------------------------------------------------------------
    @property
    def lane_height(self) -> int:
        return int(self.cfg.danmaku_font_size * 1.62)

    @property
    def font(self) -> tuple:
        return (self.cfg.font_family, -int(self.cfg.danmaku_font_size), "bold")

    def resolve_region(self) -> tuple[int, int, int, int]:
        cfg = self.cfg
        if cfg.danmaku_band == "custom" and cfg.danmaku_region:
            x, y, w, h = cfg.danmaku_region
            return x, y, max(200, w), max(80, h)
        if cfg.danmaku_band == "above_chat" and cfg.chat_region:
            cx, cy, cw, ch = cfg.chat_region
            h = self.lane_height * cfg.danmaku_lanes + 10
            return cx, max(0, cy - h - 8), max(400, cw), h
        sx = u32.GetSystemMetrics(76)
        sy = u32.GetSystemMetrics(77)
        sw = u32.GetSystemMetrics(78)
        sh = u32.GetSystemMetrics(79)
        h = self.lane_height * cfg.danmaku_lanes + 10
        if cfg.danmaku_band == "top":
            return sx, sy + 40, sw, h
        # 默认放在屏幕上部（避开准星区域）
        return sx, sy + int(sh * 0.06), sw, h

    def apply_region(self) -> None:
        x, y, w, h = self.resolve_region()
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.canvas.configure(width=w, height=h)
        self.width, self.height = w, h

    # ------------------------------------------------------------------
    def push(self, text: str, color: str = "#ffffff") -> None:
        if not text.strip() or not self.visible:
            return
        self._seq += 1
        tag = f"d{self._seq}"
        x = float(self.width + 10)
        lanes = max(1, int(self.cfg.danmaku_lanes))
        lane = self._pick_lane(lanes)
        y = 6 + lane * self.lane_height + self.lane_height // 2
        stroke = "#000000"
        ids = []
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
            ids.append(self.canvas.create_text(
                x + dx, y + dy, text=text, fill=stroke, font=self.font,
                anchor="w", tags=(tag,)))
        ids.append(self.canvas.create_text(
            x, y, text=text, fill=color, font=self.font, anchor="w", tags=(tag,)))
        box = self.canvas.bbox(tag)
        w = (box[2] - box[0]) if box else 200
        self.items.append(DanmakuItem(tag, x, w, lane, time.perf_counter()))

    def _pick_lane(self, lanes: int) -> int:
        margin = 40
        busy = {i: 0.0 for i in range(lanes)}
        for it in self.items:
            if it.lane in busy:
                busy[it.lane] = max(busy[it.lane], it.x + it.w)
        free = [i for i in range(lanes) if busy[i] < self.width - margin]
        if free:
            return min(free, key=lambda i: busy[i])
        return min(busy, key=lambda i: busy[i])

    # ------------------------------------------------------------------
    def tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.08, now - self._last)
        self._last = now
        step = float(self.cfg.danmaku_speed) * dt
        for it in self.items[:]:
            it.x -= step
            self.canvas.move(it.tag, -step, 0)
            if it.x + it.w < -30:
                self.canvas.delete(it.tag)
                self.items.remove(it)
        self.win.after(16, self.tick)

    def _keep_topmost(self) -> None:
        if self.visible and self._hwnd:
            try:
                self.win.attributes("-topmost", True)
            except tk.TclError:
                pass
        self.win.after(1500, self._keep_topmost)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.canvas.delete("all")
        self.items.clear()

    def set_visible(self, flag: bool) -> None:
        self.visible = flag
        if flag:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
        else:
            self.win.withdraw()

    def set_font_size(self, size: int) -> None:
        self.cfg.danmaku_font_size = int(size)
        self.clear()
        self.apply_region()

    def close(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ----------------------------------------------------------------------
class RegionPicker:
    """全屏半透明遮罩，拖拽框选一块区域。"""

    def __init__(self, root: tk.Tk, on_done, hint: str = "拖拽框选游戏聊天区域 · 框完自动记住 · Esc 取消"):
        self.on_done = on_done
        self.start = None
        vx = u32.GetSystemMetrics(76)
        vy = u32.GetSystemMetrics(77)
        vw = u32.GetSystemMetrics(78)
        vh = u32.GetSystemMetrics(79)
        self.origin = (vx, vy)
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.attributes("-alpha", 0.32)
        self.top.configure(bg="black")
        self.top.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.canvas = tk.Canvas(self.top, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.hint_id = self.canvas.create_text(
            vw // 2, 60, text=hint, fill="#ffffff", tags=("hint",),
            font=("Microsoft YaHei UI", -28, "bold"))
        self.rect = None
        self.size_id = None
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.top.bind("<Escape>", lambda e: self._cancel())
        self.top.focus_force()

    def _press(self, ev) -> None:
        self.start = (ev.x, ev.y)
        self.canvas.delete("hint")
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(ev.x, ev.y, ev.x, ev.y,
                                                 outline="#00e5ff", width=3)
        self.size_id = self.canvas.create_text(ev.x + 8, ev.y - 16, text="", anchor="w",
                                               fill="#00e5ff",
                                               font=("Microsoft YaHei UI", -18, "bold"))

    def _drag(self, ev) -> None:
        if not self.start:
            return
        x0, y0 = self.start
        self.canvas.coords(self.rect, x0, y0, ev.x, ev.y)
        self.canvas.coords(self.size_id, min(x0, ev.x) + 8, min(y0, ev.y) - 16)
        self.canvas.itemconfigure(self.size_id,
                                  text=f"{abs(ev.x - x0)} × {abs(ev.y - y0)}")

    def _release(self, ev) -> None:
        if not self.start:
            return self._cancel()
        x0, y0 = self.start
        x, y = min(x0, ev.x), min(y0, ev.y)
        w, h = abs(ev.x - x0), abs(ev.y - y0)
        ox, oy = self.origin
        self.top.destroy()
        if w < 40 or h < 20:
            self.on_done(None)
        else:
            self.on_done([x + ox, y + oy, w, h])

    def _cancel(self) -> None:
        try:
            self.top.destroy()
        finally:
            self.on_done(None)

# ----------------------------------------------------------------------
class SubtitleBox:
    """屏幕下方居中的半透明字幕框：译文一条条往上叠，到时间自动消失。

    和滚动弹幕的区别：位置固定、不挡视野、读起来像字幕。
    """

    def __init__(self, root: tk.Tk, cfg: Config):
        self.cfg = cfg
        self.visible = True
        self.entries: list[dict] = []
        self._shown = False
        self._hwnd = 0
        self.width = 800
        self.screen = (0, 0, 1920, 1080)
        self.bottom_y = 700
        self._font = tkfont.Font(family=cfg.font_family,
                                 size=-int(cfg.danmaku_font_size), weight="bold")
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=cfg.box_bg)
        try:
            self.win.attributes("-alpha", float(cfg.box_alpha))
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, bg=cfg.box_bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.apply_region()
        self.win.update_idletasks()
        hwnd = u32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        self._hwnd = hwnd
        set_click_through(hwnd)
        self._keep_topmost()
        self.tick()

    # ------------------------------------------------------------------
    def apply_region(self) -> None:
        sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        self.screen = (0, 0, sw, sh)
        ratio = float(getattr(self.cfg, "box_width_ratio", 0.46))
        self.width = max(460, min(int(sw * ratio), 1500))
        self.bottom_y = sh - int(getattr(self.cfg, "box_bottom_margin", 260))
        self._relayout()

    @property
    def line_height(self) -> int:
        return int(self.cfg.danmaku_font_size * 1.62)

    # ------------------------------------------------------------------
    def push(self, text: str, color: str = "#ffffff") -> None:
        if not self.visible or not text.strip():
            return
        self.entries.append({"text": text.strip(), "color": color, "ts": time.time()})
        limit = max(1, int(getattr(self.cfg, "box_max_lines", 4)))
        if len(self.entries) > limit:
            del self.entries[: len(self.entries) - limit]
        self._relayout()

    def _fit(self, text: str, maxw: int) -> str:
        if self._font.measure(text) <= maxw:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._font.measure(text[:mid] + "…") <= maxw:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + "…"

    def _relayout(self) -> None:
        n = len(self.entries)
        if n == 0 or not self.visible:
            if self._shown:
                self.win.withdraw()
                self._shown = False
            return
        lh = self.line_height
        pad_x, pad_y = 24, 12
        h = n * lh + pad_y * 2
        x = self.screen[0] + (self.screen[2] - self.width) // 2
        y = self.bottom_y - h
        self.win.geometry(f"{self.width}x{h}+{x}+{y}")
        self.canvas.configure(width=self.width, height=h)
        self.canvas.delete("all")
        self.canvas.create_rectangle(1, 1, self.width - 1, h - 1,
                                     outline=str(getattr(self.cfg, "box_border", "#33415a")),
                                     width=1)
        for i, e in enumerate(self.entries):
            cy = pad_y + i * lh + lh // 2
            txt = self._fit(e["text"], self.width - pad_x * 2)
            self.canvas.create_text(self.width // 2, cy, text=txt, anchor="center",
                                    fill=e["color"], font=self._font)
        if not self._shown:
            self.win.deiconify()
            self._shown = True
        self.win.attributes("-topmost", True)

    # ------------------------------------------------------------------
    def tick(self) -> None:
        ttl = float(getattr(self.cfg, "box_ttl_s", 8.0))
        now = time.time()
        before = len(self.entries)
        self.entries = [e for e in self.entries if now - e["ts"] < ttl]
        if len(self.entries) != before:
            self._relayout()
        self.win.after(250, self.tick)

    def _keep_topmost(self) -> None:
        if self._shown:
            try:
                self.win.attributes("-topmost", True)
            except tk.TclError:
                pass
        self.win.after(1500, self._keep_topmost)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.entries.clear()
        self.canvas.delete("all")
        self._relayout()

    def set_visible(self, flag: bool) -> None:
        self.visible = flag
        if not flag:
            self.win.withdraw()
            self._shown = False
        else:
            self._relayout()

    def set_font_size(self, size: int) -> None:
        self.cfg.danmaku_font_size = int(size)
        self._font.configure(size=-int(size))
        self._relayout()

    def close(self) -> None:
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def create_view(root: tk.Tk, cfg: Config):
    """按配置创建底部字幕框或全屏滚动弹幕。"""
    if getattr(cfg, "display_mode", "box") == "scroll":
        return DanmakuOverlay(root, cfg)
    try:
        from .subs import LayeredSubtitleBox
        return LayeredSubtitleBox(root, cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"[提示] 分层窗口不可用（{exc}），退回 Tk 字幕框", flush=True)
        return SubtitleBox(root, cfg)
