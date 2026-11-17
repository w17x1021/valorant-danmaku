"""日文 OCR 的离线兜底通道（PaddleOCR 识别模型）。

背景：Windows 自带的 OCR 只有中英文，日文要装 `Language.OCR~~~ja-JP` 语言包；
但很多机器上这个语言包会卡在"安装挂起"（Windows 更新服务下不动）。
这里用 PaddleOCR 的轻量识别模型补上：

* 不做整图检测（太慢，1 秒以上），而是复用 Windows OCR 已经切好的**行框**，
  只对每一行做识别（4 行约 100~250ms）；
* 只有当某一行「Windows 认出来没有假名、但 Paddle 认出了假名」时才替换，
  所以中英文的行完全不受影响。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import Config, project_root
from .win_ocr import OcrLine

KANA = set(range(0x3040, 0x30FF)) | set(range(0x31F0, 0x31FF))
HAN = set(range(0x3400, 0x4DBF)) | set(range(0x4E00, 0x9FFF))


def _kana_count(text: str) -> int:
    return sum(1 for ch in text if ord(ch) in KANA)


def _han_count(text: str) -> int:
    return sum(1 for ch in text if ord(ch) in HAN)


def _prepare_cache_env() -> Path:
    """把 Paddle 的三处缓存都挪进项目目录。

    Paddle 默认往 `~/.cache/paddle`、`~/.paddlex` 写东西，在家目录受限、
    或者 C 盘被清理过的机器上会直接 PermissionError，整个日文兜底就起不来。
    """
    cache = project_root() / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    pdx = cache / "paddlex"          # 已下载的模型在这里，沿用
    pdx.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(pdx))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache / "paddle-cache"))
    os.environ.setdefault("PADDLE_HOME", str(cache / "paddle-cache" / "paddle"))
    os.environ.setdefault("HF_HOME", str(cache / "paddle-cache" / "hf"))
    os.environ.setdefault("FLAGS_call_stack_level", "0")
    return pdx


def _purge_modules() -> None:
    """导入失败后清掉半初始化的模块，否则下次 import 会拿到残缺的 paddle。"""
    for name in [m for m in list(sys.modules)
                 if m == "paddle" or m.startswith(("paddle.", "paddlex"))]:
        sys.modules.pop(name, None)


class PaddleJa:
    """懒加载，只有真的需要时才吃这几百 MB 内存。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.model = None
        self.loading = False
        self.error = ""
        self.enabled = False
        self._lock = threading.Lock()
        self._failed_at = 0.0
        self._attempts = 0

    # ------------------------------------------------------------------
    def ensure(self) -> bool:
        if self.model is not None:
            return True
        with self._lock:
            if self.model is not None:
                return True
            # 加载失败后不要每帧都重试：paddle 导入本身就要几秒，会把 OCR 拖死
            if self._failed_at and time.time() - self._failed_at < 120:
                return False
            if self._attempts >= 3:
                return False
            self.loading = True
            self._attempts += 1
            try:
                _prepare_cache_env()
                from paddlex import create_model  # 很重，放这里懒加载
                self.model = create_model("PP-OCRv5_mobile_rec")
                self.enabled = True
                self.error = ""
            except Exception as exc:  # noqa: BLE001
                self.error = f"{type(exc).__name__}: {exc}"
                self.enabled = False
                self._failed_at = time.time()
                _purge_modules()
            finally:
                self.loading = False
        return self.model is not None

    # ------------------------------------------------------------------
    def refine(self, image: Image.Image, lines: list[OcrLine]) -> list[OcrLine]:
        """把 Windows OCR 的行结果换成更靠谱的日文识别（仅当日文时）。"""
        if not lines or not self.ensure():
            return lines
        crops, idx = [], []
        for i, ln in enumerate(lines):
            if ln.w < 8 or ln.h < 6:
                continue
            if _kana_count(ln.text) >= 2:
                continue                  # Windows 已经认出假名，不用再跑 Paddle
            if not _kana_count(ln.text) and not _han_count(ln.text):
                continue                  # 纯英文/数字的行不可能是日文
            pad_x = max(6, int(ln.h * 0.7))
            pad_y = max(2, int(ln.h * 0.18))
            box = (max(0, ln.x - pad_x), max(0, ln.y - pad_y),
                   min(image.width, ln.x + ln.w + pad_x), min(image.height, ln.y + ln.h + pad_y))
            if box[2] - box[0] < 6 or box[3] - box[1] < 6:
                continue
            crop = image.crop(box)
            if crop.height < 40:
                scale = 40 / crop.height
                crop = crop.resize((max(8, int(crop.width * scale)), 40), Image.LANCZOS)
            crops.append(np.array(crop.convert("RGB"))[:, :, ::-1])  # RGB -> BGR
            idx.append(i)
        if not crops:
            return lines
        try:
            results = list(self.model.predict(crops))
        except Exception as exc:  # noqa: BLE001
            self.error = f"识别失败: {exc}"
            return lines

        out = list(lines)
        for pos, res in zip(idx, results):
            text = (res.get("rec_text") or "").strip()
            score = float(res.get("rec_score") or 0.0)
            if not text or score < 0.55:
                continue
            old = out[pos].text
            if _kana_count(old) >= 2:        # Windows 已经认出日文了，不用换
                continue
            if _kana_count(text) >= 2:       # Paddle 认出假名 → 这行是日文
                out[pos] = OcrLine("ja", text, out[pos].x, out[pos].y,
                                   out[pos].w, out[pos].h)
            elif score >= 0.9 and _ascii_ratio(old) < 0.6 and _ascii_ratio(text) < 0.6:
                # 中英混排但两边都不是 ASCII 主导，取置信度更高的（中文行更准）
                if len(text) > len(old) * 0.6:
                    out[pos] = OcrLine("zh", text, out[pos].x, out[pos].y,
                                       out[pos].w, out[pos].h)
        return out


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = sum(1 for c in text if c.isascii() and c.isalnum())
    return letters / max(1, len(text))
