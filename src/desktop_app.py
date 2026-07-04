import json
import os
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QSettings, QStandardPaths
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QSpinBox,
    QTextEdit, QSplitter, QMessageBox, QHeaderView, QGroupBox, QStatusBar,
    QTabWidget, QInputDialog, QToolButton, QSizePolicy,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


def _resource_root() -> Path:
    """Locate bundled read-only resources.
    - Frozen (PyInstaller --onefile): sys._MEIPASS
    - Frozen (PyInstaller --onedir): dir containing the exe
    - Dev: project root (parent of src/)
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


APP_ORG = "StarCitizen"
APP_NAME = "CargoOptimizer"
APP_VERSION = "0.1.3"


def _user_data_dir() -> Path:
    """Per-user writable directory under platform AppData. Resolved without
    Qt so it works at import time, before QApplication exists."""
    base = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not base:
        base = str(Path.home() / "AppData" / "Roaming")
    p = Path(base) / APP_ORG / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


# In dev, src/ is alongside the resources; in frozen, src/ ships next to resources too.
sys.path.insert(0, str(_resource_root() / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scu_manifest_generator import SCU_DEFINITIONS
from packing_core.grid_utils import grid_usable_volume, serialize_grid

RESOURCE_ROOT = _resource_root()
SHIPS_FILE = RESOURCE_ROOT / "ships_cargo_grids.json"
VIEWER_HTML = RESOURCE_ROOT / "frontend" / "viewer.html"
PRESETS_FILE = _user_data_dir() / "presets.json"
MAX_PRIORITY = 5

# App-wide theme palettes. Keys and colors mirror the PALETTES `css` blocks in
# frontend/viewer.html — keep the two in sync. The viewer broadcasts theme
# changes through its page title ("sc-theme|<style>|<palette>") and the main
# window restyles the whole app to match.
THEME_PALETTES = {
    "default": {"bg": "#0d1117", "border": "#30363d", "fg": "#e6edf3", "muted": "#8b949e",
                "accent": "#58a6ff", "warn": "#d29922", "bad": "#f85149", "good": "#3fb950",
                "btn": "#21262d", "btn_hover": "#30363d"},
    "drake":   {"bg": "#120c07", "border": "#4a3524", "fg": "#f2e7da", "muted": "#a68d75",
                "accent": "#ff6a2b", "warn": "#e0a33c", "bad": "#ff4633", "good": "#4fa866",
                "btn": "#251a10", "btn_hover": "#3a2818"},
    "origin":  {"bg": "#eef1f4", "border": "#c3ccd6", "fg": "#1c2733", "muted": "#5f6b78",
                "accent": "#0289a8", "warn": "#9a6700", "bad": "#c93a31", "good": "#1a7f37",
                "btn": "#ffffff", "btn_hover": "#dfe6ec"},
    "rsi":     {"bg": "#06121f", "border": "#1d4062", "fg": "#dcebfa", "muted": "#7fa3c4",
                "accent": "#3fb6ff", "warn": "#d9a03c", "bad": "#ff5d5d", "good": "#35d07f",
                "btn": "#0d2438", "btn_hover": "#16334e"},
    "aegis":   {"bg": "#0b100d", "border": "#2c3b32", "fg": "#dde8df", "muted": "#8ba392",
                "accent": "#4fd1a5", "warn": "#d0a136", "bad": "#e5484d", "good": "#62c462",
                "btn": "#16211b", "btn_hover": "#24352b"},
    "misc":    {"bg": "#0c1416", "border": "#29444a", "fg": "#e2f1f0", "muted": "#86a8a6",
                "accent": "#35d0ba", "warn": "#d99e35", "bad": "#ef476f", "good": "#6ede8a",
                "btn": "#12262a", "btn_hover": "#1d3a40"},
    "crusader": {"bg": "#081226", "border": "#24406e", "fg": "#e8eefc", "muted": "#8fa3cc",
                 "accent": "#ffa62b", "warn": "#dcae4a", "bad": "#ff4f58", "good": "#43d17c",
                 "btn": "#101f3e", "btn_hover": "#1b2f57"},
    "argo":    {"bg": "#0f0f0d", "border": "#4a452c", "fg": "#f0eee3", "muted": "#a3a08a",
                "accent": "#ffd60a", "warn": "#d9a03c", "bad": "#ff4438", "good": "#7ac74f",
                "btn": "#211f16", "btn_hover": "#35321f"},
}
THEME_STYLES = ("modern", "retro")


def _mix(hex_a, hex_b, t):
    """Blend two #rrggbb colors; t=0 -> a, t=1 -> b."""
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _text_on(hex_color):
    """Black or white, whichever reads better on the given color."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#0d1117" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def build_qss(style_key, palette_key):
    p = THEME_PALETTES.get(palette_key, THEME_PALETTES["default"])
    retro = style_key == "retro"
    c = dict(p)
    c["surface"] = _mix(p["bg"], p["btn"], 0.5)
    c["sel"] = p["accent"]
    c["sel_fg"] = _text_on(p["accent"])
    c["good_fg"] = _text_on(p["good"])
    c["good_hi"] = _mix(p["good"], "#ffffff", 0.15)
    c["good_lo"] = _mix(p["good"], "#000000", 0.2)
    c["good_dis"] = _mix(p["good"], p["bg"], 0.7)
    c["bad_dim"] = _mix(p["bad"], p["bg"], 0.85)
    c["font"] = ('Consolas, "Courier New", monospace' if retro
                 else '"Segoe UI", system-ui, sans-serif')
    # Retro: chunky square corners to match the viewer's 8-bit chrome.
    c["r4"] = c["r5"] = c["r6"] = "0px" if retro else None
    if not retro:
        c["r4"], c["r5"], c["r6"] = "4px", "5px", "6px"
    return """
