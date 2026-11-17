"""麦克风采集（我用来说话的那一路），和环回采集分开。"""
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


def list_microphones() -> list[str]:
    try:
        return [str(m.name) for m in sc.all_microphones(include_loopback=False)]
    except Exception:  # noqa: BLE001
        return []


def _resolve_mic(name: str | None):
    if name:
        try:
            return sc.get_microphone(id=str(name), include_loopback=False)
        except Exception:  # noqa: BLE001
            pass
    return sc.default_microphone()


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


class MicCapture(threading.Thread):
    def __init__(self, cfg, out: queue.Queue, stop: threading.Event):
        super().__init__(daemon=True, name="mic-capture")
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
                mic = _resolve_mic(getattr(self.cfg, "mic_device", None))
                self.device = str(mic.name)
                rate = 48000
                with mic.recorder(samplerate=rate, channels=1) as rec:
                    self.status = "running"
                    while not self.stop.is_set():
                        data = rec.record(numframes=int(rate * BLOCK_SECONDS))
                        mono = np.asarray(data, dtype=np.float32).reshape(-1)
                        self.level = float(np.sqrt(np.mean(mono ** 2))) if mono.size else 0.0
                        if self._paused.is_set():
                            continue
                        self.out.put(_decimate(mono, rate, TARGET_RATE))
            except Exception as exc:  # noqa: BLE001
                self.status = "error"
                self.error = f"{type(exc).__name__}: {exc}"
                time.sleep(2.0)
