"""faster-whisper 语音识别封装。

* 有 NVIDIA 显卡时自动走 CUDA（fp16），没有就退回 CPU（int8）；
* 用「瓦罗兰特词表」做 initial_prompt，显著减少 B点/绕后/下包 这类黑话被听错；
* 模型已下载时 local_files_only=True，启动不再联网校验，加载快很多。
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from pathlib import Path

import numpy as np

from ..config import Config, project_root

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

HALLUCINATIONS = {
    "thank you", "thanks", "thank you very much", "thanks for watching",
    "please subscribe", "subscribe", "bye", "you", "mm", "uh", "oh",
    "the end", "subtitles by", "amara org", "www amara org",
    "请不吝点赞 订阅 转发 打赏支持明镜与点点栏目",
    "ご視聴ありがとうございました", "ありがとうございました",
}
PUNCT_RE = re.compile(r"[^\w\u3040-\u30ff\u3400-\u9fff]+")

# 配置里点的模型本机没装时，按这个顺序退到已经下载好的
FALLBACK_ORDER = ("small", "base", "tiny", "medium", "large-v3-turbo", "large-v3")

# 各语言的「游戏词表」提示，用来给解码器打底
PROMPTS = {
    "zh": ("以下是简体中文普通话的瓦罗兰特游戏语音：A点、B点、C点、中路、绕后、"
           "进攻、下包、拆包、残血、闪光弹、烟雾弹、保枪、经济局、快攻、回防。"
           "英雄：捷风、贤者、尚勃勒、钱包、奶妈、雷兹、火男、夜露、零、苏瓦。"),
    "en": ("VALORANT voice chat: push A site, B site, mid, rotate, flank, plant the spike, "
           "defuse, eco round, one HP, nice shot, hold the angle, fall back."),
    "ja": ("VALORANTのボイスチャット：Aサイト、Bサイト、ミッド、ローテート、"
           "フランク、突っ込む、スパイク設置、解除、エコ、残り1。"),
}


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.，。")


def _setup_cuda_dlls() -> None:
    r"""pip 装的 cuBLAS/cuDNN 在 Windows 上不在 DLL 搜索路径里，手动加进去。

    打包成 exe 后位置变成 <程序目录>\_internal\nvidia\...，这里两种都找。
    """
    roots = [Path(sys.prefix) / "Lib" / "site-packages"]
    try:
        from ..config import project_root
        roots.append(project_root() / "cuda")        # 按需下载的显卡加速包
    except Exception:  # noqa: BLE001
        pass
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        roots += [base / "_internal", base]
    for root in roots:
        for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_nvrtc/bin"):
            p = root / sub
            if p.exists():
                try:
                    os.add_dll_directory(str(p))
                except (OSError, AttributeError):
                    pass
                os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")


class Asr:
    def __init__(self, cfg: Config, on_status=None):
        self.cfg = cfg
        self.on_status = on_status or (lambda *_: None)
        self.model = None
        self.ready = False
        self.device_used = ""
        self.compute_used = ""
        self.loading = False
        self.error = ""
        custom_dir = str(getattr(cfg, "asr_model_dir", "") or "").strip()
        self.model_dir = Path(custom_dir) if custom_dir else project_root() / "models"
        self._lock = threading.Lock()
        self._infer_lock = threading.Lock()
        self._last_lang = ""

    # ------------------------------------------------------------------
    def _installed(self, name: str) -> Path | None:
        """本机已下载、文件完整的模型快照。

        只有 refs/ 或 trees/ 的半截目录（下载中断 / 只拉到元数据）不算数，
        否则界面会显示「已拥有」，实际一加载就报错。
        """
        try:
            if not self.model_dir.exists():
                return None
            for d in sorted(self.model_dir.glob("models--*")):
                if not d.name.lower().endswith("-" + name.lower()):
                    continue
                snaps = d / "snapshots"
                if not snaps.is_dir():
                    continue
                for sub in sorted(snaps.iterdir(), reverse=True):
                    if (sub / "model.bin").is_file() and (sub / "config.json").is_file():
                        return sub
        except OSError:
            pass
        return None

    def _pick_local_model(self) -> Path | None:
        """挑一个本机能直接用的模型：导入目录 > 配置的 > 已下载的别的。

        绝不在启动时偷偷联网下几百 MB～几 GB：下载一律走「模型 → 下载」，
        那里有队列、进度条和速度。
        """
        custom = (getattr(self.cfg, "asr_model_path", "") or "").strip()
        if custom:
            p = Path(custom)
            if (p / "model.bin").is_file() and (p / "config.json").is_file():
                return p
        wanted = str(getattr(self.cfg, "asr_model", "small") or "small")
        found = self._installed(wanted)
        if found is not None:
            return found
        for name in FALLBACK_ORDER:
            if name == wanted:
                continue
            found = self._installed(name)
            if found is not None:
                self.cfg.asr_model = name
                self.on_status("loading", f"{wanted} 还没下载，先用本机已有的 {name}")
                return found
        return None

    def ensure_loaded(self, timeout: float = 600.0) -> bool:
        if self.model is not None:
            return True
        with self._lock:
            if self.model is not None:
                return True
            self.loading = True
            self.on_status("loading", "正在加载语音模型…")

            target = self._pick_local_model()
            if target is None:
                self.loading = False
                self.error = "语音模型还没下载"
                self.on_status("missing",
                               "语音模型还没下载：到「模型 → 语音包」下载一个（有进度条）")
                return False

            from faster_whisper import WhisperModel

            dev_cfg = str(getattr(self.cfg, "asr_device", "auto") or "auto").lower()
            comp_cfg = str(getattr(self.cfg, "asr_compute", "auto") or "auto").lower()
            plan: list[tuple[str, str]] = []
            if dev_cfg in ("auto", "cuda"):
                plan.append(("cuda", "float16" if comp_cfg == "auto" else comp_cfg))
            if dev_cfg in ("auto", "cpu") or not plan:
                plan.append(("cpu", "int8" if comp_cfg == "auto" else comp_cfg))

            self.model_dir.mkdir(parents=True, exist_ok=True)
            last_err = ""
            for device, compute in plan:
                if device == "cuda":
                    _setup_cuda_dlls()
                try:
                    self.model = WhisperModel(str(target), device=device,
                                              compute_type=compute,
                                              local_files_only=True)
                    self.device_used, self.compute_used = device, compute
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = f"{device}: {type(exc).__name__}: {exc}"
                    self.model = None
                    continue

            self.loading = False
            if self.model is None:
                self.error = last_err or "未知错误"
                self.on_status("error", f"语音模型加载失败：{self.error}")
                return False
            tag = "GPU" if self.device_used == "cuda" else "CPU"
            self.on_status("ready", f"语音模型就绪（{tag} · {self.cfg.asr_model}）")
            # 第一次推理要初始化 cuDNN 内核（十几秒），先跑一段静音预热掉，
            # 免得用户开口的第一句等太久
            try:
                probe = np.zeros(16000, dtype=np.float32)
                list(self.model.transcribe(probe, language="zh", beam_size=1)[0])
            except Exception:  # noqa: BLE001
                pass
            self.ready = True
            self.on_status("ready", f"语音模型就绪（{tag} · {self.cfg.asr_model}）")
            return True

    # ------------------------------------------------------------------
    def _prompt_for(self, language: str | None) -> str | None:
        if language:
            return PROMPTS.get(language)
        return PROMPTS.get(self._last_lang) if self._last_lang else None

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> dict | None:
        if not self.ensure_loaded():
            return None
        allow = {str(x).lower() for x in self.cfg.asr_languages}
        prompt = self._prompt_for(language)
        try:
            # ctranslate2 的 CUDA 模型不能并发推理（会直接把上下文搞崩），这里串行化
            with self._infer_lock:
                segments, info = self.model.transcribe(
                    audio,
                    language=language,
                    initial_prompt=prompt,
                    beam_size=1,
                    vad_filter=False,          # 前面已经有自己的 VAD 切段了，再做一次纯属浪费
                    without_timestamps=True,   # 不要时间戳，解码更快
                    condition_on_previous_text=False,
                    no_speech_threshold=0.55,
                    log_prob_threshold=-1.0,
                    temperature=0.0,
                )
                segs = list(segments)
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"
            return None
        if not segs:
            return None

        lang = (info.language or "").lower()
        text = _clean(" ".join(s.text for s in segs))
        if not text:
            return None
        avg_logprob = sum(s.avg_logprob for s in segs) / len(segs)
        no_speech = max(s.no_speech_prob for s in segs)
        compact = PUNCT_RE.sub(" ", text.lower()).strip()
        if compact in HALLUCINATIONS or any(h in compact for h in HALLUCINATIONS if len(h) > 4):
            return None
        if no_speech > 0.55 and avg_logprob < -0.75:
            return None
        if avg_logprob < -1.1:
            return None
        if len(PUNCT_RE.sub("", text)) < 2:
            return None
        if allow and lang not in allow and info.language_probability > 0.55:
            return None
        # 记住这局队友说哪国话，下次用对应词表打底
        if lang and info.language_probability > 0.6:
            self._last_lang = lang
        return {"text": text, "lang": lang, "prob": float(info.language_probability),
                "no_speech": float(no_speech), "logprob": float(avg_logprob)}
