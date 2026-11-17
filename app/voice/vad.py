"""能量 VAD：把连续的音频切成"一句一句"的片段。

游戏里枪声、脚步、UI 音效也是声音，所以噪声底会自动估计，
只有明显高于底噪、并且持续足够久的声音才会被当成一句话。
"""
from __future__ import annotations

import numpy as np

SR = 16000
FRAME = 480          # 30ms


class Segmenter:
    def __init__(self, threshold: float = 0.010, silence_ms: int = 650,
                 min_ms: int = 450, max_s: float = 14.0, preroll_ms: int = 240):
        self.base_threshold = float(threshold)
        self.silence_frames = max(1, int(silence_ms / 30))
        self.min_frames = max(1, int(min_ms / 30))
        self.max_frames = max(self.min_frames + 1, int(max_s * 1000 / 30))
        self.preroll_frames = max(0, int(preroll_ms / 30))
        self.noise = 0.0035
        self._buf = np.zeros(0, dtype=np.float32)
        self._pre: list[np.ndarray] = []
        self._frames: list[np.ndarray] = []
        self._speaking = False
        self._silent = 0

    # ------------------------------------------------------------------
    @property
    def threshold(self) -> float:
        return max(self.base_threshold, self.noise * 3.2)

    def push(self, samples: np.ndarray) -> list[np.ndarray]:
        self._buf = np.concatenate([self._buf, samples.astype(np.float32)]) if self._buf.size else samples.astype(np.float32)
        done: list[np.ndarray] = []
        while self._buf.size >= FRAME:
            frame, self._buf = self._buf[:FRAME], self._buf[FRAME:]
            chunk = self._frame_step(frame)
            if chunk is not None:
                done.append(chunk)
        return done

    def _frame_step(self, frame: np.ndarray) -> np.ndarray | None:
        rms = float(np.sqrt(np.mean(frame ** 2)))
        thr = self.threshold
        if not self._speaking:
            self.noise = 0.98 * self.noise + 0.02 * min(rms, 0.05)
            self._pre.append(frame)
            if len(self._pre) > self.preroll_frames + 2:
                self._pre.pop(0)
        if rms > thr:
            if not self._speaking:
                self._speaking = True
                self._frames = list(self._pre)
                self._pre.clear()
            self._silent = 0
            if self._speaking:
                self._frames.append(frame)
        else:
            if self._speaking:
                self._frames.append(frame)
                self._silent += 1
                if self._silent >= self.silence_frames:
                    return self._flush()

        if self._speaking and len(self._frames) >= self.max_frames:
            return self._flush()
        return None

    def _flush(self) -> np.ndarray | None:
        frames, self._frames = self._frames, []
        self._speaking = False
        self._silent = 0
        self._pre = []
        if len(frames) < self.min_frames:
            return None
        audio = np.concatenate(frames).astype(np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak > 0:
            audio = audio / max(1.0, peak / 0.95)
        return audio

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        self._pre = []
        self._frames = []
        self._speaking = False
        self._silent = 0
