"""下载队列窗口：实时看每个任务的进度条、速度和剩余时间。

只读 `app.downloads` 的快照，250ms 刷一次；所有 tkinter 操作都在主线程。
"""
from __future__ import annotations

import tkinter as tk

from ..downloads import (CANCELLED, DONE, FAILED, RUNNING, WAITING, fmt_eta,
                         fmt_size, fmt_speed, manager)
from .theme import (ACCENT, ACCENT_SOFT, ACCENT_TEXT, BG, BORDER, CARD, CARD_SOFT,
                    DANGER, FONT, GREEN, TEXT, TEXT_DIM, TEXT_FAINT, YELLOW,
                    round_poly)
from .widgets import RoundButton, RoundedWindow, label

WIDTH, HEIGHT = 600, 520
TICK_MS = 250

STATUS_COLOR = {
    WAITING: TEXT_DIM,
    RUNNING: ACCENT_TEXT,
    DONE: GREEN,
    FAILED: DANGER,
    CANCELLED: TEXT_FAINT,
}


class ProgressBar(tk.Canvas):
    """细圆角进度条；progress 未知时画一段来回跑的光条。"""

    def __init__(self, master, height: int = 8, bg: str = CARD):
        super().__init__(master, height=height, bg=bg, highlightthickness=0, bd=0)
        self._frac: float | None = None
        self._color = ACCENT
        self._phase = 0.0
        self._animate = False
        self.bind("<Configure>", lambda _e: self._draw())

    def set(self, frac: float | None, color: str | None = None,
            animate: bool = False) -> None:
        self._frac = frac
        if color:
            self._color = color
        self._animate = animate
        if animate:
            self._phase = (self._phase + 0.06) % 1.0
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        w = max(1, self.winfo_width())
        h = max(1, self.winfo_height())
        round_poly(self, 0, 0, w, h, h / 2, fill=CARD_SOFT, outline="")
        if self._frac is None:
            if not self._animate:
                return
            seg = max(28.0, w * 0.22)
            x = (w + seg) * self._phase - seg
            x1, x2 = max(0.0, x), min(float(w), x + seg)
            if x2 > x1:
                round_poly(self, x1, 0, x2, h, h / 2, fill=self._color, outline="")
            return
        width = max(0.0, min(1.0, self._frac)) * w
        if width > 1:
            round_poly(self, 0, 0, max(width, h), h, h / 2, fill=self._color,
                       outline="")


class TaskRow(tk.Frame):
    """一行：标题 + 右侧百分比/速度 + 进度条 + 状态。"""

    def __init__(self, master, task_id: int, on_cancel):
        super().__init__(master, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1)
        self.task_id = task_id
        self._on_cancel = on_cancel

        inner = tk.Frame(self, bg=CARD)
        inner.pack(fill="x", padx=12, pady=8)

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill="x")
        self.title = label(top, "", size=10, color=TEXT, bold=True, bg=CARD)
        self.title.pack(side="left")
        self.right = label(top, "", size=9, color=TEXT_DIM, bg=CARD)
        self.right.pack(side="right")
        self.cancel_btn = RoundButton(top, "取消", command=self._cancel, width=48,
                                      height=22, kind="ghost", bg=CARD, font_size=8)
        self.cancel_btn.pack(side="right", padx=(0, 8))
        self._btn_shown = True

        self.detail = label(inner, "", size=8, color=TEXT_FAINT, bg=CARD)
        self.detail.pack(anchor="w", pady=(2, 6))

        self.bar = ProgressBar(inner, height=8, bg=CARD)
        self.bar.pack(fill="x")

        self.foot = label(inner, "", size=8, color=TEXT_DIM, bg=CARD)
        self.foot.pack(anchor="w", pady=(5, 0))

    def _cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel(self.task_id)

    def update_row(self, snap: dict) -> None:
        status = snap["status"]
        color = STATUS_COLOR.get(status, TEXT_DIM)
        self.title.configure(text=snap["title"])
        self.right.configure(text=snap["status_text"], fg=color)

        detail = snap["detail"]
        note = snap.get("note") or ""
        if status == RUNNING and note:
            detail = f"{note}   ·   {detail}" if detail else note
        self.detail.configure(text=detail or " ", fg=TEXT_FAINT)

        if snap["error"]:
            self.foot.configure(text=snap["error"][:110], fg=DANGER)
        else:
            self.foot.configure(text=self._progress_text(snap), fg=TEXT_DIM)

        frac = snap["fraction"]
        spinning = status == RUNNING and frac is None
        self.bar.set(frac, color=color if status != FAILED else DANGER,
                     animate=spinning)
        # 只有排队中 / 下载中才能取消
        show = status in (WAITING, RUNNING)
        if show != self._btn_shown:
            if show:
                self.cancel_btn.set_text("取消")
                self.cancel_btn.pack(side="right", padx=(0, 8))
            else:
                self.cancel_btn.pack_forget()
            self._btn_shown = show

    @staticmethod
    def _progress_text(snap: dict) -> str:
        total, done = snap["total"], snap["done"]
        if snap["status"] == DONE:
            return f"完成 · {fmt_size(done or total)}"
        if total:
            text = f"{fmt_size(done)} / {fmt_size(total)}"
            if snap["fraction"] is not None:
                text += f"  ({snap['fraction'] * 100:.0f}%)"
        else:
            text = f"{fmt_size(done)}"
        if snap["status"] == RUNNING:
            text += f"   ·   {fmt_speed(snap['speed'])}"
            eta = snap["eta"]
            if eta:
                text += f"   ·   剩余 {fmt_eta(eta)}"
        return text


