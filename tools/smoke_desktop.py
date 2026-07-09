"""Capture the desktop layout at its narrow supported width."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --ignore-gpu-blocklist")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from desktop_app import MainWindow


OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("TEMP", ".")) / "desktop-smoke.png"
app = QApplication(sys.argv)


class SmokeWindow(MainWindow):
    def _start_model_load(self):
        pass


window = SmokeWindow()
window.resize(760, 620)
window.cargo_table.clear_all()
window.cargo_table.add_row("1 SCU", 999, 1)
window.cargo_table.add_row("8 SCU", 8, 2)
window.cargo_table.add_row("32 SCU", 4, 3)
window.show()


def finish():
    image = window.grab()
    saved = image.save(str(OUTPUT))
    print(f"saved={saved} size={image.width()}x{image.height()}")
    window.close()
    app.exit(0 if saved else 1)


QTimer.singleShot(1500, finish)
QTimer.singleShot(10000, lambda: app.exit(2))
sys.exit(app.exec())
