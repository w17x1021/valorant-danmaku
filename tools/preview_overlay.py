"""弹幕浮层视觉自测：弹出浮层 -> 打几条样例 -> 截图保存。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tkinter as tk

from app.config import Config
from app.main import enable_dpi_awareness
from app.ui.overlay import DanmakuOverlay

enable_dpi_awareness()
cfg = Config.load()
cfg.danmaku_band = "custom"
cfg.danmaku_region = [0, 40, 1600, 300]
cfg.danmaku_lanes = 5

root = tk.Tk()
root.withdraw()
ov = DanmakuOverlay(root, cfg)

SAMPLES = [
    ("[EN] Kirito: 推进 B 点，中路两个敌人", cfg.color_en),
    ("[JA] 夜桜: 等等，这边有敌人", cfg.color_ja),
    ("[EN] SovaMain: 好枪，兄弟", cfg.color_voice),
    ("[中] 小明: 中路有人，小心", cfg.color_zh),
    ("[JA] ありがとう: 谢了", cfg.color_ja),
]
for i, (text, color) in enumerate(SAMPLES):
    root.after(150 + i * 220, lambda t=text, c=color: ov.push(t, c))


def shoot():
    from PIL import ImageGrab
    x, y, w, h = cfg.danmaku_region
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    out = ROOT / "tools" / "_overlay.png"
    img.save(out)
    print("saved", out, img.size)
    root.after(100, root.destroy)


root.after(2600, shoot)
root.mainloop()