QMainWindow, QWidget#central {{ background-color: {bg}; }}
QWidget {{ color: {fg}; font-family: {font}; font-size: 12px; }}
QLabel {{ color: {fg}; }}
QLabel#hint {{ color: {muted}; font-size: 11px; }}
QLabel#capacity_ok {{ color: {good}; font-weight: 600; }}
QLabel#capacity_warn {{ color: {warn}; font-weight: 600; }}
QLabel#capacity_full {{ color: {bad}; font-weight: 600; }}
QLabel#status_dot_loading {{ color: {warn}; font-size: 14px; }}
QLabel#status_dot_ready {{ color: {good}; font-size: 14px; }}
QLabel#status_dot_error {{ color: {bad}; font-size: 14px; }}
QGroupBox {{
    border: 1px solid {border}; border-radius: {r6};
    margin-top: 14px; padding: 10px 8px 8px 8px;
    background-color: {bg};
    font-weight: 600;
}}
QGroupBox::title {{
    color: {muted}; subcontrol-origin: margin;
    left: 12px; padding: 0 6px; background-color: {bg};
}}
QPushButton {{
    background-color: {btn}; color: {fg};
    border: 1px solid {border}; border-radius: {r5};
    padding: 6px 14px; min-height: 22px;
}}
QPushButton:hover {{ background-color: {btn_hover}; border-color: {muted}; }}
QPushButton:pressed {{ background-color: {surface}; }}
QPushButton:disabled {{ color: {muted}; background-color: {surface}; }}
QPushButton#optimize_btn {{
    background-color: {good}; color: {good_fg};
    font-size: 13px; font-weight: 600;
    border: 1px solid {good_hi}; min-height: 32px;
}}
QPushButton#optimize_btn:hover {{ background-color: {good_hi}; }}
QPushButton#optimize_btn:pressed {{ background-color: {good_lo}; }}
QPushButton#optimize_btn:disabled {{ background-color: {good_dis}; color: {muted}; border-color: {border}; }}
QPushButton#danger {{ color: {bad}; }}
QPushButton#danger:hover {{ background-color: {bad_dim}; border-color: {bad}; }}
QToolButton {{
    background-color: transparent; color: {fg};
    border: 1px solid {border}; border-radius: {r4}; padding: 3px 6px;
}}
QToolButton:hover {{ background-color: {btn_hover}; }}
QComboBox, QSpinBox, QLineEdit {{
    background-color: {surface}; color: {fg};
    border: 1px solid {border}; border-radius: {r4};
    padding: 3px 6px; min-height: 22px;
    selection-background-color: {sel}; selection-color: {sel_fg};
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {muted}; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {surface}; color: {fg};
    border: 1px solid {border}; selection-background-color: {sel};
    selection-color: {sel_fg};
    outline: 0;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 14px; border: none; background: {btn}; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {btn_hover}; }}
