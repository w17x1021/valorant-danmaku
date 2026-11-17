"""端到端延迟测量：VAD 切段 → ASR → 翻译 → 出字幕，打印每段耗时。"""
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config
from app.translator import Translator


def read_wav(path: Path, target: int = 16000) -> np.ndarray:
    with wave.open(str(path), "rb") as fh:
        n, ch, rate = fh.getnframes(), fh.getnchannels(), fh.getframerate()
        raw = fh.readframes(n)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != target:
        data = data[np.arange(0, len(data) - 1, rate / target).astype(np.int64)]
    return data


def main() -> None:
    cfg = Config.load()
    print("model:", cfg.asr_model, "| silence:", cfg.vad_silence_ms, flush=True)
    from app.voice.asr import Asr

    asr = Asr(cfg, on_status=lambda k, m: None)
    t0 = time.time()
    asr.ensure_loaded()
    print(f"load: {time.time()-t0:.1f}s  device={asr.device_used}/{asr.compute_used}", flush=True)

    audio = read_wav(ROOT / "tools" / "_bench.wav")
    tr = Translator(cfg)
    for i in range(3):
        t0 = time.time()
        res = asr.transcribe(audio, language="en")
        t_asr = (time.time() - t0) * 1000
        t0 = time.time()
        out = tr.translate(res["text"], res["lang"]) if res else None
        t_tr = (time.time() - t0) * 1000
        print(f"#{i+1} asr={t_asr:.0f}ms trans={t_tr:.0f}ms total={t_asr+t_tr:.0f}ms "
              f"| {res['text'][:60] if res else None} -> {out.text if out else None}", flush=True)


if __name__ == "__main__":
    main()
