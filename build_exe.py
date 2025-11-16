#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build script for creating Windows EXE from GearLedger desktop app.
Run this script on Windows to build the executable.

Usage:
    python build_exe.py
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def main():
    """Build the Windows EXE using PyInstaller."""

    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("❌ PyInstaller is not installed.")
        print("   Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller installed.")

    # Get the project root directory
    project_root = Path(__file__).parent.absolute()
    os.chdir(project_root)

    print(f"📦 Building EXE from: {project_root}")
    print("=" * 60)

    # PyInstaller command
    # Using --onedir instead of --onefile for MUCH faster startup on Windows
    # --onefile extracts to temp on every launch (very slow!)
    # --onedir creates a folder (faster startup, easier distribution)
    cmd = [
        "pyinstaller",
        "--name=GearLedger",
        "--windowed",  # No console window
        "--onedir",  # Folder with EXE (faster than onefile on Windows)
        "--icon=NONE",  # You can add an icon file later if needed
        f"--add-data=gearledger{os.pathsep}gearledger",  # Include the gearledger package (Windows uses ;)
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=openpyxl",
        "--hidden-import=xlrd",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=cv2",
        "--hidden-import=serial",
        "--hidden-import=openai",
        "--hidden-import=fuzzywuzzy",
        "--hidden-import=Levenshtein",
        "--hidden-import=PIL",
        "--hidden-import=multiprocessing",
        "--collect-all=PyQt6",
        "--collect-all=openpyxl",
        "--collect-all=pandas",
        "--collect-all=numpy",
        "--collect-all=cv2",
        "--noconfirm",  # Overwrite existing dist/build folders
        "app_desktop.py",
    ]

    print("🔨 Running PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        subprocess.check_call(cmd)
        print("=" * 60)
        print("✅ Build completed successfully!")
        print(f"📁 EXE location: {project_root / 'dist' / 'GearLedger.exe'}")
        print(
            "\n💡 Note: The first run may be slower as Windows Defender scans the new executable."
        )
    except subprocess.CalledProcessError as e:
        print("=" * 60)
        print(f"❌ Build failed with error code: {e.returncode}")
        print("   Check the output above for details.")
        sys.exit(1)
    except Exception as e:
        print("=" * 60)
        print(f"❌ Build failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
