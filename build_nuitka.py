#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build script using Nuitka (alternative to PyInstaller).
Nuitka often has better antivirus reputation and doesn't require exclusions.

Installation:
    pip install nuitka

Usage:
    python build_nuitka.py
"""

import os
import sys
import subprocess
from pathlib import Path


def main():
    """Build the Windows EXE using Nuitka."""

    # Check if we're on Windows
    if sys.platform != "win32":
        print("=" * 60)
        print("⚠️  Warning: This build script is designed for Windows.")
        print("=" * 60)

    # Check if Nuitka is installed
    try:
        import nuitka
    except ImportError:
        print("❌ Nuitka is not installed.")
        print("   Installing Nuitka...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "nuitka"])
        print("✅ Nuitka installed.")

    # Get the project root directory
    project_root = Path(__file__).parent.absolute()
    os.chdir(project_root)

    print(f"📦 Building EXE with Nuitka from: {project_root}")
    print("=" * 60)

    # Check which optional modules are available
    optional_modules = []

    # Check for xlrd (optional, for .xls file support)
    try:
        import xlrd

        optional_modules.append("xlrd")
        print("✅ xlrd found (for .xls file support)")
    except ImportError:
        print("⚠️  xlrd not found (optional - for .xls file support)")

    # Nuitka command
    # Nuitka compiles to C++ and creates a standalone executable
    # Better antivirus reputation than PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",  # Create standalone executable
        "--onefile",  # Single file (Nuitka's onefile is faster than PyInstaller's)
        "--windows-console-mode=disable",  # No console window (updated syntax)
        "--enable-plugin=pyqt6",  # PyQt6 support
        "--include-package-data=gearledger",  # Include gearledger package
        "--include-module=PyQt6.QtCore",
        "--include-module=PyQt6.QtGui",
        "--include-module=PyQt6.QtWidgets",
        "--include-module=openpyxl",
        "--include-module=pandas",
        "--include-module=numpy",
        "--include-module=cv2",
        "--include-module=serial",
        "--include-module=openai",
        "--include-module=fuzzywuzzy",
        "--include-module=Levenshtein",
        "--include-module=PIL",
        "--include-module=multiprocessing",
        "--output-dir=dist",  # Output directory
        "--output-filename=GearLedger.exe",
        "app_desktop.py",
    ]

    # Add optional modules if available
    for module in optional_modules:
        cmd.insert(-1, f"--include-module={module}")

    print("🔨 Running Nuitka...")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)
    print("💡 Note: Nuitka compilation takes longer but produces faster executables")
    print("   with better antivirus reputation (usually no exclusions needed).")
    print("=" * 60)

    try:
        subprocess.check_call(cmd)
        print("=" * 60)
        print("✅ Build completed successfully!")
        print(f"📁 EXE location: {project_root / 'dist' / 'GearLedger.exe'}")
        print("\n💡 Nuitka executables typically have better antivirus reputation.")
        print("   You may not need Windows Defender exclusions!")
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
