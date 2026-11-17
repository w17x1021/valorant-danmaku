"""环境自检窗口：一条条列出检测结果，没过的给出修复办法。"""
from __future__ import annotations

import tkinter as tk

from ..selfcheck import run_all, summary
from .theme import BG, BORDER, CARD, FONT, GREEN, TEXT, TEXT_DIM, TEXT_FAINT, YELLOW
from .widgets import Pill, RoundButton, RoundedWindow, label

WIDTH, HEIGHT = 700, 640


class SelfCheckWindow(RoundedWindow):
    def __init__(self, master, app):
        self.app = app
        self.cfg = app.cfg
        super().__init__(master, "环境检测", WIDTH, HEIGHT, on_close=self.destroy,
                         bg_fill=BG)
        body = self.body
        frame = tk.Frame(body, bg=BG)
        frame.pack(fill="both", expand=True, padx=18, pady=12)

        head = tk.Frame(frame, bg=BG)
        head.pack(fill="x")
        label(head, "环境检测", size=13, color=TEXT, bold=True, bg=BG).pack(side="left")
        self.summary_lbl = label(head, "", size=9, color=TEXT_DIM, bg=BG)
        self.summary_lbl.pack(side="right")

        self.list_box = tk.Frame(frame, bg=BG)
        self.list_box.pack(fill="both", expand=True, pady=(10, 8))

        foot = tk.Frame(frame, bg=BG)
        foot.pack(side="bottom", fill="x", pady=(6, 0))
        RoundButton(foot, "重新检测", command=self.refresh, width=96, height=32,
                    kind="ghost", bg=BG).pack(side="left")
        RoundButton(foot, "关闭", command=self.destroy, width=88, height=32,
                    kind="primary", bg=BG).pack(side="right")

        self.refresh()

    def refresh(self) -> None:
        for w in self.list_box.winfo_children():
            w.destroy()
        checks = run_all(self.cfg, self.app)
        ok, total = summary(checks)
        self.summary_lbl.configure(
            text=f"{ok}/{total} 项通过" + ("　全部就绪，可以开玩" if ok == total else ""))

        for c in checks:
            card = tk.Frame(self.list_box, bg=CARD, highlightbackground=BORDER,
                            highlightthickness=1)
            card.pack(fill="x", pady=2)
            inner = tk.Frame(card, bg=CARD)
            inner.pack(fill="x", padx=12, pady=7)

            left = tk.Frame(inner, bg=CARD)
            left.pack(side="left", fill="x", expand=True)
            label(left, c.name, size=10, color=TEXT, bold=True, bg=CARD).pack(anchor="w")
            label(left, c.detail, size=8,
                  color=TEXT_FAINT if c.ok else TEXT_DIM, bg=CARD).pack(anchor="w", pady=(2, 0))
            if c.fix and not c.ok:
                label(left, "→ " + c.fix, size=8, color="#c8873a", bg=CARD).pack(
                    anchor="w", pady=(2, 0))

            Pill(inner, "通过" if c.ok else "待处理", GREEN if c.ok else YELLOW,
                 bg=CARD, width=68, height=24).pack(side="right")
