# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SC Cargo Optimizer.

Build:
    pyinstaller app.spec
        # uses whatever torch is in the current env (CPU or CUDA).
        # set BUILD_VARIANT=cpu (or gpu) before invocation to tag dist folder.

Output: dist/SCCargoOptimizer-<variant>/SCCargoOptimizer.exe
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Tag the dist folder by build variant so CPU and GPU builds can coexist.
VARIANT = os.environ.get("BUILD_VARIANT", "gpu").strip().lower()
DIST_NAME = f"SCCargoOptimizer-{VARIANT}"

# Collect dynamically-loaded packages. torch and torch_geometric pull in many
# C extensions and submodules at runtime, so collect_all is the safe option.
torch_d, torch_b, torch_h = collect_all("torch")
tg_d, tg_b, tg_h = collect_all("torch_geometric")
shiboken_d, shiboken_b, shiboken_h = collect_all("shiboken6")

# PySide6: only the modules we actually use. PyInstaller's per-module hooks
# (e.g. hook-PySide6.QtWidgets.py) pull in their required binaries automatically.
# Avoid collect_all here — it would drag in Qt3D, QtMultimedia, QtNfc, QtQuick3D,
# QtPdf, etc., which roughly doubles the bundle size for no benefit.
pyside_d = []
pyside_b = []
pyside_h = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",         # required by QtWebEngine
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
]

# Optional torch_geometric companions — collect if present, skip if not.
optional_collected = []
for opt in ("torch_scatter", "torch_sparse", "torch_cluster", "torch_spline_conv"):
    try:
        d, b, h = collect_all(opt)
        optional_collected.append((d, b, h))
    except Exception:
        pass

opt_d = sum((x[0] for x in optional_collected), [])
opt_b = sum((x[1] for x in optional_collected), [])
opt_h = sum((x[2] for x in optional_collected), [])

a = Analysis(
    ["src/desktop_app.py"],
    pathex=["src"],
    binaries=torch_b + tg_b + pyside_b + shiboken_b + opt_b,
    datas=[
        ("frontend", "frontend"),
        ("ships_cargo_grids.json", "."),
        ("small_gnn_model.pt", "."),
        ("medium_gnn_model.pt", "."),
        ("large_gnn_model.pt", "."),
    ] + torch_d + tg_d + pyside_d + shiboken_d + opt_d,
    hiddenimports=[
        "scu_manifest_generator",
        "ensemble_inference",
        "packing_core",
        "packing_core.box3d",
        "packing_core.drl_env",
        "packing_core.grid_utils",
        "packing_core.mer_manager",
        "packing_core.models",
        "packing_core.utils",
    ] + torch_h + tg_h + pyside_h + shiboken_h + opt_h,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib.tests",
        "numpy.tests",
        "torch.test",
        "torch.testing",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SCCargoOptimizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX often breaks Qt DLLs; leave off
    console=False,       # windowed app — no console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # add a .ico path here when one's ready
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=DIST_NAME,
)
