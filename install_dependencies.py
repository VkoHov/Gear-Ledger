#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Install all required dependencies for GearLedger.
Run this before building the EXE.

Usage:
    python install_dependencies.py
"""

import sys
import subprocess

# All required dependencies
REQUIRED_PACKAGES = [
    "nuitka",  # Build tool
    "PyQt6",  # GUI framework
    "openpyxl",  # Excel files (.xlsx)
    "xlrd>=2.0.1",  # Excel files (.xls) - optional but recommended
    "pandas",  # Data processing
    "numpy",  # Numerical operations
    "opencv-python",  # Camera (imported as cv2)
    "pyserial",  # Scale communication (imported as serial)
    "openai",  # OpenAI API
    "fuzzywuzzy",  # Fuzzy matching
    "python-Levenshtein",  # Fuzzy matching performance
    "Pillow",  # Image processing (imported as PIL)
]


def main():
    """Install all required dependencies."""
    print("=" * 60)
    print("📦 Installing GearLedger Dependencies")
    print("=" * 60)
    print()

    print("Installing packages:")
    for package in REQUIRED_PACKAGES:
        print(f"  - {package}")

    print()
    print("This may take a few minutes...")
    print()

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade"] + REQUIRED_PACKAGES
        )

        print()
        print("=" * 60)
        print("✅ All dependencies installed successfully!")
        print("=" * 60)
        print()
        print("You can now build the EXE:")
        print("  python build_nuitka.py")
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
