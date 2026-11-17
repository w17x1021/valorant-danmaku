"""底部字幕框（Win32 分层窗口 + Pillow 渲染）。

Tk 的 -transparentcolor 只能做"整块透明"，做不出圆角、投影、渐隐这些效果。
这里直接用 UpdateLayeredWindow 送一张 32 位预乘 alpha 的位图上去，
于是圆角、投影、半透明、抗锯齿全都能做到，而且窗口对鼠标完全穿透。
"""
from __future__ import annotations

import ctypes as c
import threading
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import Config

user32 = c.WinDLL("user32", use_last_error=True)
gdi32 = c.WinDLL("gdi32", use_last_error=True)
kernel32 = c.WinDLL("kernel32", use_last_error=True)

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_POPUP = 0x80000000
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
PM_REMOVE = 0x0001
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


class BLENDFUNCTION(c.Structure):
    _fields_ = [("BlendOp", c.c_ubyte), ("BlendFlags", c.c_ubyte),
                ("SourceConstantAlpha", c.c_ubyte), ("AlphaFormat", c.c_ubyte)]


class SIZE(c.Structure):
    _fields_ = [("cx", c.c_long), ("cy", c.c_long)]


class POINT(c.Structure):
    _fields_ = [("x", c.c_long), ("y", c.c_long)]


class BITMAPINFOHEADER(c.Structure):
    _fields_ = [("biSize", c.c_uint32), ("biWidth", c.c_int32), ("biHeight", c.c_int32),
                ("biPlanes", c.c_uint16), ("biBitCount", c.c_uint16),
                ("biCompression", c.c_uint32), ("biSizeImage", c.c_uint32),
                ("biXPelsPerMeter", c.c_int32), ("biYPelsPerMeter", c.c_int32),
                ("biClrUsed", c.c_uint32), ("biClrImportant", c.c_uint32)]


class BITMAPINFO(c.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", c.c_uint32 * 3)]


WNDPROC = c.WINFUNCTYPE(c.c_ssize_t, wintypes.HWND, c.c_uint, c.c_size_t, c.c_ssize_t)


class WNDCLASSW(c.Structure):
    _fields_ = [("style", c.c_uint), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", c.c_int), ("cbWndExtra", c.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    c.c_int, c.c_int, c.c_int, c.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]

user32.UpdateLayeredWindow.restype = wintypes.BOOL
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, c.POINTER(POINT), c.POINTER(SIZE), wintypes.HDC,
    c.POINTER(POINT), wintypes.DWORD, c.POINTER(BLENDFUNCTION), wintypes.DWORD]

user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, c.c_int, c.c_int,
                                c.c_int, c.c_int, c.c_uint]

gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, c.POINTER(BITMAPINFO), wintypes.UINT,
                                   c.POINTER(c.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

user32.DefWindowProcW.restype = c.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, c.c_uint, c.c_size_t, c.c_ssize_t]
_defproc = WNDPROC(lambda hwnd, msg, wparam, lparam: user32.DefWindowProcW(hwnd, msg, wparam, lparam))
_CLASS_NAME = "VdmSubtitleBoxWnd"
_class_atom = None
_class_lock = threading.Lock()


def _register_class() -> None:
    global _class_atom
    with _class_lock:
        if _class_atom:
            return
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = _defproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = _CLASS_NAME
        atom = user32.RegisterClassW(c.byref(wc))
        if not atom and c.get_last_error() not in (0, 1410):
            raise c.WinError(c.get_last_error())
        _class_atom = atom or 1


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


