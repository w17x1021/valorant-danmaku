"""文字 + 语音同时验证：假聊天窗口 + TTS 语音，最后截一张完整的字幕框。"""
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import winsound
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

CHAT_WIN = (120, 520, 760, 210)
LINES = [
    ("Kirito", "push b site, two enemies mid", "#96c8ff"),
    ("小明", "中路有人，小心", "#ffdc8c"),
]


def chat_window():
    root = tk.Tk()
    root.overrideredirect(True)
    x, y, w, h = CHAT_WIN
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.attributes("-topmost", True)
    c = tk.Canvas(root, bg="#15181f", highlightthickness=0)
    c.pack(fill="both", expand=True)
    f = ("Microsoft YaHei UI", 15)
    yy = 12
    for name, msg, color in LINES:
        c.create_text(12, yy, text=f"{name}: ", anchor="nw", fill=color, font=f)
        c.create_text(12 + 9 * len(name) + 16, yy, text=msg, anchor="nw",
                      fill="#ececec", font=f)
        yy += 40
    c.create_text(12, h - 12, text="[TEAM] 模拟聊天窗口", anchor="sw",
                  fill="#556070", font=("Microsoft YaHei UI", 9))
    root.after(30000, root.destroy)
    root.mainloop()


def main() -> None:
    threading.Thread(target=chat_window, daemon=True).start()
    time.sleep(1.0)

    cfg_path = ROOT / "config.json"
    backup = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None
    cfg_path.write_text(json.dumps({
        "ocr_enabled": True,
        "chat_region": [CHAT_WIN[0], CHAT_WIN[1], CHAT_WIN[2], CHAT_WIN[3]],
        "ocr_interval_ms": 240,
        "voice_enabled": True,
        "display_mode": "box",
        "danmaku_font_size": 22,
        "box_max_lines": 4,
        "box_ttl_s": 40.0,
        "log_enabled": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["HF_ENDPOINT"] = "https://hf-mirror.com"
    proc = subprocess.Popen([sys.executable, "-u", "-m", "app.main"], cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(10)
    winsound.PlaySound(str(ROOT / "tools" / "_tts.wav"), winsound.SND_FILENAME)
    time.sleep(7)

    full = ImageGrab.grab(all_screens=True)
    full.crop((0, full.height - 700, full.width, full.height)).save(ROOT / "tools" / "_both.png")

    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill(); out = b""
    (ROOT / "tools" / "_both_log.txt").write_text(out.decode("utf-8", "replace")[-2000:],
                                                  encoding="utf-8")
    log = ROOT / "logs" / "chat.jsonl"
    if log.exists():
        (ROOT / "tools" / "_both_chat.jsonl").write_text(log.read_text(encoding="utf-8"),
                                                         encoding="utf-8")
        log.unlink()
    if backup is None:
        cfg_path.unlink(missing_ok=True)
    else:
        cfg_path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    main()
