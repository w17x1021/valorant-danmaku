"""语音监听：环回采集 -> VAD 切句 -> Whisper 识别 -> 产出聊天事件。"""
from __future__ import annotations

import queue
import threading
import time

from ..config import Config
from ..ocr.chat_reader import ChatEvent
from .asr import Asr
from .capture import LoopbackCapture
from .filters import is_agent_voice_line
from .vad import Segmenter


class VoiceListener:
    def __init__(self, cfg: Config, out_q: queue.Queue, on_status=None, asr=None):
        self.cfg = cfg
        self.out = out_q
        self.on_status = on_status or (lambda *_: None)
        self.stop = threading.Event()
        self.segments: queue.Queue = queue.Queue(maxsize=24)
        self.asr = asr or Asr(cfg, on_status=self._asr_status)
        self._raw: queue.Queue = queue.Queue(maxsize=200)
        self.capture = LoopbackCapture(cfg, self._raw, self.stop)
        self.segmenter = Segmenter(
            threshold=cfg.vad_threshold,
            silence_ms=cfg.vad_silence_ms,
            min_ms=cfg.vad_min_ms,
            max_s=cfg.vad_max_s,
        )
        self.status = "starting"
        self.note = ""
        self.utterances = 0
        self._paused = threading.Event()
        self._chat_rms = 0.0
        self.filtered = 0
        self.active = threading.Event()
        self.active.set()

    # ------------------------------------------------------------------
    def _asr_status(self, kind: str, msg: str) -> None:
        self.note = msg
        self.status = "ready" if kind == "ready" else ("error" if kind == "error" else "loading")
        self.on_status(kind, msg)

    def start(self) -> None:
        self.capture.start()
        threading.Thread(target=self._segment_loop, daemon=True, name="vad").start()
        threading.Thread(target=self._asr_loop, daemon=True, name="asr").start()
        threading.Thread(target=self._preload, daemon=True, name="asr-preload").start()

    def _preload(self) -> None:
        self.asr.ensure_loaded()

    def pause(self, flag: bool) -> None:
        self._paused.set() if flag else self._paused.clear()
        self.capture.pause(flag)

    def set_active(self, flag: bool) -> None:
        """开/关语音识别：只暂停，不销毁线程和模型，再打开时秒恢复。"""
        if flag:
            self.active.set()
            self._paused.clear()
            self.capture.pause(False)
            self.status = "running"
        else:
            self.active.clear()
            self.capture.pause(True)
            self.status = "idle"

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
                self.utterances += 1
                try:
                    self.segments.put_nowait(utt)
                except queue.Full:
                    pass

    def _asr_loop(self) -> None:
        while not self.stop.is_set():
            try:
                audio = self.segments.get(timeout=0.3)
            except queue.Empty:
                continue
            if self._paused.is_set():
                continue
            if not getattr(self.asr, "ready", False):
                continue          # 模型还在预热（首次约 30 秒），这句先丢掉
            t0 = time.time()
            res = self.asr.transcribe(audio)
            if not res:
                continue
            text = res["text"]
            if len(text) < 2:
                continue
            # 英雄台词（"Watch this!" 之类）不算队友说话，丢掉
            if is_agent_voice_line(text, audio, self._chat_rms, self.cfg):
                self.filtered += 1
                continue
            self._update_rms(audio)
            ev = ChatEvent("voice", "", text, res["lang"])
            ev.elapsed = time.time() - t0  # type: ignore[attr-defined]
            self.out.put(ev)

    # ------------------------------------------------------------------
    def stop_all(self) -> None:
        self.stop.set()

    def shutdown(self, timeout: float = 2.5) -> None:
        """真正退出：停采集 + 等采集线程放开设备，避免再开时抢不到设备。"""
        self.stop.set()
        self.active.clear()
        try:
            self.capture.join(timeout=timeout)
        except RuntimeError:
            pass

    @property
    def level(self) -> float:
        return self.capture.level
