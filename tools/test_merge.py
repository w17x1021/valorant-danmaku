import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ocr import chat_reader as cr

ocr = cr.WindowsOcr(ROOT / "app" / "ocr" / "ocr_worker.ps1", ["en-US", "ja", "zh-Hans-CN"])
lines = ocr.recognize(ROOT / "tools" / "_ocr_in.png")
print("raw lines:", len(lines))
for l in lines:
    print(f"  {l.lang:12s} y={l.y:4d} {l.text!r}  rank={cr.rank_candidate(l):.2f}")
merged = cr.merge_lines(lines)
print("merged:", len(merged))
for m in merged:
    print(f"  {m.text!r} -> parse={cr.parse_line(m.text)}")
ocr.close()
