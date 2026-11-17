"""独立测试 Windows OCR 常驻进程：生成一张模拟游戏聊天的图片并识别。"""
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "app" / "ocr" / "ocr_worker.ps1"

LINES = [
    ("Kirito", "push b site, two enemies mid", (140, 200, 255)),
    ("夜桜", "こんにちは、よろしくお願いします", (255, 180, 220)),
    ("小明", "中路有人，小心", (255, 220, 140)),
    ("SovaMain", "nice shot lol", (140, 200, 255)),
]


def make_image(path: Path, scale: int = 1) -> None:
    w, h = 640, 200
    img = Image.new("RGB", (w, h), (24, 26, 32))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    except OSError:
        font = ImageFont.load_default()
    y = 12
    for name, msg, color in LINES:
        d.text((12, y), f"{name}: ", font=font, fill=color)
        d.text((12 + d.textlength(f"{name}: ", font=font), y), msg, font=font, fill=(235, 235, 235))
        y += 44
    if scale != 1:
        img = img.resize((w * scale, h * scale), Image.LANCZOS)
    img.save(path)


def main() -> None:
    out = ROOT / "tools" / "_ocr_in.png"
    make_image(out, scale=int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    p = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WORKER)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", bufsize=1,
    )
    hello = json.loads(p.stdout.readline())
    print("ready:", hello.get("available"))
    for i in range(2):
        t0 = time.perf_counter()
        p.stdin.write(json.dumps({"path": str(out), "langs": ["en-US", "ja", "zh-Hans-CN"]}) + "\n")
        p.stdin.flush()
        res = json.loads(p.stdout.readline())
        dt = (time.perf_counter() - t0) * 1000
        print(f"--- run {i} {dt:.0f}ms ok={res.get('ok')} ---")
        for ln in res.get("lines", []):
            print(f"  [{ln['lang']:10s}] y={ln['y']:4d} x={ln['x']:4d} {ln['text']}")
    p.stdin.close()
    p.wait(timeout=5)
    err = p.stderr.read()
    if err.strip():
        print("stderr:", err[:2000])


if __name__ == "__main__":
    main()
