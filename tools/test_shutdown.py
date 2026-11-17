"""退出流程自测：启动完整 App，3 秒后走正常退出路径。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import App, enable_dpi_awareness

enable_dpi_awareness()
t0 = time.time()
app = App()
app.root.after(3000, app.quit)
app.run()
print(f"clean exit after {time.time()-t0:.1f}s")
