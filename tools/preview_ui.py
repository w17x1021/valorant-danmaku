"""新界面截图：先拍主面板，再开「我说的话」拍它自己。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.main import App, enable_dpi_awareness

SAMPLE = {
    "zh": "等一下，我从后面绕过去，你们正面推进",
    "ja": "ちょっと待って、後ろから回るから、君たちは正面から進めて",
    "en": "Hold on, I'll go around the back, you push from the front",
    "src": "zh", "ts": time.time(),
}


def grab(win, name):
    x, y = win.winfo_rootx(), win.winfo_rooty()
    w, h = win.winfo_width(), win.winfo_height()
    ImageGrab.grab(bbox=(x - 6, y - 6, x + w + 6, y + h + 6),
                   all_screens=True).save(ROOT / "docs" / name)


def main() -> None:
    enable_dpi_awareness()
    app = App()

    def fill():
        app.panel.set_last("Kirito: 推进B点，中路有两个敌人")
        app.panel.set_status("OCR 运行中 · 已翻译 12 条 · 抓帧 30 · 最后 01:40:12")
        app.panel.set_voice("语音：识别中 · GPU")
        app.panel.set_region([120, 520, 760, 230])

    app.root.after(900, fill)
    app.root.after(1500, lambda: grab(app.panel, "_ui_panel.png"))
    app.root.after(1700, app.open_selftalk)
    app.root.after(2300, lambda: app._show_self(SAMPLE))
    app.root.after(2900, lambda: grab(app.selftalk_window, "_ui_talk.png"))
    app.root.after(3200, app.quit)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
