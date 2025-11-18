# app_desktop.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, multiprocessing as mp

# Make local package importable when running from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from pathlib import Path

# Import the modular main window
from gearledger.desktop.main_window import MainWindow
from gearledger.desktop.settings_manager import load_settings


def _set_application_icon(app: QApplication):
    """Set the application icon from icon.ico or icon.png if available."""
    # Try multiple possible locations for icon files
    possible_paths = [
        Path(__file__).parent / "icon.ico",  # Project root - ICO
        Path(__file__).parent / "icon.png",  # Project root - PNG (for macOS)
        Path.cwd() / "icon.ico",  # Current working directory - ICO
        Path.cwd() / "icon.png",  # Current working directory - PNG
    ]

    # Also check if running as EXE (PyInstaller/Nuitka)
    if hasattr(sys, "_MEIPASS"):  # PyInstaller
        possible_paths.insert(0, Path(sys._MEIPASS) / "icon.ico")
        possible_paths.insert(1, Path(sys._MEIPASS) / "icon.png")
    if hasattr(sys, "_NUITKA_ONEFILE_TEMP"):  # Nuitka onefile
        possible_paths.insert(0, Path(sys._NUITKA_ONEFILE_TEMP) / "icon.ico")
        possible_paths.insert(1, Path(sys._NUITKA_ONEFILE_TEMP) / "icon.png")

    # Try to find and load icon
    for icon_path in possible_paths:
        if icon_path.exists():
            try:
                app.setWindowIcon(QIcon(str(icon_path)))
                return
            except Exception:
                pass


def main():
    # macOS-safe multiprocessing start method
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

    # Load settings and inject into environment
    settings = load_settings()

    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    os.environ["CAM_INDEX"] = str(settings.cam_index)
    os.environ["CAM_WIDTH"] = str(settings.cam_width)
    os.environ["CAM_HEIGHT"] = str(settings.cam_height)
    os.environ["VISION_BACKEND"] = settings.vision_backend

    app = QApplication(sys.argv)

    # Set application icon if available
    _set_application_icon(app)

    # Show settings dialog on first launch if API key is missing and using OpenAI
    if not settings.openai_api_key and settings.vision_backend == "openai":
        from gearledger.desktop.settings_page import SettingsPage
        from PyQt6.QtWidgets import QDialog

        dlg = QDialog()
        dlg.setWindowTitle("Gear Ledger - Initial Setup")
        dlg.setMinimumWidth(600)
        layout = dlg.layout() if dlg.layout() else None
        if not layout:
            from PyQt6.QtWidgets import QVBoxLayout

            layout = QVBoxLayout(dlg)

        settings_page = SettingsPage(dlg)
        layout.addWidget(settings_page)

        # Override save to close dialog
        original_save = settings_page._on_save

        def save_and_close():
            original_save()
            dlg.accept()

        settings_page._on_save = save_and_close

        # Show dialog
        dlg.exec()

        # Reload settings after dialog
        settings = load_settings()
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