class DownloadsWindow(RoundedWindow):
    """下载任务队列。重复打开时由 App.open_downloads() 复用同一个窗口。"""

    def __init__(self, master, app=None):
        self.app = app
        super().__init__(master, "下载队列", WIDTH, HEIGHT,
                         on_close=self._close, bg_fill=BG)
        self._rows: dict[int, TaskRow] = {}
        self._alive = True

        body = self.body
        body_frame = tk.Frame(body, bg=BG)
        body_frame.pack(fill="both", expand=True, padx=16, pady=10)

        head = tk.Frame(body_frame, bg=BG)
        head.pack(fill="x")
        label(head, "下载任务", size=11, color=TEXT, bold=True, bg=BG).pack(side="left")
        self.summary = label(head, "", size=9, color=ACCENT_TEXT, bold=True, bg=BG)
        self.summary.pack(side="right")

        self.hint = label(body_frame, "所有下载都排在这里，一次只跑一个，进度和速度实时更新",
                          size=8, color=TEXT_FAINT, bg=BG)
        self.hint.pack(anchor="w", pady=(2, 8))

        # 可滚动的任务列表
        wrap = tk.Frame(body_frame, bg=BG)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        self.vbar = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.list_frame,
                                              anchor="nw")
        self.list_frame.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        # 绑在窗口上：子控件里的滚轮事件也会冒泡到这里（bindtags 含 toplevel）
        self.bind("<MouseWheel>", self._on_wheel)

        self.empty = label(self.list_frame, "还没有下载任务", size=9, color=TEXT_FAINT,
                           bg=BG)

        foot = tk.Frame(body_frame, bg=BG)
        foot.pack(fill="x", pady=(8, 0))
        RoundButton(foot, "全部取消", command=self._cancel_all, width=92, height=32,
                    kind="ghost", bg=BG).pack(side="left")
        RoundButton(foot, "清理已完成", command=self._clear, width=100, height=32,
                    kind="ghost", bg=BG).pack(side="left", padx=(8, 0))
        RoundButton(foot, "关闭", command=self._close, width=80, height=32,
                    kind="primary", bg=BG).pack(side="right")

        self._tick()

    # ------------------------------------------------------------------
    def _on_inner(self, _ev=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, ev) -> None:
        self.canvas.itemconfigure(self._win, width=ev.width)

    def _on_wheel(self, ev) -> None:
        try:
            if not self.winfo_exists():
                return
            self.canvas.yview_scroll(int(-ev.delta / 120), "units")
        except tk.TclError:
            pass

    def _cancel_all(self) -> None:
        manager().cancel_all()

    def _clear(self) -> None:
        manager().clear_finished()

    def _close(self) -> None:
        self._alive = False
        self.destroy()

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if not self._alive:
            return
        try:
            self._refresh()
            self.after(TICK_MS, self._tick)
        except tk.TclError:
            self._alive = False

    def _refresh(self) -> None:
        snap = manager().snapshot()
        tasks = snap["tasks"]

        if snap["running"]:
            text = f"{snap['running']} 个下载中 · {fmt_speed(snap['speed'])}"
            if snap["queued"]:
                text += f" · {snap['queued']} 个排队"
        elif snap["queued"]:
            text = f"{snap['queued']} 个排队中"
        else:
            text = "空闲"
        self.summary.configure(text=text)

        if not tasks:
            self.empty.pack(pady=(18, 0))
        else:
            self.empty.pack_forget()

        live_ids = set()
        added = False
        for row_snap in tasks:
            tid = row_snap["id"]
            live_ids.add(tid)
            row = self._rows.get(tid)
            if row is None:
                row = TaskRow(self.list_frame, tid, self._cancel_one)
                row.pack(fill="x", pady=2)
                self._rows[tid] = row
                added = True
            row.update_row(row_snap)

        for tid in list(self._rows):
            if tid not in live_ids:
                self._rows.pop(tid).destroy()

        # 只在有新任务时滑到底部，别抢用户正在看的位置
        if added:
            self.canvas.update_idletasks()
            self.canvas.yview_moveto(1.0)
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        """内容不超过一屏就把滚动条藏起来，省得右边挂一条灰条。"""
        try:
            self.canvas.update_idletasks()
            need = self.list_frame.winfo_reqheight() > self.canvas.winfo_height() + 2
            shown = bool(self.vbar.winfo_ismapped())
            if need and not shown:
                self.vbar.pack(side="right", fill="y")
            elif not need and shown:
                self.vbar.pack_forget()
        except tk.TclError:
            pass

    def _cancel_one(self, task_id: int) -> None:
        manager().cancel(task_id)
