"""给 ./translator.py 做联网自测：直接打印各翻译源结果。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Config
from app.translator import Translator, detect_language

SAMPLES = [
    ("en", "push b site fast, im going mid"),
    ("en", "nice shot bro"),
    ("en", "one hp behind the box"),
    ("ja", "ちょっと待って、こっちに敵がいる"),
    ("ja", "ありがとう！"),
    ("zh", "中路有人"),
]

cfg = Config()
tr = Translator(cfg)
t0 = time.time()
print("warmup:", tr.warmup(), f"{int((time.time()-t0)*1000)}ms")
for src, text in SAMPLES:
    t0 = time.time()
    res = tr.translate(text, src)
    lang = detect_language(text)
    print(f"[{lang}] {text!r} -> {res.text!r} ({res.provider}, {int((time.time()-t0)*1000)}ms)")
tr.flush_cache()
