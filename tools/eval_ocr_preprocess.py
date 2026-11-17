"""离线评测：同一张聊天截图在不同预处理管线下的识别效果。

目的：找出"对比度/锐化/放大/二值化"里哪个组合对游戏聊天字体最准，
避免凭感觉调参。用法：.venv\\Scripts\\python.exe tools\\eval_ocr_preprocess.py
"""
from __future__ import annotations

import difflib
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ocr.win_ocr import WindowsOcr  # noqa: E402
from app.ocr.chat_reader import merge_lines, parse_line, normalize  # noqa: E402
from app.translator import detect_language  # noqa: E402

WORKER = ROOT / "app" / "ocr" / "ocr_worker.ps1"
LANGS = ["en-US", "ja", "zh-Hans-CN"]

SAMPLES = [
    ("Reyna", "push b site, they keep flanking", "en", (140, 200, 255)),
    ("夜桜", "こんにちは、よろしくお願いします", "ja", (255, 180, 220)),
    ("小明", "中路有人，小心", "zh", (255, 220, 140)),
    ("SovaMain", "nice shot lol", "en", (140, 200, 255)),
]
EXPECTED = [(s[0], s[1], s[2]) for s in SAMPLES]


def make_game_shot(path: Path, font_px: int, w: int = 430, h: int = 190,
                   bg=(18, 20, 26), opaque=True) -> None:
    """模拟游戏内聊天：小字号白字 + 深色描边，贴在半透明深色底上。"""
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", font_px)
    bold = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", font_px) if Path(
        "C:/Windows/Fonts/msyhbd.ttc").exists() else font
    y = 8
    for name, msg, _lang, color in SAMPLES:
        tag = f"{name}: "
        tw = d.textlength(tag, font=bold)
        # 描边：先画一圈黑，再画字，模拟游戏字体的 outline
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                d.text((10 + dx, y + dy), tag, font=bold, fill=(0, 0, 0, 255))
                d.text((10 + tw + dx, y + dy), msg, font=font, fill=(0, 0, 0, 255))
        d.text((10, y), tag, font=bold, fill=color + (255,))
        d.text((10 + tw, y), msg, font=font, fill=(245, 245, 245, 255))
        y += font_px + 12
    if opaque:
        out = Image.new("RGB", (w, h), bg)
        out.paste(base, (0, 0), base)
    else:
        out = base.convert("RGB")
    out.save(path)


def var_current(img: Image.Image, scale: float) -> Image.Image:
    if scale > 1.01:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.25)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120))
    return img


def var_plain(img: Image.Image, scale: float) -> Image.Image:
    if scale > 1.01:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    return img.convert("RGB")


def var_autocontrast(img: Image.Image, scale: float) -> Image.Image:
    if scale > 1.01:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    return g.convert("RGB")


def var_binarize(img: Image.Image, scale: float) -> Image.Image:
    if scale > 1.01:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    g = img.convert("L")
    hist = g.histogram()
    total = sum(hist)
    # 取亮部 8% 作为文字像素，阈值落在文字与背景之间
    acc, thr = 0, 255
    for v in range(255, -1, -1):
        acc += hist[v]
        if acc >= total * 0.08:
            thr = v
            break
    thr = max(90, min(200, thr - 25))
    return g.point(lambda p: 255 if p >= thr else 0).convert("RGB")


def var_binarize_blur(img: Image.Image, scale: float) -> Image.Image:
    if scale > 1.01:
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    g = img.convert("L").filter(ImageFilter.MedianFilter(3))
    hist = g.histogram()
    total = sum(hist)
    acc, thr = 0, 255
    for v in range(255, -1, -1):
        acc += hist[v]
        if acc >= total * 0.08:
            thr = v
            break
    thr = max(90, min(200, thr - 25))
    return g.point(lambda p: 255 if p >= thr else 0).convert("RGB")


def var_upscale3_bin(img: Image.Image, scale: float) -> Image.Image:
    img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
    return var_binarize(img, 1.0)


VARIANTS = [
    ("current(1.25对比+锐化)", var_current),
    ("plain(仅放大)", var_plain),
    ("autocontrast", var_autocontrast),
    ("binarize", var_binarize),
    ("binarize+median", var_binarize_blur),
    ("3x+binarize", var_upscale3_bin),
]


def score(expected: list[tuple[str, str, str]], got: list[tuple[str, str]]) -> str:
    pairs = []
    used = set()
    for speaker, text, lang in expected:
        best, bi = 0.0, -1
        for i, (sp, tx) in enumerate(got):
            if i in used:
                continue
            a = normalize(f"{speaker} {text}")
            b = normalize(f"{sp} {tx}")
            r = difflib.SequenceMatcher(None, a, b).ratio()
            if r > best:
                best, bi = r, i
        if bi >= 0:
            used.add(bi)
        pairs.append(best)
    if not pairs:
        return "0.00"
    return f"{sum(pairs)/len(pairs):.2f} (min {min(pairs):.2f})"


def run_case(ocr: WindowsOcr, title: str, img: Image.Image, scale: float,
             expected: list[tuple[str, str, str]]) -> None:
    print(f"\n=== {title}  size={img.width}x{img.height} scale={scale} ===")
    for name, fn in VARIANTS:
        t0 = time.perf_counter()
        out = fn(img.copy(), scale)
        t1 = time.perf_counter()
        lines = ocr.recognize(out)
        t2 = time.perf_counter()
        merged = merge_lines(lines)
        parsed = [p for p in (parse_line(l.text) for l in merged) if p]
        print(f"  {name:22s} 预处理{int((t1-t0)*1000):4d}ms OCR{int((t2-t1)*1000):4d}ms "
              f"得分 {score(expected, parsed)}  行数 {len(parsed)}")
        for sp, tx in parsed:
            print(f"      [{detect_language(tx)}] {sp} | {tx}")


def main() -> None:
    ocr = WindowsOcr(WORKER, LANGS)
    try:
        print("available:", ocr.available)
        sample = ROOT / "cache" / "chat_region.png"
        if sample.exists():
            img = Image.open(sample).convert("RGB")
            # 这张图上第一行是两个文字叠印的坏样本，不算进评分
            exp = EXPECTED
            run_case(ocr, "cache/chat_region.png", img, 2.0, exp)
        tmp = ROOT / "tools" / "_eval_shot.png"
        for px in (12, 14, 18):
            make_game_shot(tmp, px)
            run_case(ocr, f"模拟游戏 {px}px", Image.open(tmp).convert("RGB"), 2.0, EXPECTED)
    finally:
        ocr.close()


if __name__ == "__main__":
    main()
