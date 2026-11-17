"""生成程序图标 assets/app.ico（深蓝圆角底 + 白色「译」字）。"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "app.ico"

SIZE = 256


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 竖向渐变
    grad = Image.new("RGB", (1, SIZE))
    top, bottom = (32, 52, 92), (12, 16, 26)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    img = grad.resize((SIZE, SIZE)).convert("RGBA")

    mask = rounded_mask(SIZE, 56)
    img.putalpha(mask)

    d = ImageDraw.Draw(img)
    # 内描边
    d.rounded_rectangle([6, 6, SIZE - 7, SIZE - 7], radius=50,
                        outline=(120, 160, 230, 90), width=2)
    # 中央「译」字
    font = None
    for path in (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"):
        try:
            font = ImageFont.truetype(path, 132)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    text = "译"
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text(((SIZE - tw) / 2 - box[0], (SIZE - th) / 2 - box[1] - 6), text,
           font=font, fill=(238, 244, 255, 255))
    # 底部小绿点（在线/运行中）
    d.ellipse([SIZE - 74, SIZE - 74, SIZE - 40, SIZE - 40],
              fill=(46, 204, 113, 255), outline=(12, 16, 26, 255), width=4)

    img.save(OUT, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("saved", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
