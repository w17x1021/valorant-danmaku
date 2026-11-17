"""验证日文兜底通道（PaddleOCR）在"没装日语语言包"的机器上的效果。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ocr.chat_reader import merge_lines, parse_line  # noqa: E402
from app.ocr.paddle_ja import PaddleJa  # noqa: E402
from app.ocr.win_ocr import WindowsOcr  # noqa: E402
from app.config import Config  # noqa: E402

WORKER = ROOT / "app" / "ocr" / "ocr_worker.ps1"


def main() -> None:
    cfg = Config.load()
    ocr = WindowsOcr(WORKER, ["en-US", "ja", "zh-Hans-CN"])
    helper = PaddleJa(cfg)
    print("windows langs:", ocr.available)
    try:
        for path in [ROOT / "cache" / "chat_region.png", ROOT / "tools" / "_eval_shot.png"]:
            if not path.exists():
                continue
            img = Image.open(path).convert("RGB")
            img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
            lines = merge_lines(ocr.recognize(img))
            print(f"\n=== {path.name} 放大2x 行数={len(lines)} ===")
            for ln in lines:
                print(f"  win [{ln.lang:10s}] {ln.text}")
            t0 = time.perf_counter()
            refined = helper.refine(img, lines)
            print(f"  paddle 耗时 {int((time.perf_counter()-t0)*1000)}ms, error={helper.error}")
            for ln in refined:
                print(f"  ref [{ln.lang:10s}] {ln.text}  -> {parse_line(ln.text)}")
    finally:
        ocr.close()


if __name__ == "__main__":
    main()
