"""模型管理自测：切换语音包、导入校验、状态读取。"""
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import App, enable_dpi_awareness
from app.ui.models import ModelManager


def watchdog(seconds=90):
    def kill():
        time.sleep(seconds)
        print("WATCHDOG 超时", flush=True)
        os._exit(2)
    threading.Thread(target=kill, daemon=True).start()


def main() -> None:
    watchdog()
    enable_dpi_awareness()
    app = App()
    holder = {}

    def step1():
        win = holder.setdefault("w", ModelManager(app.panel, app))
        print("installed small:", app.cfg and bool(__import__("app.models", fromlist=["x"]).installed_path(app.cfg, "small")), flush=True)
        win._use_voice("small")
        print("after use small:", app.cfg.asr_model, flush=True)

    def step2():
        win = holder["w"]
        try:
            __import__("app.models", fromlist=["x"]).import_folder(ROOT / "docs", app.cfg)
            print("import bad folder: 没报错（有问题）", flush=True)
        except Exception as exc:  # noqa: BLE001
            print("import bad folder 正确拒绝:", str(exc)[:40], flush=True)
        win._use_voice("large-v3-turbo")
        print("restored:", app.cfg.asr_model, "| path:", repr(app.cfg.asr_model_path), flush=True)
        app.root.after(400, app.quit)

    app.root.after(1300, step1)
    app.root.after(3200, step2)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
