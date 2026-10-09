# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path
import os
import sys

# Conda keeps Tk and other native dependencies outside the Python executable directory.
# Make their location explicit so builds also work without an activated Conda shell.
conda_bin = Path(sys.prefix) / "Library" / "bin"
if conda_bin.is_dir():
    os.environ["PATH"] = str(conda_bin) + os.pathsep + os.environ.get("PATH", "")

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('tkinterdnd2'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'scipy', 'matplotlib', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PDF-Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
