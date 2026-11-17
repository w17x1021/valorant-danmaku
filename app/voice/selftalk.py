"""「我说的话」：麦克风 -> 中文识别 -> 日文 / 英文译文。

和「队友语音」的区别：
* 采集的是麦克风（不是系统环回）；
* 识别出来的是中文，再反向翻成日文和英文，方便复制粘贴到游戏聊天框。
"""
from __future__ import annotations

import queue
import threading
import time

from ..config import Config
from .mic import MicCapture
from .vad import Segmenter


class SelfTalk:
    def __init__(self, cfg: Config, translator, on_result=None, on_status=None,
                 asr=None):
        self.cfg = cfg
        self.translator = translator
        self.on_result = on_result or (lambda *_: None)
        self.on_status = on_status or (lambda *_: None)
        self.asr = asr
        self.stop = threading.Event()
        self._raw: queue.Queue = queue.Queue(maxsize=200)
        self._segs: queue.Queue = queue.Queue(maxsize=16)
        self.capture: MicCapture | None = None
        self.segmenter = Segmenter(
            threshold=max(0.008, float(cfg.vad_threshold) * 0.9),
            silence_ms=cfg.vad_silence_ms,
            min_ms=max(350, cfg.vad_min_ms - 100),
            max_s=min(12.0, cfg.vad_max_s),
        )
        self.status = "idle"
        self.note = ""
        self.last: dict = {}
        self.count = 0
        self._paused = threading.Event()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.capture is not None:
            return
        self.status = "starting"
        self.capture = MicCapture(self.cfg, self._raw, self.stop)
        self.capture.start()
        threading.Thread(target=self._segment_loop, daemon=True, name="self-vad").start()
        threading.Thread(target=self._work_loop, daemon=True, name="self-asr").start()
        self.on_status("running", "麦克风已启动")

    def stop_all(self) -> None:
        self.stop.set()
        self.capture = None
        self.status = "idle"

    def pause(self, flag: bool) -> None:
        self._paused.set() if flag else self._paused.clear()

    # ------------------------------------------------------------------
    def _segment_loop(self) -> None:
        while not self.stop.is_set():
            try:
                chunk = self._raw.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._paused.is_set():
                continue
            for utt in self.segmenter.push(chunk):
                try:
                    self._segs.put_nowait(utt)
                except queue.Full:
                    pass

    def _work_loop(self) -> None:
        while not self.stop.is_set():
            try:
                audio = self._segs.get(timeout=0.3)
            except queue.Empty:
                continue
            if self.asr is None or not getattr(self.asr, "ready", False):
                continue
            lang = str(getattr(self.cfg, "selftalk_language", "zh") or "").lower()
            res = self.asr.transcribe(audio, language=None if lang in ("", "auto") else lang)
            if not res:
                continue
            text = (res.get("text") or "").strip()
            if len(text) < 2:
                continue
            src = res.get("lang") or "zh"
            if src not in ("zh", "en", "ja"):
                src = "zh"
            ja = en = ""
            if src != "ja":
                r = self.translator.translate_to(text, src, "ja")
                ja = r.text if r else ""
            if src != "en":
                r = self.translator.translate_to(text, src, "en")
                en = r.text if r else ""
            self.count += 1
            self.last = {"zh": text, "ja": ja, "en": en, "src": src, "ts": time.time()}
            self.on_result(dict(self.last))

    # ------------------------------------------------------------------
    @property
    def level(self) -> float:
        return self.capture.level if self.capture else 0.0
