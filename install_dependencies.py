#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Install all required dependencies for GearLedger.
This script installs all packages from requirements.txt, including:
- Core dependencies (OCR, GUI, data processing)
- Excel file support (openpyxl, xlrd, pyexcel for repair)
- Build tools (optional)

Usage:
    python install_dependencies.py
"""

import sys
import subprocess
import os
from pathlib import Path


def main():
    """Install all required dependencies from requirements.txt."""
    print("=" * 60)
    print("📦 Installing GearLedger Dependencies")
    print("=" * 60)
    print()

    # Get project root
    project_root = Path(__file__).parent.absolute()
    requirements_file = project_root / "requirements.txt"

    if not requirements_file.exists():
        print("❌ requirements.txt not found!")
        print(f"   Expected at: {requirements_file}")
        sys.exit(1)

    print(f"📄 Installing from: {requirements_file}")
    print()
    print("📦 This will install:")
    print("   • Core OCR (PaddleOCR, PaddlePaddle)")
    print("   • GUI framework (PyQt6)")
    print("   • Excel support (openpyxl, xlrd, pyexcel + plugins)")
    print("   • Data processing (pandas, numpy)")
    print("   • Image processing (Pillow)")
    print("   • Camera & Scale (opencv-python, pyserial)")
    print("   • Fuzzy matching (fuzzywuzzy, Levenshtein)")
    print("   • OpenAI API support")
    print("   • Text-to-speech (pyttsx3)")
    print()
    print("⏳ This may take a few minutes...")
    print()

    try:
        # Install all packages from requirements.txt
        print("🔨 Installing packages...")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "-r",
                str(requirements_file),
            ]
        )

        print()
        print("=" * 60)
        print("✅ All dependencies installed successfully!")
        print("=" * 60)
        print()
        print("📋 Installed packages include:")
        print("   • Core OCR (PaddleOCR)")
        print("   • GUI (PyQt6)")
        print("   • Excel support (openpyxl, xlrd, pyexcel)")
        print("   • Data processing (pandas, numpy)")
        print("   • Camera & Scale (opencv-python, pyserial)")
        print("   • Fuzzy matching (fuzzywuzzy, Levenshtein)")
        print("   • OpenAI API support")
        print()
        print("🚀 You can now:")
        print("   • Run the app: python app_desktop.py")
        print("   • Build EXE: python build_nuitka.py")
        print("   • Build EXE (PyInstaller): python build_exe.py")
        print()

    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print(f"❌ Installation failed with error code: {e.returncode}")
        print("   Check the output above for details.")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Installation failed with error: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
