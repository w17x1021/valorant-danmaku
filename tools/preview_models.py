"""模型管理窗口截图。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.main import App, enable_dpi_awareness
from app.ui.models import ModelManager


def main() -> None:
    enable_dpi_awareness()
    app = App()
    holder = {}

    app.root.after(900, lambda: holder.setdefault("w", ModelManager(app.panel, app)))

    def shoot():
        win = holder.get("w")
        if win is not None:
            x, y = win.winfo_rootx(), win.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            ImageGrab.grab(bbox=(x - 6, y - 6, x + w + 6, y + h + 6),
                           all_screens=True).save(ROOT / "docs" / "_ui_models.png")
            print("size", w, h, flush=True)
            win.destroy()
        app.root.after(200, app.quit)

    app.root.after(2200, shoot)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
