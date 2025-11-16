# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for GearLedger Windows EXE.
This file can be used directly with: pyinstaller GearLedger.spec
"""

import os
from pathlib import Path

block_cipher = None

# Get project root
project_root = Path(SPECPATH).parent

# Collect all data files
datas = [
    ('gearledger', 'gearledger'),
]

# Hidden imports (modules that PyInstaller might miss)
hiddenimports = [
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.QtOpenGL',
    'openpyxl',
    'openpyxl.cell._writer',
    'xlrd',
    'pandas',
    'pandas._libs.tslibs.timedeltas',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.np_datetime',
    'numpy',
    'cv2',
    'serial',
    'serial.serialutil',
    'openai',
    'fuzzywuzzy',
    'fuzzywuzzy.fuzz',
    'fuzzywuzzy.process',
    'Levenshtein',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'multiprocessing',
    'multiprocessing.pool',
    'multiprocessing.dummy',
]

a = Analysis(
    ['app_desktop.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use onedir instead of onefile for faster startup on Windows
# onefile extracts everything to temp on each launch (slow!)
# onedir creates a folder with the EXE and dependencies (much faster)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GearLedger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: 'path/to/icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GearLedger',
)

