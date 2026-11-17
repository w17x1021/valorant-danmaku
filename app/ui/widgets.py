"""自绘控件：圆角窗口、圆角按钮、导航项、状态胶囊、滑块、提示条。"""
from __future__ import annotations

import ctypes
import tkinter as tk

from .theme import (ACCENT, ACCENT_DARK, ACCENT_SOFT, ACCENT_TEXT, BG, BORDER, CARD,
                    CARD_SOFT, DANGER, DANGER_SOFT, FONT, GREEN, MAGIC, RAIL, SHADOW,
                    TEXT, TEXT_DIM, TEXT_FAINT, darken, lighten, round_poly)

u32 = ctypes.windll.user32


def _draw_glyph(c: tk.Canvas, glyph: str, cx: float, cy: float, color: str,
                scale: float = 1.0) -> None:
    """在画布上画一个简单的线性图标。"""
    k = scale
    if glyph == "chat":
        c.create_rectangle(cx - 8 * k, cy - 7 * k, cx + 8 * k, cy + 5 * k,
                           outline=color, width=max(1, int(1.6 * k)))
        c.create_line(cx - 3 * k, cy + 5 * k, cx - 3 * k, cy + 9 * k,
                      cx + 2 * k, cy + 5 * k, fill=color, width=max(1, int(1.6 * k)))
    elif glyph == "mic":
        c.create_rectangle(cx - 3 * k, cy - 10 * k, cx + 3 * k, cy + 2 * k,
                           outline=color, width=max(1, int(1.6 * k)))
        c.create_arc(cx - 7 * k, cy - 6 * k, cx + 7 * k, cy + 6 * k, start=0,
                     extent=180, style="arc", outline=color, width=max(1, int(1.6 * k)))
        c.create_line(cx, cy + 6 * k, cx, cy + 10 * k, fill=color, width=max(1, int(1.6 * k)))
        c.create_line(cx - 4 * k, cy + 10 * k, cx + 4 * k, cy + 10 * k,
                      fill=color, width=max(1, int(1.6 * k)))
    elif glyph == "gear":
        c.create_oval(cx - 4 * k, cy - 4 * k, cx + 4 * k, cy + 4 * k,
                      outline=color, width=max(1, int(1.6 * k)))
        for dx, dy in ((0, -9), (0, 9), (-9, 0), (9, 0), (-6, -6), (6, 6), (-6, 6), (6, -6)):
            c.create_line(cx + dx * 0.72 * k, cy + dy * 0.72 * k, cx + dx * k, cy + dy * k,
                          fill=color, width=max(1, int(1.6 * k)))
    elif glyph == "box":
        c.create_rectangle(cx - 8 * k, cy - 6 * k, cx + 8 * k, cy + 7 * k,
                           outline=color, width=max(1, int(1.6 * k)))
        c.create_line(cx - 8 * k, cy - 1 * k, cx + 8 * k, cy - 1 * k, fill=color,
                      width=max(1, int(1.6 * k)))
    elif glyph == "power":
        c.create_arc(cx - 8 * k, cy - 8 * k, cx + 8 * k, cy + 8 * k, start=40,
                     extent=280, style="arc", outline=color, width=max(1, int(1.6 * k)))
        c.create_line(cx, cy - 10 * k, cx, cy - 1 * k, fill=color, width=max(1, int(1.6 * k)))
    elif glyph == "close":
        c.create_line(cx - 6 * k, cy - 6 * k, cx + 6 * k, cy + 6 * k, fill=color,
                      width=max(1, int(1.6 * k)))
        c.create_line(cx - 6 * k, cy + 6 * k, cx + 6 * k, cy - 6 * k, fill=color,
                      width=max(1, int(1.6 * k)))


