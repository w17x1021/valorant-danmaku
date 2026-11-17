"""「我说的话」窗口视觉 + 快捷键复制 自测。"""
import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.main import App, enable_dpi_awareness

SAMPLES = [
    {"zh": "等一下，我从后面绕过去，你们正面推进",
     "ja": "ちょっと待って、後ろから回るから、君たちは正面から進めて",
     "en": "Hold on, I'll go around the back, you push from the front",
     "src": "zh", "ts": time.time()},
]


def press(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def main() -> None:
    enable_dpi_awareness()
    app = App()
    app.root.after(600, app.open_selftalk)
    app.root.after(1500, lambda: app._show_self(SAMPLES[0]))
    app.root.after(2600, lambda: press(0x78))      # F9 -> 复制日语

    def check():
        try:
            print("clipboard:", repr(app.root.clipboard_get()), flush=True)
        except Exception as exc:  # noqa: BLE001
            print("clipboard error:", exc, flush=True)
        win = app.selftalk_window
        if win is not None:
            x, y = win.winfo_rootx(), win.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            ImageGrab.grab(bbox=(x - 10, y - 10, x + w + 10, y + h + 10),
                           all_screens=True).save(ROOT / "docs" / "我说的话.png")
            print("saved window", w, h, flush=True)
        app.root.after(200, app.quit)

    app.root.after(3400, check)
    app.run()


if __name__ == "__main__":
    main()