class LayeredWindow:
    """一个鼠标穿透、置顶、逐像素 alpha 的窗口。"""

    def __init__(self):
        _register_class()
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE | WS_EX_TOPMOST,
            _CLASS_NAME, "", WS_POPUP, 0, 0, 1, 1, None, None,
            kernel32.GetModuleHandleW(None), None)
        if not self.hwnd:
            raise c.WinError(c.get_last_error())
        self.hdc_screen = user32.GetDC(None)
        self.mem_dc = gdi32.CreateCompatibleDC(self.hdc_screen)
        self.bitmap = None
        self.old_bitmap = None
        self.bits = c.c_void_p()
        self.size = (0, 0)
        self.visible = False
        self.alpha = 255

    # ------------------------------------------------------------------
    def _ensure_surface(self, w: int, h: int) -> None:
        if self.size == (w, h) and self.bitmap:
            return
        if self.bitmap:
            gdi32.SelectObject(self.mem_dc, self.old_bitmap)
            gdi32.DeleteObject(self.bitmap)
            self.bitmap = None
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = c.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h          # 负数 = 自上而下
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0      # BI_RGB
        self.bitmap = gdi32.CreateDIBSection(
            self.mem_dc, c.byref(bmi), 0, c.byref(self.bits), None, 0)
        if not self.bitmap:
            raise c.WinError(c.get_last_error())
        self.old_bitmap = gdi32.SelectObject(self.mem_dc, self.bitmap)
        self.size = (w, h)

    def _write(self, img: Image.Image) -> None:
        w, h = img.size
        arr = np.asarray(img.convert("RGBA"), dtype=np.float32)
        alpha = arr[:, :, 3:4] / 255.0
        out = np.empty((h, w, 4), dtype=np.uint8)
        out[:, :, 0] = (arr[:, :, 2] * alpha[:, :, 0]).astype(np.uint8)   # B
        out[:, :, 1] = (arr[:, :, 1] * alpha[:, :, 0]).astype(np.uint8)   # G
        out[:, :, 2] = (arr[:, :, 0] * alpha[:, :, 0]).astype(np.uint8)   # R
        out[:, :, 3] = arr[:, :, 3].astype(np.uint8)
        c.memmove(self.bits, out.tobytes(), out.nbytes)

    def render(self, img: Image.Image, x: int, y: int, alpha: int = 255) -> None:
        w, h = img.size
        self._ensure_surface(w, h)
        self._write(img)
        gdi32.GdiFlush()
        dst = POINT(x, y)
        size = SIZE(w, h)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, max(0, min(255, alpha)), AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, self.hdc_screen, c.byref(dst),
                                   c.byref(size), self.mem_dc, c.byref(src), 0,
                                   c.byref(blend), ULW_ALPHA)
        if not self.visible:
            user32.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE
            self.visible = True
        user32.SetWindowPos(self.hwnd, wintypes.HWND(-1), 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def keep_topmost(self) -> None:
        """有的游戏会把自己顶到最前，这里定期再抢一次。"""
        if self.hwnd:
            user32.SetWindowPos(self.hwnd, wintypes.HWND(-1), 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def hide(self) -> None:
        if self.visible:
            user32.ShowWindow(self.hwnd, 0)  # SW_HIDE
            self.visible = False

    def pump(self) -> None:
        msg = wintypes.MSG()
        while user32.PeekMessageW(c.byref(msg), self.hwnd, 0, 0, PM_REMOVE):
            user32.TranslateMessage(c.byref(msg))
            user32.DispatchMessageW(c.byref(msg))

    def destroy(self) -> None:
        try:
            if self.bitmap:
                gdi32.SelectObject(self.mem_dc, self.old_bitmap)
                gdi32.DeleteObject(self.bitmap)
                self.bitmap = None
            if self.mem_dc:
                gdi32.DeleteDC(self.mem_dc)
                self.mem_dc = None
            if self.hdc_screen:
                user32.ReleaseDC(None, self.hdc_screen)
                self.hdc_screen = None
            if self.hwnd:
                user32.DestroyWindow(self.hwnd)
                self.hwnd = None
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------------
class LayeredSubtitleBox:
    """底部居中的圆角字幕气泡，译文向上叠。"""

    MARGIN = 22          # 给投影留的边距
    RADIUS = 14
    PAD_X = 20
    PAD_Y = 10

    def __init__(self, root, cfg: Config):
        self.cfg = cfg
        self.root = root
        self.visible = True
        self.entries: list[dict] = []
        self.window = LayeredWindow()
        self._shadow_cache: dict[tuple[int, int], Image.Image] = {}
        self._img: Image.Image | None = None
        self._img_pos = (0, 0)
        self._img_key = None
        self._shown = False
        self._fade = 0.0
        self._state = "hidden"      # hidden / showing / shown / hiding
        self._last_render = 0.0
        self._font = _load_font(self.font_px)
        self.screen = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        root.after(60, self.tick_anim)
        root.after(500, self.tick_expire)

    # ------------------------------------------------------------------
    @property
    def font_px(self) -> int:
        return int(self.cfg.danmaku_font_size)

    def _line_height(self) -> int:
        return int(self.font_px * float(getattr(self.cfg, "box_line_spacing", 1.62) or 1.62))

    # ------------------------------------------------------------------
    def push(self, text: str, color: str = "#ffffff") -> None:
        if not self.visible or not text.strip():
            return
        self.entries.append({"text": text.strip(), "color": color, "ts": time.time()})
        limit = max(1, int(self.cfg.box_max_lines))
        if len(self.entries) > limit:
            del self.entries[: len(self.entries) - limit]
        if self._state in ("hidden", "hiding"):
            self._state = "showing"
            self._fade = 0.0
        self._render(alpha=255 if self._state == "shown" else max(38, int(255 * self._fade)))

    def set_visible(self, flag: bool) -> None:
        self.visible = flag
        if not flag:
            self.entries.clear()
            self.window.hide()
            self._state = "hidden"
            self._shown = False

    def set_font_size(self, size: int) -> None:
        self.cfg.danmaku_font_size = int(size)
        self._font = _load_font(self.font_px)
        self._shadow_cache.clear()
        self._render()

    def set_box_width(self, px: int) -> None:
        self.cfg.box_width_px = max(320, min(int(px), 1600))
        self._render()

    def set_max_lines(self, n: int) -> None:
        self.cfg.box_max_lines = max(1, min(int(n), 6))
        if len(self.entries) > self.cfg.box_max_lines:
            del self.entries[: len(self.entries) - self.cfg.box_max_lines]
        self._render()

    def clear(self) -> None:
        self.entries.clear()
        self.window.hide()
        self._state = "hidden"
        self._shown = False

    def apply_region(self) -> None:
        self.screen = (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        self._render()

    def close(self) -> None:
        self.window.destroy()

    # ------------------------------------------------------------------
    def tick_expire(self) -> None:
        ttl = float(self.cfg.box_ttl_s)
        now = time.time()
        before = len(self.entries)
        self.entries = [e for e in self.entries if now - e["ts"] < ttl]
        if len(self.entries) != before:
            if self.entries:
                self._render()
            else:
                self._state = "hiding"
        self.root.after(400, self.tick_expire)

    def tick_anim(self) -> None:
        self._ticks = getattr(self, "_ticks", 0) + 1
        if self._ticks % 20 == 0 and self._shown:
            try:                      # 每约 0.9 秒重新抢一次置顶
                self.window.keep_topmost()
            except Exception:  # noqa: BLE001
                pass
        if self._state == "showing":
            self._fade = min(1.0, self._fade + 0.18)
            if self._fade >= 1.0:
                self._state = "shown"
            self._render(alpha=int(255 * self._fade))
        elif self._state == "hiding":
            self._fade = max(0.0, self._fade - 0.16)
            if self._fade <= 0.01:
                self._state = "hidden"
                self._shown = False
                self.window.hide()
            else:
                self._render(alpha=int(255 * self._fade))
        self.window.pump()
        self.root.after(45, self.tick_anim)

    # ------------------------------------------------------------------
    def _shadow(self, w: int, h: int) -> Image.Image:
        key = (w, h)
        hit = self._shadow_cache.get(key)
        if hit is not None:
            return hit
        m = self.MARGIN
        layer = Image.new("RGBA", (w + m * 2, h + m * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle([m, m + 4, m + w, m + h + 4], radius=self.RADIUS,
                            fill=(0, 0, 0, 170))
        layer = layer.filter(ImageFilter.GaussianBlur(9))
        if len(self._shadow_cache) > 12:
            self._shadow_cache.clear()
        self._shadow_cache[key] = layer
        return layer

    def _compose(self) -> tuple[Image.Image, int, int]:
        m = self.MARGIN
        lh = self._line_height()
        px = int(getattr(self.cfg, "box_width_px", 0) or 0)
        max_w = px if px > 0 else int(self.screen[0] * float(self.cfg.box_width_ratio))
        max_w = max(320, min(max_w, 1600))
        inner_max = max(160, max_w - self.PAD_X * 2)

        lines = []
        mic_prefix = "🎤 "
        for e in self.entries:
            raw = e["text"]
            mic = raw.startswith(mic_prefix)
            if mic:
                raw = raw[len(mic_prefix):]
            speaker, sep, body = raw.partition(": ")
            if sep:
                lines.append((speaker + ": ", body, e["color"], mic))
            else:
                lines.append(("", raw, e["color"], mic))

        icon_w = max(10, int(self.font_px * 0.62))
        widths = []
        for name, body, _, mic in lines:
            total = self._font.getlength(name) + self._font.getlength(body)
            widths.append(total + (icon_w + 6 if mic else 0))
        box_w = int(min(max_w, max(300, max(widths) + self.PAD_X * 2 + 4)))
        box_h = lh * len(lines) + self.PAD_Y * 2

        img = Image.new("RGBA", (box_w + m * 2, box_h + m * 2), (0, 0, 0, 0))
        img.alpha_composite(self._shadow(box_w, box_h), (0, 0))
        d = ImageDraw.Draw(img)

        bg = _hex_to_rgba(self.cfg.box_bg, int(getattr(self.cfg, "box_bg_alpha", 205)))
        d.rounded_rectangle([m, m, m + box_w, m + box_h], radius=self.RADIUS, fill=bg)
        # 顶部一层很淡的高光，让框看起来有质感
        d.rounded_rectangle([m + 1, m + 1, m + box_w - 1, m + box_h - 1],
                            radius=self.RADIUS - 1,
                            outline=(255, 255, 255, 26), width=1)

        inner_w = box_w - self.PAD_X * 2
        for i, (name, body, color, mic) in enumerate(lines):
            cy = m + self.PAD_Y + i * lh + lh // 2
            text_color = _hex_to_rgba(color, 255)
            name_color = _hex_to_rgba(color, 190)
            extra = icon_w + 6 if mic else 0
            total = self._font.getlength(name) + self._font.getlength(body) + extra
            if total > inner_w - 1:
                body = self._ellipsize(body, inner_w - self._font.getlength(name) - extra)
                total = self._font.getlength(name) + self._font.getlength(body) + extra
            x = m + (box_w - total) / 2
            if mic:
                _draw_mic(d, x, cy, icon_w, text_color)
                x += extra
            if name:
                # 文字底下加一点暗影，压住游戏画面
                d.text((x + 1, cy + 1), name, font=self._font, fill=(0, 0, 0, 120), anchor="lm")
                d.text((x, cy), name, font=self._font, fill=name_color, anchor="lm")
                x += self._font.getlength(name)
            d.text((x + 1, cy + 1), body, font=self._font, fill=(0, 0, 0, 120), anchor="lm")
            d.text((x, cy), body, font=self._font, fill=text_color, anchor="lm")

        x = (self.screen[0] - (box_w + m * 2)) // 2
        y = self.screen[1] - int(self.cfg.box_bottom_margin) - box_h - m
        return img, x, y

    def _ellipsize(self, text: str, maxw: float) -> str:
        if self._font.getlength(text) <= maxw:
            return text
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._font.getlength(text[:mid] + "…") <= maxw:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + "…"

    def _render(self, alpha: int = 255) -> None:
        if not self.visible or not self.entries:
            return
        key = (tuple(e["text"] for e in self.entries), self.font_px,
               self.screen, float(self.cfg.box_width_ratio),
               int(getattr(self.cfg, "box_width_px", 0) or 0),
               int(self.cfg.box_bottom_margin), int(getattr(self.cfg, "box_max_lines", 4)),
               int(getattr(self.cfg, "box_bg_alpha", 205)))
        if key != self._img_key:
            img, x, y = self._compose()
            self._img, self._img_pos = img, (x, y)
            self._img_key = key
        self.window.render(self._img, self._img_pos[0], self._img_pos[1], alpha)
        self._shown = True


def _hex_to_rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    value = (value or "#000000").lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        r, g, b = 0, 0, 0
    return (r, g, b, max(0, min(255, int(alpha))))

def _draw_mic(d: ImageDraw.ImageDraw, x: float, cy: float, w: int, color: tuple) -> None:
    """画一个小话筒图标（比 emoji 稳，任何字体都能显示）。"""
    s = w / 12.0
    cx = x + w / 2
    top = cy - 6 * s
    body_w = 5 * s
    d.rounded_rectangle([cx - body_w / 2, top, cx + body_w / 2, cy + 1 * s],
                        radius=body_w / 2, fill=color)
    d.arc([cx - 5 * s, cy - 4 * s, cx + 5 * s, cy + 5 * s], start=0, end=180,
          fill=color, width=max(1, int(1.6 * s)))
    d.line([(cx, cy + 5 * s), (cx, cy + 7 * s)], fill=color, width=max(1, int(1.6 * s)))
    d.line([(cx - 3 * s, cy + 7.5 * s), (cx + 3 * s, cy + 7.5 * s)],
           fill=color, width=max(1, int(1.6 * s)))
