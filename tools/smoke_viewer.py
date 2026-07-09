"""Offscreen smoke render for the Three.js viewer."""

import json
import os
import sys
from pathlib import Path

ONSCREEN = "--onscreen" in sys.argv
if ONSCREEN:
    sys.argv.remove("--onscreen")
os.environ.setdefault("QT_QPA_PLATFORM", "windows" if ONSCREEN else "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --ignore-gpu-blocklist")

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("TEMP", ".")) / "viewer-smoke.png"


class SmokePage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.errors = []

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(f"{source_id}:{line_number}: {message}")


app = QApplication(sys.argv)
view = QWebEngineView()
page = SmokePage(view)
view.setPage(page)
view.resize(1200, 800)
view.show()

payload = {
    "ship_grids": [{"name": "Main", "dimensions": [8, 8, 4]}],
    "placements": [
        {"scu_type": "8 SCU", "position": [0, 0, 0], "dimensions": [2, 2, 2], "priority": 1, "grid_idx": 0, "grid_name": "Main"},
        {"scu_type": "16 SCU", "position": [2, 0, 0], "dimensions": [2, 4, 2], "priority": 2, "grid_idx": 0, "grid_name": "Main"},
    ],
    "unplaced_items": [],
    "metrics": {"success_rate": 1.0, "volume_utilization": 0.05},
}


def finish():
    image = view.grab()
    saved = image.save(str(OUTPUT))
    print(json.dumps({"saved": saved, "size": [image.width(), image.height()], "errors": page.errors}))
    app.exit(1 if page.errors or not saved else 0)


def loaded(ok):
    if not ok:
        print("viewer load failed")
        app.exit(1)
        return
    encoded = json.dumps(payload)
    script = f"window.loadPacking({encoded}); window.loadPacking({encoded}); 'loaded';"
    page.runJavaScript(script, lambda _result: QTimer.singleShot(1200, finish))


view.loadFinished.connect(loaded)
view.load(QUrl.fromLocalFile(str(ROOT / "frontend" / "viewer.html")))
QTimer.singleShot(15000, lambda: app.exit(2))
sys.exit(app.exec())
