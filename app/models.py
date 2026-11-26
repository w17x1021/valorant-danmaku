"""语音包（Whisper 模型）与语言包（OCR）的目录管理、下载、导入。

下载走的是 HF 镜像的 HTTP 接口而不是 `snapshot_download`：
* 能先拿到每个文件的大小，从而算出总进度、速度、剩余时间；
* 断了能续传（`.part` 文件 + Range），几百 MB 的包不用从头再来；
* 进度直接喂给 app.downloads 的任务对象，UI 那边就能实时看。
"""
from __future__ import annotations

import fnmatch
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import Config, project_root
from .downloads import fetch_file


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
WANTED_PATTERNS = ("*.json", "*.bin", "*.txt")

HF_ENDPOINT = "https://hf-mirror.com"
MIRRORS = (HF_ENDPOINT, "https://huggingface.co")
USER_AGENT = "valorant-danmaku/1.0 (+https://github.com/w17x1021/valorant-danmaku)"


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
            if subs and valid_model_dir(subs[-1]):
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
# Hugging Face 镜像的 HTTP 访问
def _mirrors() -> list[str]:
    env = (os.environ.get("HF_ENDPOINT") or "").strip().rstrip("/")
    out = [env] if env else []
    for m in MIRRORS:
        if m not in out:
            out.append(m)
    return out


def _get_json(url: str, timeout: float = 25.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.loads(fh.read().decode("utf-8", "replace"))


def repo_files(repo: str) -> tuple[list[tuple[str, int]], str, str]:
    """返回 ([(文件名, 字节数)], 版本 sha, 用的镜像地址)。"""
    last = ""
    for base in _mirrors():
        try:
            data = _get_json(f"{base}/api/models/{repo}?blobs=true")
        except Exception as exc:  # noqa: BLE001
            last = f"{base}: {type(exc).__name__}: {exc}"
            continue
        rev = str(data.get("sha") or "main")
        files: list[tuple[str, int]] = []
        for sib in data.get("siblings") or []:
            name = str(sib.get("rfilename") or "")
            if not name:
                continue
            size = int(sib.get("size") or 0)
            if not size:
                lfs = sib.get("lfs") or {}
                size = int(lfs.get("size") or 0)
            files.append((name, size))
        if files:
            return files, rev, base
    raise RuntimeError(last or "取不到模型文件清单")


def _wanted(name: str) -> bool:
    if name.startswith("."):
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in WANTED_PATTERNS)


# ----------------------------------------------------------------------
def download(pack_id: str, cfg: Config, progress=None, task=None) -> Path:
    """下载语音包到模型目录，返回快照路径。"""
    os.environ.setdefault("HF_ENDPOINT", HF_ENDPOINT)
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

    pack = PACK_BY_ID.get(pack_id)
    repo = pack.repo if pack else f"Systran/faster-whisper-{pack_id}"
    root = models_dir(cfg)
    root.mkdir(parents=True, exist_ok=True)

    files, rev, base = repo_files(repo)
    wanted = [(name, size) for name, size in files if _wanted(name)]
    if not wanted:
        raise RuntimeError(f"{repo} 里没有可下载的模型文件")

    target = root / f"models--{repo.replace('/', '--')}" / "snapshots" / rev
    target.mkdir(parents=True, exist_ok=True)

    pending: list[tuple[str, int]] = []
    ready_bytes = 0
    for name, size in wanted:
        dest = target / name
        part = dest.with_name(dest.name + ".part")
        if dest.exists() and (not size or dest.stat().st_size == size):
            ready_bytes += size or dest.stat().st_size
            continue
        if part.exists():
            ready_bytes += part.stat().st_size
        pending.append((name, size))

    total = sum(size for _, size in wanted)
    if task:
        task.set_total(total)
        task.set_done(ready_bytes)
    if progress:
        progress(f"{repo}：共 {total / 1024 / 1024:.0f} MB，{len(pending)} 个文件待下载")

    # 一条线路下不动就换下一条（镜像站 / 原站），别让整包卡死在一个域名上
    bases = [base] + [m for m in _mirrors() if m != base]
    for index, (name, size) in enumerate(pending, 1):
        last = ""
        for candidate in bases:
            if task:
                task.check_cancel()
                task.set_note(f"{name}  ({index}/{len(pending)})")
            try:
                fetch_file(f"{candidate}/{repo}/resolve/main/{name}",
                           target / name, size, task=task)
                break
            except Exception as exc:  # noqa: BLE001
                last = f"{candidate}: {type(exc).__name__}: {exc}"
                if task:
                    task.set_note(f"{name} 换线路重试…")
        else:
            raise RuntimeError(f"{name} 下载失败（所有线路都试过了）：{last}")

    return target


def download_async(pack_id: str, cfg: Config, done, progress=None):
    """排进下载队列，返回 Task（见 app.downloads）。"""
    from .downloads import manager

    pack = PACK_BY_ID.get(pack_id)
    title = f"语音包 {pack_id}" if pack is None else f"语音包 {pack.label.split(' ')[0]}"
    detail = f"{pack.size} · {pack.note}" if pack else ""

    def job(task):
        try:
            path = download(pack_id, cfg, progress=progress, task=task)
        except Exception as exc:  # noqa: BLE001
            if done:
                done(False, str(exc))
            raise
        if done:
            done(True, str(path))

    return manager().add(title, job, detail=detail)


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
    """语言包状态：语言代码 -> (可用, 说明)。

    日语有两条路：装了 Windows 的日语 OCR 就算可用（最省 CPU），
    没装但有 PaddleOCR 离线包也算可用（程序会自动走兜底）。
    """
    out: dict[str, tuple[bool, str]] = {}
    langs = set(available_langs or ["en-US", "zh-Hans"])
    def has(prefix: str) -> bool:
        return any(str(x).lower().startswith(prefix) for x in langs)

    out["en"] = (has("en"), "Windows 自带 OCR")
    out["zh"] = (has("zh"), "Windows 自带 OCR")
    pack = paddle_dir(cfg) / "official_models" / "PP-OCRv5_mobile_rec"
    if has("ja"):
        out["ja"] = (True, "Windows 自带 OCR")
    elif pack.is_dir():
        out["ja"] = (True, "PaddleOCR 离线包")
    else:
        out["ja"] = (False, "未安装")
    return out
