"""验证：F9/F10 热键复制能把译文放进系统剪贴板（并且不依赖窗口焦点）。"""
import ctypes
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import App, enable_dpi_awareness
from app.ui.clipboard import get_text

WM_HOTKEY = 0x0312


def watchdog(seconds=40):
    """兜底：卡住就强杀，免得测试进程挂死不退出。"""
    def kill():
        time.sleep(seconds)
        print("WATCHDOG: 超时强退", flush=True)
        os._exit(2)
    threading.Thread(target=kill, daemon=True).start()


def main() -> None:
    watchdog()
    enable_dpi_awareness()
    app = App()

    def step1():
        app.last_selftalk = {"zh": "等一下", "ja": "ちょっと待って",
                             "en": "Hold on", "src": "zh", "ts": time.time()}
        print("bound:", app.hotkeys.bound, flush=True)
        ctypes.windll.user32.PostThreadMessageW(app.hotkeys.thread_id, WM_HOTKEY, 1, 0)

    def step2():
        print("clipboard after F9:", repr(get_text()), flush=True)
        ctypes.windll.user32.PostThreadMessageW(app.hotkeys.thread_id, WM_HOTKEY, 2, 0)

    def step3():
        print("clipboard after F10:", repr(get_text()), flush=True)
        app.root.after(300, app.quit)

    app.root.after(1300, step1)
    app.root.after(2100, step2)
    app.root.after(2900, step3)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
