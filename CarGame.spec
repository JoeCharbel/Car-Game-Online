# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for Car Game.

Build with:  py -3.14 -m PyInstaller --noconfirm --clean CarGame.spec
Output:      dist/CarGame/CarGame.exe  (folder build)
"""

import glob
import os

HERE = SPECPATH  # injected by PyInstaller: folder holding this spec

# Every sprite ships inside the bundle; paths.py finds them via _MEIPASS.
datas = [(path, ".") for path in sorted(glob.glob(os.path.join(HERE, "*.png")))]

a = Analysis(
    [os.path.join(HERE, "game.py")],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CarGame",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="CarGame",
)
