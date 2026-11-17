"""环境自检：把「能不能正常用」拆成几条，逐条检测并给出怎么修。"""
from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import cuda_pack, models as ml
from .config import Config, project_root


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    fix: str = ""


def _dll_roots() -> list[Path]:
    roots = [Path(__import__("sys").prefix) / "Lib" / "site-packages"]
    try:
        roots.append(project_root() / "cuda")
    except Exception:  # noqa: BLE001
        pass
    exe_dir = Path(__import__("sys").executable).parent
    roots += [exe_dir / "_internal", exe_dir]
    return roots


def _find_cuda_dll(name: str) -> Path | None:
    for root in _dll_roots():
        for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_nvrtc/bin"):
            p = root / sub / name
            if p.exists():
                return p
    return None


def run_all(cfg: Config, app=None) -> list[Check]:
    out: list[Check] = []

    # 1. 运行环境
    out.append(Check("程序文件", True, f"运行目录：{project_root()}"))

    # 2. 显卡加速库
    cublas = _find_cuda_dll("cublas64_12.dll") or _find_cuda_dll("cublasLt64_12.dll")
    cudnn = _find_cuda_dll("cudnn64_9.dll")
    if cublas and cudnn:
        out.append(Check("显卡加速库", True, "cuBLAS + cuDNN 已就绪（GPU 加速可用）"))
    else:
        missing = [n for n, v in (("cuBLAS", cublas), ("cuDNN", cudnn)) if not v]
        out.append(Check("显卡加速库", False, f"缺少 {' / '.join(missing)}",
                         "到「模型」页点「下载显卡加速包」（约 1.6GB），或继续用 CPU 模式（慢一些）"))

    # 3. 有没有 CUDA 设备
    try:
        import ctranslate2
        n = ctranslate2.get_cuda_device_count()
        if n > 0:
            out.append(Check("CUDA 显卡", True, f"检测到 {n} 块可用 CUDA 设备"))
        else:
            out.append(Check("CUDA 显卡", False, "没有可用的 CUDA 设备（会走 CPU）",
                             "确认装了 NVIDIA 驱动；没有独立显卡就忽略这条"))
    except Exception as exc:  # noqa: BLE001
        out.append(Check("CUDA 显卡", False, f"检测失败：{type(exc).__name__}", ""))

    # 4. 语音包
    custom = (getattr(cfg, "asr_model_path", "") or "").strip()
    if custom and ml.valid_model_dir(Path(custom)):
        out.append(Check("语音包（识别模型）", True, f"使用导入的模型：{custom}"))
    else:
        pack = getattr(cfg, "asr_model", "small")
        path = ml.installed_path(cfg, pack)
        if path:
            out.append(Check("语音包（识别模型）", True,
                             f"{pack} 已下载（{ml.dir_size_mb(path):.0f} MB）"))
        else:
            out.append(Check("语音包（识别模型）", False, f"{pack} 还没下载",
                             "到「模型」页点对应模型的「下载」，下完点「使用」"))

    # 5. 语言包
    langs = getattr(getattr(app, "ocr", None), "available", None)
    status = ml.ocr_status(cfg, langs)
    for code, name, _ in ml.OCR_LANGS:
        ok, note = status.get(code, (False, "未知"))
        fix = ""
        if not ok and code == "ja":
            fix = "到「模型」页点「安装日语包」"
        elif not ok:
            fix = "Windows 设置 → 时间和语言 → 语言 → 添加语言（含 OCR）"
        out.append(Check(f"语言包 · {name}", ok, note, fix))

    # 6. 翻译可用性
    tr = getattr(app, "translator", None)
    if tr is not None:
        try:
            res = tr.translate("hello", "en")
            if res and res.text:
                out.append(Check("在线翻译", True, f"{res.provider} 正常：hello → {res.text}"))
            else:
                out.append(Check("在线翻译", False, "翻译返回空", "检查网络，或在设置里换翻译源"))
        except Exception as exc:  # noqa: BLE001
            out.append(Check("在线翻译", False, f"失败：{str(exc)[:60]}", "检查网络或换翻译源"))

    # 7. 音频设备
    try:
        import soundcard as sc
        speakers = sc.all_speakers()
        mics = sc.all_microphones(include_loopback=True)
        out.append(Check("音频设备", bool(speakers and mics),
                         f"扬声器 {len(speakers)} 个 · 麦克风 {len(mics)} 个",
                         "听不到队友语音就检查系统默认播放设备"))
    except Exception as exc:  # noqa: BLE001
        out.append(Check("音频设备", False, f"枚举失败：{type(exc).__name__}",
                         "安装「语音」依赖后重试"))

    # 8. 磁盘
    try:
        free = shutil.disk_usage(project_root()).free / 1024 ** 3
        out.append(Check("磁盘空间", free > 2, f"剩余 {free:.1f} GB",
                         "下载语音包至少需要 2GB" if free <= 2 else ""))
    except OSError:
        pass

    return out


def summary(checks: list[Check]) -> tuple[int, int]:
    ok = sum(1 for c in checks if c.ok)
    return ok, len(checks)
