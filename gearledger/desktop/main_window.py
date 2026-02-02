# gearledger/desktop/main_window.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QSplitter,
    QPushButton,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
)
from PyQt6.QtGui import QFont

# Import our modular components
from .camera_widget import CameraWidget
from .settings_widget import SettingsWidget
from .results_widget import ResultsWidget
from .logs_widget import LogsWidget
from .results_pane import ResultsPane
from .process_helpers import ProcessManager
from .scale_widget import ScaleWidget
from .translations import tr
from .sse_client import SSEClientThread

# Optional speech helpers (guarded)
try:
    from gearledger.speech import speak, speak_match, speak_name, _spell_code
except Exception as e:
    # If anything goes wrong importing speech, log it so we can see why
    # and fall back to no-op implementations instead of crashing.
    try:
        import traceback

        print("[MAIN_WINDOW] Failed to import gearledger.speech:", e)
        traceback.print_exc()
    except Exception:
        pass

    def speak(*a, **k):
        pass

    def speak_match(*a, **k):
        pass

    def speak_name(*a, **k):
        pass  # Speech not available, silently ignore

    def _spell_code(x):
        return x


class NameConfirmationDialog(QDialog):
    """Custom dialog for confirming user/client name after successful entry."""

    def __init__(self, parent, client_name: str):
        super().__init__(parent)
        self.client_name = client_name
        self._setup_ui()
        # Speak only the client name when dialog opens
        speak_name(client_name)

    def _setup_ui(self):
        """Set up the dialog UI with improved layout and typography."""
        self.setWindowTitle(tr("manual_entry_success"))
        self.setMinimumSize(700, 400)  # Increased to accommodate larger text
        self.setModal(True)

        # Center dialog on parent window
        if self.parent():
            parent_geometry = self.parent().geometry()
            dialog_size = self.sizeHint()
            x = (
                parent_geometry.x()
                + (parent_geometry.width() - dialog_size.width()) // 2
            )
            y = (
                parent_geometry.y()
                + (parent_geometry.height() - dialog_size.height()) // 2
            )
            self.move(x, y)

        # Main layout with generous padding
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(32, 32, 32, 32)

        # Client name as main headline
        name_label = QLabel(self.client_name)
        name_font = QFont()
        name_font.setPointSize(84)  # Doubled from 42 to 84
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        # Use font-size in stylesheet as well to ensure it's applied
        name_label.setStyleSheet(
            """
            color: #2c3e50;
            padding: 16px;
            background-color: #f8f9fa;
            border-radius: 8px;
            font-size: 84pt;
            font-weight: bold;
        """
        )
        main_layout.addWidget(name_label)

        # Friendly confirmation message
        confirmation_label = QLabel(tr("entry_saved_confirmation"))
        confirmation_font = QFont()
        confirmation_font.setPointSize(18)  # Increased from 14 to 18
        confirmation_label.setFont(confirmation_font)
        confirmation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        confirmation_label.setWordWrap(True)
        confirmation_label.setStyleSheet("color: #5a6c7d; padding: 12px;")
        main_layout.addWidget(confirmation_label)

        # Add stretch to push buttons down
        main_layout.addStretch()

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        # Copy name button (optional secondary action)
        copy_btn = QPushButton(tr("copy_name"))
        copy_btn.setMinimumHeight(48)  # Increased from 40 to 48
        copy_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #e9ecef;
                color: #495057;
                border: 1px solid #ced4da;
                border-radius: 6px;
                padding: 10px 20px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #dee2e6;
            }
            QPushButton:pressed {
                background-color: #ced4da;
            }
        """
        )
        copy_btn.clicked.connect(self._copy_name)
        button_layout.addWidget(copy_btn)

        button_layout.addStretch()

        # OK button (primary action) - detect language
        try:
            from gearledger.speech import get_speech_language

            current_lang = get_speech_language()
        except Exception:
            current_lang = "en"
        ok_text = "OK" if current_lang == "en" else "ОК"
        ok_btn = QPushButton(ok_text)
        ok_btn.setMinimumHeight(48)  # Increased from 40 to 48
        ok_btn.setMinimumWidth(140)  # Increased from 120 to 140
        ok_btn.setDefault(True)
        ok_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 28px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """
        )
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        main_layout.addLayout(button_layout)

    def _copy_name(self):
        """Copy the client name to clipboard."""
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(self.client_name)


