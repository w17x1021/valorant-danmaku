"""对比 small / large-v3-turbo 在 5070 Ti 上的速度和准确率。"""
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / ".venv" / "Lib" / "site-packages"
for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_nvrtc/bin"):
    p = SITE / sub
    if p.exists():
        os.add_dll_directory(str(p))
        os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")


def read_wav(path: Path, target: int = 16000) -> np.ndarray:
    with wave.open(str(path), "rb") as fh:
        n, ch, rate = fh.getnframes(), fh.getnchannels(), fh.getframerate()
        raw = fh.readframes(n)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != target:
        idx = np.arange(0, len(data) - 1, rate / target).astype(np.int64)
        data = data[idx]
    return data


PROMPT_EN = ("VALORANT voice chat: push A site, B site, mid, rotate, flank, plant the spike, "
             "defuse, eco round, one HP, nice shot, hold the angle, fall back.")


def bench(tag: str, model_name: str, audio: np.ndarray) -> None:
    from faster_whisper import WhisperModel
    try:
        t0 = time.time()
        m = WhisperModel(model_name, device="cuda", compute_type="float16",
                         download_root=str(ROOT / "models"))
        load = time.time() - t0
        t0 = time.time()
        list(m.transcribe(audio[:16000], language="en", beam_size=1)[0])
        warm = time.time() - t0
        times = []
        text = ""
        for _ in range(3):
            t0 = time.time()
            segs, info = m.transcribe(audio, language="en", beam_size=1,
                                      initial_prompt=PROMPT_EN,
                                      condition_on_previous_text=False,
                                      without_timestamps=True)
            text = "".join(s.text for s in segs)
            times.append((time.time() - t0) * 1000)
        print(f"[{tag}] load={load:.1f}s warm={warm*1000:.0f}ms "
              f"avg={sum(times)/len(times):.0f}ms  {text!r}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[{tag}] FAILED {type(exc).__name__}: {str(exc)[:160]}", flush=True)


if __name__ == "__main__":
    wav = ROOT / "tools" / "_bench.wav"
    if not wav.exists():
        print("need tools/_bench.wav")
        sys.exit(1)
    audio = read_wav(wav)
    print(f"audio {len(audio)/16000:.1f}s", flush=True)
    bench("small", "small", audio)
    bench("turbo", "large-v3-turbo", audio)
