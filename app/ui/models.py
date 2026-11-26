"""模型管理窗口：语音包（识别模型）与语言包（OCR）的选用、下载、导入。"""
from __future__ import annotations

import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import models as ml
from ..config import project_root
from .theme import ACCENT_SOFT, ACCENT_TEXT, BG, BORDER, CARD, CARD_SOFT, FONT, GREEN, \
    TEXT, TEXT_DIM, TEXT_FAINT, YELLOW
from .widgets import Card, Pill, RoundButton, RoundedWindow, label

WIDTH, HEIGHT = 780, 944


class ModelManager(RoundedWindow):
    def __init__(self, master, app):
        self.app = app
        self.cfg = app.cfg
        super().__init__(master, "模型管理", WIDTH, HEIGHT, on_close=self.destroy,
                         bg_fill=BG)
        body = self.body
        self.body_frame = tk.Frame(body, bg=BG)
        self.body_frame.pack(fill="both", expand=True, padx=18, pady=12)

        head = tk.Frame(self.body_frame, bg=BG)
        head.pack(fill="x")
        label(head, "语音包 / 语言包", size=13, color=TEXT, bold=True, bg=BG).pack(side="left")
        self.path_lbl = label(head, "", size=8, color=TEXT_FAINT, bg=BG)
        self.path_lbl.pack(side="right")

        self.notice = label(self.body_frame, "", size=8, color=YELLOW, bg=BG)
        self.notice.pack(anchor="w", pady=(4, 0), fill="x")

        self.status = label(self.body_frame, "", size=9, color=TEXT_DIM, bg=BG)
        self.status.pack(side="bottom", anchor="w")

        foot = tk.Frame(self.body_frame, bg=BG)
        foot.pack(side="bottom", fill="x", pady=(8, 6))

        self.list_box = tk.Frame(self.body_frame, bg=BG)
        self.list_box.pack(fill="both", expand=True, pady=(8, 4))
        RoundButton(foot, "打开模型文件夹", command=self._open_folder, width=124,
                    height=32, kind="ghost", bg=BG).pack(side="left")
        RoundButton(foot, "从文件夹导入语音包…", command=self._import_voice, width=158,
                    height=32, kind="ghost", bg=BG).pack(side="left", padx=(8, 0))
        RoundButton(foot, "导入语言包…", command=self._import_ocr, width=112, height=32,
                    kind="ghost", bg=BG).pack(side="left", padx=(8, 0))
        RoundButton(foot, "下载队列", command=self._open_queue, width=84, height=32,
                    kind="outline", bg=BG).pack(side="left", padx=(8, 0))
        RoundButton(foot, "关闭", command=self.destroy, width=88, height=32,
                    kind="primary", bg=BG).pack(side="right")
        RoundButton(foot, "环境检测", command=self._selfcheck, width=96, height=32,
                    kind="outline", bg=BG).pack(side="right", padx=(0, 8))

        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        for w in self.list_box.winfo_children():
            w.destroy()
        self.path_lbl.configure(text=f"模型目录：{ml.models_dir(self.cfg)}")
        self._update_notice()

        self._section("语音包（队友语音识别模型）")

        for pack in ml.VOICE_PACKS:
            path = ml.installed_path(self.cfg, pack.id)
            used = (bool(path) and ml.current_pack(self.cfg) == pack.id
                    and not (self.cfg.asr_model_path or "").strip())
            self._row(
                title=pack.label,
                desc=f"{pack.size} · 显存 {pack.vram} · {pack.note}",
                installed=bool(path),
                used=used,
                # 没下载的模型不给「使用」按钮，否则等于选中一个不存在的东西
                on_use=(lambda pid=pack.id: self._use_voice(pid)) if path else None,
                on_download=lambda pid=pack.id: self._download(pid),
                on_delete=lambda pid=pack.id: self._delete(pid),
            )

        custom = (self.cfg.asr_model_path or "").strip()
        if custom:
            self._row(title="已导入的自定义模型", desc=custom, installed=True, used=True,
                      on_use=None, on_download=None,
                      on_delete=lambda: self._clear_custom())

        self._section("显卡加速（可选，装了才用 GPU，约 1.6GB）")
        self._cuda_row()

        self._section("语言包（聊天文字 OCR）")
        langs = self.app.ocr.available if getattr(self.app, "ocr", None) else None
        status = ml.ocr_status(self.cfg, langs)
        for code, name, kind in ml.OCR_LANGS:
            ok, note = status.get(code, (False, "未知"))
            self._ocr_row(name, ok, note, code)

    # ------------------------------------------------------------------
    def _update_notice(self) -> None:
        """配置里选中的模型却没装时，明确告诉用户「还没下」，别让人以为已经有了。"""
        custom = (self.cfg.asr_model_path or "").strip()
        if custom:
            if ml.valid_model_dir(Path(custom)):
                self.notice.configure(text=f"正在用导入的模型：{custom}")
            else:
                self.notice.configure(
                    text=f"导入的模型目录已经失效（{custom}），请重新导入或下载一个")
            return
        pack_id = ml.current_pack(self.cfg)
        pack = ml.PACK_BY_ID.get(pack_id)
        if pack is not None and not ml.installed_path(self.cfg, pack_id):
            self.notice.configure(
                text=f"设置里选的是 {pack.label}，但本机还没下载 —— 点它右边的「下载」"
                     f"（约 {pack.size}，进度和速度在下载队列里看）")
        else:
            self.notice.configure(text="")

    def _section(self, text: str) -> None:
        row = tk.Frame(self.list_box, bg=BG)
        row.pack(fill="x", pady=(6, 2))
        label(row, text, size=10, color=TEXT, bold=True, bg=BG).pack(side="left")

    def _row(self, title: str, desc: str, installed: bool, used: bool,
             on_use, on_download, on_delete) -> None:
        card = tk.Frame(self.list_box, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="x", pady=1)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=5)

        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left", fill="x", expand=True)
        label(left, title, size=10, color=TEXT, bold=True, bg=CARD).pack(anchor="w")
        label(left, desc, size=8, color=TEXT_FAINT, bg=CARD).pack(anchor="w", pady=(2, 0))

        right = tk.Frame(inner, bg=CARD)
        right.pack(side="right")
        if on_download is not None:
            if installed:
                RoundButton(right, "删除", command=on_delete, width=62, height=28,
                            kind="ghost", bg=CARD, font_size=8).pack(side="right", padx=(6, 0))
            else:
                RoundButton(right, "下载", command=on_download, width=62, height=28,
                            kind="ghost", bg=CARD, font_size=8).pack(side="right", padx=(6, 0))
        if used:
            Pill(right, "使用中", GREEN, bg=CARD, width=64, height=24).pack(side="right")
        elif on_use is not None:
            RoundButton(right, "使用", command=on_use, width=62, height=28,
                        kind="primary", bg=CARD, font_size=8).pack(side="right", padx=(6, 0))
        else:
            Pill(right, "未下载", TEXT_DIM, bg=CARD, width=64, height=24).pack(side="right")

    # ------------------------------------------------------------------
    def _cuda_row(self) -> None:
        from .. import cuda_pack
        ok = cuda_pack.installed()
        card = tk.Frame(self.list_box, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="x", pady=1)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=5)
        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left", fill="x", expand=True)
        label(left, "CUDA 加速库（cuBLAS + cuDNN）", size=10, color=TEXT, bold=True,
              bg=CARD).pack(anchor="w")
        label(left, (f"已安装 {cuda_pack.installed_size_mb():.0f} MB" if ok
                     else "不装也能用，只是语音识别走 CPU（慢 5~10 倍）"),
              size=8, color=TEXT_FAINT, bg=CARD).pack(anchor="w", pady=(2, 0))
        right = tk.Frame(inner, bg=CARD)
        right.pack(side="right")
        if ok:
            Pill(right, "已就绪", GREEN, bg=CARD, width=68, height=24).pack(side="right")
        else:
            RoundButton(right, "下载安装", command=self._install_cuda, width=92, height=28,
                        kind="primary", bg=CARD, font_size=8).pack(side="right")

    def _install_cuda(self) -> None:
        from .. import cuda_pack
        self.status.configure(text="已把显卡加速包加入下载队列（约 1.6GB，可看进度）…")
        cuda_pack.install_async(None)
        self._open_queue()
        self._watch_queue()

    def _selfcheck(self) -> None:
        from .selfcheck_win import SelfCheckWindow
        SelfCheckWindow(self, self.app)

    def _ocr_row(self, name: str, ok: bool, note: str, code: str) -> None:
        card = tk.Frame(self.list_box, bg=CARD, highlightbackground=BORDER,
                        highlightthickness=1)
        card.pack(fill="x", pady=1)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=12, pady=5)

        left = tk.Frame(inner, bg=CARD)
        left.pack(side="left", fill="x", expand=True)
        label(left, name, size=10, color=TEXT, bold=True, bg=CARD).pack(anchor="w")
        label(left, note, size=8, color=TEXT_FAINT, bg=CARD).pack(anchor="w", pady=(2, 0))

        right = tk.Frame(inner, bg=CARD)
        right.pack(side="right")
        if code == "ja" and not ok:
            RoundButton(right, "安装日语包", command=self._install_ja, width=100, height=28,
                        kind="primary", bg=CARD, font_size=8).pack(side="right")
        else:
            Pill(right, "可用" if ok else "不可用", GREEN if ok else YELLOW,
                 bg=CARD, width=64, height=24).pack(side="right")

    # ------------------------------------------------------------------
    def _use_voice(self, pack_id: str) -> None:
        self.cfg.asr_model = pack_id
        self.cfg.asr_model_path = ""
        self.cfg.save()
        self.status.configure(text=f"已切换到 {pack_id}，正在重新加载…")
        self.app.restart_voice()
        self._refresh()

    def _download(self, pack_id: str) -> None:
        self.status.configure(text=f"已把 {pack_id} 加入下载队列…")
        ml.download_async(pack_id, self.cfg, done=None)
        self._open_queue()
        self._watch_queue()

    def _delete(self, pack_id: str) -> None:
        if messagebox.askyesno("删除语音包", f"确定删除 {pack_id}？\n（可以再下载回来）",
                               parent=self):
            ml.delete_pack(pack_id, self.cfg)
            if self.cfg.asr_model == pack_id:
                self.cfg.asr_model = "small"
                self.cfg.save()
            self.status.configure(text=f"已删除 {pack_id}")
            self._refresh()

    def _clear_custom(self) -> None:
        self.cfg.asr_model_path = ""
        self.cfg.save()
        self.app.restart_voice()
        self.status.configure(text="已取消导入的模型")
        self._refresh()

    def _import_voice(self) -> None:
        path = filedialog.askdirectory(title="选择 faster-whisper 模型文件夹", parent=self)
        if not path:
            return
        try:
            ml.import_folder(path, self.cfg)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导入失败", str(exc), parent=self)
            return
        self.cfg.save()
        self.app.restart_voice()
        self.status.configure(text=f"已导入：{path}")
        self._refresh()

    def _import_ocr(self) -> None:
        path = filedialog.askdirectory(title="选择 paddlex 缓存目录（含 official_models）",
                                       parent=self)
        if not path:
            return
        self.cfg.ocr_model_dir = path
        self.cfg.save()
        self.status.configure(text=f"语言包目录已设为：{path}（重启程序生效）")
        self._refresh()

    def _install_ja(self) -> None:
        """装日语识别包。

        优先走程序内的 PaddleOCR 离线包（不需要管理员、不走 Windows
        更新、带进度条）；只有源码版缺依赖时才去跑安装脚本。
        """
        from ..ocr import paddle_ja
        if paddle_ja.paddle_available():
            self.status.configure(text="已把日语识别包加入下载队列（约 10~20MB）…")
            paddle_ja.install_async(self.cfg, done=None)
            self._open_queue()
            self._watch_queue()
            return
        for name in ("安装日语识别-离线.bat", "安装日语识别.bat"):
            bat = project_root() / name
            if bat.exists():
                subprocess.Popen(f'start "" "{bat}"', shell=True,
                                 cwd=str(project_root()))
                self.status.configure(
                    text=f"缺 PaddleOCR 依赖，已打开「{name}」；装完回来再点一次")
                return
        self.status.configure(text="缺少 PaddleOCR 依赖，也没找到安装脚本；请重新安装程序")

    # ------------------------------------------------------------------
    def _open_queue(self) -> None:
        """打开下载队列窗口（程序里有就复用）。"""
        opener = getattr(self.app, "open_downloads", None)
        if callable(opener):
            try:
                opener()
                return
            except Exception:  # noqa: BLE001
                pass
        from .downloads import DownloadsWindow
        try:
            win = getattr(self, "_queue_win", None)
            if win is not None and win.winfo_exists():
                win.lift()
                return
        except tk.TclError:
            pass
        self._queue_win = DownloadsWindow(self, self.app)

    def _watch_queue(self) -> None:
        """队列跑完后刷新一下列表，让「下载 / 删除」按钮变成正确状态。"""
        from ..downloads import manager
        if getattr(self, "_watching", False):
            return
        self._watching = True

        def tick() -> None:
            try:
                if not self.winfo_exists():
                    self._watching = False
                    return
                if manager().active_count() == 0:
                    self._watching = False
                    self.status.configure(text="下载队列已空闲")
                    self._refresh()
                    return
            except tk.TclError:
                self._watching = False
                return
            self.after(700, tick)

        self.after(700, tick)

    def _open_folder(self) -> None:
        path = ml.models_dir(self.cfg)
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{path}"', shell=True)
