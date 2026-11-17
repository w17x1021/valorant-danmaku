"""配置读写。所有可调参数集中在 Config 里，保存在项目根目录 config.json。"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

APP_NAME = "瓦罗兰特实时翻译弹幕"
APP_ID = "valorant-danmaku"


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def project_root() -> Path:
    """配置 / 日志 / 模型的落点。

    打包成 exe 后优先用安装目录（绿色版）；装在 Program Files 这类没写权限的地方时，
    自动退到 %LOCALAPPDATA%\\ValorantDanmaku，保证还能保存设置、下载模型。
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        if _writable(exe_dir):
            return exe_dir
        fallback = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ValorantDanmaku"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    return Path(__file__).resolve().parents[1]


def asset_path(name: str) -> Path:
    """资源文件（图标等）在源码和打包后的 exe 里都能找到。"""
    cands: list[Path] = []
    if getattr(sys, "frozen", False):
        cands.append(Path(sys.executable).parent / "assets")
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            cands.append(Path(meipass) / "assets")
    cands.append(Path(__file__).resolve().parents[1] / "assets")
    cands.append(project_root() / "assets")
    for c in cands:
        p = c / name
        if p.exists():
            return p
    return cands[0] / name


@dataclass
class Config:
    # ---------- 文字聊天 OCR ----------
    ocr_enabled: bool = True
    chat_region: list[int] | None = None          # [x, y, w, h]，屏幕绝对坐标
    ocr_interval_ms: int = 260                    # 抓屏间隔
    ocr_upscale: float = 2.0                      # 送 OCR 前放大倍数（小字更准）
    ocr_langs: list[str] = field(default_factory=lambda: ["en-US", "ja", "zh-Hans-CN"])
    ocr_min_length: int = 3
    ja_fallback: str = "auto"                     # auto=Windows 没有日语包时用 PaddleOCR 兜底 / off=关闭

    # ---------- 语音（队友开麦） ----------
    voice_enabled: bool = True
    voice_device: str | None = None               # 环回设备名，None = 默认扬声器
    asr_model: str = "large-v3-turbo"              # 见 设置 → 模型管理
    asr_model_path: str = ""                       # 导入的模型目录（优先于 asr_model）
    asr_model_dir: str = ""                        # 语音包存放目录，空=项目 models/
    ocr_model_dir: str = ""                        # 语言包(paddlex)目录，空=项目 cache/paddlex
    asr_device: str = "auto"                      # auto=有显卡用 GPU，没有就 CPU
    asr_compute: str = "auto"                     # auto / int8 / float16
    asr_languages: list[str] = field(default_factory=lambda: ["en", "ja", "zh"])
    vad_threshold: float = 0.010                  # 语音能量阈值（自适应底噪的倍数基准）
    vad_silence_ms: int = 400                     # 静音多久算一句结束
    vad_min_ms: int = 450                         # 太短的片段丢弃
    vad_max_s: float = 14.0

    # ---------- 我说的話（中文 -> 日文/英文，复制到聊天框） ----------
    selftalk_enabled: bool = True
    mic_device: str | None = None                 # 麦克风设备名，None = 系统默认
    selftalk_auto_copy: str = "off"               # off / ja / en：识别完自动复制哪个
    selftalk_language: str = "zh"                 # 我说的语言；zh 固定简体（auto=自动判断）

    # ---------- 语音播报（看不见弹幕时听译文） ----------
    tts_enabled: bool = False
    tts_voice: str = ""                            # 留空=自动挑中文音色
    tts_rate: int = 1                              # -10~10，越大越快
    tts_max_chars: int = 60

    # ---------- 翻译 ----------
    provider_order: list[str] = field(default_factory=lambda: ["youdao", "bing", "mymemory"])
    target_lang: str = "zh-Hans"
    translate_timeout: float = 5.0
    dedupe_window_s: float = 25.0                 # 同一句话多少秒内不重复出弹幕
    openai_base: str = "https://api.deepseek.com/v1"
    openai_key: str = ""
    openai_model: str = "deepseek-chat"

    # ---------- 弹幕外观 ----------
    font_family: str = "Microsoft YaHei UI"
    display_mode: str = "box"                     # box=屏幕下方字幕框 / scroll=全屏滚动
    danmaku_font_size: int = 22
    danmaku_speed: float = 250.0                  # 像素/秒（仅 scroll 模式）
    danmaku_lanes: int = 5                        # 仅 scroll 模式
    box_width_ratio: float = 0.34                 # 字幕框最大宽度占屏幕比例（box_width_px 为 0 时用）
    box_width_px: int = 760                       # 字幕框最大宽度（像素），0 = 按比例
    box_bottom_margin: int = 210                  # 字幕框底边距屏幕底部的像素
    box_max_lines: int = 3                        # 框里最多叠几条
    box_ttl_s: float = 7.0                        # 每条显示多少秒后消失
    box_line_spacing: float = 1.62                # 行距（行高 = 字号 × 这个数）
    box_alpha: float = 0.92
    box_bg: str = "#0b0d12"
    box_bg_alpha: int = 205                       # 底色不透明度 0-255
    box_border: str = "#33415a"
    danmaku_opacity: float = 0.95
    danmaku_band: str = "top"                     # top / above_chat / custom
    danmaku_region: list[int] | None = None       # 自定义弹幕区域 [x, y, w, h]
    color_en: str = "#9ec9ff"
    color_ja: str = "#ffb0d4"
    color_zh: str = "#ffffff"
    color_voice: str = "#b6ffcf"
    show_speaker: bool = True
    show_source_tag: bool = False                 # 弹幕前加 [EN]/[JA]（颜色已能区分语言）

    # ---------- 其它 ----------
    # ---------- 快捷键（可自定义） ----------
    hotkey_panel: str = "F6"
    hotkey_danmaku: str = "F7"
    hotkey_talk: str = "F8"
    hotkey_ja: str = "F9"
    hotkey_en: str = "F10"

    panel_geometry: str = ""
    log_enabled: bool = True
    history_size: int = 200

    # ------------------------------------------------------------------
    @classmethod
    def path(cls) -> Path:
        return project_root() / "config.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        p = path or cls.path()
        cfg = cls()
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            cfg.update(raw)
        return cfg

    def update(self, raw: dict[str, Any]) -> None:
        known = {f.name for f in fields(self)}
        for k, v in (raw or {}).items():
            if k in known and v is not None:
                setattr(self, k, v)

    def save(self, path: Path | None = None) -> None:
        p = path or self.path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
