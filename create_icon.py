#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Helper script to convert PNG image to ICO format for Windows app icon.

Usage:
    python create_icon.py logo.png

This will create icon.ico in the project root.
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("❌ Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)


def create_icon(png_path: str, output_path: str = "icon.ico"):
    """Convert PNG to ICO format with multiple sizes."""
    png_file = Path(png_path)

    if not png_file.exists():
        print(f"❌ File not found: {png_path}")
        sys.exit(1)

    try:
        # Open the PNG image
        img = Image.open(png_file)

        # Create ICO with multiple sizes (Windows prefers these sizes)
        sizes = [(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]

        # Save as ICO
        img.save(output_path, format="ICO", sizes=sizes)

        print(f"✅ Created {output_path} from {png_path}")
        print(f"   Icon includes sizes: {', '.join(f'{w}x{h}' for w, h in sizes)}")

    except Exception as e:
        print(f"❌ Error creating icon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_icon.py <png_file> [output.ico]")
        print("\nExample:")
        print("  python create_icon.py logo.png")
        print("  python create_icon.py logo.png icon.ico")
        sys.exit(1)

    png_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "icon.ico"

    create_icon(png_path, output_path)