class MainWindow(QWidget):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gear Ledger")
        self.resize(1100, 820)

        # Try to load icon from file
        self._set_window_icon()

        # Apply global application styling
        self._apply_styling()

        # Initialize process manager
        self.process_manager = ProcessManager()

        # Initialize widgets (lightweight first)
        self._setup_widgets()
        self._setup_connections()
        self._setup_layout()
        self._setup_timers()

        # Initialize state (non-blocking)
        # Use QTimer to defer heavy operations
        QTimer.singleShot(0, lambda: self.append_logs(["Ready."]))
        self._update_controls()

        # Apply initial logs visibility setting
        self._update_logs_visibility()

        # Register client change callback if server is already running
        QTimer.singleShot(100, self._register_server_callbacks)
        # Auto-set uploaded catalog if server is running but no catalog is selected
        QTimer.singleShot(200, self._auto_set_uploaded_catalog)

        # Initialize client connection sequentially on startup if in client mode
        QTimer.singleShot(300, self._initialize_client_connection)

    def _set_window_icon(self):
        """Set the window icon from icon.ico or icon.png file if available."""
        # Try multiple possible locations for icon files
        possible_paths = [
            Path(__file__).parent.parent.parent / "icon.ico",  # Project root - ICO
            Path(__file__).parent.parent.parent / "icon.png",  # Project root - PNG
            Path.cwd() / "icon.ico",  # Current working directory - ICO
            Path.cwd() / "icon.png",  # Current working directory - PNG
            Path(__file__).parent / "icon.ico",  # Desktop folder - ICO
            Path(__file__).parent / "icon.png",  # Desktop folder - PNG
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
                    self.setWindowIcon(QIcon(str(icon_path)))
                    return
                except Exception:
                    pass

        # Fallback: use application icon if set
        from PyQt6.QtWidgets import QApplication

        app_icon = QApplication.instance().windowIcon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
            return

        # Final fallback to system theme icon
        try:
            self.setWindowIcon(QIcon.fromTheme("applications-graphics"))
        except Exception:
            pass

    def _apply_styling(self):
        """Apply global application styling."""
        self.setStyleSheet(
            """
            QWidget {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-family: Arial, sans-serif;
                font-size: 11px;
            }
            
            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #34495e;
                background-color: #ffffff;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                min-height: 20px;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #21618c;
            }
            
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            
            QLineEdit {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                font-size: 11px;
                selection-background-color: #3498db;
            }
            
            QLineEdit:focus {
                border-color: #3498db;
            }
            
            QLineEdit:read-only {
                background-color: #ecf0f1;
                color: #7f8c8d;
            }
            
            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 6px;
                background-color: #ffffff;
                font-size: 11px;
                min-width: 100px;
            }
            
            QComboBox:focus {
                border-color: #3498db;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #7f8c8d;
                margin-right: 5px;
            }
            
            QComboBox QAbstractItemView {
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
                selection-background-color: #3498db;
                selection-color: white;
            }
            
            QRadioButton {
                font-size: 11px;
                color: #2c3e50;
                spacing: 8px;
            }
            
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
            }
            
            QRadioButton::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
            }
            
            QRadioButton::indicator:hover {
                border-color: #3498db;
            }
            
            QCheckBox {
                font-size: 11px;
                color: #2c3e50;
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
            }
            
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }
            
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
            
            QListWidget {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ffffff;
                selection-background-color: #3498db;
                selection-color: white;
                font-size: 11px;
            }
            
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #ecf0f1;
            }
            
            QListWidget::item:hover {
                background-color: #e8f4fd;
            }
            
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QTextEdit {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #0b1220;
                color: #e5e7eb;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
                padding: 8px;
            }
            
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            
            QScrollBar:vertical {
                background-color: #ecf0f1;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #bdc3c7;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #95a5a6;
            }
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QSplitter::handle {
                background-color: #bdc3c7;
                height: 3px;
            }
            
            QSplitter::handle:hover {
                background-color: #3498db;
            }
        """
        )

    def _setup_widgets(self):
        """Initialize all widgets."""
        # Settings widget
        self.settings_widget = SettingsWidget()

        # Camera widget
        self.camera_widget = CameraWidget()

        # Results widget
        self.results_widget = ResultsWidget()

        # Logs widget
        self.logs_widget = LogsWidget()

        # Scale widget
        self.scale_widget = ScaleWidget()

        # Results pane (Excel table)
        self.results_pane = ResultsPane(self.settings_widget.get_results_path())

    def _setup_connections(self):
        """Set up signal connections between widgets."""
        # Camera capture callback
        self.camera_widget.set_capture_callback(self._on_camera_capture)
        # Camera manual code callback
        self.camera_widget.set_manual_code_callback(self._on_manual_code_submitted)

        # Settings callbacks
        self.settings_widget.set_catalog_changed_callback(self._on_catalog_path_changed)
        self.settings_widget.set_results_changed_callback(self._on_results_path_changed)
        self.settings_widget.set_results_refresh_callback(self.results_pane.refresh)
        self.settings_widget.set_manual_entry_requested_callback(
            self._on_manual_entry_requested
        )
        self.settings_widget.set_generate_invoice_requested_callback(
            self._on_generate_invoice_requested
        )

        # Results widget callbacks
        self.results_widget.set_fuzzy_requested_callback(self._on_fuzzy_requested)
        self.results_widget.set_manual_search_requested_callback(
            self._on_manual_search_requested
        )

        # Scale widget callbacks
        self.scale_widget.set_weight_ready_callback(self._on_weight_ready)
        self.scale_widget.weight_changed.connect(self._on_weight_changed)
        self.scale_widget.manual_weight_set.connect(self._on_manual_weight_set)
        self.scale_widget.set_log_callback(self.append_logs)

        # Track if camera was auto-started by scale
        self._camera_auto_started = False

    def _setup_layout(self):
        """Set up the main layout."""
        # Root layout
        outer = QVBoxLayout()

        # Add settings buttons at the top
        settings_btn_layout = QHBoxLayout()
        settings_btn_layout.addStretch(1)

        # Network status label (shows current mode and connection status)
        self.network_status_label = QLabel("")
        self.network_status_label.setStyleSheet(
            """
            QLabel {
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
        """
        )
        self._update_network_status()
        settings_btn_layout.addWidget(self.network_status_label)

        # Client initialization progress label (shows initialization steps)
        self.client_init_progress_label = QLabel("")
        self.client_init_progress_label.setStyleSheet(
            """
            QLabel {
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 10px;
                background-color: #ecf0f1;
                color: #2c3e50;
            }
        """
        )
        self.client_init_progress_label.setVisible(False)
        settings_btn_layout.addWidget(self.client_init_progress_label)

        # Network settings button
        self.network_settings_btn = QPushButton("🌐 " + tr("network_configuration"))
        self.network_settings_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """
        )
        self.network_settings_btn.clicked.connect(self._open_network_settings)
        settings_btn_layout.addWidget(self.network_settings_btn)

        # Settings button
        self.settings_btn = QPushButton(tr("settings_button"))
        self.settings_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """
        )
        self.settings_btn.clicked.connect(self._open_settings)
        settings_btn_layout.addWidget(self.settings_btn)
        outer.addLayout(settings_btn_layout)

        # Add Settings widget (file selection)
        outer.addWidget(self.settings_widget)

        # Create main content area
        main_content = self._create_main_content()

        # Splitter for resizable layout (main content on top, results pane on bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(main_content)
        splitter.addWidget(self.results_pane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer.addWidget(splitter)
        self.setLayout(outer)

    def _create_main_content(self) -> QWidget:
        """Create the main content area with scale and camera."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container for scrollable content
        container = QWidget()
        container_layout = QVBoxLayout(container)

        # Scale and Camera side by side with resizable splitter
        scale_camera_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Set minimum widths to ensure all important info is visible
        # Scale widget: compact - just weight display and buttons
        self.scale_widget.setMinimumWidth(200)
        # Camera widget: needs space for preview and 3 buttons
        self.camera_widget.setMinimumWidth(480)

        # Add widgets to splitter with stretch factors
        scale_camera_splitter.addWidget(self.scale_widget)
        scale_camera_splitter.addWidget(self.camera_widget)

        # Set stretch factors (camera gets more space initially)
        scale_camera_splitter.setStretchFactor(0, 1)  # Scale widget
        scale_camera_splitter.setStretchFactor(1, 2)  # Camera widget

        # Set initial sizes (scale: 30%, camera: 70%)
        scale_camera_splitter.setSizes([300, 700])

        container_layout.addWidget(scale_camera_splitter)

        # Add results widget
        container_layout.addWidget(self.results_widget)

        # Add logs widget
        container_layout.addWidget(self.logs_widget, 1)

        # Store reference to container layout for updating logs visibility
        self.main_container_layout = container_layout

        # Make scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(container)

        layout.addWidget(scroll)
        return widget

    def _setup_timers(self):
        """Set up polling timers for process queues."""
        self.poll_main_timer = QTimer(self)
        self.poll_main_timer.timeout.connect(self._poll_main_queue)

        self.poll_fuzzy_timer = QTimer(self)
        self.poll_fuzzy_timer.timeout.connect(self._poll_fuzzy_queue)

        # Sync version tracking for catalog sync in client mode
        self._sync_version = 0
        # SSE client for real-time event notifications (replaces polling timer)
        self._sse_client: Optional[Any] = None
        # Flag to prevent concurrent catalog sync requests
        self._syncing_catalog = False
        # Flag to track if client is fully initialized (to avoid re-initialization on reconnection)
        self._client_initialized = False
        # Start SSE connection in client mode (will be updated when mode changes)
        self._update_sse_connection()

    def _update_controls(self):
        """Update control states based on process status and catalog availability."""
        busy = self.process_manager.any_running
        catalog_valid = self.settings_widget.validate_catalog()

        # Check if client is initialized (in client mode)
        from gearledger.data_layer import get_network_mode

        mode = get_network_mode()
        client_ready = True
        if mode == "client":
            client_ready = self._client_initialized

        # Update all widgets
        self.settings_widget.set_controls_enabled(
            True
        )  # Always allow catalog selection
        # Only enable functionality if catalog is valid, not busy, and client is ready
        self.camera_widget.set_controls_enabled(
            not busy and catalog_valid and client_ready
        )
        self.results_widget.set_controls_enabled(
            not busy and catalog_valid and client_ready
        )
        self.scale_widget.set_controls_enabled(
            not busy and catalog_valid and client_ready
        )

    def _on_camera_capture(self, image_path: str):
        """Handle camera capture and start processing."""
        if not self.settings_widget.validate_catalog():
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, tr("error"), tr("choose_valid_catalog"))
            return

        # Show processing indicator
        self.camera_widget.show_processing()

        # Clear previous results
        self.results_widget.clear_results()
        # Clear logs
        self.logs_widget.clear_logs()
        self.append_logs([tr("log_running")])

        # Get current weight from scale if available
        current_weight = self.scale_widget.get_current_weight()
        if current_weight > 0:
            self.append_logs([tr("log_using_scale_weight", weight=current_weight)])

        # Start main processing job
        if self.process_manager.start_main_job(
            image_path,
            self.settings_widget.get_catalog_path(),
            self.settings_widget.get_target(),
            self.settings_widget.get_model(),
        ):
            self.poll_main_timer.start(100)  # Poll every 100ms
            self._update_controls()

    def _on_weight_changed(self, weight: float):
        """Handle weight change from scale - auto-start camera if not started."""
        # Only auto-start camera if we're in camera mode (not manual mode)
        if self.camera_widget.is_manual_mode:
            return

        # Auto-start camera when scale detects a meaningful weight (> 0.01 kg)
        if weight > 0.01 and not self.camera_widget.cap:
            self.append_logs([tr("log_scale_detected", weight=weight)])
            try:
                self.camera_widget.start_camera()
                self._camera_auto_started = True
                self.append_logs([tr("log_camera_started")])
            except Exception as e:
                self.append_logs([tr("log_failed_autostart_camera", error=e)])

    def _on_manual_weight_set(self, weight: float):
        """Handle manual weight set from scale widget."""
        self.append_logs([tr("log_manual_weight_set", weight=weight)])

    def _on_manual_code_submitted(self, code: str):
        """Handle manual part code submission from camera widget."""
        if not self.settings_widget.validate_catalog():
            self.camera_widget.show_manual_result(False, tr("log_select_catalog_first"))
            return

        # Get weight (from scale or manual)
        weight = self.scale_widget.get_current_weight()
        if weight <= 0:
            self.camera_widget.show_manual_result(False, tr("log_set_weight_first"))
            return

        self.append_logs([tr("log_manual_code_submitted", code=code, weight=weight)])

        # Use the manual entry handler
        self._on_manual_entry_requested(code, weight)

        # Show result in camera widget
        # The result will be shown through the normal processing flow
        self.camera_widget.show_manual_result(
            True, tr("log_processing_code", code=code)
        )

    def _on_weight_ready(self, weight: float):
        """Handle weight ready from scale - automatically trigger camera capture when weight stabilizes."""
        self.append_logs([tr("log_weight_ready_debug", weight=weight)])

        # Don't auto-capture if camera is in manual mode
        if self.camera_widget.is_manual_mode:
            self.append_logs([tr("log_weight_stabilized_manual_mode", weight=weight)])
            return

        if not self.settings_widget.validate_catalog():
            self.append_logs([tr("log_weight_stabilized_no_catalog", weight=weight)])
            return

        # If camera is not started, try to start it first
        if not self.camera_widget.cap:
            self.append_logs(
                [tr("log_weight_stabilized_starting_camera", weight=weight)]
            )
            try:
                self.camera_widget.start_camera()
                self._camera_auto_started = True
                # Wait a bit for camera to initialize, then capture
                # Use longer delay to ensure camera is fully ready
                QTimer.singleShot(2000, lambda: self._capture_after_stable(weight))
                return
            except Exception as e:
                self.append_logs([tr("log_failed_start_camera", error=e)])
                return

        # Camera is ready, but need to wait for first frame
        # Check if camera has grabbed a frame yet
        if self.camera_widget._last_frame is None:
            self.append_logs([tr("log_weight_stabilized_waiting_frame", weight=weight)])
            # Wait for camera to grab first frame, then capture
            QTimer.singleShot(500, lambda: self._capture_after_stable(weight))
            return

        # Camera is ready and has a frame, capture immediately
        self.append_logs([tr("log_weight_stabilized_capturing", weight=weight)])
        try:
            self.camera_widget.capture_and_run()
        except Exception as e:
            self.append_logs([tr("log_failed_capture", error=e)])

    def _capture_after_stable(self, weight: float):
        """Capture image after camera has started (called with delay)."""
        if not self.camera_widget.cap:
            self.append_logs([tr("log_camera_not_ready")])
            # Try one more time after another delay (max 3 attempts)
            if not hasattr(self, "_capture_attempts"):
                self._capture_attempts = 0
            self._capture_attempts += 1
            if self._capture_attempts < 3:
                QTimer.singleShot(1000, lambda: self._capture_after_stable(weight))
            else:
                self.append_logs([tr("log_camera_init_failed")])
                self._capture_attempts = 0
            return

        # Reset attempts counter
        if hasattr(self, "_capture_attempts"):
            self._capture_attempts = 0

        # Check if camera has a frame ready
        if self.camera_widget._last_frame is None:
            self.append_logs([tr("log_waiting_camera_frame")])
            QTimer.singleShot(500, lambda: self._capture_after_stable(weight))
            return

        self.append_logs([tr("log_camera_ready_capturing", weight=weight)])
        try:
            self.camera_widget.capture_and_run()
        except Exception as e:
            self.append_logs([tr("log_failed_capture_delay", error=e)])

    def _ensure_catalog_file(self):
        """Ensure catalog file is selected before allowing app functionality."""
        if not self.settings_widget.validate_catalog():
            # Show blocking dialog to force catalog selection
            from PyQt6.QtWidgets import (
                QMessageBox,
                QDialog,
                QVBoxLayout,
                QLabel,
                QPushButton,
            )

            dlg = QDialog(self)
            dlg.setWindowTitle(tr("catalog_required_title"))
            dlg.setModal(True)
            dlg.setMinimumWidth(500)

            layout = QVBoxLayout(dlg)
            layout.setSpacing(15)

            # Icon and message
            icon_label = QLabel("📋")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("font-size: 48px;")
            layout.addWidget(icon_label)

            title = QLabel(tr("catalog_file_required"))
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
            layout.addWidget(title)

            message = QLabel(tr("catalog_required_message"))
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message.setWordWrap(True)
            message.setStyleSheet("font-size: 12px; color: #7f8c8d; padding: 10px;")
            layout.addWidget(message)

            # Button to open file dialog
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            select_btn = QPushButton(tr("select_catalog_file"))
            select_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 5px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                """
            )
            select_btn.clicked.connect(lambda: self._select_catalog_from_dialog(dlg))
            btn_layout.addWidget(select_btn)
            btn_layout.addStretch()

            layout.addLayout(btn_layout)

            # Disable functionality until catalog is set
            self._disable_app_functionality()

            # Show dialog (blocking)
            dlg.exec()

    def _select_catalog_from_dialog(self, dialog: QDialog):
        """Open catalog file selection from the required dialog."""
        # Trigger the catalog selection
        self.settings_widget.pick_catalog_excel()

        # Check if catalog is now valid
        if self.settings_widget.validate_catalog():
            # Catalog is set, close dialog and enable functionality
            dialog.accept()
            self._enable_app_functionality()
            self.append_logs(
                ["[INFO] Catalog file selected. App functionality enabled."]
            )
        # If not valid, dialog stays open (user can try again or cancel)

    def _enable_app_functionality(self):
        """Enable all app functionality when catalog is set."""
        # Enable all widgets (unless processing is running)
        busy = self.process_manager.any_running
        self.settings_widget.set_controls_enabled(True)  # Always allow catalog change
        self.camera_widget.set_controls_enabled(not busy)
        self.results_widget.set_controls_enabled(not busy)
        self.scale_widget.set_controls_enabled(not busy)

    def _disable_app_functionality(self):
        """Disable app functionality when catalog is not set."""
        # Disable functionality widgets, but keep catalog selection enabled
        self.camera_widget.set_controls_enabled(False)
        self.results_widget.set_controls_enabled(False)
        self.scale_widget.set_controls_enabled(False)
        # Settings widget catalog selection should remain enabled

    def _on_catalog_path_changed(self, path: str):
        """Handle catalog path change - enable functionality when catalog is set."""
        if path and os.path.exists(path):
            # Catalog is set and valid, enable all functionality
            self._enable_app_functionality()
        else:
            # Catalog is invalid or removed, disable functionality
            self._disable_app_functionality()

    def _on_results_path_changed(self, path: str):
        """Handle results path change."""
        self.results_pane.set_ledger_path(path)

    def _open_settings(self):
        """Open the settings page dialog."""
        from .settings_page import SettingsPage
        from gearledger.desktop.settings_manager import load_settings
        import os

        dlg = QDialog(self)
        dlg.setWindowTitle("Gear Ledger - Settings")
        dlg.setMinimumWidth(700)
        dlg.setMinimumHeight(800)

        layout = QVBoxLayout(dlg)
        settings_page = SettingsPage(dlg)
        settings_page._parent_dialog = dlg  # Store reference for closing
        layout.addWidget(settings_page)

        # Handle settings save callback
        def on_settings_saved(settings):
            # Re-apply environment variables
            if settings.openai_api_key:
                os.environ["OPENAI_API_KEY"] = settings.openai_api_key
            os.environ["CAM_INDEX"] = str(settings.cam_index)
            os.environ["CAM_WIDTH"] = str(settings.cam_width)
            os.environ["CAM_HEIGHT"] = str(settings.cam_height)
            os.environ["VISION_BACKEND"] = settings.vision_backend

            # Update scale widget with new settings
            self.scale_widget.scale_port = settings.scale_port
            self.scale_widget.scale_baudrate = settings.scale_baudrate
            self.scale_widget.weight_threshold = settings.weight_threshold
            self.scale_widget.stable_time = settings.stable_time

            # Update logs visibility
            self._update_logs_visibility()

            # Settings are now stored in settings manager, no need to update UI

            self.append_logs(
                ["[INFO] Settings have been updated. Some changes may require restart."]
            )

        settings_page.on_settings_saved = on_settings_saved

        dlg.exec()

    def _open_network_settings(self):
        """Open the network settings dialog."""
        from .network_settings_dialog import NetworkSettingsDialog
        from gearledger.server import get_server

        dlg = NetworkSettingsDialog(self)

        # Connect signals
        dlg.network_mode_changed.connect(self._on_network_mode_changed)
        dlg.server_data_changed.connect(self._on_server_data_changed)

        dlg.exec()

        # Register main window callback with server for client change notifications
        # This ensures we get updates even when dialog is closed
        server = get_server()
        if server and server.is_running():
            # Add callback to update main window status when clients connect/disconnect
            def on_client_changed_main_window(count):
                """Update main window status when client count changes."""
                QTimer.singleShot(0, self._update_network_status)

            server.add_client_changed_callback(on_client_changed_main_window)

        # Register callback with server (in case it was just started)
        self._register_server_callbacks()

        # Update status after dialog closes (in case settings changed)
        self._update_network_status()

    def _register_server_callbacks(self):
        """Register main window callbacks with server for client change and data change notifications."""
        from gearledger.server import get_server

        server = get_server()
        if server and server.is_running():
            # Add callback to update main window status when clients connect/disconnect
            # Store reference to avoid creating duplicate callbacks
            if not hasattr(self, "_client_changed_callback_ref"):

                def on_client_changed_main_window(count):
                    """Update main window status when client count changes."""

                    # Use QTimer to ensure UI update happens on main thread
                    # Pass count directly to avoid race condition
                    def update_ui():
                        self._update_network_status()
                        # Force immediate visual update
                        if hasattr(self, "network_status_label"):
                            self.network_status_label.update()
                            self.network_status_label.repaint()

                    QTimer.singleShot(0, update_ui)

                self._client_changed_callback_ref = on_client_changed_main_window
                server.add_client_changed_callback(self._client_changed_callback_ref)
                print(
                    f"[MAIN_WINDOW] Registered client change callback with server (total callbacks: {len(server._client_changed_callbacks)})"
                )
            else:
                print(
                    "[MAIN_WINDOW] Callback already registered, skipping duplicate registration"
                )

            # Register data changed callback to refresh results pane when clients send data
            if not hasattr(self, "_data_changed_callback_registered"):
                # Store the existing callback if any (from NetworkSettingsDialog)
                existing_callback = server.on_data_changed

                def on_data_changed():
                    """Refresh results pane when data changes on server."""
                    # Call existing callback first (if any) to maintain signal emission
                    if existing_callback:
                        try:
                            existing_callback()
                        except Exception as e:
                            print(
                                f"[MAIN_WINDOW] Error in existing data changed callback: {e}"
                            )
                    # Refresh results pane
                    # Use QTimer to ensure UI update happens on main thread
                    # Add small delay to ensure database write is visible
                    QTimer.singleShot(150, self.results_pane.refresh)

                server.on_data_changed = on_data_changed
                self._data_changed_callback_registered = True
                print("[MAIN_WINDOW] Registered data changed callback with server")

    def _auto_set_uploaded_catalog(self):
        """
        Automatically use uploaded catalog if server is running and catalog is uploaded.

        When a catalog is uploaded, it's stored in memory only.
        The server will automatically use the uploaded catalog via get_catalog_path()
        (which returns empty string when in-memory catalog is available), and the
        data layer will automatically use the in-memory catalog for lookups.
        """
        from gearledger.data_layer import get_network_mode
        from gearledger.server import get_server

        mode = get_network_mode()
        if mode != "server":
            return

        server = get_server()
        if not server or not server.is_running():
            return

        # Check if there's an uploaded catalog in memory
        if server.get_uploaded_catalog_data() is not None:
            # Catalog is in memory, server will automatically use it for lookups
            print("[MAIN_WINDOW] Uploaded catalog available in memory")

    def _sync_catalog_from_server(self, force: bool = False):
        """Download catalog from server if in client mode.

        Args:
            force: If True, always download even if cached file exists and appears up to date.
        """
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client
        from gearledger.desktop.settings_manager import APP_DIR
        import requests

        mode = get_network_mode()
        if mode != "client":
            return

        client = get_client()
        if not client or not client.is_connected():
            return

        # Prevent concurrent catalog sync requests
        if self._syncing_catalog:
            print("[MAIN_WINDOW] Catalog sync already in progress, skipping")
            return

        self._syncing_catalog = True
        try:
            # Check if catalog exists on server
            print("[MAIN_WINDOW] Checking catalog info from server...")
            info = client.get_catalog_info()
            print(f"[MAIN_WINDOW] Catalog info: {info}")
            if not info.get("ok") or not info.get("exists"):
                print("[MAIN_WINDOW] No catalog on server")
                # Update UI to show no catalog
                if hasattr(self, "settings_widget"):
                    self.settings_widget.update_catalog_ui_for_mode()
                return

            # Download catalog to cache
            catalog_cache_dir = os.path.join(APP_DIR, "catalog_cache")
            os.makedirs(catalog_cache_dir, exist_ok=True)
            cached_catalog = os.path.join(catalog_cache_dir, "server_catalog.xlsx")

            # Check if we need to update (compare modification time, unless forced)
            server_modified = info.get("modified", 0)
            needs_update = force
            if not force and os.path.exists(cached_catalog):
                local_modified = os.path.getmtime(cached_catalog)
                # Update if server catalog is newer (server_modified > local_modified)
                if server_modified > local_modified:
                    needs_update = True
                    print(
                        f"[MAIN_WINDOW] Server catalog is newer (server: {server_modified}, local: {local_modified})"
                    )
                else:
                    needs_update = False
                    print(
                        f"[MAIN_WINDOW] Catalog is up to date (server: {server_modified}, local: {local_modified})"
                    )
            else:
                if force:
                    print(
                        "[MAIN_WINDOW] Force download requested, will download catalog"
                    )
                else:
                    print("[MAIN_WINDOW] No local catalog cache, will download")

            if needs_update:
                print("[MAIN_WINDOW] Downloading catalog from server...")
                result = client.download_catalog(cached_catalog)
                if result.get("ok"):
                    print(f"[MAIN_WINDOW] ✓ Catalog downloaded: {cached_catalog}")
                    # Update catalog UI to show status
                    if hasattr(self, "settings_widget"):
                        self.settings_widget.update_catalog_ui_for_mode()
                        # Trigger catalog path change to enable functionality
                        self._on_catalog_path_changed(cached_catalog)
                    print("[MAIN_WINDOW] Catalog UI updated after download")
                else:
                    print(
                        f"[MAIN_WINDOW] ✗ Failed to download catalog: {result.get('error')}"
                    )
            else:
                # Even if no download needed, update UI to show current status
                if hasattr(self, "settings_widget"):
                    self.settings_widget.update_catalog_ui_for_mode()
                    print("[MAIN_WINDOW] Catalog UI updated (no download needed)")
        except KeyboardInterrupt:
            # App is being terminated, silently exit
            return
        except (
            requests.exceptions.RequestException,
            ConnectionError,
            TimeoutError,
        ) as e:
            # Network errors - server may be down or unreachable
            # Don't spam logs during shutdown
            pass
        except Exception as e:
            print(f"[MAIN_WINDOW] Error syncing catalog: {e}")
        finally:
            self._syncing_catalog = False

    def _update_sse_connection(self):
        """
        Start/stop SSE connection based on network mode.

        Note: This method is kept for backward compatibility but now uses
        the sequential initialization flow via _initialize_client_connection().
        """
        from gearledger.data_layer import get_network_mode

        mode = get_network_mode()
        if mode == "client":
            # Use the new sequential initialization
            self._initialize_client_connection()
        else:
            # In server/standalone mode, stop SSE connection
            if self._sse_client:
                print("[MAIN_WINDOW] Stopping SSE connection (not in client mode)")
                self.append_logs(["🔌 Disconnecting from server..."])
                self._sse_client.stop()
                self._sse_client = None

    def _initialize_sync_version(self):
        """Initialize sync version from server if in client mode."""
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client

        mode = get_network_mode()
        if mode != "client":
            return

        client = get_client()
        if client and client.is_connected():
            try:
                self._sync_version = client.get_sync_version()
                print(f"[MAIN_WINDOW] Initialized sync version: {self._sync_version}")
            except Exception as e:
                print(f"[MAIN_WINDOW] Error initializing sync version: {e}")

    def _on_sse_catalog_uploaded(self, event: dict):
        """Handle SSE catalog uploaded event."""
        filename = event.get("filename", "catalog")
        size = event.get("size", 0)
        print(f"[MAIN_WINDOW] 🔄 Catalog uploaded event received: {event}")

        # Show user-friendly message
        self.append_logs(
            [f"📦 New catalog received from server: {filename} ({size:,} bytes)"]
        )

        self._sync_version = event.get("version", self._sync_version)
        # Force sync catalog from server (don't check modification time, always download)
        self._sync_catalog_from_server(force=True)
        # Update catalog UI
        if hasattr(self, "settings_widget"):
            self.settings_widget.update_catalog_ui_for_mode()

    def _on_sse_results_changed(self, event: dict):
        """Handle SSE results changed event."""
        print(f"[MAIN_WINDOW] 🔄 Results changed event received: {event}")
        self._sync_version = event.get("version", self._sync_version)
        # Show user-friendly message
        self.append_logs(["🔄 Server results updated - refreshing..."])
        # Refresh results pane to show updated data
        QTimer.singleShot(150, self.results_pane.refresh)

    def _on_sse_connected(self):
        """Handle SSE connection established (for reconnections after initial setup)."""
        print("[MAIN_WINDOW] ✓ SSE connection re-established")
        # Show user-friendly message for reconnections
        self.append_logs(
            [
                "✅ Real-time sync reconnected",
                "   Receiving updates from server again",
            ]
        )

    def _on_sse_disconnected(self):
        """Handle SSE connection lost."""
        print("[MAIN_WINDOW] ✗ SSE connection lost, will attempt to reconnect")
        # Show user-friendly message
        self.append_logs(
            [
                "⚠️ Real-time sync connection lost - attempting to reconnect...",
                "   Updates may be delayed until connection is restored",
            ]
        )
        # Update network status to show disconnection
        self._update_network_status()
        # Show prominent disconnection indicator
        if self._client_initialized:
            self._update_client_init_progress(
                "⚠️ Real-time sync disconnected - reconnecting...", "#e67e22"
            )
            self.client_init_progress_label.setVisible(True)
        # SSE client will automatically retry in background thread

    def _on_sse_error(self, error: str):
        """Handle SSE error."""
        print(f"[MAIN_WINDOW] SSE error: {error}")
        # Only show error message for unexpected errors
        # Timeouts and connection errors are handled by disconnected signal
        if "Unexpected error" in error:
            self.append_logs([f"❌ SSE error: {error}"])
        # SSE client will automatically retry in background thread

    def _on_server_data_changed(self):
        """Handle server data changed - refresh results pane and sync catalog."""
        print(
            "[MAIN_WINDOW] Server data changed - refreshing results pane and syncing catalog"
        )
        # Sync catalog from server (if in client mode)
        self._sync_catalog_from_server()
        # Refresh results pane
        self.results_pane.refresh()
        # Update network status (client count may have changed)
        self._update_network_status()

    def _on_network_mode_changed(self, mode: str, address: str):
        """Handle network mode change - update results pane refresh button."""
        print(f"[MAIN_WINDOW] Network mode changed to: {mode}")
        # Update results pane to show/hide refresh button based on mode
        self.results_pane.update_refresh_button_visibility()
        # Update network status label
        self._update_network_status()

        if mode == "client":
            # Initialize client connection sequentially
            self._initialize_client_connection()
        else:
            # In server/standalone mode, stop SSE connection
            if self._sse_client:
                self.append_logs(["🔌 Disconnecting from server..."])
                self._sse_client.stop()
                self._sse_client = None
            # Reset initialization flag
            self._client_initialized = False
            # Hide progress indicator
            if hasattr(self, "client_init_progress_label"):
                self.client_init_progress_label.setVisible(False)
            # Enable all controls (not in client mode)
            self._set_client_enabled(True)
            # Update catalog UI
            if hasattr(self, "settings_widget"):
                self.settings_widget.update_catalog_ui_for_mode()

    def _initialize_client_connection(self):
        """Initialize client connection sequentially: connect, SSE, sync version, catalog."""
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client

        mode = get_network_mode()
        if mode != "client":
            return

        client = get_client()
        if not client or not client.is_connected():
            self.append_logs(["⚠️ Client not connected - cannot initialize"])
            self._update_client_init_progress("⚠️ Not connected", "#e74c3c")
            return

        # Disable client functionality during initialization
        self._set_client_enabled(False)

        # Show progress indicator
        if hasattr(self, "client_init_progress_label"):
            self.client_init_progress_label.setVisible(True)

        # Step 1: Show connection message
        self.append_logs(
            ["🔌 Initializing client connection...", f"   Server: {client.server_url}"]
        )
        self._update_client_init_progress("1️⃣ Connecting to server...", "#f39c12")

        # Step 2: Initialize sync version
        QTimer.singleShot(100, lambda: self._initialize_sync_version_step())

    def _initialize_sync_version_step(self):
        """Step 2: Initialize sync version, then proceed to SSE connection."""
        from gearledger.api_client import get_client

        client = get_client()
        if not client or not client.is_connected():
            return

        self._update_client_init_progress("2️⃣ Getting sync version...", "#f39c12")

        try:
            self._sync_version = client.get_sync_version()
            print(f"[MAIN_WINDOW] Initialized sync version: {self._sync_version}")
            self.append_logs([f"✓ Sync version initialized: {self._sync_version}"])
        except Exception as e:
            print(f"[MAIN_WINDOW] Error initializing sync version: {e}")
            self.append_logs([f"⚠️ Failed to get sync version: {e}"])

        # Step 3: Start SSE connection
        QTimer.singleShot(100, lambda: self._start_sse_connection_step())

    def _start_sse_connection_step(self):
        """Step 3: Start SSE connection and wait for it to be established."""
        from gearledger.api_client import get_client

        client = get_client()
        if not client or not client.is_connected():
            return

        # Only start if not already started
        if self._sse_client:
            # Already connected, proceed to catalog sync
            QTimer.singleShot(100, lambda: self._sync_catalog_step())
            return

        server_url = client.server_url
        print(f"[MAIN_WINDOW] Starting SSE connection to {server_url}")

        # Show user-friendly message
        self.append_logs(
            [
                "🔌 Connecting to server for real-time updates...",
                f"   Server: {server_url}",
            ]
        )
        self._update_client_init_progress(
            "3️⃣ Establishing real-time connection...", "#f39c12"
        )

        # Create and start SSE client
        # Use 60 second timeout (longer than server keepalive interval of 20 seconds)
        self._sse_client = SSEClientThread(server_url, timeout=60)
        self._sse_client.catalog_uploaded.connect(self._on_sse_catalog_uploaded)
        self._sse_client.results_changed.connect(self._on_sse_results_changed)
        self._sse_client.connected.connect(self._on_sse_connected_and_ready)
        self._sse_client.disconnected.connect(self._on_sse_disconnected)
        self._sse_client.error_occurred.connect(self._on_sse_error)
        self._sse_client.start()

        # Wait for SSE connection to be established before proceeding
        # The _on_sse_connected_and_ready will continue the initialization

    def _on_sse_connected_and_ready(self):
        """Called when SSE is connected - continue with catalog sync if initializing."""
        print("[MAIN_WINDOW] ✓ SSE connection established")

        # Check if this is initial connection or reconnection
        if not self._client_initialized:
            # Initial connection - continue with sequential initialization
            # Show user-friendly message
            self.append_logs(
                [
                    "✅ Real-time sync connected",
                    "   You will receive instant updates when server data changes",
                ]
            )
            self._update_client_init_progress("4️⃣ Syncing catalog...", "#f39c12")
            # Update network status to show SSE connected
            self._update_network_status()
            # Step 4: Sync catalog
            QTimer.singleShot(200, lambda: self._sync_catalog_step())
        else:
            # Reconnection after being disconnected - just show reconnected message
            self.append_logs(
                [
                    "✅ Real-time sync reconnected",
                    "   Receiving updates from server again",
                ]
            )
            # Update network status to show SSE reconnected
            self._update_network_status()

    def _sync_catalog_step(self):
        """Step 4: Sync catalog from server, then mark client as ready."""
        from gearledger.api_client import get_client

        client = get_client()
        if not client or not client.is_connected():
            return

        self.append_logs(["📥 Syncing catalog from server..."])

        # Sync catalog (this will update UI when done)
        self._sync_catalog_from_server()

        # Step 5: Update UI and mark as ready
        QTimer.singleShot(500, lambda: self._finalize_client_connection())

    def _finalize_client_connection(self):
        """Step 5: Finalize client connection - update UI and mark as ready."""
        # Update catalog UI
        if hasattr(self, "settings_widget"):
            self.settings_widget.update_catalog_ui_for_mode()

        # Mark client as initialized
        self._client_initialized = True

        # Show ready message
        self.append_logs(
            [
                "✅ Client connection initialized successfully",
                "   Ready to receive updates from server",
            ]
        )

        # Update progress indicator to show ready
        self._update_client_init_progress("✅ Ready", "#27ae60")

        # Enable client functionality
        self._set_client_enabled(True)

        # Hide progress indicator after a short delay
        QTimer.singleShot(
            2000, lambda: self.client_init_progress_label.setVisible(False)
        )

    def _update_network_status(self):
        """Update the network status label showing current mode and connection status."""
        from gearledger.data_layer import get_network_mode
        from gearledger.server import get_server
        from gearledger.api_client import get_client

        mode = get_network_mode()

        if mode == "server":
            server = get_server()
            if server and server.is_running():
                count = server.get_connected_clients_count()
                sse_count = server.get_sse_clients_count()
                if count > 0:
                    if sse_count > 0:
                        status_text = f"🖥️ Server: Running ({count} client{'s' if count != 1 else ''}, {sse_count} real-time)"
                        bg_color = "#27ae60"  # Green
                    else:
                        status_text = f"🖥️ Server: Running ({count} client{'s' if count != 1 else ''}, ⚠️ no real-time sync)"
                        bg_color = "#e67e22"  # Orange-red
                else:
                    status_text = "🖥️ Server: Running (0 clients)"
                    bg_color = "#f39c12"  # Orange
            else:
                status_text = "🖥️ Server: Stopped"
                bg_color = "#95a5a6"  # Gray
        elif mode == "client":
            client = get_client()
            if client and client.is_connected():
                # Check SSE connection status
                if self._sse_client and self._sse_client.is_connected():
                    if self._client_initialized:
                        status_text = "💻 Client: Connected (Real-time sync active)"
                        bg_color = "#27ae60"  # Green
                    else:
                        status_text = "💻 Client: Initializing..."
                        bg_color = "#f39c12"  # Orange
                else:
                    status_text = "💻 Client: Connected (⚠️ Real-time sync disconnected)"
                    bg_color = "#e67e22"  # Orange-red
            else:
                status_text = "💻 Client: Disconnected"
                bg_color = "#e74c3c"  # Red
        else:
            status_text = "📱 Standalone"
            bg_color = "#95a5a6"  # Gray

        print(f"[MAIN_WINDOW] Updating status label to: {status_text}")
        self.network_status_label.setText(status_text)
        self.network_status_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg_color};
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }}
        """
        )
        # Force update the label
        self.network_status_label.update()
        self.network_status_label.repaint()

    def _update_client_init_progress(self, message: str, color: str = "#f39c12"):
        """Update client initialization progress indicator."""
        if hasattr(self, "client_init_progress_label"):
            self.client_init_progress_label.setText(message)
            self.client_init_progress_label.setStyleSheet(
                f"""
                QLabel {{
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 10px;
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                }}
            """
            )
            self.client_init_progress_label.setVisible(True)

    def _set_client_enabled(self, enabled: bool):
        """Enable or disable client functionality during initialization."""
        # Update controls based on enabled state
        # This will be called by _update_controls which checks _client_initialized
        # So we just need to trigger an update
        self._update_controls()

    def _on_fuzzy_requested(self, candidates):
        """Handle fuzzy matching request."""
        from gearledger.config import DEFAULT_MIN_FUZZY

        if self.process_manager.start_fuzzy_job(
            self.settings_widget.get_catalog_path(), candidates, DEFAULT_MIN_FUZZY
        ):
            self.append_logs(["Starting fuzzy…"])
            self.poll_fuzzy_timer.start(100)
            self._update_controls()

    def _poll_main_queue(self):
        """Poll the main job queue for results."""
        print("[TIMER] _poll_main_queue() called - checking main processing queue")
        result = self.process_manager.poll_main_queue()
        if result is not None:
            print("[TIMER] _poll_main_queue() - found result, finishing process")
            self._finish_main_process(result)
        else:
            print("[TIMER] _poll_main_queue() - no result yet")

    def _poll_fuzzy_queue(self):
        """Poll the fuzzy job queue for results."""
        print("[TIMER] _poll_fuzzy_queue() called - checking fuzzy matching queue")
        result = self.process_manager.poll_fuzzy_queue()
        if result is not None:
            print("[TIMER] _poll_fuzzy_queue() - found result, finishing process")
            self._finish_fuzzy_process(result)
        else:
            print("[TIMER] _poll_fuzzy_queue() - no result yet")

    def _show_excel_error_popup(self, excel_error: dict | Any) -> bool:
        """
        Show user-friendly popup for Excel read errors.
        Returns True if popup was shown, False otherwise.
        """
        if not excel_error:
            return False

        from PyQt6.QtWidgets import QMessageBox

        # excel_error is now a dict (not exception object) due to multiprocessing
        excel_path = (
            excel_error.get("excel_path", "")
            if isinstance(excel_error, dict)
            else excel_error.excel_path
        )
        # Get just the filename for cleaner display
        file_name = os.path.basename(excel_path) if excel_path else "Unknown file"

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(tr("excel_file_problem"))
        msg.setText(tr("catalog_cannot_open"))
        msg.setInformativeText(tr("catalog_corrupted_msg", file=file_name))
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        return True

    def _finish_main_process(self, res: Dict[str, Any] | None):
        """Handle completion of main processing job."""
        self.poll_main_timer.stop()
        self.process_manager._finish_main_process(res)

        # Hide processing indicator
        self.camera_widget.hide_processing()

        # Reset camera to live feed after processing
        self.camera_widget.reset_to_live_feed()

        if res is None:
            self.append_logs([tr("log_job_canceled")])
            self.results_widget.set_match_result(tr("canceled"))
            return

        # Handle main result
        self.append_logs(res.get("logs"))

        # Check for Excel read error FIRST (before generic error handler)
        if self._show_excel_error_popup(res.get("excel_error")):
            return

        # Handle other errors (non-Excel)
        if not res.get("ok"):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, tr("run_failed"), str(res.get("error")))
            return

        # Update result fields
        self.results_widget.set_best_visible(res.get("best_visible") or "")
        self.results_widget.set_best_normalized(res.get("best_normalized") or "")

        # Handle match result
        client = res.get("match_client")
        artikul = res.get("match_artikul")
        ledger_path = self.settings_widget.get_results_path()

        if client and artikul:
            self.results_widget.set_match_result(f"{artikul} → {client}")
            speak_match(artikul, client)

            # Validate weight price before recording
            if not self.settings_widget.is_weight_price_valid():
                error_msg = self.settings_widget.get_weight_price_error_message()
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.critical(
                    self,
                    tr("weight_price_required"),
                    tr("cannot_record_match", error=error_msg),
                )
                return

            # Record the match with scale weight
            from gearledger.data_layer import record_match_unified

            # Use scale weight if available, otherwise default to 1
            scale_weight = self.scale_widget.get_current_weight()
            weight_to_use = scale_weight if scale_weight > 0 else 1.0

            rec = record_match_unified(
                ledger_path,
                artikul,
                client,
                qty_inc=1,
                weight_inc=weight_to_use,
                catalog_path=self.settings_widget.get_catalog_path(),
                weight_price=self.settings_widget.get_weight_price(),
            )
            if rec["ok"]:
                self.append_logs(
                    [
                        tr(
                            "log_logged_to_results",
                            action=rec["action"],
                            path=rec["path"],
                        )
                    ]
                )
                # Force refresh with delay in server mode to ensure database write is visible
                from gearledger.data_layer import get_network_mode

                mode = get_network_mode()
                if mode == "server":
                    # In server mode, add a small delay to ensure database transaction is committed and visible
                    QTimer.singleShot(150, self.results_pane.refresh)
                else:
                    self.results_pane.refresh()
            else:
                self.append_logs([tr("log_results_log_failed", error=rec["error"])])
        else:
            self.results_widget.set_match_result(tr("status_not_found"))
            best = res.get("best_visible") or res.get("best_normalized")
            if best:
                speak(tr("speak_no_match_best_guess", code=_spell_code(best)))
            else:
                speak(tr("speak_no_match"))

        # Update cost
        cost = res.get("gpt_cost")
        self.results_widget.set_cost(cost)

        # Show fuzzy options if no exact match
        cand_order = res.get("cand_order") or []
        if not client and res.get("prompt_fuzzy") and cand_order:
            self.results_widget.show_fuzzy_options(cand_order, True)
        elif not client:
            # Show manual input option if no fuzzy candidates
            self.results_widget.show_manual_input()

        self._update_controls()

    def _finish_fuzzy_process(self, res: Dict[str, Any] | None):
        """Handle completion of fuzzy matching job."""
        self.poll_fuzzy_timer.stop()
        self.process_manager._finish_fuzzy_process(res)

        # Hide processing indicator
        self.camera_widget.hide_processing()

        # Reset camera to live feed after processing
        self.camera_widget.reset_to_live_feed()

        if res is None:
            self.append_logs([tr("log_fuzzy_canceled")])
            return

        self.append_logs(res.get("logs"))
        if not res.get("ok"):
            from PyQt6.QtWidgets import QMessageBox

            # Check if it's an Excel read error
            if not self._show_excel_error_popup(res.get("excel_error")):
                QMessageBox.critical(
                    self,
                    tr("search_failed"),
                    tr("unable_search_catalog"),
                )
            return

        # Handle fuzzy result
        c = res.get("match_client")
        a = res.get("match_artikul")
        ledger_path = self.settings_widget.get_results_path()

        if c and a:
            self.results_widget.update_fuzzy_result(c, a)
            # Speak only the client name (via configured engine: OS/OpenAI/Piper)
            try:
                print(f"[SPEECH] _finish_fuzzy_process speaking client='{c}'")
            except Exception:
                pass
            speak_name(c)

            # Validate weight price before recording
            if not self.settings_widget.is_weight_price_valid():
                error_msg = self.settings_widget.get_weight_price_error_message()
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.critical(
                    self,
                    tr("weight_price_required"),
                    tr("cannot_record_match", error=error_msg),
                )
                return

            # Record the match with scale weight
            from gearledger.data_layer import record_match_unified

            # Use scale weight if available, otherwise default to 1
            scale_weight = self.scale_widget.get_current_weight()
            weight_to_use = scale_weight if scale_weight > 0 else 1.0

            catalog_path = self.settings_widget.get_catalog_path()
            print(
                f"[MAIN_WINDOW] Recording match: artikul={a}, client={c}, catalog_path={catalog_path}"
            )

            rec = record_match_unified(
                ledger_path,
                a,
                c,
                qty_inc=1,
                weight_inc=weight_to_use,
                catalog_path=catalog_path,
                weight_price=self.settings_widget.get_weight_price(),
            )
            if rec["ok"]:
                self.append_logs(
                    [
                        tr(
                            "log_logged_to_results",
                            action=rec["action"],
                            path=rec["path"],
                        )
                    ]
                )
                # Force refresh with delay in server mode to ensure database write is visible
                from gearledger.data_layer import get_network_mode

                mode = get_network_mode()
                if mode == "server":
                    # In server mode, add a small delay to ensure database transaction is committed and visible
                    QTimer.singleShot(150, self.results_pane.refresh)
                else:
                    self.results_pane.refresh()
            else:
                self.append_logs([tr("log_results_log_failed", error=rec["error"])])

        self._update_controls()

    def _on_manual_search_requested(self, code: str):
        """Handle manual search request."""
        from gearledger.pipeline import run_fuzzy_match
        from gearledger.config import DEFAULT_MIN_FUZZY

        if not self.settings_widget.validate_catalog():
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, tr("error"), tr("choose_valid_catalog"))
            return

        catalog = self.settings_widget.get_catalog_path()

        self.append_logs([tr("log_searching_manual_code", code=code)])

        try:
            # Create a single candidate with the manual code
            cand_order = [(code, code)]  # (visible, normalized)

            # Run fuzzy match with the manual code
            result = run_fuzzy_match(catalog, cand_order, DEFAULT_MIN_FUZZY)

            if result.get("ok"):
                client = result.get("match_client")
                artikul = result.get("match_artikul")
                ledger_path = self.settings_widget.get_results_path()

                if client and artikul:
                    self.results_widget.update_manual_result(client, artikul)
                    speak_match(artikul, client)

                    # Validate weight price before recording
                    if not self.settings_widget.is_weight_price_valid():
                        error_msg = (
                            self.settings_widget.get_weight_price_error_message()
                        )
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.critical(
                            self,
                            tr("weight_price_required"),
                            tr("cannot_record_manual_search", error=error_msg),
                        )
                        return

                    # Record the match
                    from gearledger.data_layer import record_match_unified

                    rec = record_match_unified(
                        ledger_path,
                        artikul,
                        client,
                        qty_inc=1,
                        weight_inc=1,
                        catalog_path=self.settings_widget.get_catalog_path(),
                        weight_price=self.settings_widget.get_weight_price(),
                    )
                    if rec["ok"]:
                        self.append_logs(
                            [
                                tr(
                                    "log_logged_to_results",
                                    action=rec["action"],
                                    path=rec["path"],
                                )
                            ]
                        )
                        # Force refresh with delay in server mode to ensure database write is visible
                        from gearledger.data_layer import get_network_mode

                        mode = get_network_mode()
                        if mode == "server":
                            QTimer.singleShot(150, self.results_pane.refresh)
                        else:
                            self.results_pane.refresh()
                    else:
                        self.append_logs(
                            [tr("log_results_log_failed", error=rec["error"])]
                        )
                else:
                    self.results_widget.update_manual_result("", "")
            else:
                self.append_logs(
                    [
                        tr(
                            "log_manual_search_failed",
                            error=result.get("error", "Unknown error"),
                        )
                    ]
                )
                self.results_widget.update_manual_result("", "")

        except Exception as e:
            self.append_logs([tr("log_manual_search_error", error=str(e))])
            self.results_widget.update_manual_result("", "")

    def _on_manual_entry_requested(self, part_code: str, weight: float):
        """Handle manual entry request."""
        from gearledger.pipeline import run_fuzzy_match
        from gearledger.config import DEFAULT_MIN_FUZZY

        if not self.settings_widget.validate_catalog():
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, tr("error"), tr("choose_valid_catalog"))
            return

        catalog = self.settings_widget.get_catalog_path()

        self.append_logs([tr("log_manual_entry", code=part_code, weight=weight)])

        try:
            # Create a single candidate with the manual code
            cand_order = [(part_code, part_code)]  # (visible, normalized)

            # Run fuzzy match with the manual code
            result = run_fuzzy_match(catalog, cand_order, DEFAULT_MIN_FUZZY)

            if result.get("ok"):
                client = result.get("match_client")
                artikul = result.get("match_artikul")
                ledger_path = self.settings_widget.get_results_path()

                if client and artikul:
                    # Don't speak here - dialog will speak only the client name
                    # speak_match(artikul, client)

                    # Validate weight price before recording
                    if not self.settings_widget.is_weight_price_valid():
                        error_msg = (
                            self.settings_widget.get_weight_price_error_message()
                        )
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.critical(
                            self,
                            tr("weight_price_required"),
                            tr("cannot_record_manual_entry", error=error_msg),
                        )
                        return

                    # Record the match with the specified weight
                    from gearledger.data_layer import record_match_unified

                    rec = record_match_unified(
                        ledger_path,
                        artikul,
                        client,
                        qty_inc=1,
                        weight_inc=weight,
                        catalog_path=self.settings_widget.get_catalog_path(),
                        weight_price=self.settings_widget.get_weight_price(),
                    )
                    if rec["ok"]:
                        self.append_logs(
                            [
                                tr(
                                    "log_manual_entry_logged",
                                    artikul=artikul,
                                    client=client,
                                    weight=weight,
                                )
                            ]
                        )
                        # Force refresh with delay in server mode to ensure database write is visible
                        from gearledger.data_layer import get_network_mode

                        mode = get_network_mode()
                        if mode == "server":
                            QTimer.singleShot(150, self.results_pane.refresh)
                        else:
                            self.results_pane.refresh()

                        # Clear the manual entry fields
                        self.settings_widget.clear_manual_entry()

                        # Show success message with improved dialog
                        def show_dialog():
                            dialog = NameConfirmationDialog(self, client)
                            dialog.exec()

                        # Ensure dialog opens on main thread
                        QTimer.singleShot(0, show_dialog)
                    else:
                        self.append_logs(
                            [tr("log_manual_entry_failed", error=rec["error"])]
                        )
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.warning(
                            self,
                            tr("manual_entry_failed"),
                            tr("manual_entry_failed_msg", error=rec["error"]),
                        )
                else:
                    self.append_logs([tr("log_no_match_manual_code", code=part_code)])
                    # Speak that no match was found
                    speak(tr("speak_no_match_for_code", code=_spell_code(part_code)))

                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        self,
                        tr("no_match_found"),
                        tr("no_match_for_part_code", code=part_code),
                    )
            else:
                error_msg = result.get("error", "Unknown error")
                self.append_logs(
                    [tr("log_manual_entry_search_failed", error=error_msg)]
                )
                from PyQt6.QtWidgets import QMessageBox

                # Check if it's an Excel read error
                if not self._show_excel_error_popup(result.get("excel_error")):
                    QMessageBox.critical(
                        self,
                        tr("search_failed"),
                        tr("unable_search_part_code", code=part_code),
                    )

        except Exception as e:
            self.append_logs([tr("log_manual_entry_error", error=str(e))])
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                tr("manual_entry_error"),
                tr("error_occurred", error=str(e)),
            )

    def _on_generate_invoice_requested(self):
        """Handle invoice generation request."""
        from PyQt6.QtWidgets import QMessageBox, QFileDialog
        from gearledger.invoice_generator import generate_invoice_from_results

        # Validate files exist
        results_path = self.settings_widget.get_results_path()
        catalog_path = self.settings_widget.get_catalog_path()

        if not results_path or not os.path.exists(results_path):
            QMessageBox.warning(
                self,
                tr("generate_invoice_title"),
                tr("no_results_file_invoice"),
            )
            return

        if not self.settings_widget.validate_catalog():
            QMessageBox.critical(
                self,
                tr("generate_invoice_title"),
                tr("choose_valid_catalog_first"),
            )
            return

        # Get catalog path (may be empty if using in-memory catalog)
        catalog_path = self.settings_widget.get_catalog_path()

        # Validate weight price
        if not self.settings_widget.is_weight_price_valid():
            error_msg = self.settings_widget.get_weight_price_error_message()
            QMessageBox.critical(
                self,
                tr("generate_invoice_title"),
                tr("weight_price_validation_failed", error=error_msg),
            )
            return

        # Ask user where to save the invoice
        default_name = f"invoice_{os.path.basename(results_path)}"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_invoice_as"),
            default_name,
            filter=tr("excel_filter"),
            initialFilter="Excel (*.xlsx)",
        )

        if not output_path:
            return  # User cancelled

        # Ensure .xlsx extension
        if not output_path.endswith(".xlsx"):
            output_path += ".xlsx"

        self.append_logs([tr("log_generating_invoice")])

        # Generate invoice
        weight_price = self.settings_widget.get_weight_price()
        result = generate_invoice_from_results(
            results_path, catalog_path, output_path, weight_price
        )

        if result.get("ok"):
            self.append_logs(
                [
                    tr("log_invoice_success"),
                    tr("log_invoice_output", path=result["path"]),
                    tr("log_invoice_clients", clients=result.get("clients", 0)),
                ]
            )

            QMessageBox.information(
                self,
                tr("invoice_generated"),
                tr(
                    "invoice_generated_msg",
                    path=result["path"],
                    clients=result.get("clients", 0),
                ),
            )
        else:
            self.append_logs([tr("log_invoice_failed", error=result.get("error"))])

            QMessageBox.critical(
                self,
                tr("invoice_generation_failed"),
                tr("invoice_generation_failed_msg", error=result.get("error")),
            )

    def append_logs(self, lines):
        """Append log lines to the log widget."""
        self.logs_widget.append_logs(lines)

    def _update_logs_visibility(self):
        """Update logs widget visibility based on settings."""
        from gearledger.desktop.settings_manager import load_settings

        settings = load_settings()
        show_logs = settings.show_logs

        # Update visibility
        self.logs_widget.setVisible(show_logs)

    def closeEvent(self, event):
        """Handle application close event."""
        # Clean up processes
        self.process_manager.cancel_all()

        # Clean up camera
        self.camera_widget.cleanup()

        # Clean up scale
        self.scale_widget.cleanup()

        # Stop timers
        if hasattr(self, "poll_main_timer"):
            self.poll_main_timer.stop()
        if hasattr(self, "poll_fuzzy_timer"):
            self.poll_fuzzy_timer.stop()
        # Stop SSE client to prevent network requests during shutdown
        if hasattr(self, "_sse_client") and self._sse_client:
            self._sse_client.stop()
            self._sse_client = None

        super().closeEvent(event)
