"""采集"电脑正在播放的声音"（WASAPI 环回），也就是队友语音。

队友语音从扬声器/耳机出来，我们录的是同一路混音，所以游戏音效也会一起进来；
后面靠 VAD + Whisper 的 no_speech 概率把它们过滤掉。
"""
from __future__ import annotations

import queue
import threading
import time
import warnings

import numpy as np
import soundcard as sc

warnings.filterwarnings("ignore", module="soundcard")

TARGET_RATE = 16000
BLOCK_SECONDS = 0.1


def list_loopback_devices() -> list[str]:
    names = []
    for mic in sc.all_microphones(include_loopback=True):
        name = str(mic.name)
        if name not in names:
            names.append(name)
    return names


def _resolve_device(device_name: str | None):
    if device_name:
        try:
            return sc.get_microphone(id=str(device_name), include_loopback=True)
        except Exception:  # noqa: BLE001
            pass
    return sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)


def _decimate(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return x.astype(np.float32, copy=False)
    factor = max(1, int(round(src / dst)))
    if factor == 1:
        return x.astype(np.float32, copy=False)
    pad = (-len(x)) % factor
    if pad:
        x = np.concatenate([x, np.zeros(pad, dtype=np.float32)])
    return x.reshape(-1, factor).mean(axis=1).astype(np.float32)


class LoopbackCapture(threading.Thread):
    """把环回音频切成 0.1 秒的小块，统一重采样到 16k 单声道后丢进队列。"""

    def __init__(self, cfg, out: queue.Queue, stop: threading.Event):
        super().__init__(daemon=True, name="voice-capture")
        self.cfg = cfg
        self.out = out
        self.stop = stop
        self.status = "starting"
        self.error = ""
        self.level = 0.0
        self.device = ""
        self._paused = threading.Event()

    def pause(self, flag: bool) -> None:
        self._paused.set() if flag else self._paused.clear()

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                mic = _resolve_device(getattr(self.cfg, "voice_device", None))
                self.device = str(mic.name)
                self.status = "running"
                rate = 48000
                with mic.recorder(samplerate=rate, channels=1) as rec:
                    self.status = "running"
                    while not self.stop.is_set():
                        if self._paused.is_set():
                            time.sleep(0.1)
                            rec.record(numframes=int(rate * 0.1))
                            continue
                        data = rec.record(numframes=int(rate * BLOCK_SECONDS))
                        mono = np.asarray(data, dtype=np.float32).reshape(-1)
                        self.level = float(np.sqrt(np.mean(mono ** 2))) if mono.size else 0.0
                        self.out.put(_decimate(mono, rate, TARGET_RATE))
            except Exception as exc:  # noqa: BLE001
                self.status = "error"
                self.error = f"{type(exc).__name__}: {exc}"
                time.sleep(2.0)
