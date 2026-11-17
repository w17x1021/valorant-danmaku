"""端到端自测：起一个假的“游戏聊天框”窗口，启动真实程序去识别它。

用法: python tools/e2e_test.py
跑完会在 tools/ 下生成 _e2e.png（弹幕区截图）与 _e2e_full.png（全屏截图）。
"""
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

CHAT_WIN = (120, 520, 760, 230)   # x, y, w, h
LINES = [
    ("Kirito", "push b site, two enemies mid", "#96c8ff"),
    ("夜桜", "ちょっと待って、こっちに敵がいる", "#ffb4dc"),
    ("小明", "中路有人，小心", "#ffdc8c"),
    ("SovaMain", "nice shot bro", "#96c8ff"),
]


def make_chat_window(stop_evt: threading.Event):
    root = tk.Tk()
    root.overrideredirect(True)
    x, y, w, h = CHAT_WIN
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.attributes("-topmost", True)
    canvas = tk.Canvas(root, bg="#15181f", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    state = {"n": 0}

    def draw():
        canvas.delete("all")
        font = ("Microsoft YaHei UI", 15)
        yy = 10
        shown = LINES[: state["n"]]
        for name, msg, color in shown[-8:]:
            canvas.create_text(12, yy, text=f"{name}: ", anchor="nw", fill=color, font=font)
            name_w = 8 * len(name) + 14
            canvas.create_text(12 + name_w, yy, text=msg, anchor="nw",
                               fill="#ececec", font=font)
            yy += 34
        canvas.create_text(12, h - 14, text="[TEAM] 模拟聊天窗口", anchor="sw",
                           fill="#556070", font=("Microsoft YaHei UI", 9))

    def tick():
        if state["n"] < len(LINES):
            state["n"] += 1
            draw()
        root.after(1400, tick)

    draw()
    root.after(1400, tick)

    root.after(20000, root.destroy)   # safety net, main thread only
    root.mainloop()


def main() -> None:
    stop_evt = threading.Event()
    t = threading.Thread(target=make_chat_window, args=(stop_evt,), daemon=True)
    t.start()
    time.sleep(1.2)

    cfg_path = ROOT / "config.json"
    backup = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else None
    cfg = {
        "ocr_enabled": True,
        "chat_region": [CHAT_WIN[0], CHAT_WIN[1], CHAT_WIN[2], CHAT_WIN[3]],
        "ocr_interval_ms": 220,
        "ocr_upscale": 1.5,
        "display_mode": "box",
        "danmaku_font_size": 22,
        "danmaku_lanes": 4,
        "voice_enabled": False,
        "log_enabled": True,
    }
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen([sys.executable, "-u", "-m", "app.main"], cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(9.0)
    full = ImageGrab.grab(all_screens=True)
    full.save(ROOT / "tools" / "_e2e_full.png")
    band = ImageGrab.grab(bbox=(0, full.height - 620, full.width, full.height), all_screens=True)
    band.save(ROOT / "tools" / "_e2e.png")

    proc.terminate()
    try:
        out, _ = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out = b""
    (ROOT / "tools" / "_e2e_log.txt").write_text(
        out.decode("utf-8", "replace")[-4000:], encoding="utf-8")
    log = ROOT / "logs" / "chat.jsonl"
    if log.exists():
        (ROOT / "tools" / "_e2e_chat.jsonl").write_text(log.read_text(encoding="utf-8"),
                                                        encoding="utf-8")
        log.unlink()

    stop_evt.set()
    time.sleep(1.0)
    if backup is None:
        cfg_path.unlink(missing_ok=True)
    else:
        cfg_path.write_text(backup, encoding="utf-8")


if __name__ == "__main__":
    main()
