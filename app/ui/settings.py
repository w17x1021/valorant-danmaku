"""设置对话框（深色）。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..config import Config
from .theme import BORDER, CARD, CARD_SOFT, FONT, TEXT, TEXT_DIM, TEXT_FAINT, dark_titlebar
from .widgets import RoundedWindow, RoundButton, label

DEFAULT_DEVICE = "（系统默认）"
DISPLAY_MODES = {"屏幕下方字幕框": "box", "全屏滚动弹幕": "scroll"}
DISPLAY_REVERSE = {v: k for k, v in DISPLAY_MODES.items()}


def _loopback_devices() -> list[str]:
    try:
        from ..voice.capture import list_loopback_devices
        return [DEFAULT_DEVICE] + [d for d in list_loopback_devices() if d]
    except Exception:  # noqa: BLE001
        return [DEFAULT_DEVICE]


def _mic_devices() -> list[str]:
    try:
        from ..voice.mic import list_microphones
        return [DEFAULT_DEVICE] + [d for d in list_microphones() if d]
    except Exception:  # noqa: BLE001
        return [DEFAULT_DEVICE]


class SettingsDialog(RoundedWindow):
    W, H = 470, 920

    def __init__(self, parent, app):
        self.app = app
        self.cfg: Config = app.cfg
        super().__init__(parent, "设置", self.W, self.H, on_close=self.destroy)
        self._build()
        self.update_idletasks()
        self.geometry(f"{self.W}x{self.H}"
                      f"+{max(0, self.winfo_screenwidth() // 2 - self.W // 2)}"
                      f"+{max(0, self.winfo_screenheight() // 2 - self.H // 2)}")
        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------
    def _row(self, parent, row: int, text: str) -> None:
        label(parent, text, size=9, color=TEXT_DIM).grid(
            row=row, column=0, sticky="e", padx=(0, 10), pady=5)

    def _build(self) -> None:
        frm = tk.Frame(self.body, bg=CARD, padx=18, pady=12)
        frm.pack(fill="both", expand=True)

        label(frm, "改完点保存，部分项目会立即生效", size=8, color=TEXT_FAINT).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        r = 1
        self._row(frm, r, "大模型密钥")
        self.key_var = tk.StringVar(value=self.cfg.openai_key)
        ttk.Entry(frm, textvariable=self.key_var, width=38, show="*").grid(
            row=r, column=1, sticky="ew", pady=4)
        r += 1

        self._row(frm, r, "接口地址")
        self.base_var = tk.StringVar(value=self.cfg.openai_base)
        ttk.Entry(frm, textvariable=self.base_var, width=38).grid(
            row=r, column=1, sticky="ew", pady=4)
        r += 1

        self._row(frm, r, "模型名")
        self.model_var = tk.StringVar(value=self.cfg.openai_model)
        ttk.Entry(frm, textvariable=self.model_var, width=24).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        tk.Frame(frm, bg=BORDER, height=1).grid(row=r, column=0, columnspan=2,
                                                sticky="ew", pady=10)
        r += 1

        self._row(frm, r, "字幕样式")
        self.mode_var = tk.StringVar(
            value=DISPLAY_REVERSE.get(getattr(self.cfg, "display_mode", "box"), "屏幕下方字幕框"))
        ttk.Combobox(frm, textvariable=self.mode_var, state="readonly", width=22,
                     values=list(DISPLAY_MODES)).grid(row=r, column=1, sticky="w", pady=4)
        r += 1

        self._row(frm, r, "翻译源")
        providers = {"有道（最快 ~0.2s）": "youdao", "必应（最准 ~0.8s）": "bing",
                     "MyMemory（备用）": "mymemory", "Google（需外网）": "google"}
        reverse = {v: k for k, v in providers.items()}
        current = (list(self.cfg.provider_order) or ["youdao"])[0]
        self.provider_var = tk.StringVar(value=reverse.get(current, "有道（最快 ~0.2s）"))
        ttk.Combobox(frm, textvariable=self.provider_var, state="readonly", width=22,
                     values=list(providers)).grid(row=r, column=1, sticky="w", pady=4)
        r += 1
        self._providers = providers

        self._row(frm, r, "OCR 间隔(ms)")
        self.interval_var = tk.StringVar(value=str(self.cfg.ocr_interval_ms))
        ttk.Entry(frm, textvariable=self.interval_var, width=8).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        self._row(frm, r, "行距(1.2~2.0)")
        self.spacing_var = tk.StringVar(value=f"{self.cfg.box_line_spacing:.2f}")
        ttk.Entry(frm, textvariable=self.spacing_var, width=8).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        self._row(frm, r, "离底部(px)")
        self.bottom_var = tk.StringVar(value=str(self.cfg.box_bottom_margin))
        ttk.Entry(frm, textvariable=self.bottom_var, width=8).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        self._row(frm, r, "底色不透明(0~255)")
        self.alpha_var = tk.StringVar(value=str(self.cfg.box_bg_alpha))
        ttk.Entry(frm, textvariable=self.alpha_var, width=8).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        self._row(frm, r, "滚动轨道数")
        self.lanes_var = tk.StringVar(value=str(self.cfg.danmaku_lanes))
        ttk.Entry(frm, textvariable=self.lanes_var, width=8).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        tk.Frame(frm, bg=BORDER, height=1).grid(row=r, column=0, columnspan=2,
                                                sticky="ew", pady=10)
        r += 1

        self._row(frm, r, "队友语音来源")
        devices = _loopback_devices()
        self.device_var = tk.StringVar(
            value=self.cfg.voice_device if self.cfg.voice_device in devices else DEFAULT_DEVICE)
        ttk.Combobox(frm, textvariable=self.device_var, values=devices,
                     state="readonly", width=30).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        self._row(frm, r, "我的麦克风")
        mics = _mic_devices()
        self.mic_var = tk.StringVar(
            value=self.cfg.mic_device if self.cfg.mic_device in mics else DEFAULT_DEVICE)
        ttk.Combobox(frm, textvariable=self.mic_var, values=mics,
                     state="readonly", width=30).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1

        self._row(frm, r, "语音模型")
        self.asr_model_var = tk.StringVar(value=self.cfg.asr_model)
        ttk.Combobox(frm, textvariable=self.asr_model_var, width=16, state="readonly",
                     values=["tiny", "base", "small", "medium", "large-v3-turbo"]).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        self._row(frm, r, "过滤英雄台词")
        self.agent_filter_var = tk.BooleanVar(
            value=bool(getattr(self.cfg, "filter_agent_lines", True)))
        ttk.Checkbutton(frm, text="不翻译角色语音（Watch this! 之类）",
                        variable=self.agent_filter_var).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1

        tk.Frame(frm, bg=BORDER, height=1).grid(row=r, column=0, columnspan=2,
                                                sticky="ew", pady=10)
        r += 1
        tk.Label(frm, text="快捷键（下拉选，被占用会自动换下一个）", bg=CARD, fg=TEXT_DIM,
                 font=(FONT, 9, "bold")).grid(row=r, column=0, columnspan=2,
                                              sticky="w", pady=(0, 4))
        r += 1
        keys = [f"F{i}" for i in range(1, 13)] + [f"Ctrl+Alt+F{i}" for i in range(1, 13)]
        for label_text, attr, default in (
                ("面板显示/隐藏", "hotkey_panel", "F6"),
                ("弹幕显示/隐藏", "hotkey_danmaku", "F7"),
                ("我说的话窗口", "hotkey_talk", "F8"),
                ("复制日语", "hotkey_ja", "F9"),
                ("复制英语", "hotkey_en", "F10")):
            self._row(frm, r, label_text)
            var = tk.StringVar(value=getattr(self.cfg, attr, default))
            ttk.Combobox(frm, textvariable=var, values=keys, width=13,
                         state="readonly").grid(row=r, column=1, sticky="w", pady=2)
            setattr(self, f"{attr}_var", var)
            r += 1

        btns = tk.Frame(frm, bg=CARD)
        btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(16, 0))
        RoundButton(btns, "取消", command=self.destroy, width=84, height=32,
                    kind="ghost").pack(side="right", padx=(8, 0))
        RoundButton(btns, "保存", command=self._save, width=96, height=32,
                    kind="primary").pack(side="right")

        frm.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    def _save(self) -> None:
        cfg = self.cfg
        old_device, old_model, old_mic = cfg.voice_device, cfg.asr_model, cfg.mic_device
        old_mode = getattr(cfg, "display_mode", "box")

        cfg.openai_key = self.key_var.get().strip()
        chosen = self._providers.get(self.provider_var.get(), "youdao")
        rest = [p for p in cfg.provider_order if p != chosen]
        cfg.provider_order = [chosen] + rest
        cfg.openai_base = self.base_var.get().strip() or cfg.openai_base
        cfg.openai_model = self.model_var.get().strip() or cfg.openai_model
        dev = self.device_var.get().strip()
        cfg.voice_device = None if dev == DEFAULT_DEVICE else dev
        mic = self.mic_var.get().strip()
        cfg.mic_device = None if mic == DEFAULT_DEVICE else mic
        cfg.asr_model = self.asr_model_var.get().strip() or cfg.asr_model
        cfg.display_mode = DISPLAY_MODES.get(self.mode_var.get(), old_mode)
        try:
            cfg.filter_agent_lines = bool(self.agent_filter_var.get())
        except Exception:  # noqa: BLE001
            pass
        try:
            cfg.ocr_interval_ms = max(80, int(self.interval_var.get()))
        except ValueError:
            pass
        try:
            cfg.danmaku_lanes = max(1, min(10, int(self.lanes_var.get())))
        except ValueError:
            pass
        try:
            cfg.box_line_spacing = min(2.2, max(1.1, float(self.spacing_var.get())))
        except ValueError:
            pass
        try:
            cfg.box_bottom_margin = max(60, min(900, int(self.bottom_var.get())))
        except ValueError:
            pass
        try:
            cfg.box_bg_alpha = max(0, min(255, int(self.alpha_var.get())))
        except ValueError:
            pass

        old_keys = tuple(getattr(cfg, k, "") for k in
                         ("hotkey_panel", "hotkey_danmaku", "hotkey_talk",
                          "hotkey_ja", "hotkey_en"))
        for attr in ("hotkey_panel", "hotkey_danmaku", "hotkey_talk",
                     "hotkey_ja", "hotkey_en"):
            value = getattr(self, f"{attr}_var").get().strip()
            if value:
                setattr(cfg, attr, value)
        cfg.save()

        self.app.reload_translator()
        try:
            cfg.save()
        except Exception:  # noqa: BLE001
            pass
        new_keys = tuple(getattr(cfg, k, "") for k in
                         ("hotkey_panel", "hotkey_danmaku", "hotkey_talk",
                          "hotkey_ja", "hotkey_en"))
        if new_keys != old_keys:
            self.app.reload_hotkeys()
        try:
            self.app.overlay.apply_region()
        except Exception:  # noqa: BLE001
            pass
        if cfg.voice_device != old_device or cfg.asr_model != old_model:
            self.app.restart_voice()
        if cfg.mic_device != old_mic and self.app.selftalk is not None:
            self.app.restart_selftalk()
        if cfg.display_mode != old_mode:
            self.app.toggle_display_mode()
            if cfg.display_mode != old_mode:      # 切反了就再切一次
                self.app.toggle_display_mode()
        self.app.panel.set_display_mode(cfg.display_mode)
        self.destroy()
