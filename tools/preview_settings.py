"""设置窗截图（含快捷键与字幕细节）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import ImageGrab

from app.main import App, enable_dpi_awareness
from app.ui.settings import SettingsDialog


def main() -> None:
    enable_dpi_awareness()
    app = App()
    holder = {}

    app.root.after(900, lambda: holder.setdefault("dlg", SettingsDialog(app.panel, app)))

    def shoot():
        dlg = holder.get("dlg")
        if dlg is not None:
            x, y = dlg.winfo_rootx(), dlg.winfo_rooty()
            w, h = dlg.winfo_width(), dlg.winfo_height()
            ImageGrab.grab(bbox=(x - 6, y - 6, x + w + 6, y + h + 6),
                           all_screens=True).save(ROOT / "docs" / "_ui_settings.png")
            print("size", w, h, flush=True)
            dlg.destroy()
        app.root.after(200, app.quit)

    app.root.after(2400, shoot)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
