"""抓取游戏聊天区域 -> OCR -> 合并成一条条聊天消息。

设计要点：
* 抓屏用 PIL.ImageGrab，只截聊天框那一小块，几乎不占 CPU；
* 画面没变化直接跳过，避免无脑 OCR；
* 同一行会同时被 en/ja/zh 三个引擎识别，按字符构成挑最靠谱的那条；
* 同一条消息会连续出现若干帧，用相似度去重 + 两次确认，避免半截字上屏。
"""
from __future__ import annotations

import hashlib
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageGrab

from ..config import Config, project_root
from ..translator import detect_language
from .win_ocr import OcrLine, WindowsOcr

KANA_RE = re.compile(r"[\u3040-\u30ff]")
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
SPEAKER_RE = re.compile(r"^\s*(?:[\[\(【][^\]\)】]{1,10}[\]\)】]\s*)*"
                        r"([^:：;]{1,24}?)\s*[:：;]\s*(.+)$")
CJK_GAP_RE = re.compile(r"(?<=[\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uff00-\uffef])"
                        r"\s+(?=[\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uff00-\uffef])")

UI_NOISE = {
    "team", "all", "party", "whisper", "system", "队伍", "全部", "小队", "私聊",
    "系统", "回合", "聊天", "玩家", "已屏蔽", "屏蔽",
}


@dataclass
class ChatEvent:
    source: str                 # text / voice
    speaker: str
    text: str
    lang: str
    ts: float = field(default_factory=time.time)


