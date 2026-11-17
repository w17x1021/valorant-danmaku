"""主面板（浅色卡片风，参考瓦语通：左侧导航 + 白卡片 + 淡蓝按钮）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..config import Config
from .theme import (ACCENT, ACCENT_TEXT, BG, BORDER, CARD, CARD_SOFT, FONT, GREEN,
                    RAIL, TEXT, TEXT_DIM, TEXT_FAINT, YELLOW)
from .widgets import Card, NavItem, Pill, RoundButton, RoundedWindow, Slider, label

PROVIDER_LABELS = {
    "bing": "必应翻译（推荐）",
    "mymemory": "MyMemory（备用）",
    "google": "Google（需外网）",
}
LABEL_TO_NAME = {v: k for k, v in PROVIDER_LABELS.items()}

WIDTH, HEIGHT = 900, 604

REC_FONT = 22
REC_WIDTH = 760
REC_LINES = 3
REC_SPEED = 250

RAIL_W = 176


class ControlPanel(RoundedWindow):
    def __init__(self, root: tk.Tk, app):
        self.app = app
        self.cfg: Config = app.cfg
        super().__init__(root, "瓦罗兰特 · 实时翻译助手", WIDTH, HEIGHT,
                         on_close=app.quit, bg_fill=BG)
        self._build()
        self._restore_geometry()

    # ------------------------------------------------------------------
    def _restore_geometry(self) -> None:
        geo = (self.cfg.panel_geometry or "").strip()
        if "+" in geo:
            try:
                size, x, y = geo.split("+")
                self.place_at(int(x), int(y))
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    def _build(self) -> None:
        body = self.body

        # ---------------- 左侧导航 ----------------
        rail = tk.Frame(body, bg=RAIL, width=RAIL_W)
        rail.pack(side="left", fill="y", padx=(0, 0), pady=0)
        rail.pack_propagate(False)

        tk.Frame(rail, bg=BORDER, height=1).pack(fill="x")
        self.nav_ocr = NavItem(rail, "chat", "翻译", command=self.app.pick_region,
                               selected=True, bg=RAIL)
        self.nav_ocr.pack(pady=(14, 4), padx=9)
        NavItem(rail, "mic", "我说的话", command=self.app.open_selftalk, bg=RAIL).pack(
            pady=2, padx=9)
        NavItem(rail, "box", "模型", command=self.app.open_models, bg=RAIL).pack(
            pady=2, padx=9)
        NavItem(rail, "gear", "设置", command=self.app.open_settings, bg=RAIL).pack(
            pady=2, padx=9)

        bottom = tk.Frame(rail, bg=RAIL)
        bottom.pack(side="bottom", fill="x", pady=(0, 12), padx=9)
        NavItem(bottom, "power", "退出", command=self.app.quit, bg=RAIL).pack(fill="x")
        self.version_lbl = label(bottom, "v1.0 · 本地运行", size=8, color=TEXT_FAINT, bg=RAIL)
        self.version_lbl.pack(anchor="w", padx=10, pady=(6, 0))

        # ---------------- 右侧内容 ----------------
        content = tk.Frame(body, bg=BG)
        content.pack(side="left", fill="both", expand=True, padx=(16, 16), pady=12)

        head = tk.Frame(content, bg=BG)
        head.pack(fill="x", pady=(0, 10))
        self.ocr_pill = Pill(head, "OCR 初始化…", YELLOW, bg=BG, width=180)
        self.ocr_pill.pack(side="left")
        self.voice_pill = Pill(head, "语音 启动中…", YELLOW, bg=BG, width=150)
        self.voice_pill.pack(side="left", padx=(8, 0))
        self.voice_btn = RoundButton(head, "语音关", command=self.app.toggle_voice,
                                     width=84, height=28, kind="outline", bg=BG,
                                     font_size=8)
        self.voice_btn.pack(side="right")
        self.pause_btn = RoundButton(head, "暂停识别", command=self.app.toggle_pause,
                                     width=92, height=28, kind="outline", bg=BG,
                                     font_size=8)
        self.pause_btn.pack(side="right", padx=(0, 8))

        cards = tk.Frame(content, bg=BG)
        cards.pack(fill="both", expand=False)

        # ---- 卡片 1：翻译 ----
        card1 = Card(cards, 336, 306, bg=BG)
        card1.pack(side="left")
        inner = card1.inner
        label(inner, "翻译", size=11, color=TEXT, bold=True, bg=CARD).pack(anchor="w")
        tag_row = tk.Frame(inner, bg=CARD)
        tag_row.pack(anchor="w", pady=(6, 10))
        Pill(tag_row, "英语 / 日语 → 中文", TEXT_DIM, bg=CARD, width=142, height=22).pack(
            side="left")
        Pill(tag_row, "语音 + 文字", TEXT_DIM, bg=CARD, width=98, height=22).pack(
            side="left", padx=(6, 0))

        self.state_var = tk.StringVar(value="● 准备就绪")
        self.state_lbl = tk.Label(inner, textvariable=self.state_var, bg=CARD,
                                  fg="#34c38f", font=(FONT, 20, "bold"), anchor="w")
        self.state_lbl.pack(anchor="w", pady=(4, 0))
        self.state_sub = label(inner, "等待队友说话…", size=9, color=TEXT_FAINT, bg=CARD)
        self.state_sub.pack(anchor="w", pady=(0, 12))

        self.region_var = tk.StringVar(value="聊天区域  未设置")
        tk.Label(inner, textvariable=self.region_var, bg=CARD, fg=TEXT_DIM,
                 font=(FONT, 9), anchor="w", justify="left",
                 wraplength=300).pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(inner, bg=CARD)
        btns.pack(fill="x", pady=(0, 6))
        RoundButton(btns, "重新框选", command=self.app.pick_region, width=100, height=30,
                    kind="ghost", bg=CARD, font_size=8).pack(side="left")
        RoundButton(btns, "截图选", command=self.app.pick_region_capture, width=86,
                    height=30, kind="ghost", bg=CARD, font_size=8).pack(side="left", padx=(8, 0))
        RoundButton(btns, "测试", command=self.app.test_danmaku, width=70, height=30,
                    kind="ghost", bg=CARD, font_size=8).pack(side="right")

        self.talk_btn = RoundButton(inner, "我说的话  ·  中 → 日 / 英",
                                    command=self.app.open_selftalk, width=308, height=40,
                                    kind="primary", font_size=10)
        self.talk_btn.pack(side="bottom", pady=(8, 0))

        # ---- 卡片 2：弹幕外观 ----
        card2 = Card(cards, 336, 306, bg=BG)
        card2.pack(side="left", padx=(14, 0))
        inner2 = card2.inner
        label(inner2, "弹幕外观", size=11, color=TEXT, bold=True, bg=CARD).pack(anchor="w")
        label(inner2, "灰色竖线 = 推荐值", size=8, color=TEXT_FAINT, bg=CARD).pack(
            anchor="w", pady=(2, 6))

        self.size_slider = Slider(inner2, "字号", 14, 44, int(self.cfg.danmaku_font_size),
                                  command=self._on_size, width=306, bg=CARD,
                                  recommended=REC_FONT)
        self.size_slider.pack(anchor="w")
        self.width_slider = Slider(inner2, "框宽", 360, 1200,
                                   int(getattr(self.cfg, "box_width_px", 0) or REC_WIDTH),
                                   command=self._on_width, width=306, bg=CARD,
                                   recommended=REC_WIDTH)
        self.width_slider.pack(anchor="w")
        self.lines_slider = Slider(inner2, "行数", 1, 6, int(self.cfg.box_max_lines),
                                   command=self._on_lines, width=306, bg=CARD,
                                   recommended=REC_LINES)
        self.lines_slider.pack(anchor="w")
        self.speed_slider = Slider(inner2, "速度", 80, 600, int(self.cfg.danmaku_speed),
                                   command=self._on_speed, width=306, bg=CARD,
                                   recommended=REC_SPEED)
        self.speed_slider.pack(anchor="w")

        row = tk.Frame(inner2, bg=CARD)
        row.pack(fill="x", pady=(8, 0))
        self.danmaku_btn = RoundButton(row, "隐藏弹幕", command=self.app.toggle_danmaku,
                                       width=96, height=30, kind="ghost", bg=CARD,
                                       font_size=8)
        self.danmaku_btn.pack(side="left")
        RoundButton(row, "恢复推荐", command=self._reset_recommended, width=96, height=30,
                    kind="outline", bg=CARD, font_size=8).pack(side="right")

        # ---- 底部：最近 ----
        foot = tk.Frame(content, bg=BG)
        foot.pack(fill="x", pady=(12, 0))
        self.last_var = tk.StringVar(value="最近：—")
        self.last_lbl = tk.Label(foot, textvariable=self.last_var, bg=BG, fg=TEXT_DIM,
                                 font=(FONT, 9), anchor="w", justify="left",
                                 wraplength=680)
        self.last_lbl.pack(anchor="w")

        self.hint_lbl = label(foot, self._hint_text(), size=8, color=TEXT_FAINT, bg=BG)
        self.hint_lbl.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------
    def _hint_text(self) -> str:
        k = getattr(self.app, "hotkey_labels", {}) or {}
        return (f"{k.get('panel', 'F6')} 面板   ·   {k.get('danmaku', 'F7')} 弹幕   ·   "
                f"{k.get('talk', 'F8')} 我说的话   ·   {k.get('ja', 'F9')} 复制日语   ·   "
                f"{k.get('en', 'F10')} 复制英语")

    def set_hotkey_hint(self, text: str = "") -> None:
        try:
            self.hint_lbl.configure(text=text or self._hint_text())
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    def _on_size(self, value) -> None:
        try:
            self.cfg.danmaku_font_size = int(value)
            self.app.overlay.set_font_size(int(value))
        except (TypeError, ValueError, AttributeError):
            pass

    def _on_width(self, value) -> None:
        try:
            self.cfg.box_width_px = int(value)
            self.app.overlay.set_box_width(int(value))
        except (TypeError, ValueError, AttributeError):
            pass

    def _on_lines(self, value) -> None:
        try:
            self.cfg.box_max_lines = int(value)
            self.app.overlay.set_max_lines(int(value))
        except (TypeError, ValueError, AttributeError):
            pass

    def _on_speed(self, value) -> None:
        try:
            self.cfg.danmaku_speed = float(value)
        except (TypeError, ValueError):
            pass

    def _reset_recommended(self) -> None:
        for slider, val in ((self.size_slider, REC_FONT), (self.width_slider, REC_WIDTH),
                            (self.lines_slider, REC_LINES), (self.speed_slider, REC_SPEED)):
            slider.set(val)
        self._on_size(REC_FONT)
        self._on_width(REC_WIDTH)
        self._on_lines(REC_LINES)
        self._on_speed(REC_SPEED)

    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        color = GREEN
        if "错误" in text or "不可用" in text or "失败" in text:
            color, short = "#e5484d", "OCR 出错"
        elif "已关闭" in text:
            color, short = YELLOW, "OCR 已关闭"
        elif "暂停" in text:
            color, short = YELLOW, "OCR 已暂停"
        elif "已翻译" in text:
            n = text.split("已翻译")[1].split("条")[0].strip()
            short = f"OCR 运行 · {n} 条"
        else:
            short = "OCR 初始化…"
        self.ocr_pill.set(short, color)

    def set_voice(self, text: str) -> None:
        if "未安装" in text:
            short, color = "语音 未安装", "#e5484d"
        elif "出错" in text or "不可用" in text or "失败" in text:
            short, color = "语音 出错", "#e5484d"
        elif "加载" in text:
            short, color = "语音 加载中…", YELLOW
        elif "已关闭" in text or "未启用" in text:
            short, color = "语音 已关闭", YELLOW
        elif "启动" in text:
            short, color = "语音 启动中…", YELLOW
        elif "GPU" in text:
            short, color = "语音 识别中·GPU", GREEN
        else:
            short, color = "语音 识别中", GREEN
        self.voice_pill.set(short, color)
        try:
            active = bool(getattr(self.app, "voice", None)
                          and self.app.voice.active.is_set())
            self.voice_btn.set_text("语音关" if active else "语音开")
        except Exception:  # noqa: BLE001
            pass

    def _mode_text(self) -> str:
        mode = getattr(self.cfg, "display_mode", "box")
        return "样式：下方字幕框" if mode == "box" else "样式：全屏滚动"

    def set_display_mode(self, mode: str) -> None:
        self.cfg.display_mode = mode

    def set_region(self, region) -> None:
        if region:
            self.region_var.set(f"聊天区域  {region[2]}×{region[3]}  @ ({region[0]}, {region[1]})")
        else:
            self.region_var.set("聊天区域未设置，点上方「重新框选」")

    def set_last(self, text: str) -> None:
        self.last_var.set(f"最近：{text}"[:160])

    def set_paused(self, paused: bool) -> None:
        self.pause_btn.set_text("继续识别" if paused else "暂停识别")

    def set_danmaku_visible(self, visible: bool) -> None:
        self.danmaku_btn.set_text("隐藏弹幕" if visible else "显示弹幕")

    def warn(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message, parent=self)

    def open_settings(self) -> None:
        from .settings import SettingsDialog
        SettingsDialog(self, self.app)
