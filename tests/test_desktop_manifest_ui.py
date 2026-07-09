import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication

from desktop_app import CargoTable, CompressibleLabel


APP = QApplication.instance() or QApplication([])


def test_row_remove_button_removes_its_current_row():
    table = CargoTable()
    table.add_row("1 SCU", 2, 1)
    table.add_row("8 SCU", 3, 2)

    first_remove_button = table.cellWidget(0, 4)
    first_remove_button.click()
    APP.processEvents()

    assert table.rowCount() == 1
    assert table.cellWidget(0, 0).currentText() == "8 SCU"
    assert table.total_items() == 3


def test_compressible_label_keeps_full_text_available():
    text = "Total: 999 / 4,608 SCU (22%)"
    label = CompressibleLabel(text)
    label.resize(90, 24)
    label.show()
    APP.processEvents()

    assert label.toolTip() == text
    assert "font-size: 9px" in label.styleSheet()
