"""语音链路端到端自测：播放 TTS 音频 -> 环回采集 -> VAD -> Whisper -> 聊天事件。"""
import queue
import sys
import threading
import time
import winsound
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config
from app.voice.listener import VoiceListener

WAV = ROOT / "tools" / "_tts.wav"


def main() -> None:
    cfg = Config()
    cfg.voice_enabled = True
    q: queue.Queue = queue.Queue()
    v = VoiceListener(cfg, q, lambda k, m: print(f"[status {k}] {m}", flush=True))
    v.start()
    print("waiting model…", flush=True)
    for _ in range(120):
        if getattr(v.asr, "ready", False):
            break
        time.sleep(0.5)
    print("model ready:", v.asr.model is not None, flush=True)
    time.sleep(0.6)

    def play():
        winsound.PlaySound(str(WAV), winsound.SND_FILENAME)

    threading.Thread(target=play, daemon=True).start()
    t0 = time.time()
    got = []
    while time.time() - t0 < 8:
        try:
            ev = q.get(timeout=0.5)
        except queue.Empty:
            continue
        got.append(ev)
        print(f"  +{time.time()-t0:4.1f}s [{ev.lang}] {ev.text!r}", flush=True)
    print("utterances:", v.utterances, "events:", len(got))
    print("device:", v.capture.device, "| level:", round(v.level, 4))
    v.stop_all()
    time.sleep(0.5)


if __name__ == "__main__":
    main()
