"""语音链路自测：SAPI 合成一句英文 -> 播到默认扬声器 -> WASAPI 环回录音 -> Whisper 识别。"""
import sys
import threading
import time
import winsound
from pathlib import Path

import numpy as np
import soundcard as sc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WAV = ROOT / "tools" / "_tts.wav"
OUT = ROOT / "tools" / "_rec.wav"


def record(samplerate: int, seconds: float) -> np.ndarray:
    speaker = sc.default_speaker()
    mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    chunks = []
    with mic.recorder(samplerate=samplerate, channels=1) as rec:
        t0 = time.time()
        while time.time() - t0 < seconds:
            chunks.append(rec.record(numframes=int(samplerate * 0.1)))
    data = np.concatenate(chunks, axis=0).reshape(-1).astype(np.float32)
    return data


def downsample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return x
    factor = max(1, round(src / dst))
    if factor > 1:
        pad = (-len(x)) % factor
        if pad:
            x = np.concatenate([x, np.zeros(pad, dtype=np.float32)])
        x = x.reshape(-1, factor).mean(axis=1)
    return x.astype(np.float32)


def main() -> None:
    print("default speaker:", sc.default_speaker().name)
    speaker = sc.default_speaker()
    mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    print("loopback device:", mic)

    for rate in (16000, 48000):
        try:
            t0 = time.time()
            data = record(rate, 0.8)
            print(f"  record at {rate}Hz ok, {len(data)/rate:.2f}s, rms={np.sqrt((data**2).mean()):.4f}, {int((time.time()-t0)*1000)}ms")
        except Exception as exc:  # noqa: BLE001
            print(f"  record at {rate}Hz FAILED: {exc}")

    # 边播边录
    rate = 48000
    threading.Thread(target=lambda: winsound.PlaySound(str(WAV), winsound.SND_FILENAME),
                     daemon=True).start()
    time.sleep(0.05)
    audio = record(rate, 4.5)
    print("recorded", len(audio) / rate, "s rms", float(np.sqrt((audio ** 2).mean())))

    import wave
    with wave.open(str(OUT), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())

    pcm16 = downsample(audio, rate, 16000)
    print("downsampled to", len(pcm16) / 16000, "s")

    from faster_whisper import WhisperModel
    t0 = time.time()
    model = WhisperModel("small", device="cpu", compute_type="int8",
                         download_root=str(ROOT / "models"))
    print(f"model loaded in {time.time()-t0:.1f}s")
    t0 = time.time()
    segments, info = model.transcribe(pcm16, language=None, beam_size=1,
                                      vad_filter=True, condition_on_previous_text=False)
    segs = list(segments)
    print(f"transcribe {time.time()-t0:.2f}s  lang={info.language} p={info.language_probability:.2f}")
    for s in segs:
        print(f"  [{s.start:.1f}-{s.end:.1f}] nsp={s.no_speech_prob:.2f} lp={s.avg_logprob:.2f} {s.text!r}")


if __name__ == "__main__":
    main()
