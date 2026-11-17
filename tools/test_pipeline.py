"""OCR 管线自测：用一张模拟聊天截图喂给 ChatReader，验证去重/合并/语言判定。"""
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

IMG = Image.open(ROOT / "tools" / "_ocr_in.png")


def fake_grab(bbox=None, all_screens=True, **kw):
    return IMG.copy()


cr.ImageGrab.grab = fake_grab

cfg = Config()
cfg.chat_region = [0, 0, IMG.width, IMG.height]
cfg.ocr_upscale = 1.0
cfg.ocr_interval_ms = 200

ocr = cr.WindowsOcr(ROOT / "app" / "ocr" / "ocr_worker.ps1", cfg.ocr_langs)
print("ocr languages:", ocr.available)
q: queue.Queue = queue.Queue()
stop = threading.Event()
reader = cr.ChatReader(cfg, ocr, q, stop)
reader.start()
time.sleep(2.2)

# 再换一张图（模拟新消息到达）
img2 = IMG.copy()
from PIL import ImageDraw, ImageFont
d = ImageDraw.Draw(img2)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
d.text((12, 12), "Reyna: rotate now, they are rushing a", font=font, fill=(235, 235, 235))
img2.save(ROOT / "tools" / "_ocr_in2.png")
IMG2 = Image.open(ROOT / "tools" / "_ocr_in2.png")
cr.ImageGrab.grab = lambda bbox=None, all_screens=True, **kw: IMG2.copy()
reader._last_hash = ""
time.sleep(1.6)
stop.set()
reader.join(timeout=3)
ocr.close()

print("stats:", reader.stats)
events = []
while not q.empty():
    events.append(q.get())
for ev in events:
    print(f"  [{ev.lang}] {ev.speaker!r}: {ev.text!r}")
