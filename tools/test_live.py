"""实时抓屏诊断：开模拟聊天窗口，连续抓取 + OCR，打印每一帧的结果。"""
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.ocr import chat_reader as cr

WIN = (120, 520, 760, 230)
LINES = [
    ("Kirito", "push b site, two enemies mid", "#96c8ff"),
    ("夜桜", "ちょっと待って、こっちに敵がいる", "#ffb4dc"),
    ("小明", "中路有人，小心", "#ffdc8c"),
    ("SovaMain", "nice shot bro", "#96c8ff"),
]


def chat_window():
    root = tk.Tk()
    root.overrideredirect(True)
    x, y, w, h = WIN
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.attributes("-topmost", True)
    c = tk.Canvas(root, bg="#15181f", highlightthickness=0)
    c.pack(fill="both", expand=True)
    state = {"n": 3}

    def draw():
        c.delete("all")
        f = ("Microsoft YaHei UI", 15)
        yy = 10
        for name, msg, color in LINES[: state["n"]]:
            c.create_text(12, yy, text=f"{name}: ", anchor="nw", fill=color, font=f)
            c.create_text(12 + 9 * len(name) + 16, yy, text=msg, anchor="nw",
                          fill="#ececec", font=f)
            yy += 34
        c.create_text(12, h - 12, text="[TEAM] 模拟聊天窗口", anchor="sw",
                      fill="#556070", font=("Microsoft YaHei UI", 9))

    def add():
        if state["n"] < len(LINES):
            state["n"] += 1
            draw()
            root.after(1500, add)

    draw()
    root.after(1500, add)
    root.after(26000, root.destroy)
    root.mainloop()


threading.Thread(target=chat_window, daemon=True).start()
time.sleep(1.5)

ocr = cr.WindowsOcr(ROOT / "app" / "ocr" / "ocr_worker.ps1",
                    ["en-US", "ja", "zh-Hans-CN"])
out = []
last = ""
for i in range(14):
    img = ImageGrab.grab(bbox=(WIN[0], WIN[1], WIN[0] + WIN[2], WIN[1] + WIN[3]),
                         all_screens=True)
    img = img.resize((int(img.width * 1.5), int(img.height * 1.5)))
    t0 = time.time()
    lines = ocr.recognize(img)
    dt = (time.time() - t0) * 1000
    merged = cr.merge_lines(lines)
    parsed = [p for p in (cr.parse_line(m.text) for m in merged) if p]
    out.append(f"--- frame {i} {dt:.0f}ms raw={len(lines)} merged={len(merged)} parsed={parsed} err={ocr.last_error!r}")
    for m in merged:
        out.append(f"    {m.lang:11s} {m.text!r}")
    time.sleep(0.35)
ocr.close()
(ROOT / "tools" / "_live.txt").write_text("\n".join(out), encoding="utf-8")