class RoundedWindow(tk.Toplevel):
    """无系统边框的圆角卡片窗口，自带标题栏（可拖动）+ 关闭按钮。"""

    HEADER = 46

    def __init__(self, master, title: str, width: int, height: int,
                 radius: int = 16, on_close=None, icon: bool = True,
                 bg_fill: str = CARD):
        super().__init__(master)
        self.withdraw()
        self.title(title)          # 给系统一个标题，单实例找窗口时靠它
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=MAGIC)
        self._cw, self._ch, self._rad = width, height, radius
        self._on_close = on_close
        self._drag = None
        self._icon = icon

        self.canvas = tk.Canvas(self, width=width, height=height, bg=MAGIC,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        # 卡片底（浅色 + 细边）
        round_poly(self.canvas, 1, 1, width - 1, height - 1, radius,
                   fill=bg_fill, outline=BORDER, width=1)

        x = 18
        if icon:
            round_poly(self.canvas, 16, 12, 44, 40, 9, fill=ACCENT, outline="")
            _draw_glyph(self.canvas, "chat", 30, 26, "#ffffff", 0.72)
            x = 52
        self.canvas.create_text(x, self.HEADER // 2 + 1, text=title, anchor="w",
                                fill=TEXT, font=(FONT, 11, "bold"))

        self._close_id = self.canvas.create_text(
            width - 22, self.HEADER // 2 + 1, text="✕", fill=TEXT_FAINT,
            font=(FONT, 11), tags=("close",))
        self.canvas.tag_bind("close", "<Enter>", lambda e: self.canvas.itemconfigure(
            self._close_id, fill=TEXT))
        self.canvas.tag_bind("close", "<Leave>", lambda e: self.canvas.itemconfigure(
            self._close_id, fill=TEXT_FAINT))
        self.canvas.tag_bind("close", "<Button-1>", lambda e: self._close())
        self.canvas.create_line(0, self.HEADER, width, self.HEADER, fill=BORDER, width=1)

        self.body = tk.Frame(self, bg=bg_fill)
        self.body.place(x=1, y=self.HEADER + 1, width=width - 2,
                        height=height - self.HEADER - 12)

        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.bind("<Escape>", lambda e: self._close())

        self.show_at_default()

    # ------------------------------------------------------------------
    def show_at_default(self) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, sw - self._cw - 24)
        y = max(0, sh - self._ch - 72)
        self.geometry(f"{self._cw}x{self._ch}+{x}+{y}")
        self.deiconify()
        self.update_idletasks()
        try:
            self.attributes("-transparentcolor", MAGIC)
        except tk.TclError:
            pass
        self.lift()

    def place_at(self, x: int, y: int) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(int(x), max(0, sw - self._cw)))
        y = max(0, min(int(y), max(0, sh - self._ch)))
        self.geometry(f"{self._cw}x{self._ch}+{x}+{y}")

    # ------------------------------------------------------------------
    def _press(self, ev) -> None:
        if ev.y <= self.HEADER:
            self._drag = (ev.x_root - self.winfo_x(), ev.y_root - self.winfo_y())

    def _motion(self, ev) -> None:
        if self._drag:
            self.geometry(f"+{ev.x_root - self._drag[0]}+{ev.y_root - self._drag[1]}")

    def _close(self) -> None:
        if self._on_close:
            self._on_close()
        else:
            self.destroy()


