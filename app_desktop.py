# app_desktop.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, multiprocessing as mp

# Make local package importable when running from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt6.QtGui import QIcon
from pathlib import Path

# Import the modular main window
from gearledger.desktop.main_window import MainWindow
from gearledger.desktop.settings_manager import load_settings
from gearledger.logging_utils import setup_logging, get_logger, get_log_path


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
    # Initialize file logging before anything else
    setup_logging()
    _log = get_logger(__name__)

    # macOS-safe multiprocessing start method
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

    # Load settings and inject into environment
    settings = load_settings()

    # One-time upgrade path for anyone still on the old "standalone"
    # storage mode — must run before any other code (including MainWindow
    # construction) reads network_mode, since it normalizes the persisted
    # value to "server" and imports any legacy results.xlsx into the DB.
    from gearledger.data_layer import migrate_legacy_standalone_storage

    settings = migrate_legacy_standalone_storage(settings)

    # Seed the runtime network mode from the persisted setting immediately.
    # get_network_mode() prefers _runtime_mode over settings, and that
    # global defaults to "server" until something calls set_runtime_mode()
    # - previously nothing did that synchronously, so the app always
    # rendered as Local/server mode on launch even when settings said
    # "client", until either the (deferred, async) auto-connect happened
    # to succeed or the user opened Network Settings (whose radio-toggle
    # handler was the only thing that set it eagerly).
    from gearledger.data_layer import set_runtime_mode

    set_runtime_mode("client" if settings.network_mode == "client" else "server")

    _log.info(
        "Settings: backend=%s lang=%s network=%s log_file=%s",
        settings.vision_backend,
        settings.language,
        settings.network_mode,
        get_log_path(),
    )

    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key

    os.environ["CAM_INDEX"] = str(settings.cam_index)
    os.environ["CAM_WIDTH"] = str(settings.cam_width)
    os.environ["CAM_HEIGHT"] = str(settings.cam_height)
    os.environ["VISION_BACKEND"] = settings.vision_backend

    # Load language setting
    from gearledger.desktop.translations import set_current_language
    from gearledger.speech import set_speech_language

    set_current_language(settings.language)
    set_speech_language(settings.language)  # Sync speech language with UI language

    app = QApplication(sys.argv)

    # Allow Ctrl+C in the terminal to quit the app cleanly.
    # PyQt's event loop blocks Python's SIGINT handler; a short QTimer lets
    # the interpreter check for signals between Qt events.
    import signal
    from PyQt6.QtCore import QTimer

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    _sigint_timer = QTimer()
    _sigint_timer.setInterval(200)
    _sigint_timer.timeout.connect(lambda: None)  # wake Python interpreter
    _sigint_timer.start()

    # Set application icon if available
    _set_application_icon(app)

    # Require a cloud account before the app can be used at all -- and, as
    # of 2026-08-28, require it to be verified *live* on every launch, not
    # just present locally. Earlier this gate only checked token
    # presence, deliberately, so the app stayed usable offline; that left
    # a real loophole (a deactivated account could keep using the app
    # forever just by never reconnecting), and the explicit product
    # decision was to close it even at the cost of the offline-friendly
    # launch: a genuine network outage (the user's or the server's) now
    # blocks launch entirely too. This is a real tradeoff, not a free
    # win -- see SAAS_ROADMAP.md's "how much offline fallback matters"
    # open question, which this resolves in favor of strict enforcement.
    from gearledger.desktop import settings_manager as _sm
    from gearledger.desktop.login_dialog import LoginDialog
    from gearledger.desktop.translations import tr

    def _require_active_online_account_or_exit():
        """Blocks until there's a stored token AND a live connection
        proves it's both valid and active, or the user gives up (Close).
        Declining login, or closing on a Retry/Close prompt, exits the
        whole process. Reused both for the initial launch and — via the
        main-window loop below — after a Logout."""
        from gearledger.api_client import (
            connect_to_server,
            get_last_connect_error,
            disconnect_from_server,
        )

        while True:
            token = _sm.get_auth_token()
            current_settings = _sm.load_settings()

            if not token or not current_settings.cloud_server_url:
                login_dlg = LoginDialog(required=True)
                if login_dlg.exec() != QDialog.DialogCode.Accepted or not login_dlg.result:
                    sys.exit(0)
                continue  # re-check now that login just saved a token

            client = connect_to_server(
                current_settings.cloud_server_url, refresh_token=token
            )
            if client:
                # Just a validation probe -- MainWindow's own connection
                # logic handles the real connect-for-actual-use from a
                # clean slate, based on the user's chosen network_mode.
                disconnect_from_server()
                return

            detail = get_last_connect_error()
            if detail == "UNAUTHORIZED":
                _sm.clear_auth()
                continue  # loop back -> no token now -> re-prompt login

            if detail == "ACCOUNT_INACTIVE":
                message = tr("account_inactive_message")
            elif detail == "NO_NETWORK":
                message = tr("no_network_launch_message")
            else:
                message = tr("server_unreachable_launch_message")

            reply = QMessageBox.question(
                None,
                tr("cloud_login_title"),
                message,
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Close,
                QMessageBox.StandardButton.Retry,
            )
            if reply == QMessageBox.StandardButton.Close:
                sys.exit(0)
            # else Retry -> loop and try again

    _require_active_online_account_or_exit()

    # Validate API key if OpenAI backend is selected (after QApplication is created)
    if settings.vision_backend == "openai" and settings.openai_api_key:

        def _validate_openai_api_key(api_key: str) -> tuple[bool, str]:
            """Validate OpenAI API key by making a test API call."""
            if not api_key:
                return False, "API key is empty"

            if not api_key.startswith("sk-"):
                return False, "API key format is invalid (should start with 'sk-')"

            try:
                from openai import OpenAI

                client = OpenAI(api_key=api_key)
                # Try with limit first (newer API versions), fallback without limit
                try:
                    list(client.models.list(limit=1))
                except TypeError:
                    # If limit is not supported, try without it
                    list(client.models.list())
                return True, ""
            except Exception as e:
                error_msg = str(e)
                if "Invalid API key" in error_msg or "Incorrect API key" in error_msg:
                    return (
                        False,
                        "Invalid API key. Please check your key and try again.",
                    )
                elif "authentication" in error_msg.lower() or "401" in error_msg:
                    return False, "Authentication failed. Please check your API key."
                else:
                    return (
                        True,
                        f"Warning: Could not verify API key ({error_msg[:100]})",
                    )

        is_valid, error_msg = _validate_openai_api_key(settings.openai_api_key)

        if not is_valid:
            QMessageBox.critical(
                None,
                "Invalid API Key",
                f"Your OpenAI API key appears to be invalid:\n\n{error_msg}\n\n"
                "Please update it in Settings.\n\n"
                "You can get your API key from: https://platform.openai.com/api-keys",
            )
            # Continue anyway - user can fix it in settings

    # Show settings dialog on first launch if API key is missing and using OpenAI
    if not settings.openai_api_key and settings.vision_backend == "openai":
        from gearledger.desktop.settings_page import SettingsPage

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

    # Normally runs once. Logging out (Network Settings -> Logout) closes
    # MainWindow the same way any normal close does, but sets
    # win._logout_requested first (see MainWindow._on_logout_requested) --
    # that's the signal to drop back to the login gate and rebuild the
    # window in-process instead of exiting, so logging out doesn't force a
    # full manual relaunch to log back in.
    while True:
        win = MainWindow()
        win.show()

        # Check if catalog file is required and not set
        win._ensure_catalog_file()

        exit_code = app.exec()

        if not getattr(win, "_logout_requested", False):
            sys.exit(exit_code)

        _require_active_online_account_or_exit()


if __name__ == "__main__":
    main()
