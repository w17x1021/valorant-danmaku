"""「我说的话」窗口（深色圆角卡片）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .theme import ACCENT, BLUE, BORDER, CARD, CARD_SOFT, GREEN, PINK, TEXT, TEXT_DIM, TEXT_FAINT
from .widgets import RoundedWindow, RoundButton, label

PLACEHOLDER = "对着麦克风说一句中文试试…"
AUTO_OPTIONS = {"关闭": "off", "自动复制日语": "ja", "自动复制英语": "en"}
AUTO_REVERSE = {v: k for k, v in AUTO_OPTIONS.items()}

WIDTH, HEIGHT = 478, 408


class SelfTalkPanel(RoundedWindow):
    def __init__(self, root: tk.Tk, app):
        self.app = app
        super().__init__(root, "我说的话 · 中 → 日 / 英", WIDTH, HEIGHT,
                         on_close=app.close_selftalk)
        self._build()
        self._position()

    def _position(self) -> None:
        """默认贴在主面板左边，避免两个窗口叠在一起。"""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = sw - WIDTH - 60, sh - HEIGHT - 120
        panel = getattr(self.app, "panel", None)
        try:
            if panel is not None and panel.winfo_exists():
                px, py = panel.winfo_x(), panel.winfo_y()
                if px > WIDTH + 40:
                    x, y = px - WIDTH - 12, py + 40
        except Exception:  # noqa: BLE001
            pass
        self.place_at(x, y)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        b = self.body
        pad = {"padx": 18}

        self.status_var = tk.StringVar(value="麦克风启动中…")
        self.status_lbl = label(b, "麦克风启动中…", size=9, color=TEXT_DIM)
        self.status_lbl.pack(anchor="w", pady=(10, 6), **pad)

        self.zh_lbl = self._block(b, "中文识别", TEXT_DIM)
        self.zh_lbl.pack_configure(pady=(0, 6))
        self.ja_value, row_ja, self.ja_lbl = self._block_with_button(b, "日语", PINK)
        self.en_value, row_en, self.en_lbl = self._block_with_button(b, "英语", BLUE)

        # ---- 自动复制 ----
        bottom = tk.Frame(b, bg=CARD)
        bottom.pack(side="bottom", fill="x", pady=(4, 12), **pad)
        label(bottom, "识别完自动复制", size=9, color=TEXT_DIM).pack(side="left")
        self.auto_var = tk.StringVar(value=AUTO_REVERSE.get(self.app.cfg.selftalk_auto_copy, "关闭"))
        combo = ttk.Combobox(bottom, textvariable=self.auto_var, state="readonly",
                             width=13, values=list(AUTO_OPTIONS))
        combo.pack(side="left", padx=(8, 0))
        combo.bind("<<ComboboxSelected>>", self._on_auto)

        hint = tk.Frame(b, bg=CARD)
        hint.pack(side="bottom", fill="x", padx=18, pady=(0, 8))
        label(hint, "F6 面板  ·  F7 弹幕  ·  F8 开/关本窗口  ·  F9 复制日语  ·  F10 复制英语",
              size=8, color=TEXT_FAINT).pack(anchor="w")

        self.zh_lbl.configure(text=PLACEHOLDER)

    # ------------------------------------------------------------------
    def _block(self, parent, title: str, color: str) -> tk.Label:
        wrap = tk.Frame(parent, bg=CARD)
        wrap.pack(fill="x", padx=18, pady=(0, 6))
        head = tk.Frame(wrap, bg=CARD)
        head.pack(fill="x")
        tk.Frame(head, bg=color, width=3, height=14).pack(side="left", pady=2)
        label(head, title, size=9, color=TEXT_DIM).pack(side="left", padx=(8, 0))
        lbl = tk.Label(wrap, text="—", bg=CARD, fg=TEXT, justify="left", anchor="w",
                       wraplength=420, font=("Microsoft YaHei UI", 11))
        lbl.pack(anchor="w", fill="x", pady=(4, 0))
        return lbl

    def _block_with_button(self, parent, title: str, color: str):
        wrap = tk.Frame(parent, bg=CARD)
        wrap.pack(fill="x", padx=18, pady=(0, 10))
        head = tk.Frame(wrap, bg=CARD)
        head.pack(fill="x")
        tk.Frame(head, bg=color, width=3, height=14).pack(side="left", pady=2)
        label(head, title, size=9, color=TEXT_DIM).pack(side="left", padx=(8, 0))
        action = "ja" if title == "日语" else "en"
        hotkey = (getattr(self.app, "hotkey_labels", {}) or {}).get(action, "")
        btn = RoundButton(head, f"复制 {hotkey}".strip(),
                          command=lambda: self.app.copy_selftext(action),
                          width=104 if hotkey else 64, height=26, kind="ghost",
                          font_size=8)
        btn.pack(side="right")
        lbl = tk.Label(wrap, text="—", bg=CARD, fg=TEXT, justify="left", anchor="w",
                       wraplength=420, font=("Microsoft YaHei UI", 11))
        lbl.pack(anchor="w", fill="x", pady=(4, 0))
        return lbl, wrap, lbl

    # ------------------------------------------------------------------
    def _on_auto(self, _evt=None) -> None:
        self.app.cfg.selftalk_auto_copy = AUTO_OPTIONS.get(self.auto_var.get(), "off")
        self.app.cfg.save()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.status_lbl.configure(text=text)

    def update_result(self, res: dict) -> None:
        self.zh_lbl.configure(text=(res.get("zh") or PLACEHOLDER)[:80])
        self.ja_lbl.configure(text=(res.get("ja") or "—")[:80])
        self.en_lbl.configure(text=(res.get("en") or "—")[:80])

    def clear(self) -> None:
        self.zh_lbl.configure(text=PLACEHOLDER)
        self.ja_lbl.configure(text="—")
        self.en_lbl.configure(text="—")