class RoundButton(tk.Canvas):
    """圆角按钮：primary / ghost / outline / danger。"""

    def __init__(self, master, text: str, command=None, width: int = 150,
                 height: int = 34, kind: str = "ghost", bg: str = CARD,
                 font_size: int = 9, radius: int = 9, bold: bool | None = None):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._cw, self._ch, self._rad = width, height, radius
        self._kind = kind
        self._text = text
        self._command = command
        self._enabled = True
        bold = (kind == "primary") if bold is None else bold
        self._font = (FONT, font_size, "bold" if bold else "normal")
        self._draw()
        self.bind("<Enter>", lambda e: self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw())
        self.bind("<Button-1>", lambda e: self._draw(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)

    # ------------------------------------------------------------------
    def _colors(self, hover=False, pressed=False):
        if self._kind == "primary":
            base = ACCENT
            if pressed:
                base = ACCENT_DARK
            elif hover:
                base = lighten(ACCENT, 0.10)
            return base, "#ffffff", base
        if self._kind == "danger":
            base = DANGER_SOFT
            if hover:
                base = lighten(DANGER_SOFT, 0.4)
            return base, DANGER, lighten(DANGER, 0.55)
        if self._kind == "outline":
            base = CARD
            if hover:
                base = ACCENT_SOFT
            return base, TEXT if hover else TEXT_DIM, BORDER if not hover else ACCENT
        base = CARD_SOFT
        if pressed:
            base = darken(CARD_SOFT, 0.06)
        elif hover:
            base = lighten(CARD_SOFT, 0.55)
        return base, TEXT, BORDER

    def _draw(self, hover=False, pressed=False) -> None:
        self.delete("all")
        fill, fg, border = self._colors(hover, pressed)
        round_poly(self, 1, 1, self._cw - 1, self._ch - 1, self._rad,
                   fill=fill, outline=border, width=1)
        self.create_text(self._cw / 2, self._ch / 2 + (1 if pressed else 0),
                         text=self._text, fill=fg, font=self._font)

    def _release(self, ev) -> None:
        self._draw(hover=True)
        if 0 <= ev.x <= self._cw and 0 <= ev.y <= self._ch and self._command:
            self._command()

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self._draw()

    def set_enabled(self, flag: bool) -> None:
        self._enabled = bool(flag)


class NavItem(tk.Canvas):
    """左侧导航项：图标 + 文字，选中时浅蓝胶囊。"""

    def __init__(self, master, glyph: str, text: str, command=None,
                 width: int = 158, height: int = 42, selected: bool = False,
                 bg: str = RAIL):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._cw, self._ch = width, height
        self._glyph = glyph
        self._text = text
        self._command = command
        self._selected = selected
        self._draw()
        self.bind("<Enter>", lambda e: self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw())
        self.bind("<ButtonRelease-1>", self._release)

    def _draw(self, hover=False) -> None:
        self.delete("all")
        if self._selected:
            fill, fg = ACCENT_SOFT, ACCENT_TEXT
        elif hover:
            fill, fg = CARD_SOFT, TEXT
        else:
            fill, fg = None, TEXT_DIM
        if fill:
            round_poly(self, 1, 2, self._cw - 1, self._ch - 2, 10,
                       fill=fill, outline="")
        _draw_glyph(self, self._glyph, 22, self._ch / 2, fg, 0.78)
        self.create_text(44, self._ch / 2 + 1, text=self._text, anchor="w",
                         fill=fg, font=(FONT, 10, "bold" if self._selected else "normal"))

    def _release(self, ev) -> None:
        if 0 <= ev.x <= self._cw and 0 <= ev.y <= self._ch and self._command:
            self._command()

    def set_selected(self, flag: bool) -> None:
        self._selected = flag
        self._draw()


class IconButton(tk.Canvas):
    """圆角方块图标按钮。"""

    def __init__(self, master, glyph: str, command=None, size: int = 42,
                 bg: str = CARD, active: bool = False, tooltip: str = ""):
        super().__init__(master, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self._cz = size
        self._glyph = glyph
        self._command = command
        self._active = active
        self._bg = bg
        self._draw()
        self.bind("<Enter>", lambda e: self._draw(hover=True))
        self.bind("<Leave>", lambda e: self._draw())
        self.bind("<Button-1>", lambda e: self._draw(pressed=True))
        self.bind("<ButtonRelease-1>", self._release)

    def _draw(self, hover=False, pressed=False) -> None:
        self.delete("all")
        s = self._cz
        if self._active:
            fill, border, fg = ACCENT_SOFT, ACCENT, ACCENT_TEXT
        else:
            fill = CARD_SOFT if hover else self._bg
            if pressed:
                fill = darken(CARD_SOFT, 0.05)
            border, fg = BORDER, TEXT if hover else TEXT_DIM
        round_poly(self, 1, 1, s - 1, s - 1, 10, fill=fill, outline=border, width=1)
        _draw_glyph(self, self._glyph, s / 2, s / 2, fg, 0.9)

    def _release(self, ev) -> None:
        self._draw(hover=True)
        if 0 <= ev.x <= self._cz and 0 <= ev.y <= self._cz and self._command:
            self._command()

    def set_active(self, flag: bool) -> None:
        self._active = flag
        self._draw()


class Pill(tk.Canvas):
    """小状态胶囊：圆点 + 文字。"""

    def __init__(self, master, text: str, color: str = GREEN, bg: str = CARD,
                 width: int = 150, height: int = 24):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._cw, self._ch = width, height
        self._text = text
        self._color = color
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        round_poly(self, 1, 1, self._cw - 1, self._ch - 1, 10,
                   fill=CARD_SOFT, outline="")
        self.create_oval(11, self._ch / 2 - 3, 17, self._ch / 2 + 3,
                         fill=self._color, outline="")
        self.create_text(24, self._ch / 2 + 1, text=self._text, anchor="w",
                         fill=TEXT_DIM, font=(FONT, 8))

    def set(self, text: str | None = None, color: str | None = None) -> None:
        if text is not None:
            self._text = text
        if color is not None:
            self._color = color
        self._draw()


class Slider(tk.Canvas):
    """标签 + 轨道 + 拖拽圆点 + 数值。"""

    def __init__(self, master, label: str, lo: int, hi: int, value: int,
                 command=None, width: int = 330, height: int = 34,
                 bg: str = CARD, step: int = 1, recommended: int | None = None):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._cw, self._ch = width, height
        self._lo, self._chi = lo, hi
        self._value = value
        self._label = label
        self._command = command
        self._step = step
        self._recommended = recommended
        self._track_x1 = 74
        self._track_x2 = width - 52
        self._draw()
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_press)
        self.bind("<ButtonRelease-1>", lambda e: self._changed())

    def _frac(self) -> float:
        span = max(1, self._chi - self._lo)
        return max(0.0, min(1.0, (self._value - self._lo) / span))

    def _draw(self) -> None:
        self.delete("all")
        cy = self._ch / 2
        self.create_text(4, cy, text=self._label, anchor="w", fill=TEXT_DIM,
                         font=(FONT, 9))
        x1, x2 = self._track_x1, self._track_x2
        self.create_line(x1, cy, x2, cy, fill=CARD_SOFT, width=6, capstyle="round")
        if self._recommended is not None:
            span = max(1, self._chi - self._lo)
            rx = x1 + (x2 - x1) * (self._recommended - self._lo) / span
            self.create_line(rx, cy - 9, rx, cy + 9, fill="#c8cfdb", width=1)
        kx = x1 + (x2 - x1) * self._frac()
        self.create_line(x1, cy, kx, cy, fill=ACCENT, width=6, capstyle="round")
        self.create_oval(kx - 7, cy - 7, kx + 7, cy + 7, fill="#ffffff",
                         outline=ACCENT, width=2)
        self.create_text(self._cw - 6, cy, text=str(self._value), anchor="e",
                         fill=TEXT, font=(FONT, 9, "bold"))

    def _on_press(self, ev) -> None:
        x1, x2 = self._track_x1, self._track_x2
        t = (ev.x - x1) / max(1, x2 - x1)
        t = max(0.0, min(1.0, t))
        val = int(round(self._lo + t * (self._chi - self._lo)))
        if self._step > 1:
            val = int(round(val / self._step) * self._step)
        if val != self._value:
            self._value = val
            self._draw()
            if self._command:
                self._command(val)
        else:
            self._draw()

    def _changed(self) -> None:
        if self._command:
            self._command(self._value)

    def set(self, value: int) -> None:
        self._value = max(self._lo, min(self._chi, int(value)))
        self._draw()


class Toast(tk.Toplevel):
    """轻量提示条：按快捷键后闪一下，1.4 秒自动消失。"""

    def __init__(self, master, text: str, ms: int = 1400):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=MAGIC)
        pad_x, pad_y = 22, 11
        font = (FONT, 10, "bold")
        probe = tk.Canvas(self, width=1, height=1, bg=MAGIC, highlightthickness=0)
        probe.pack()
        tid = probe.create_text(0, 0, text=text, font=font, anchor="nw")
        box = probe.bbox(tid)
        w = max(180, (box[2] - box[0]) + pad_x * 2)
        h = (box[3] - box[1]) + pad_y * 2
        probe.destroy()

        c = tk.Canvas(self, width=w, height=h, bg=MAGIC, highlightthickness=0, bd=0)
        c.pack()
        round_poly(c, 1, 1, w - 1, h - 1, 12, fill=CARD, outline=BORDER, width=1)
        c.create_text(w / 2, h / 2, text=text, fill=TEXT, font=font)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{int(sh * 0.78)}")
        self.update_idletasks()
        try:
            self.attributes("-transparentcolor", MAGIC)
        except tk.TclError:
            pass
        self.after(ms, self._close)

    def _close(self) -> None:
        try:
            self.destroy()
        except tk.TclError:
            pass


def label(master, text: str, size: int = 9, color: str = TEXT,
          bold: bool = False, bg: str = CARD, **kw):
    return tk.Label(master, text=text, bg=bg,
                    fg=color, font=(FONT, size, "bold" if bold else "normal"), **kw)

class Card(tk.Canvas):
    """白色圆角卡片（带一层很淡的投影），内容放在 self.inner 里。"""

    def __init__(self, master, width: int, height: int, bg: str = BG,
                 radius: int = 14, pad: int = 14):
        super().__init__(master, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._cw, self._ch = width, height
        round_poly(self, 2, 5, width - 2, height - 1, radius, fill=SHADOW, outline="")
        round_poly(self, 1, 1, width - 3, height - 5, radius, fill=CARD,
                   outline=BORDER, width=1)
        self.inner = tk.Frame(self, bg=CARD)
        self.create_window(pad, pad, window=self.inner, anchor="nw",
                           width=width - pad * 2 - 2, height=height - pad * 2 - 4)
