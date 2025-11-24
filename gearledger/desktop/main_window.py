# gearledger/desktop/main_window.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Dict, Any

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
    QTabWidget,
    QGroupBox,
    QLabel,
    QLineEdit,
)

# Import our modular components
from .camera_widget import CameraWidget
from .settings_widget import SettingsWidget
from .results_widget import ResultsWidget
from .logs_widget import LogsWidget
from .results_pane import ResultsPane
from .process_helpers import ProcessManager
from .scale_widget import ScaleWidget

# Optional speech helpers (guarded)
try:
    from gearledger.speech import speak, speak_match, _spell_code
except Exception:

    def speak(*a, **k):
        pass

    def speak_match(*a, **k):
        pass

    def _spell_code(x):
        return x


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

        # Logs widgets (one for each tab)
        self.logs_widget_automated = LogsWidget()
        self.logs_widget_manual = LogsWidget()
        # Keep reference to both for appending logs
        self.logs_widgets = [self.logs_widget_automated, self.logs_widget_manual]

        # Scale widget
        self.scale_widget = ScaleWidget()

        # Results pane (Excel table)
        self.results_pane = ResultsPane(self.settings_widget.get_results_path())

    def _setup_connections(self):
        """Set up signal connections between widgets."""
        # Camera capture callback
        self.camera_widget.set_capture_callback(self._on_camera_capture)

        # Settings callbacks
        self.settings_widget.set_catalog_changed_callback(self._on_catalog_path_changed)
        self.settings_widget.set_results_changed_callback(self._on_results_path_changed)
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
        self.scale_widget.set_log_callback(self.append_logs)

        # Track if camera was auto-started by scale
        self._camera_auto_started = False

    def _setup_layout(self):
        """Set up the main layout."""
        # Root layout
        outer = QVBoxLayout()

        # Add settings button at the top (global, visible in all tabs)
        settings_btn_layout = QHBoxLayout()
        settings_btn_layout.addStretch(1)
        self.settings_btn = QPushButton("⚙️ Settings")
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

        # Add Settings widget (file selection) - shared between both tabs
        outer.addWidget(self.settings_widget)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #ecf0f1;
                color: #2c3e50;
                padding: 10px 20px;
                border: 1px solid #bdc3c7;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3498db;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #d5dbdb;
            }
        """
        )

        # Create Automated tab
        automated_tab = self._create_automated_tab()
        self.tab_widget.addTab(automated_tab, "🤖 Automated")

        # Create Manual tab
        manual_tab = self._create_manual_tab()
        self.tab_widget.addTab(manual_tab, "✋ Manual")

        # Set Automated as default (index 0)
        self.tab_widget.setCurrentIndex(0)

        # Splitter for resizable layout (tabs on top, results pane on bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.tab_widget)
        splitter.addWidget(self.results_pane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer.addWidget(splitter)
        self.setLayout(outer)

    def _create_automated_tab(self) -> QWidget:
        """Create the Automated tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container for scrollable content
        container = QWidget()
        container_layout = QVBoxLayout(container)

        # Scale and Camera side by side with resizable splitter
        scale_camera_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Set minimum widths to ensure all important info is visible
        # Scale widget: needs space for port/baudrate controls, weight display, 3 buttons
        self.scale_widget.setMinimumWidth(350)
        # Camera widget: needs space for preview and 3 buttons (reduced from 640 to allow flexibility)
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

        # Add widgets for automated mode (settings widget is now above tabs)
        container_layout.addWidget(self.results_widget)
        container_layout.addWidget(self.logs_widget_automated, 1)

        # Store reference to container layout for updating logs visibility
        self.automated_container_layout = container_layout

        # Make scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(container)

        layout.addWidget(scroll)
        return tab

    def _create_manual_tab(self) -> QWidget:
        """Create the Manual tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container for scrollable content
        container = QWidget()
        container_layout = QVBoxLayout(container)

        # Manual entry section (settings widget is now above tabs)
        manual_entry_box = QGroupBox("Manual Entry")
        manual_entry_layout = QVBoxLayout(manual_entry_box)

        # Part code input
        code_layout = QHBoxLayout()
        code_layout.addWidget(QLabel("Part Code:"))
        self.manual_part_code = QLineEdit()
        self.manual_part_code.setPlaceholderText("Enter part code (e.g., PK-5396)")
        code_layout.addWidget(self.manual_part_code, 1)
        manual_entry_layout.addLayout(code_layout)

        # Weight input
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("Weight (kg):"))
        self.manual_weight = QLineEdit()
        self.manual_weight.setPlaceholderText("Enter weight")
        weight_layout.addWidget(self.manual_weight, 1)
        manual_entry_layout.addLayout(weight_layout)

        # Add button
        self.btn_add_manual_tab = QPushButton("Add to Results")
        self.btn_add_manual_tab.clicked.connect(self._on_manual_entry_from_tab)
        manual_entry_layout.addWidget(self.btn_add_manual_tab)

        container_layout.addWidget(manual_entry_box)

        # Add logs widget
        container_layout.addWidget(self.logs_widget_manual, 1)

        # Store reference to container layout for updating logs visibility
        self.manual_container_layout = container_layout

        # Make scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(container)

        layout.addWidget(scroll)
        return tab

    def _on_manual_entry_from_tab(self):
        """Handle manual entry from the Manual tab."""
        from PyQt6.QtWidgets import QMessageBox

        part_code = self.manual_part_code.text().strip()
        weight_text = self.manual_weight.text().strip()

        if not part_code:
            QMessageBox.warning(
                self,
                "Manual Entry",
                "Please enter a part code.",
            )
            return

        if not weight_text:
            QMessageBox.warning(
                self,
                "Manual Entry",
                "Please enter the weight.",
            )
            return

        try:
            weight = float(weight_text)
            if weight <= 0:
                QMessageBox.warning(
                    self,
                    "Manual Entry",
                    "Weight must be greater than 0.",
                )
                return
        except ValueError:
            QMessageBox.warning(
                self,
                "Manual Entry",
                "Please enter a valid weight number.",
            )
            return

        # Use the same handler as the automated tab
        self._on_manual_entry_requested(part_code, weight)

        # Clear fields after successful entry
        self.manual_part_code.clear()
        self.manual_weight.clear()

    def _setup_timers(self):
        """Set up polling timers for process queues."""
        self.poll_main_timer = QTimer(self)
        self.poll_main_timer.timeout.connect(self._poll_main_queue)

        self.poll_fuzzy_timer = QTimer(self)
        self.poll_fuzzy_timer.timeout.connect(self._poll_fuzzy_queue)

    def _update_controls(self):
        """Update control states based on process status and catalog availability."""
        busy = self.process_manager.any_running
        catalog_valid = self.settings_widget.validate_catalog()

        # Update all widgets
        self.settings_widget.set_controls_enabled(
            True
        )  # Always allow catalog selection
        # Only enable functionality if catalog is valid and not busy
        self.camera_widget.set_controls_enabled(not busy and catalog_valid)
        self.results_widget.set_controls_enabled(not busy and catalog_valid)
        self.scale_widget.set_controls_enabled(not busy and catalog_valid)

    def _on_camera_capture(self, image_path: str):
        """Handle camera capture and start processing."""
        if not self.settings_widget.validate_catalog():
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Error", "Please choose a valid Catalog Excel file."
            )
            return

        # Show processing indicator
        self.camera_widget.show_processing()

        # Clear previous results
        self.results_widget.clear_results()
        # Clear all log widgets
        for logs_widget in self.logs_widgets:
            logs_widget.clear_logs()
        self.append_logs(["Running…"])

        # Get current weight from scale if available
        current_weight = self.scale_widget.get_current_weight()
        if current_weight > 0:
            self.append_logs([f"Using scale weight: {current_weight:.3f} kg"])

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
        # Auto-start camera when scale detects a meaningful weight (> 0.01 kg)
        if weight > 0.01 and not self.camera_widget.cap:
            self.append_logs(
                [
                    f"[INFO] Scale detected weight: {weight:.3f} kg - auto-starting camera"
                ]
            )
            try:
                self.camera_widget.start_camera()
                self._camera_auto_started = True
                self.append_logs(["[INFO] Camera started automatically"])
            except Exception as e:
                self.append_logs([f"[ERROR] Failed to auto-start camera: {e}"])

    def _on_weight_ready(self, weight: float):
        """Handle weight ready from scale - automatically trigger camera capture when weight stabilizes."""
        self.append_logs([f"[DEBUG] Weight ready signal received: {weight:.3f} kg"])

        if not self.settings_widget.validate_catalog():
            self.append_logs(
                [
                    f"[INFO] Weight stabilized: {weight:.3f} kg, but no catalog file selected"
                ]
            )
            return

        # If camera is not started, try to start it first
        if not self.camera_widget.cap:
            self.append_logs(
                [f"[INFO] Weight stabilized: {weight:.3f} kg - starting camera..."]
            )
            try:
                self.camera_widget.start_camera()
                self._camera_auto_started = True
                # Wait a bit for camera to initialize, then capture
                # Use longer delay to ensure camera is fully ready
                QTimer.singleShot(2000, lambda: self._capture_after_stable(weight))
                return
            except Exception as e:
                self.append_logs([f"[ERROR] Failed to start camera: {e}"])
                return

        # Camera is ready, but need to wait for first frame
        # Check if camera has grabbed a frame yet
        if self.camera_widget._last_frame is None:
            self.append_logs(
                [
                    f"[INFO] Weight stabilized: {weight:.3f} kg - waiting for camera frame..."
                ]
            )
            # Wait for camera to grab first frame, then capture
            QTimer.singleShot(500, lambda: self._capture_after_stable(weight))
            return

        # Camera is ready and has a frame, capture immediately
        self.append_logs(
            [
                f"[INFO] Weight stabilized: {weight:.3f} kg - capturing image and running OCR"
            ]
        )
        try:
            self.camera_widget.capture_and_run()
        except Exception as e:
            self.append_logs([f"[ERROR] Failed to capture: {e}"])

    def _capture_after_stable(self, weight: float):
        """Capture image after camera has started (called with delay)."""
        if not self.camera_widget.cap:
            self.append_logs(
                ["[WARNING] Camera not ready for capture - waiting longer..."]
            )
            # Try one more time after another delay (max 3 attempts)
            if not hasattr(self, "_capture_attempts"):
                self._capture_attempts = 0
            self._capture_attempts += 1
            if self._capture_attempts < 3:
                QTimer.singleShot(1000, lambda: self._capture_after_stable(weight))
            else:
                self.append_logs(
                    ["[ERROR] Camera failed to initialize after multiple attempts"]
                )
                self._capture_attempts = 0
            return

        # Reset attempts counter
        if hasattr(self, "_capture_attempts"):
            self._capture_attempts = 0

        # Check if camera has a frame ready
        if self.camera_widget._last_frame is None:
            self.append_logs(["[INFO] Waiting for camera frame..."])
            QTimer.singleShot(500, lambda: self._capture_after_stable(weight))
            return

        self.append_logs(
            [f"[INFO] Camera ready - capturing image for weight: {weight:.3f} kg"]
        )
        try:
            self.camera_widget.capture_and_run()
        except Exception as e:
            self.append_logs([f"[ERROR] Failed to capture after delay: {e}"])

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
            dlg.setWindowTitle("Gear Ledger - Catalog Required")
            dlg.setModal(True)
            dlg.setMinimumWidth(500)

            layout = QVBoxLayout(dlg)
            layout.setSpacing(15)

            # Icon and message
            icon_label = QLabel("📋")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("font-size: 48px;")
            layout.addWidget(icon_label)

            title = QLabel("Catalog File Required")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
            layout.addWidget(title)

            message = QLabel(
                "Please select a Catalog Excel file to continue.\n\n"
                "The catalog file contains the part codes and client information\n"
                "needed for matching scanned items."
            )
            message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message.setWordWrap(True)
            message.setStyleSheet("font-size: 12px; color: #7f8c8d; padding: 10px;")
            layout.addWidget(message)

            # Button to open file dialog
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            select_btn = QPushButton("Select Catalog File")
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
            if settings.scale_port:
                self.scale_widget.port_combo.setCurrentText(settings.scale_port)
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
        result = self.process_manager.poll_main_queue()
        if result is not None:
            self._finish_main_process(result)

    def _poll_fuzzy_queue(self):
        """Poll the fuzzy job queue for results."""
        result = self.process_manager.poll_fuzzy_queue()
        if result is not None:
            self._finish_fuzzy_process(result)

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
        msg.setWindowTitle("Excel File Problem")
        msg.setText("The catalog file cannot be opened")
        msg.setInformativeText(
            f"The file '{file_name}' appears to be corrupted or in an unsupported format.\n\n"
            f"To fix this:\n\n"
            f"1. Open the file in Microsoft Excel or LibreOffice\n"
            f"2. If it opens, click File → Save As\n"
            f"3. Choose 'Excel Workbook (.xlsx)' as the format\n"
            f"4. Save the file\n"
            f"5. Select the new .xlsx file as Catalog"
        )
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
            self.append_logs(["[INFO] Job was canceled."])
            self.results_widget.set_match_result("canceled")
            return

        # Handle main result
        self.append_logs(res.get("logs"))

        # Check for Excel read error FIRST (before generic error handler)
        if self._show_excel_error_popup(res.get("excel_error")):
            return

        # Handle other errors (non-Excel)
        if not res.get("ok"):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Run failed", str(res.get("error")))
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
                    "Weight Price Required",
                    f"Cannot record match without valid weight price:\n{error_msg}",
                )
                return

            # Record the match with scale weight
            from gearledger.result_ledger import record_match

            # Use scale weight if available, otherwise default to 1
            scale_weight = self.scale_widget.get_current_weight()
            weight_to_use = scale_weight if scale_weight > 0 else 1.0

            rec = record_match(
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
                    [f"[INFO] Logged to results: {rec['action']} → {rec['path']}"]
                )
                self.results_pane.refresh()
            else:
                self.append_logs([f"[WARN] Results log failed: {rec['error']}"])
        else:
            self.results_widget.set_match_result("not found")
            best = res.get("best_visible") or res.get("best_normalized")
            if best:
                speak(f"No match found. Best guess code: {_spell_code(best)}.")
            else:
                speak("No match found.")

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
            self.append_logs(["[INFO] Fuzzy job was canceled."])
            return

        self.append_logs(res.get("logs"))
        if not res.get("ok"):
            from PyQt6.QtWidgets import QMessageBox

            # Check if it's an Excel read error
            if not self._show_excel_error_popup(res.get("excel_error")):
                QMessageBox.critical(
                    self,
                    "Search Failed",
                    "Unable to search the catalog. Please check your settings.",
                )
            return

        # Handle fuzzy result
        c = res.get("match_client")
        a = res.get("match_artikul")
        ledger_path = self.settings_widget.get_results_path()

        if c and a:
            self.results_widget.update_fuzzy_result(c, a)
            speak_match(a, c)

            # Validate weight price before recording
            if not self.settings_widget.is_weight_price_valid():
                error_msg = self.settings_widget.get_weight_price_error_message()
                from PyQt6.QtWidgets import QMessageBox

                QMessageBox.critical(
                    self,
                    "Weight Price Required",
                    f"Cannot record match without valid weight price:\n{error_msg}",
                )
                return

            # Record the match with scale weight
            from gearledger.result_ledger import record_match

            # Use scale weight if available, otherwise default to 1
            scale_weight = self.scale_widget.get_current_weight()
            weight_to_use = scale_weight if scale_weight > 0 else 1.0

            rec = record_match(
                ledger_path,
                a,
                c,
                qty_inc=1,
                weight_inc=weight_to_use,
                catalog_path=self.settings_widget.get_catalog_path(),
                weight_price=self.settings_widget.get_weight_price(),
            )
            if rec["ok"]:
                self.append_logs(
                    [f"[INFO] Logged to results: {rec['action']} → {rec['path']}"]
                )
                self.results_pane.refresh()
            else:
                self.append_logs([f"[WARN] Results log failed: {rec['error']}"])

        self._update_controls()

    def _on_manual_search_requested(self, code: str):
        """Handle manual search request."""
        from gearledger.pipeline import run_fuzzy_match
        from gearledger.config import DEFAULT_MIN_FUZZY

        catalog = self.settings_widget.get_catalog_path()
        if not catalog or not os.path.exists(catalog):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Error", "Please choose a valid Catalog Excel file."
            )
            return

        self.append_logs([f"Searching for manual code: {code}"])

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
                            "Weight Price Required",
                            f"Cannot record manual search without valid weight price:\n{error_msg}",
                        )
                        return

                    # Record the match
                    from gearledger.result_ledger import record_match

                    rec = record_match(
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
                                f"[INFO] Logged to results: {rec['action']} → {rec['path']}"
                            ]
                        )
                        self.results_pane.refresh()
                    else:
                        self.append_logs([f"[WARN] Results log failed: {rec['error']}"])
                else:
                    self.results_widget.update_manual_result("", "")
            else:
                self.append_logs(
                    [
                        f"[ERROR] Manual search failed: {result.get('error', 'Unknown error')}"
                    ]
                )
                self.results_widget.update_manual_result("", "")

        except Exception as e:
            self.append_logs([f"[ERROR] Manual search error: {str(e)}"])
            self.results_widget.update_manual_result("", "")

    def _on_manual_entry_requested(self, part_code: str, weight: float):
        """Handle manual entry request."""
        from gearledger.pipeline import run_fuzzy_match
        from gearledger.config import DEFAULT_MIN_FUZZY

        catalog = self.settings_widget.get_catalog_path()
        if not catalog or not os.path.exists(catalog):
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Error", "Please choose a valid Catalog Excel file."
            )
            return

        self.append_logs([f"Manual entry: {part_code} (weight: {weight} kg)"])

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
                    # Speak the match
                    speak_match(artikul, client)

                    # Validate weight price before recording
                    if not self.settings_widget.is_weight_price_valid():
                        error_msg = (
                            self.settings_widget.get_weight_price_error_message()
                        )
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.critical(
                            self,
                            "Weight Price Required",
                            f"Cannot record manual entry without valid weight price:\n{error_msg}",
                        )
                        return

                    # Record the match with the specified weight
                    from gearledger.result_ledger import record_match

                    rec = record_match(
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
                                f"[INFO] Manual entry logged: {artikul} → {client} (weight: {weight} kg)"
                            ]
                        )
                        self.results_pane.refresh()

                        # Clear the manual entry fields
                        self.settings_widget.clear_manual_entry()

                        # Show success message
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.information(
                            self,
                            "Manual Entry Success",
                            f"Successfully added:\n{artikul} → {client}\nWeight: {weight} kg",
                        )
                    else:
                        self.append_logs(
                            [f"[WARN] Manual entry log failed: {rec['error']}"]
                        )
                        from PyQt6.QtWidgets import QMessageBox

                        QMessageBox.warning(
                            self,
                            "Manual Entry Failed",
                            f"Failed to log entry: {rec['error']}",
                        )
                else:
                    self.append_logs(
                        [f"[INFO] No match found for manual code: {part_code}"]
                    )
                    # Speak that no match was found
                    speak(f"No match found for code: {_spell_code(part_code)}.")

                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        self,
                        "No Match Found",
                        f"No match found for part code: {part_code}\n\nYou can still add it manually to your inventory.",
                    )
            else:
                error_msg = result.get("error", "Unknown error")
                self.append_logs([f"[ERROR] Manual entry search failed: {error_msg}"])
                from PyQt6.QtWidgets import QMessageBox

                # Check if it's an Excel read error
                if not self._show_excel_error_popup(result.get("excel_error")):
                    QMessageBox.critical(
                        self,
                        "Search Failed",
                        f"Unable to search for part code '{part_code}'.\n\nPlease check that your catalog file is set up correctly in Settings.",
                    )

        except Exception as e:
            self.append_logs([f"[ERROR] Manual entry error: {str(e)}"])
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self,
                "Manual Entry Error",
                f"An error occurred: {str(e)}",
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
                "Generate Invoice",
                "No results file found. Please run some OCR operations first to generate results.",
            )
            return

        if not catalog_path or not os.path.exists(catalog_path):
            QMessageBox.critical(
                self,
                "Generate Invoice",
                "Please choose a valid Catalog Excel file first.",
            )
            return

        # Validate weight price
        if not self.settings_widget.is_weight_price_valid():
            error_msg = self.settings_widget.get_weight_price_error_message()
            QMessageBox.critical(
                self,
                "Generate Invoice",
                f"Weight Price validation failed:\n{error_msg}",
            )
            return

        # Ask user where to save the invoice
        default_name = f"invoice_{os.path.basename(results_path)}"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Invoice As",
            default_name,
            filter="Excel (*.xlsx);;All files (*)",
            initialFilter="Excel (*.xlsx)",
        )

        if not output_path:
            return  # User cancelled

        # Ensure .xlsx extension
        if not output_path.endswith(".xlsx"):
            output_path += ".xlsx"

        self.append_logs(["[INFO] Generating invoice..."])

        # Generate invoice
        weight_price = self.settings_widget.get_weight_price()
        result = generate_invoice_from_results(
            results_path, catalog_path, output_path, weight_price
        )

        if result.get("ok"):
            self.append_logs(
                [
                    f"[INFO] Invoice generated successfully!",
                    f"[INFO] Output: {result['path']}",
                    f"[INFO] Clients processed: {result.get('clients', 0)}",
                ]
            )

            QMessageBox.information(
                self,
                "Invoice Generated",
                f"Invoice generated successfully!\n\nFile: {result['path']}\nClients: {result.get('clients', 0)}",
            )
        else:
            self.append_logs(
                [f"[ERROR] Invoice generation failed: {result.get('error')}"]
            )

            QMessageBox.critical(
                self,
                "Invoice Generation Failed",
                f"Failed to generate invoice:\n\n{result.get('error')}",
            )

    def append_logs(self, lines):
        """Append log lines to all log widgets."""
        for logs_widget in self.logs_widgets:
            logs_widget.append_logs(lines)

    def _update_logs_visibility(self):
        """Update logs widget visibility based on settings."""
        from gearledger.desktop.settings_manager import load_settings

        settings = load_settings()
        show_logs = settings.show_logs

        # Update visibility in both tabs
        self.logs_widget_automated.setVisible(show_logs)
        self.logs_widget_manual.setVisible(show_logs)

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

        super().closeEvent(event)
