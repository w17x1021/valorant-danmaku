"""生成 docs 用的字幕框演示图：**合成背景**，不截桌面（避免暴露用户环境）。

用真实的 LayeredSubtitleBox._compose() 渲染，效果和程序里一致。
"""
import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config
from app.ui.subs import LayeredSubtitleBox


def make_background(w: int = 1600, h: int = 620) -> Image.Image:
    """纯合成的「游戏画面」底图：深色渐变 + 一点光晕 + 模糊色块，不含任何真实内容。"""
    img = Image.new("RGB", (w, h), "#0e1118")
    d = ImageDraw.Draw(img)
    top, bottom = (16, 22, 34), (28, 38, 56)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=(
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t)))

    # 远处的地平线光带
    glow = Image.new("RGB", (w, h), "#000000")
    gd = ImageDraw.Draw(glow)
    gd.ellipse([w * 0.15, h * 0.42, w * 0.85, h * 1.05], fill=(52, 78, 118))
    gd.rectangle([0, int(h * 0.62), w, h], fill=(24, 30, 44))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    img = Image.blend(img, Image.blend(img, glow, 0.55), 0.6)

    # 模糊的建筑/箱子块，暗示是个场景
    blocks = Image.new("RGB", (w, h), "#0e1118")
    bd = ImageDraw.Draw(blocks)
    for x, y, bw, bh, c in [
        (90, 330, 220, 200, (30, 40, 58)), (360, 300, 180, 230, (36, 47, 66)),
        (1180, 320, 260, 210, (33, 44, 62)), (900, 250, 160, 280, (28, 37, 54)),
    ]:
        bd.rectangle([x, y, x + bw, y + bh], fill=c)
    blocks = blocks.filter(ImageFilter.GaussianBlur(6))
    img = Image.blend(img, blocks, 0.35)
    return img


def main() -> None:
    cfg = Config()
    cfg.display_mode = "box"
    cfg.danmaku_font_size = 22
    cfg.box_width_px = 760
    cfg.box_bottom_margin = 210
    cfg.box_max_lines = 3

    root = tk.Tk()
    root.withdraw()
    box = LayeredSubtitleBox(root, cfg)
    box.visible = True
    box.entries = [
        {"text": "Kirito: 推进 B 点，中路有两个敌人", "color": cfg.color_en, "ts": 0},
        {"text": "夜桜: 等一下，这边有敌人绕后", "color": cfg.color_ja, "ts": 0},
        {"text": "🎤 敌人在推进 B 点，他们两个现在在中路转点", "color": cfg.color_voice,
         "ts": 0},
    ]
    overlay, ox, oy = box._compose()

    bg = make_background(1600, 620)
    # 把字幕框放到画面中间偏下，留出「游戏画面」的空白
    px = (bg.width - overlay.width) // 2
    py = bg.height - overlay.height - 70
    bg.paste(overlay, (px, py), overlay if overlay.mode == "RGBA" else None)

    out = ROOT / "docs" / "字幕框效果.png"
    bg.save(out)
    root.destroy()
    print("saved", out, bg.size, "| box", overlay.size)


if __name__ == "__main__":
    main()
