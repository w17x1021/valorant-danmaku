"""日文文字识别（PaddleOCR 兜底）端到端自测：假聊天窗口里放日文/英文/中文，跑真实读取管线。"""
import queue
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image

import app.ocr.chat_reader as cr
from app.config import Config

IMG = Image.open(ROOT / "tools" / "_ja2x.png")
cr.ImageGrab.grab = lambda bbox=None, all_screens=True, **kw: IMG.copy()

cfg = Config()
cfg.chat_region = [0, 0, IMG.width, IMG.height]
cfg.ocr_upscale = 1.0          # 测试图已经是 2 倍
cfg.ocr_interval_ms = 250

ocr = cr.WindowsOcr(ROOT / "app" / "ocr" / "ocr_worker.ps1", cfg.ocr_langs)
print("windows ocr:", ocr.available, flush=True)
q: queue.Queue = queue.Queue()
stop = threading.Event()
reader = cr.ChatReader(cfg, ocr, q, stop)
print("paddle fallback:", reader.ja_helper is not None, flush=True)
reader.start()
time.sleep(8.0)
stop.set()
reader.join(timeout=5)
ocr.close()

print("stats:", reader.stats, flush=True)
while not q.empty():
    ev = q.get()
    print(f"  [{ev.lang}] {ev.speaker!r}: {ev.text!r}", flush=True)
if reader.ja_helper:
    print("paddle error:", reader.ja_helper.error or "(none)", flush=True)
