"""日文文字识别端到端：假聊天窗口写日文/英文/中文，跑真实程序，截图看弹幕。"""
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

WIN = (140, 480, 780, 230)
LINES = [
    ("夜桜", "ちょっと待って、Bサイトに敵が二人いる", "#ffb4dc"),
    ("Kirito", "push b site, two enemies mid", "#96c8ff"),
    ("ゆき", "今すぐ回って！", "#ffb4dc"),
]


def window():
    root = tk.Tk()
    root.overrideredirect(True)
    x, y, w, h = WIN
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.attributes("-topmost", True)
    c = tk.Canvas(root, bg="#15181f", highlightthickness=0)
    c.pack(fill="both", expand=True)
    f = ("Microsoft YaHei UI", 15)
    yy = 14
    for who, msg, color in LINES:
        c.create_text(12, yy, text=f"{who}: ", anchor="nw", fill=color, font=f)
        c.create_text(12 + 12 * len(who) + 20, yy, text=msg, anchor="nw", fill="#ececec", font=f)
        yy += 42
    root.after(40000, root.destroy)
    root.mainloop()


def main() -> None:
    threading.Thread(target=window, daemon=True).start()
    time.sleep(1.0)

    cfg_path = ROOT / "config.json"
    backup = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None
    cfg_path.write_text(json.dumps({
        "ocr_enabled": True,
        "chat_region": list(WIN),
        "ocr_interval_ms": 260,
        "voice_enabled": False,
        "display_mode": "box",
        "danmaku_font_size": 22,
        "box_max_lines": 4,
        "box_ttl_s": 30.0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen([sys.executable, "-u", "-m", "app.main"], cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(16)

    full = ImageGrab.grab(all_screens=True)
    full.crop((0, full.height - 700, full.width, full.height)).save(ROOT / "tools" / "_ja_e2e.png")

    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out = b""
    (ROOT / "tools" / "_ja_e2e_log.txt").write_text(out.decode("utf-8", "replace")[-2500:],
                                                    encoding="utf-8")
    log = ROOT / "logs" / "chat.jsonl"
    if log.exists():
        (ROOT / "tools" / "_ja_e2e_chat.jsonl").write_text(log.read_text(encoding="utf-8"),
                                                           encoding="utf-8")
        log.unlink()
    if backup is None:
        cfg_path.unlink(missing_ok=True)
    else:
        cfg_path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    main()
