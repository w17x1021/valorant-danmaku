"""「我说的话」链路自测：中文语音 -> 识别 -> 日文/英文译文。"""
import queue
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config
from app.translator import Translator
from app.voice.asr import Asr
from app.voice.selftalk import SelfTalk


def read_wav(path: Path, target: int = 16000) -> np.ndarray:
    with wave.open(str(path), "rb") as fh:
        n, ch, rate = fh.getnframes(), fh.getnchannels(), fh.getframerate()
        raw = fh.readframes(n)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != target:
        factor = rate / target
        idx = np.arange(0, len(data) - 1, factor).astype(np.int64)
        data = data[idx]
    return data.astype(np.float32)


def main() -> None:
    cfg = Config()
    results = []
    q: queue.Queue = queue.Queue()

    def on_result(res):
        results.append(res)
        q.put(res)

    asr = Asr(cfg)
    tr = Translator(cfg)
    st = SelfTalk(cfg, tr, on_result=on_result, asr=asr)

    threading.Thread(target=st._segment_loop, daemon=True).start()
    threading.Thread(target=st._work_loop, daemon=True).start()

    audio = read_wav(ROOT / "tools" / "_zh.wav")
    print(f"audio {len(audio)/16000:.1f}s", flush=True)
    # 模拟麦克风：0.1 秒一块推进去
    for i in range(0, len(audio), 1600):
        st._raw.put(audio[i:i + 1600])
        time.sleep(0.01)
    st._raw.put(np.zeros(16000, dtype=np.float32))   # 尾部静音，触发切句

    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            res = q.get(timeout=1.0)
        except queue.Empty:
            if results:
                break
            continue
        print("ZH:", res["zh"], flush=True)
        print("JA:", res["ja"], flush=True)
        print("EN:", res["en"], flush=True)
        break
    tr.flush_cache()
    if not results:
        print("!! 没有识别结果")


if __name__ == "__main__":
    main()
