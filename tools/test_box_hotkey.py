"""验证：框宽/行数实时生效 + F8 开关「我说的话」。"""
import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.main import App, enable_dpi_awareness

SAMPLES = [
    ("Kirito: 推进B点，中路有两个敌人", "#9ec9ff"),
    ("夜桜: ちょっと待って、Bサイトに敵が二人いる", "#ffb0d4"),
    ("SovaMain: 好枪，兄弟", "#b6ffcf"),
    ("小明: 中路有人，小心", "#ffffff"),
]


def press(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk, 0, 2, 0)


def main() -> None:
    enable_dpi_awareness()
    app = App()

    def narrow_box():
        app.panel._on_width(520)
        app.panel._on_lines(2)
        app.panel.size_slider.set(26)
        app.panel._on_size(26)
        for text, color in SAMPLES[:2]:
            app.overlay.push(text, color)

    app.root.after(900, narrow_box)

    def shoot():
        from PIL import ImageGrab as G
        sw, sh = app.root.winfo_screenwidth(), app.root.winfo_screenheight()
        img = G.grab(bbox=(0, sh - 420, sw, sh), all_screens=True)
        img.save(ROOT / "docs" / "_box_custom.png")
        print("box shot ok", flush=True)
        app.root.after(100, lambda: press(0x77))     # F8

    app.root.after(2200, shoot)

    def after_f8():
        print("selftalk window:", app.selftalk_window is not None, flush=True)
        app.root.after(1500, lambda: press(0x77))

    app.root.after(3200, after_f8)

    def finish():
        print("after second F8:", app.selftalk_window is None, flush=True)
        app.root.after(200, app.quit)

    app.root.after(5200, finish)
    app.run()


if __name__ == "__main__":
    main()
