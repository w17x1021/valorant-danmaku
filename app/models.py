"""语音包（Whisper 模型）与语言包（OCR）的目录管理、下载、导入。"""
from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import Config, project_root


@dataclass
class VoicePack:
    id: str
    label: str
    size: str
    vram: str
    note: str
    repo: str


VOICE_PACKS: list[VoicePack] = [
    VoicePack("tiny", "tiny · 极速", "75 MB", "~1 GB", "老显卡/核显也能跑，准确度一般",
              "Systran/faster-whisper-tiny"),
    VoicePack("base", "base · 轻量", "145 MB", "~1 GB", "比 tiny 稳一点", "Systran/faster-whisper-base"),
    VoicePack("small", "small · 均衡", "484 MB", "~2 GB", "上一版默认，够用",
              "Systran/faster-whisper-small"),
    VoicePack("medium", "medium · 准确", "1.5 GB", "~4 GB", "准确度更高，慢一倍",
              "Systran/faster-whisper-medium"),
    VoicePack("large-v3-turbo", "large-v3-turbo · 推荐", "1.6 GB", "~4 GB",
              "又快又准，5070 Ti / 4060 以上首选",
              "mobiuslabsgmbh/faster-whisper-large-v3-turbo"),
    VoicePack("large-v3", "large-v3 · 最准", "3.1 GB", "~6 GB", "最准但最慢，一般不必要",
              "Systran/faster-whisper-large-v3"),
]

PACK_BY_ID = {p.id: p for p in VOICE_PACKS}

OCR_LANGS = [
    ("en", "英语", "Windows 自带 OCR"),
    ("zh", "中文", "Windows 自带 OCR"),
    ("ja", "日语", "PaddleOCR 离线包"),
]

MODEL_FILES = ("model.bin", "config.json")


# ----------------------------------------------------------------------
def models_dir(cfg: Config) -> Path:
    custom = (getattr(cfg, "asr_model_dir", "") or "").strip()
    return Path(custom) if custom else project_root() / "models"


def paddle_dir(cfg: Config) -> Path:
    custom = (getattr(cfg, "ocr_model_dir", "") or "").strip()
    if custom:
        return Path(custom)
    return project_root() / "cache" / "paddlex"


def installed_path(cfg: Config, pack_id: str) -> Path | None:
    """已下载的模型目录（faster-whisper 的 snapshot 目录）。"""
    root = models_dir(cfg)
    if not root.is_dir():
        return None
    for d in sorted(root.glob("models--*")):
        # 必须精确以 "-<包名>" 结尾，否则 large-v3 会误匹配 large-v3-turbo
        if not d.name.lower().endswith("-" + pack_id.lower()):
            continue
        snaps = d / "snapshots"
        if snaps.is_dir():
            subs = sorted((s for s in snaps.iterdir() if s.is_dir()),
                          key=lambda p: p.stat().st_mtime)
            if subs:
                return subs[-1]
    return None


def dir_size_mb(path: Path) -> float:
    try:
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / 1024 / 1024
    except OSError:
        return 0.0


def valid_model_dir(path: Path) -> bool:
    try:
        return path.is_dir() and all((path / f).exists() for f in MODEL_FILES)
    except OSError:
        return False


def current_pack(cfg: Config) -> str:
    custom = (getattr(cfg, "asr_model_path", "") or "").strip()
    if custom:
        return "（已导入的自定义模型）"
    return getattr(cfg, "asr_model", "small")


# ----------------------------------------------------------------------
def download(pack_id: str, cfg: Config, progress=None) -> Path:
    """下载语音包到模型目录，返回快照路径。"""
    from huggingface_hub import snapshot_download

    pack = PACK_BY_ID.get(pack_id)
    repo = pack.repo if pack else f"Systran/faster-whisper-{pack_id}"
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    root = models_dir(cfg)
    root.mkdir(parents=True, exist_ok=True)

    last = ""
    for attempt in range(4):
        try:
            if progress:
                progress(f"正在下载 {pack_id}（第 {attempt + 1} 次尝试）…")
            path = snapshot_download(repo, cache_dir=str(root),
                                     allow_patterns=["*.json", "*.bin", "*.txt"])
            return Path(path)
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
            if progress:
                progress(f"下载失败：{last[:90]}，重试中…")
    raise RuntimeError(last or "下载失败")


def download_async(pack_id: str, cfg: Config, done, progress=None) -> threading.Thread:
    def run():
        try:
            path = download(pack_id, cfg, progress)
            done(True, str(path))
        except Exception as exc:  # noqa: BLE001
            done(False, str(exc))

    t = threading.Thread(target=run, daemon=True, name=f"dl-{pack_id}")
    t.start()
    return t


def delete_pack(pack_id: str, cfg: Config) -> None:
    root = models_dir(cfg)
    for d in root.glob("models--*"):
        if d.name.lower().endswith("-" + pack_id.lower()):
            shutil.rmtree(d, ignore_errors=True)


# ----------------------------------------------------------------------
def import_folder(src: Path, cfg: Config) -> Path:
    """直接使用别处的模型目录（不复制，省空间）。"""
    src = Path(src)
    if not valid_model_dir(src):
        raise RuntimeError("这个文件夹里没有 model.bin / config.json，不像是 faster-whisper 模型")
    cfg.asr_model_path = str(src)
    default = getattr(cfg, "asr_model", "")
    if not default:
        cfg.asr_model = "small"
    return src


def ocr_status(cfg: Config,
               available_langs: list[str] | None = None) -> dict[str, tuple[bool, str]]:
    """语言包状态：语言代码 -> (可用, 说明)。"""
    out: dict[str, tuple[bool, str]] = {}
    langs = set(available_langs or ["en-US", "zh-Hans"])
    def has(prefix: str) -> bool:
        return any(str(x).lower().startswith(prefix) for x in langs)

    out["en"] = (has("en"), "Windows 自带 OCR")
    out["zh"] = (has("zh"), "Windows 自带 OCR")
    pack = paddle_dir(cfg) / "official_models" / "PP-OCRv5_mobile_rec"
    out["ja"] = (pack.is_dir(), "PaddleOCR 离线包" if pack.is_dir() else "未安装")
    return out
