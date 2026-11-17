"""模拟「全新安装」状态：没有 models 目录时，模型管理窗口应显示下载按钮。"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.main import App, enable_dpi_awareness
from app.ui.models import ModelManager


def watchdog(sec=60):
    def kill():
        time.sleep(sec)
        print("WATCHDOG", flush=True)
        os._exit(2)
    threading.Thread(target=kill, daemon=True).start()


def main() -> None:
    watchdog()
    enable_dpi_awareness()
    app = App()
    # 假装是全新安装：模型目录指到一个空的临时目录
    empty = Path(tempfile.mkdtemp(prefix="vdm_empty_"))
    app.cfg.asr_model_dir = str(empty)
    app.cfg.asr_model_path = ""

    holder = {}

    def go():
        try:
            win = holder.setdefault("w", ModelManager(app.panel, app))
        except Exception as exc:  # noqa: BLE001
            print("打开失败:", type(exc).__name__, exc, flush=True)
            app.root.after(200, app.quit)
            return
        app.root.after(1200, shoot)

    def shoot():
        win = holder.get("w")
        if win is not None and win.winfo_exists():
            x, y = win.winfo_rootx(), win.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            ImageGrab.grab(bbox=(x - 6, y - 6, x + w + 6, y + h + 6),
                           all_screens=True).save(ROOT / "docs" / "_fresh_models.png")
            kids = win.list_box.winfo_children()
            print("列表里控件数:", len(kids), flush=True)
        app.root.after(200, app.quit)

    app.root.after(1200, go)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
