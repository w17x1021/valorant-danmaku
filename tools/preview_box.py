"""圆角字幕框视觉自测：推送几条 -> 截图。"""
import sys
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.config import Config
from app.main import enable_dpi_awareness
from app.ui.subs import LayeredSubtitleBox

enable_dpi_awareness()
import ctypes
u32 = ctypes.windll.user32
sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)

cfg = Config()
cfg.display_mode = "box"
cfg.danmaku_font_size = 22
cfg.box_width_ratio = 0.34
cfg.box_bottom_margin = 210
cfg.box_max_lines = 3

root = tk.Tk()
root.withdraw()
box = LayeredSubtitleBox(root, cfg)

SAMPLES = [
    ("Kirito: 推进 B 点，中路有两个敌人", cfg.color_en),
    ("夜桜: 等一下，这边有敌人", cfg.color_ja),
    ("SovaMain: 好枪，兄弟", cfg.color_voice),
]
for i, (text, color) in enumerate(SAMPLES):
    root.after(250 + i * 500, lambda t=text, c=color: box.push(t, c))


def shoot():
    w = int(sw * cfg.box_width_ratio) + 120
    h = 260
    x = (sw - w) // 2
    y = sh - cfg.box_bottom_margin - h + 40
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(
        ROOT / "docs" / "字幕框效果.png")
    print("saved")
    root.after(100, root.destroy)


root.after(2600, shoot)
root.mainloop()
