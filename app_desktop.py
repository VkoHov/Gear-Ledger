# app_desktop.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, multiprocessing as mp

# Make local package importable when running from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication

# Import the modular main window
from gearledger.desktop.main_window import MainWindow


def main():
    # macOS-safe multiprocessing start method
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
