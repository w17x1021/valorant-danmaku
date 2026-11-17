"""模型管理窗口：语音包（识别模型）与语言包（OCR）的选用、下载、导入。"""
from __future__ import annotations

import subprocess
import threading
import tkinter as tk
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

        self.status = label(self.body_frame, "", size=9, color=TEXT_DIM, bg=BG)
        self.status.pack(side="bottom", anchor="w")

        foot = tk.Frame(self.body_frame, bg=BG)
        foot.pack(side="bottom", fill="x", pady=(8, 6))

        self.list_box = tk.Frame(self.body_frame, bg=BG)
        self.list_box.pack(fill="both", expand=True, pady=(8, 4))
        RoundButton(foot, "打开模型文件夹", command=self._open_folder, width=136,
                    height=32, kind="ghost", bg=BG).pack(side="left")
        RoundButton(foot, "从文件夹导入语音包…", command=self._import_voice, width=170,
                    height=32, kind="ghost", bg=BG).pack(side="left", padx=(8, 0))
        RoundButton(foot, "导入语言包…", command=self._import_ocr, width=124, height=32,
                    kind="ghost", bg=BG).pack(side="left", padx=(8, 0))
        RoundButton(foot, "关闭", command=self.destroy, width=88, height=32,
                    kind="primary", bg=BG).pack(side="right")
        RoundButton(foot, "环境检测", command=self._selfcheck, width=104, height=32,
                    kind="outline", bg=BG).pack(side="right", padx=(0, 8))

        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        for w in self.list_box.winfo_children():
            w.destroy()
        self.path_lbl.configure(text=f"模型目录：{ml.models_dir(self.cfg)}")

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
                on_use=lambda pid=pack.id: self._use_voice(pid),
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
        self.status.configure(text="开始下载显卡加速包（约 1.6GB，走清华镜像）…")
        self._refresh()

        def progress(r: float) -> None:
            self.status.configure(text=f"正在下载显卡加速包… {r * 100:.0f}%")

        def done(ok: bool, info: str) -> None:
            if ok:
                self.status.configure(text="显卡加速包装好了，重启程序后语音就走 GPU")
            else:
                self.status.configure(text=f"下载失败：{info[:110]}")
            self._refresh()

        cuda_pack.install_async(done, progress)

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
        self.status.configure(text=f"开始下载 {pack_id}…")
        self._refresh()

        def progress(msg: str) -> None:
            self.status.configure(text=msg)

        def done(ok: bool, info: str) -> None:
            if ok:
                self.status.configure(text=f"{pack_id} 下载完成，点「使用」启用")
            else:
                self.status.configure(text=f"下载失败：{info[:120]}")
            self._refresh()

        ml.download_async(pack_id, self.cfg, done, progress)

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
        """装日语语言包：源码运行跑 bat；安装版直接在程序里下模型。"""
        bat = project_root() / "安装日语识别.bat"
        if bat.exists():
            subprocess.Popen(f'start "" "{bat}"', shell=True, cwd=str(project_root()))
            self.status.configure(text="已打开日语识别安装脚本，按提示装完重启程序")
            return
        self.status.configure(text="正在下载日语识别模型（约 20MB）…")

        def work() -> None:
            try:
                from ..ocr.paddle_ja import PaddleJaOcr
                PaddleJaOcr(self.cfg)          # 初始化时会自动下载语言包
                self.after(0, lambda: self._after_ja(True, ""))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda: self._after_ja(False, msg))

        threading.Thread(target=work, daemon=True, name="dl-ja").start()

    def _after_ja(self, ok: bool, err: str) -> None:
        self.status.configure(text="日语语言包已就绪" if ok else f"下载失败：{err[:110]}")
        self._refresh()

    def _open_folder(self) -> None:
        path = ml.models_dir(self.cfg)
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{path}"', shell=True)