# ----------------------------------------------------------------------
def normalize(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = CJK_GAP_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def payload_key(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text.lower())


def similarity(a: str, b: str) -> float:
    """轻量相似度：先看包含关系，再退回编辑距离比例。"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


def rank_candidate(line: OcrLine) -> float:
    """字符构成打分：假名 > 汉字 > 拉丁字母，并偏向对应语言的引擎。"""
    t = line.text
    kana = len(KANA_RE.findall(t))
    han = len(HAN_RE.findall(t))
    latin = len(LATIN_RE.findall(t))
    total = max(kana + han + latin, 1)
    score = kana * 6.0 + (han / total) * 3.0 + (latin / total) * 1.2
    if line.lang.startswith("ja"):
        score += kana * 1.5
    elif line.lang.startswith("zh"):
        score += (han / total) * 1.0
    else:
        score += (latin / total) * 1.0
    return score


def merge_lines(lines: list[OcrLine], y_tol: int = 12) -> list[OcrLine]:
    """按行位置聚类，每行挑出最可信的识别结果。"""
    groups: list[dict] = []
    for ln in sorted(lines, key=lambda l: (l.y, l.x)):
        for g in groups:
            if abs(g["y"] - ln.y) <= y_tol:
                g["items"].append(ln)
                break
        else:
            groups.append({"y": ln.y, "items": [ln]})
    best: list[OcrLine] = []
    for g in groups:
        ranked = sorted(g["items"], key=rank_candidate, reverse=True)
        winner = ranked[0]
        best.append(OcrLine(winner.lang, normalize(winner.text),
                            winner.x, winner.y, winner.w, winner.h))
    return best


def looks_like_noise(text: str) -> bool:
    """过滤 OCR 出来的纯噪声（反斜杠、温度符号、一串数字混汉字等）。"""
    if re.search(r"[\\|]", text):
        return True
    if "℃" in text or "™" in text:
        return True
    if HAN_RE.search(text):
        chars = [c for c in text if not c.isspace()]
        digits = sum(c.isdigit() for c in chars)
        if chars and digits >= 2 and digits / len(chars) > 0.15:
            return True
    return False


def plausible_chat(speaker: str, text: str) -> bool:
    """没识别出说话人时，只有"像一句话"的才要，避免把桌面图标/HUD 文字当成聊天。"""
    if speaker:
        return True
    words = len(re.findall(r"[A-Za-z]{2,}", text))
    cjk = len(HAN_RE.findall(text)) + len(KANA_RE.findall(text))
    return cjk >= 4 or words >= 3


def parse_line(text: str) -> tuple[str, str] | None:
    """拆出 (说话人, 内容)。"""
    text = normalize(text)
    if not text or looks_like_noise(text):
        return None
    core = re.sub(r"^[\W_]+|[\W_]+$", "", text)
    if len(core) < 2 or core.lower() in UI_NOISE:
        return None
    if not (LATIN_RE.search(core) or HAN_RE.search(core) or KANA_RE.search(core)):
        return None
    m = SPEAKER_RE.match(text)
    if m:
        speaker, body = normalize(m.group(1)), normalize(m.group(2))
        if len(speaker) > 24 or not body:
            return None
        if speaker.lower() in UI_NOISE:
            return None
        return speaker, body
    if not plausible_chat("", text):
        return None
    return "", text


# ----------------------------------------------------------------------
class MessageFilter:
    """持续多帧稳定 + 相似去重。"""

    def __init__(self, min_hits: int = 2, emit_window: float = 90.0):
        self.min_hits = min_hits
        self.emit_window = emit_window
        self._pending: list[dict] = []
        self._emitted: list[tuple[str, float]] = []

    def feed(self, items: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """items: [(speaker, text)] -> 本帧新确认的消息。"""
        now = time.time()
        fresh: list[tuple[str, str]] = []
        for speaker, text in items:
            key = payload_key(text)
            if not key:
                continue
            if any(similarity(key, k) >= 0.86 and now - ts < self.emit_window
                   for k, ts in self._emitted[-40:]):
                continue
            for item in self._pending:
                if similarity(key, item["key"]) >= 0.72:
                    item["hits"] += 1
                    item["ts"] = now
                    item["speaker"] = speaker or item["speaker"]
                    item["text"] = text if len(text) >= len(item["text"]) else item["text"]
                    break
            else:
                self._pending.append({"key": key, "speaker": speaker, "text": text,
                                      "hits": 1, "ts": now})

        for item in list(self._pending):
            if item["hits"] >= self.min_hits:
                self._pending.remove(item)
                self._emitted.append((item["key"], now))
                fresh.append((item["speaker"], item["text"]))

        self._pending = [p for p in self._pending if now - p["ts"] < 8.0]
        self._emitted = [(k, ts) for k, ts in self._emitted if now - ts < self.emit_window]
        return fresh


# ----------------------------------------------------------------------
class ChatReader(threading.Thread):
    def __init__(self, cfg: Config, ocr: WindowsOcr, out: queue.Queue,
                 stop: threading.Event):
        super().__init__(daemon=True, name="chat-reader")
        self.cfg = cfg
        self.ocr = ocr
        self.out = out
        self.stop = stop
        self.msg_filter = MessageFilter()
        self.has_win_ja = any(x.lower().startswith("ja") for x in getattr(ocr, "available", []))
        self.ja_helper = None
        if not self.has_win_ja and str(getattr(cfg, "ja_fallback", "auto")).lower() != "off":
            from .paddle_ja import PaddleJa
            self.ja_helper = PaddleJa(cfg)
            threading.Thread(target=self.ja_helper.ensure, daemon=True,
                             name="paddle-ja").start()
        self._tmp = project_root() / "cache" / "chat_region.png"
        self._tmp.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = ""
        self.stats = {"frames": 0, "ocr": 0, "found": 0, "lines": 0, "error": ""}
        self._paused = threading.Event()
        self._debug_tick = 0

    def _debug(self, msg: str) -> None:
        try:
            path = project_root() / "logs" / "reader.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(time.strftime("%H:%M:%S ") + msg + "\n")
        except OSError:
            pass

    def pause(self, flag: bool) -> None:
        self._paused.set() if flag else self._paused.clear()

    # ------------------------------------------------------------------
    def _grab(self) -> Image.Image | None:
        region = self.cfg.chat_region
        if not region or region[2] < 20 or region[3] < 10:
            return None
        x, y, w, h = region
        try:
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        except OSError as exc:
            self.stats["error"] = f"抓屏失败: {exc}"
            return None
        scale = max(1.0, float(self.cfg.ocr_upscale))
        if scale > 1.01:
            img = img.resize((int(img.width * scale), int(img.height * scale)),
                             Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")
        # 游戏里聊天字通常带描边、字号偏小，放大后提一点对比度+锐化，中文识别明显更稳
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120))
        return img

    def run(self) -> None:
        cached: list[tuple[str, str]] = []
        while not self.stop.is_set():
            if self._paused.is_set() or not self.cfg.chat_region:
                time.sleep(0.2)
                continue
            t0 = time.time()
            try:
                cached = self._tick(cached)
            except Exception as exc:  # noqa: BLE001
                self.stats["error"] = f"识别循环异常: {exc}"
                time.sleep(0.5)
            spent = time.time() - t0
            time.sleep(max(0.02, self.cfg.ocr_interval_ms / 1000.0 - spent))

    def _tick(self, cached: list[tuple[str, str]]) -> list[tuple[str, str]]:
        img = self._grab()
        if img is None:
            time.sleep(0.3)
            return cached
        digest = hashlib.blake2b(img.tobytes(), digest_size=8).hexdigest()
        if digest != self._last_hash:
            self._last_hash = digest
            self.stats["frames"] += 1
            try:
                lines = self.ocr.recognize(img)
                self.stats["ocr"] += 1
                self.stats["lines"] = len(lines)
                merged = merge_lines(lines)
                if self.ja_helper is not None:
                    merged = self.ja_helper.refine(img, merged)
                cached = [p for p in (parse_line(l.text) for l in merged) if p]
            except Exception as exc:  # noqa: BLE001
                self.stats["error"] = f"OCR 异常: {exc}"
                cached = []
        # 即使画面没变也继续喂给过滤器：同一条消息需要连续两帧确认，
        # 否则静止不动的聊天框会永远等不到第二帧。
        fresh = self.msg_filter.feed(cached)
        if self.cfg.log_enabled and (self._debug_tick % 10 == 0 or fresh):
            self._debug(f"tick={self._debug_tick} cached={cached} fresh={fresh}")
        self._debug_tick += 1
        for speaker, text in fresh:
            lang = detect_language(text)
            if lang == "und":
                continue
            self.stats["found"] += 1
            self.out.put(ChatEvent("text", speaker, text, lang))
        return cached