QTableWidget {{
    background-color: {bg}; alternate-background-color: {surface};
    gridline-color: {btn}; color: {fg};
    selection-background-color: {sel}; selection-color: {sel_fg};
    border: 1px solid {border}; border-radius: {r4};
}}
QTableWidget::item {{ padding: 2px; }}
QHeaderView::section {{
    background-color: {surface}; color: {muted};
    padding: 6px 8px; border: none;
    border-right: 1px solid {border}; border-bottom: 1px solid {border};
    font-weight: 600; text-transform: uppercase; font-size: 10px;
    letter-spacing: 0.5px;
}}
QHeaderView::section:last {{ border-right: none; }}
QTabWidget::pane {{ border: 1px solid {border}; border-radius: {r4}; background: {bg}; top: -1px; }}
QTabBar::tab {{
    background: {surface}; color: {muted};
    padding: 7px 18px; border: 1px solid {border};
    border-bottom: none; border-top-left-radius: {r4}; border-top-right-radius: {r4};
    margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {bg}; color: {fg}; border-color: {border}; }}
QTabBar::tab:hover:!selected {{ color: {fg}; }}
QTextEdit {{
    background-color: {bg}; color: {fg};
    border: 1px solid {border}; border-radius: {r4};
    selection-background-color: {sel}; selection-color: {sel_fg};
}}
QStatusBar {{ background-color: {surface}; color: {muted}; border-top: 1px solid {border}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background-color: {btn}; }}
QSplitter::handle:horizontal {{ width: 3px; }}
QSplitter::handle:vertical {{ height: 3px; }}
QSplitter::handle:hover {{ background-color: {accent}; }}
QMessageBox, QInputDialog {{ background-color: {surface}; }}
QMessageBox QLabel, QInputDialog QLabel {{ color: {fg}; }}
QScrollBar:vertical {{ background: {bg}; width: 12px; border: none; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: {r5}; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: {bg}; height: 12px; border: none; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: {r5}; min-width: 20px; }}
QScrollBar::handle:horizontal:hover {{ background: {muted}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
""".format(**c)


def load_presets():
    if not PRESETS_FILE.exists():
        return {}
    try:
        with open(PRESETS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_presets(presets):
    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=2)


class ModelLoader(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            from ensemble_inference import EnsembleRouter
            router = EnsembleRouter(base_dir=str(RESOURCE_ROOT))
            self.ready.emit(router)
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


class PackingWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, router, ship_grids, manifest):
        super().__init__()
        self.router = router
        self.ship_grids = ship_grids
        self.manifest = manifest

    def run(self):
        try:
            result = self.router.route_manifest(self.ship_grids, self.manifest, diagnose=True)
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


class CargoTable(QTableWidget):
    COLUMNS = ["SCU Type", "Qty", "Priority", "Volume"]
    capacity_changed = Signal()

    def __init__(self):
        super().__init__(0, len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.verticalHeader().setDefaultSectionSize(36)
        self.verticalHeader().setVisible(False)

    def add_row(self, scu_type="1 SCU", quantity=1, priority=1):
        row = self.rowCount()
        self.insertRow(row)

        combo = QComboBox()
        combo.addItems(list(SCU_DEFINITIONS.keys()))
        combo.setCurrentText(scu_type)
        combo.currentTextChanged.connect(self._on_row_changed)
        self.setCellWidget(row, 0, combo)

        qty_spin = QSpinBox()
        qty_spin.setRange(1, 999)
        qty_spin.setValue(quantity)
        qty_spin.valueChanged.connect(self._on_row_changed)
        self.setCellWidget(row, 1, qty_spin)

        prio_spin = QSpinBox()
        prio_spin.setRange(1, MAX_PRIORITY)
        prio_spin.setValue(priority)
        prio_spin.setPrefix("P")
        prio_spin.valueChanged.connect(self._on_row_changed)
        self.setCellWidget(row, 2, prio_spin)

        vol_item = QTableWidgetItem()
        vol_item.setFlags(Qt.ItemIsEnabled)
        vol_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 3, vol_item)
        self._update_row_volume(row)

        self.capacity_changed.emit()

    def _on_row_changed(self):
        sender = self.sender()
        for r in range(self.rowCount()):
            for c in range(3):
                if self.cellWidget(r, c) is sender:
                    self._update_row_volume(r)
                    break
        self.capacity_changed.emit()

    def _update_row_volume(self, row):
        combo = self.cellWidget(row, 0)
        qty = self.cellWidget(row, 1)
        if not combo or not qty:
            return
        unit = SCU_DEFINITIONS.get(combo.currentText(), {}).get("volume", 0)
        total = unit * qty.value()
        item = self.item(row, 3)
        if item:
            item.setText(f"{total} SCU")

    def total_volume(self):
        total = 0
        for r in range(self.rowCount()):
            combo = self.cellWidget(r, 0)
            qty = self.cellWidget(r, 1)
            if combo and qty:
                unit = SCU_DEFINITIONS.get(combo.currentText(), {}).get("volume", 0)
                total += unit * qty.value()
        return total

    def total_items(self):
        return sum(self.cellWidget(r, 1).value() for r in range(self.rowCount())
                   if self.cellWidget(r, 1))

    def remove_selected(self):
        rows = sorted({idx.row() for idx in self.selectedIndexes()}, reverse=True)
        for r in rows:
            self.removeRow(r)
        self.capacity_changed.emit()

    def duplicate_selected(self):
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        for r in rows:
            scu = self.cellWidget(r, 0).currentText()
            q = self.cellWidget(r, 1).value()
            p = self.cellWidget(r, 2).value()
            self.add_row(scu, q, p)

    def set_priority_selected(self, priority):
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if not rows:
            return False
        for r in rows:
            self.cellWidget(r, 2).setValue(priority)
        return True

    def move_selected(self, delta):
        rows = sorted({idx.row() for idx in self.selectedIndexes()})
        if not rows:
            return
        if delta < 0 and rows[0] == 0:
            return
        if delta > 0 and rows[-1] == self.rowCount() - 1:
            return
        ordered = rows if delta < 0 else list(reversed(rows))
        for r in ordered:
            self._swap_rows(r, r + delta)
        # Reselect moved rows
        self.clearSelection()
        for r in rows:
            self.selectRow(r + delta)

    def _swap_rows(self, a, b):
        scu_a = self.cellWidget(a, 0).currentText()
        q_a = self.cellWidget(a, 1).value()
        p_a = self.cellWidget(a, 2).value()
        scu_b = self.cellWidget(b, 0).currentText()
        q_b = self.cellWidget(b, 1).value()
        p_b = self.cellWidget(b, 2).value()
        self.cellWidget(a, 0).setCurrentText(scu_b)
        self.cellWidget(a, 1).setValue(q_b)
        self.cellWidget(a, 2).setValue(p_b)
        self.cellWidget(b, 0).setCurrentText(scu_a)
        self.cellWidget(b, 1).setValue(q_a)
        self.cellWidget(b, 2).setValue(p_a)

    def to_manifest(self):
        return [
            {
                "scu_type": self.cellWidget(r, 0).currentText(),
                "quantity": self.cellWidget(r, 1).value(),
                "priority": self.cellWidget(r, 2).value(),
            }
            for r in range(self.rowCount())
        ]

    def clear_all(self):
        while self.rowCount():
            self.removeRow(0)
        self.capacity_changed.emit()


class MainWindow(QMainWindow):
    SETTINGS_ORG = APP_ORG
    SETTINGS_APP = APP_NAME

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Star Citizen Cargo Optimizer v{APP_VERSION}")
        self.resize(1200, 800)

        self.settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
        self.router = None
        self.ships_data = self._load_ships()
        self.presets = load_presets()

        self.theme_style = str(self.settings.value("theme_style", "modern"))
        self.theme_palette = str(self.settings.value("theme_palette", "default"))
        if self.theme_style not in THEME_STYLES:
            self.theme_style = "modern"
        if self.theme_palette not in THEME_PALETTES:
            self.theme_palette = "default"
        self._apply_app_theme()

        self._build_ui()
        self._refresh_preset_combo()
        self._restore_state()
        self._start_model_load()

    def _load_ships(self):
        try:
            with open(SHIPS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load ships_cargo_grids.json:\n{e}")
            return {"ships": []}

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 6)
        root.setSpacing(8)

        # Top row: ship + presets + status indicator
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # Ship
        ship_box = QGroupBox("Ship")
        ship_layout = QVBoxLayout(ship_box)
        ship_layout.setContentsMargins(8, 4, 8, 8)
        self.ship_combo = QComboBox()
        ship_names = sorted(s["name"] for s in self.ships_data.get("ships", []))
        self.ship_combo.addItems(ship_names)
        self.ship_combo.currentTextChanged.connect(self._on_ship_changed)
        ship_layout.addWidget(self.ship_combo)
        self.grid_info = QLabel("")
        self.grid_info.setObjectName("hint")
        self.grid_info.setWordWrap(True)
        ship_layout.addWidget(self.grid_info)
        top_row.addWidget(ship_box, 2)

        # Presets
        preset_box = QGroupBox("Presets")
        preset_layout = QVBoxLayout(preset_box)
        preset_layout.setContentsMargins(8, 4, 8, 8)
        self.preset_combo = QComboBox()
        preset_layout.addWidget(self.preset_combo)
        preset_btns = QHBoxLayout()
        preset_btns.setSpacing(4)
        load_btn = QPushButton("Load")
        load_btn.clicked.connect(self._on_load_preset)
        save_btn = QPushButton("Save…")
        save_btn.clicked.connect(self._on_save_preset)
        del_btn = QPushButton("Delete")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._on_delete_preset)
        preset_btns.addWidget(load_btn)
        preset_btns.addWidget(save_btn)
        preset_btns.addWidget(del_btn)
        preset_layout.addLayout(preset_btns)
        top_row.addWidget(preset_box, 2)

        root.addLayout(top_row)

        # Cargo + viewer split
        self.splitter = QSplitter(Qt.Horizontal)

        # Cargo pane
        cargo_box = QGroupBox("Cargo Manifest")
        cargo_layout = QVBoxLayout(cargo_box)
        cargo_layout.setContentsMargins(8, 4, 8, 8)
        cargo_layout.setSpacing(6)

        self.cargo_table = CargoTable()
        self.cargo_table.add_row()
        self.cargo_table.capacity_changed.connect(self._update_capacity_label)
        cargo_layout.addWidget(self.cargo_table, 1)

        # Toolbar row 1: add/remove/duplicate
        bar1 = QHBoxLayout()
        bar1.setSpacing(4)
        add_btn = QPushButton("+ Row")
        add_btn.clicked.connect(lambda: self.cargo_table.add_row())
        rm_btn = QPushButton("− Row")
        rm_btn.clicked.connect(self.cargo_table.remove_selected)
        dup_btn = QPushButton("Duplicate")
        dup_btn.clicked.connect(self.cargo_table.duplicate_selected)
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._on_clear_cargo)
        bar1.addWidget(add_btn)
        bar1.addWidget(rm_btn)
        bar1.addWidget(dup_btn)
        bar1.addStretch()
        bar1.addWidget(clear_btn)
        cargo_layout.addLayout(bar1)

        # Toolbar row 2: move up/down + bulk priority
        bar2 = QHBoxLayout()
        bar2.setSpacing(4)
        up_btn = QToolButton()
        up_btn.setText("▲")
        up_btn.setToolTip("Move selected rows up")
        up_btn.clicked.connect(lambda: self.cargo_table.move_selected(-1))
        dn_btn = QToolButton()
        dn_btn.setText("▼")
        dn_btn.setToolTip("Move selected rows down")
        dn_btn.clicked.connect(lambda: self.cargo_table.move_selected(1))
        bar2.addWidget(up_btn)
        bar2.addWidget(dn_btn)
        bar2.addSpacing(10)
        bar2.addWidget(QLabel("Set Priority:"))
        for p in range(1, MAX_PRIORITY + 1):
            b = QToolButton()
            b.setText(f"P{p}")
            b.setToolTip(f"Set priority {p} for selected rows")
            b.clicked.connect(lambda _checked=False, prio=p: self._on_bulk_priority(prio))
            bar2.addWidget(b)
        bar2.addStretch()
        self.capacity_label = QLabel("Total: 0 SCU")
        self.capacity_label.setObjectName("capacity_ok")
        bar2.addWidget(self.capacity_label)
        cargo_layout.addLayout(bar2)

        hint = QLabel(
            "Tip: same-priority rows cluster together (easier to unload). "
            "Drag the splitter to resize panels."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        cargo_layout.addWidget(hint)

        self.splitter.addWidget(cargo_box)

        # Results: 3D View + Summary tabs
        results_tabs = QTabWidget()
        self.viewer = QWebEngineView()
        # Theme sync: the viewer announces Style/Palette picks via its page
        # title; on load we push the app's saved theme into the viewer.
        self.viewer.titleChanged.connect(self._on_viewer_theme_changed)
        self.viewer.loadFinished.connect(self._on_viewer_loaded)
        self.viewer.load(QUrl.fromLocalFile(str(VIEWER_HTML)))
        results_tabs.addTab(self.viewer, "3D View")
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        self.results_view.setFont(QFont("Consolas", 10))
        results_tabs.addTab(self.results_view, "Summary")
        self.splitter.addWidget(results_tabs)
        self.splitter.setSizes([500, 700])

        root.addWidget(self.splitter, 1)

        # Optimize button
        self.optimize_btn = QPushButton("Optimize Packing")
        self.optimize_btn.setObjectName("optimize_btn")
        self.optimize_btn.setEnabled(False)
        self.optimize_btn.clicked.connect(self._on_optimize)
        self.optimize_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self.optimize_btn)

        # Status bar with model indicator
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("status_dot_loading")
        self.status_text = QLabel("Loading models…")
        self.status.addWidget(self.status_dot)
        self.status.addWidget(self.status_text, 1)

        if ship_names:
            self._on_ship_changed(ship_names[0])
        self._update_capacity_label()

    def _restore_state(self):
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        sizes = self.settings.value("splitter")
        if sizes:
            try:
                self.splitter.setSizes([int(x) for x in sizes])
            except Exception:
                pass

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.sizes())
        super().closeEvent(event)

    def _palette(self):
        return THEME_PALETTES.get(self.theme_palette, THEME_PALETTES["default"])

    def _apply_app_theme(self):
        app = QApplication.instance()
        if app:
            app.setStyleSheet(build_qss(self.theme_style, self.theme_palette))
        # Re-render rich-text labels that embed palette colors inline.
        if hasattr(self, "ship_combo"):
            self._on_ship_changed(self.ship_combo.currentText())

    def _on_viewer_loaded(self, ok):
        if not ok:
            return
        js = (f"window.setTheme && window.setTheme("
              f"{json.dumps(self.theme_style)}, {json.dumps(self.theme_palette)});")
        self.viewer.page().runJavaScript(js)

    def _on_viewer_theme_changed(self, title):
        parts = str(title).split("|")
        if len(parts) != 3 or parts[0] != "sc-theme":
            return
        style, palette = parts[1], parts[2]
        if style not in THEME_STYLES or palette not in THEME_PALETTES:
            return
        if (style, palette) == (self.theme_style, self.theme_palette):
            return
        self.theme_style = style
        self.theme_palette = palette
        self.settings.setValue("theme_style", style)
        self.settings.setValue("theme_palette", palette)
        self._apply_app_theme()

    def _selected_ship(self):
        name = self.ship_combo.currentText()
        for s in self.ships_data.get("ships", []):
            if s["name"] == name:
                return s
        return None

    def _on_ship_changed(self, _name):
        ship = self._selected_ship()
        if not ship:
            self.grid_info.setText("")
            return
        pal = self._palette()
        grids = ship.get("grids", [])
        total_vol = sum(grid_usable_volume(g) for g in grids)
        parts = [f"<b style='color:{pal['fg']}'>{len(grids)}</b> grid(s) · "
                 f"<b style='color:{pal['accent']}'>{total_vol:g}</b> usable SCU"]
        for g in grids:
            d = g["dimensions"]
            bounding_vol = d[0] * d[1] * d[2]
            usable_vol = grid_usable_volume(g)
            blocked_vol = bounding_vol - usable_vol
            blocked_note = f", {blocked_vol:g} blocked" if blocked_vol > 0 else ""
            parts.append(f"&nbsp;&nbsp;<span style='color:{pal['muted']}'>{g['name']}:</span> "
                         f"{d[0]}×{d[1]}×{d[2]} ({usable_vol:g} usable{blocked_note})")
        self.grid_info.setText("<br>".join(parts))
        self._update_capacity_label()
        self.setWindowTitle(f"Star Citizen Cargo Optimizer v{APP_VERSION} — {ship['name']}")

    def _ship_capacity(self):
        ship = self._selected_ship()
        if not ship:
            return 0
        return sum(grid_usable_volume(g) for g in ship.get("grids", []))

    def _update_capacity_label(self):
        cap = self._ship_capacity()
        total = self.cargo_table.total_volume()
        if cap <= 0:
            self.capacity_label.setText(f"Total: {total} SCU")
            self.capacity_label.setObjectName("capacity_ok")
        else:
            ratio = total / cap
            pct = ratio * 100
            self.capacity_label.setText(f"Total: {total} / {cap:g} SCU ({pct:.0f}%)")
            if total > cap:
                self.capacity_label.setObjectName("capacity_full")
            elif ratio > 0.85:
                self.capacity_label.setObjectName("capacity_warn")
            else:
                self.capacity_label.setObjectName("capacity_ok")
        # Re-apply stylesheet so objectName change takes effect
        self.capacity_label.style().unpolish(self.capacity_label)
        self.capacity_label.style().polish(self.capacity_label)

    def _start_model_load(self):
        self.loader = ModelLoader()
        self.loader.ready.connect(self._on_models_ready)
        self.loader.failed.connect(self._on_models_failed)
        self.loader.start()

    def _on_models_ready(self, router):
        self.router = router
        self.optimize_btn.setEnabled(True)
        self._set_status("ready", "Models loaded · Ready to optimize")

    def _on_models_failed(self, msg):
        self._set_status("error", "Model load failed")
        QMessageBox.critical(self, "Model Load Error", msg)

    def _set_status(self, kind, text):
        # kind in {"loading", "ready", "error"}
        self.status_dot.setObjectName(f"status_dot_{kind}")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_text.setText(text)

    def _refresh_preset_combo(self):
        self.preset_combo.clear()
        self.preset_combo.addItems(sorted(self.presets.keys()))

    def _on_save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in self.presets:
            confirm = QMessageBox.question(
                self, "Overwrite?",
                f"Preset '{name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return
        self.presets[name] = {
            "ship": self.ship_combo.currentText(),
            "manifest": self.cargo_table.to_manifest(),
        }
        save_presets(self.presets)
        self._refresh_preset_combo()
        self.preset_combo.setCurrentText(name)
        self._set_status("ready", f"Saved preset '{name}'")

    def _on_load_preset(self):
        name = self.preset_combo.currentText()
        if not name or name not in self.presets:
            return
        data = self.presets[name]
        ship = data.get("ship")
        if ship:
            idx = self.ship_combo.findText(ship)
            if idx >= 0:
                self.ship_combo.setCurrentIndex(idx)
            else:
                QMessageBox.warning(self, "Ship Missing",
                                    f"Ship '{ship}' from preset not found. Keeping current ship.")
        self.cargo_table.clear_all()
        for row in data.get("manifest", []):
            self.cargo_table.add_row(
                scu_type=row.get("scu_type", "1 SCU"),
                quantity=int(row.get("quantity", 1)),
                priority=int(row.get("priority", 1)),
            )
        self._set_status("ready", f"Loaded preset '{name}'")

    def _on_delete_preset(self):
        name = self.preset_combo.currentText()
        if not name or name not in self.presets:
            return
        confirm = QMessageBox.question(
            self, "Delete?", f"Delete preset '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        del self.presets[name]
        save_presets(self.presets)
        self._refresh_preset_combo()
        self._set_status("ready", f"Deleted preset '{name}'")

    def _on_clear_cargo(self):
        if self.cargo_table.rowCount() == 0:
            return
        confirm = QMessageBox.question(
            self, "Clear all cargo?", "Remove all rows from the manifest?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.cargo_table.clear_all()

    def _on_bulk_priority(self, p):
        if not self.cargo_table.set_priority_selected(p):
            self._set_status("ready", "Select rows first to set priority")

    def _on_optimize(self):
        ship = self._selected_ship()
        if not ship:
            QMessageBox.warning(self, "No Ship", "Select a ship first.")
            return
        manifest = self.cargo_table.to_manifest()
        if not manifest:
            QMessageBox.warning(self, "No Cargo", "Add at least one cargo row.")
            return
        ship_grids = [serialize_grid(g) for g in ship["grids"]]

        self.optimize_btn.setEnabled(False)
        self._set_status("loading", "Optimizing…")
        self.results_view.setPlainText("Running packing…")

        self.worker = PackingWorker(self.router, ship_grids, manifest)
        self.worker.done.connect(self._on_pack_done)
        self.worker.failed.connect(self._on_pack_failed)
        self.worker.start()

    def _on_pack_done(self, result):
        self.optimize_btn.setEnabled(True)
        sr = result.get("metrics", {}).get("success_rate", 0) * 100
        ut = result.get("metrics", {}).get("volume_utilization", 0) * 100
        self._set_status("ready", f"Done · SR {sr:.1f}% · Util {ut:.1f}%")
        self.results_view.setPlainText(self._format_result(result))
        self._push_to_viewer(result)

    def _push_to_viewer(self, result):
        payload = {
            "ship_grids": result.get("ship_grids", []),
            "placements": result.get("placements", []),
            "unplaced_items": result.get("unplaced_items", []),
            "metrics": result.get("metrics", {}),
        }
        data_json = json.dumps(payload, default=float)
        js = (
            "(function(){"
            "  if (!window.__rendererReady) {"
            "    return 'not-ready: ' + (window.__err || 'loadPacking undefined');"
            "  }"
            f"  try {{ window.loadPacking({data_json}); return 'ok'; }}"
            "  catch (e) { return 'err: ' + (e.message || e); }"
            "})();"
        )
        def _cb(msg):
            if msg != 'ok':
                print(f"[viewer] {msg}", flush=True)
                self._set_status("error", f"3D view: {msg}")
        self.viewer.page().runJavaScript(js, 0, _cb)

    def _on_pack_failed(self, msg):
        self.optimize_btn.setEnabled(True)
        self._set_status("error", "Packing failed")
        QMessageBox.critical(self, "Packing Error", msg)

    def _format_result(self, result):
        lines = []
        metrics = result.get("metrics", {})
        sr = metrics.get("success_rate", 0) * 100
        util = metrics.get("volume_utilization", 0) * 100
        placed = len(result.get("placements", []))
        unplaced = result.get("unplaced_items", [])

        lines.append("=" * 60)
        lines.append(f"Success rate:       {sr:.1f}% ({placed} placed)")
        lines.append(f"Volume utilization: {util:.1f}%")
        lines.append(f"Unplaced items:     {len(unplaced)}")
        lines.append("=" * 60)

        by_grid = {}
        for p in result.get("placements", []):
            by_grid.setdefault(p["grid_name"], []).append(p)

        for grid_name, items in by_grid.items():
            lines.append(f"\n[Grid: {grid_name}]  {len(items)} items")
            items.sort(key=lambda x: (x["priority"], x["position"][1]))
            for p in items:
                pos = p["position"]
                dims = p["dimensions"]
                lines.append(
                    f"  P{p['priority']}  {p['scu_type']:>8}  "
                    f"pos=({pos[0]:.1f},{pos[1]:.1f},{pos[2]:.1f})  "
                    f"dims=({dims[0]:.0f}×{dims[1]:.0f}×{dims[2]:.0f})"
                )

        if unplaced:
            lines.append("\n[Unplaced]")
            for u in unplaced:
                lines.append(f"  P{u['priority']}  {u['scu_type']}")

        diag = result.get("diagnostics")
        if diag:
            missed = diag.get("missed_placements", [])
            truly = diag.get("skipped_items", [])
            if missed or truly:
                lines.append("\n" + "=" * 60)
                lines.append("DIAGNOSTICS")
                lines.append("=" * 60)
            if missed:
                lines.append(f"\nMER tracking missed {len(missed)} feasible placement(s):")
                for m in missed:
                    lines.append(
                        f"  item#{m['item_idx']} dims={m['dims']} P{m['priority']} "
                        f"→ could fit at {m['feasible_position']} on '{m['grid_name']}' (rot={m['rotation']})"
                    )
            if truly:
                lines.append(f"\nNo-fit given current layout (upstream packing likely suboptimal): {len(truly)}")
                for s in truly:
                    lines.append(f"  item#{s['item_idx']} dims={s['dims']} P{s['priority']}")

        return "\n".join(lines)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Star Citizen Cargo Optimizer")
    app.setStyle("Fusion")
    win = MainWindow()  # applies the saved theme's stylesheet app-wide
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
