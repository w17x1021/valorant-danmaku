"""语音模式端到端：启动真实程序，播放 TTS 英文语音，看弹幕框里是否出现译文。"""
import json
import os
import subprocess
import sys
import time
import winsound
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

WAV = ROOT / "tools" / "_tts.wav"


def main() -> None:
    cfg_path = ROOT / "config.json"
    backup = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None
    cfg = {
        "ocr_enabled": False,
        "chat_region": [40, 620, 520, 260],
        "voice_enabled": True,
        "display_mode": "box",
        "danmaku_font_size": 22,
        "box_max_lines": 3,
        "log_enabled": True,
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    proc = subprocess.Popen([sys.executable, "-u", "-m", "app.main"], cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    time.sleep(9)            # 等模型加载 + 采集稳定
    winsound.PlaySound(str(WAV), winsound.SND_FILENAME)
    time.sleep(7)            # 等 VAD 切句 + 识别 + 翻译 + 上屏

    full = ImageGrab.grab(all_screens=True)
    full.crop((0, full.height - 620, full.width, full.height)).save(ROOT / "tools" / "_voice.png")

    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out = b""
    (ROOT / "tools" / "_voice_log.txt").write_text(
        out.decode("utf-8", "replace")[-3000:], encoding="utf-8")
    log = ROOT / "logs" / "chat.jsonl"
    if log.exists():
        (ROOT / "tools" / "_voice_chat.jsonl").write_text(log.read_text(encoding="utf-8"),
                                                          encoding="utf-8")
        log.unlink()
    if backup is None:
        cfg_path.unlink(missing_ok=True)
    else:
        cfg_path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    main()
