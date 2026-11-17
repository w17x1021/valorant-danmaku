"""配色与绘图小工具（浅色卡片风，参考瓦语通）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ---- 配色 ----
MAGIC = "#010203"          # 透明色键
BG = "#f4f6f9"             # 窗口底
RAIL = "#fbfbfd"           # 左侧导航栏
CARD = "#ffffff"           # 卡片
CARD_SOFT = "#f2f4f8"      # 次级块 / 未选中
BORDER = "#e5e8ef"
SHADOW = "#e9ecf2"
TEXT = "#1f2329"
TEXT_DIM = "#6b7280"
TEXT_FAINT = "#9aa1ad"
ACCENT = "#7cc7ec"         # 主按钮（淡蓝）
ACCENT_DARK = "#5fb0da"
ACCENT_SOFT = "#e4f4fc"    # 选中态底色
ACCENT_TEXT = "#2f8cbb"    # 蓝色文字
GREEN = "#34c38f"
YELLOW = "#e9a23b"
BLUE = "#3b82f6"
PINK = "#e879a8"
DANGER = "#e5484d"
DANGER_SOFT = "#fdeced"

FONT = "Microsoft YaHei UI"


def rgb(hex_color: str) -> tuple[int, int, int]:
    v = hex_color.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    ra, ga, ba = rgb(a)
    rb, gb, bb = rgb(b)
    return "#%02x%02x%02x" % (
        int(ra + (rb - ra) * t), int(ga + (gb - ga) * t), int(ba + (bb - ba) * t))


def lighten(color: str, t: float) -> str:
    return mix(color, "#ffffff", t)


def darken(color: str, t: float) -> str:
    return mix(color, "#000000", t)


def round_poly(canvas: tk.Canvas, x1: float, y1: float, x2: float, y2: float,
               r: float, **kw):
    """画一个圆角矩形（用平滑多边形近似），返回 item id。"""
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, splinesteps=16, **kw)


def apply_ttk_style(root: tk.Misc) -> None:
    """把 ttk 组件（下拉框、输入框）刷成浅色。"""
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure(".", background=CARD, foreground=TEXT, fieldbackground=CARD,
                 bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                 troughcolor=CARD_SOFT, focuscolor=ACCENT, font=(FONT, 9))

    st.configure("TCombobox", fieldbackground=CARD, background=CARD,
                 foreground=TEXT, arrowcolor=TEXT_DIM, borderwidth=1,
                 relief="flat", padding=4)
    st.map("TCombobox",
           fieldbackground=[("readonly", CARD), ("active", CARD)],
           foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", CARD)],
           selectforeground=[("readonly", TEXT)],
           background=[("active", CARD)],
           bordercolor=[("focus", ACCENT), ("hover", ACCENT_DARK)])
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT_SOFT)
    root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)
    root.option_add("*TCombobox*Listbox.font", (FONT, 9))

    st.configure("TEntry", fieldbackground=CARD, foreground=TEXT,
                 insertcolor=TEXT, bordercolor=BORDER, lightcolor=BORDER,
                 darkcolor=BORDER, padding=4)
    st.configure("Vertical.TScrollbar", background=CARD_SOFT, troughcolor=BG,
                 bordercolor=BG)
    st.configure("TCheckbutton", background=CARD, foreground=TEXT,
                 indicatorcolor=CARD, indicatorbackground=CARD)
    st.map("TCheckbutton", background=[("active", CARD)],
           indicatorcolor=[("selected", ACCENT)])


def dark_titlebar(window) -> None:
    """让系统标题栏也变成深色（Windows 10 2004+）。"""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
    except Exception:  # noqa: BLE001
        pass


def enable_dark_mode() -> None:
    """让系统给原生窗口标题栏用深色（进程级，需要在建窗口之前调用）。"""
    try:
        import ctypes
        ux = ctypes.WinDLL("uxtheme")
        fn = ux[135]            # SetPreferredAppMode（未公开导出，按序号调用）
        fn.restype = ctypes.c_int
        fn(2)                   # 2 = ForceDark
    except Exception:  # noqa: BLE001
        pass
