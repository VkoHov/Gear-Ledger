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

    # Get the project root directory
    project_root = Path(__file__).parent.absolute()
    os.chdir(project_root)

    # Check if we should use install_dependencies.py first
    install_script = project_root / "install_dependencies.py"
    use_install_script = False

    if install_script.exists():
        # Check if key dependencies are missing
        try:
            import PyQt6
            import pandas
            import openpyxl
        except ImportError:
            use_install_script = True

    if use_install_script:
        print("=" * 60)
        print("📦 Installing dependencies from requirements.txt...")
        print("=" * 60)
        try:
            subprocess.check_call([sys.executable, str(install_script)])
            print()
        except Exception as e:
            print(f"⚠️  Auto-install failed: {e}")
            print("   Continuing with manual dependency check...")
            print()

    print("=" * 60)
    print("📦 Checking and installing required dependencies...")
    print("=" * 60)

    # Required modules for the build (mapping: import_name -> pip_package_name)
    required_modules = {
        "nuitka": "nuitka",
        "PyQt6": "PyQt6",
        "openpyxl": "openpyxl",
        "pandas": "pandas",
        "numpy": "numpy",
        "cv2": "opencv-python",
        "serial": "pyserial",
        "openai": "openai",
        "fuzzywuzzy": "fuzzywuzzy",
        "Levenshtein": "python-Levenshtein",
        "PIL": "Pillow",
    }

    # Check and install required modules
    missing_required = []
    for import_name, pip_name in required_modules.items():
        try:
            if import_name == "cv2":
                import cv2
            elif import_name == "serial":
                import serial
            elif import_name == "PIL":
                from PIL import Image
            elif import_name == "Levenshtein":
                import Levenshtein
            else:
                __import__(import_name)
            print(f"✅ {import_name} is installed")
        except ImportError:
            print(f"❌ {import_name} is missing")
            missing_required.append(pip_name)

    # Install missing required modules
    if missing_required:
        print(f"\n📥 Installing missing modules: {', '.join(missing_required)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing_required
        )
        print("✅ All required modules installed!\n")

    # Check optional modules
    optional_modules = []
    optional_packages = {"xlrd": "xlrd"}

    for import_name, pip_name in optional_packages.items():
        try:
            __import__(import_name)
            optional_modules.append(import_name)
            print(f"✅ {import_name} found (optional - for .xls file support)")
        except ImportError:
            print(f"⚠️  {import_name} not found (optional - for .xls file support)")

    print("=" * 60)
    print(f"📦 Building EXE with Nuitka from: {project_root}")
    print("=" * 60)

    # Clean previous build (optional but recommended)
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        import shutil

        print(f"🧹 Cleaning previous build in {dist_dir}...")
        try:
            shutil.rmtree(dist_dir)
            print("✅ Previous build cleaned")
        except Exception as e:
            print(f"⚠️  Could not clean dist folder: {e}")
            print("   Continuing anyway...")

    # Check for icon file
    icon_path = project_root / "icon.ico"
    if icon_path.exists():
        print(f"✅ Found icon file: {icon_path}")
    else:
        print("⚠️  No icon.ico found - EXE will use default Windows icon")
        print("   Place icon.ico in project root to add a custom icon")

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

    # Add icon if available
    if icon_path.exists():
        cmd.insert(-1, f"--windows-icon-from-ico={icon_path}")

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
