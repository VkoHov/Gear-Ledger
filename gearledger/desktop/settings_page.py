# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QPushButton,
    QFileDialog,
    QGroupBox,
    QMessageBox,
    QCheckBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from .settings_manager import Settings, save_settings, load_settings


class SettingsPage(QWidget):
    """Comprehensive settings page for all application configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self._setup_ui()
        self._load_settings_to_ui()

    def _setup_ui(self):
        """Set up the settings page UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title (fixed at top)
        title = QLabel("Application Settings")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                background-color: #ffffff;
            }
        """
        )
        main_layout.addWidget(title)

        # Create scrollable area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background-color: #f8f9fa;
            }
        """
        )

        # Content widget (scrollable)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        # OpenAI API Settings
        openai_group = QGroupBox("OpenAI API Configuration")
        openai_layout = QVBoxLayout(openai_group)

        openai_layout.addWidget(QLabel("OpenAI API Key (required for GPT vision):"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        openai_layout.addWidget(self.api_key_edit)

        # Show/Hide API key button
        api_btn_layout = QHBoxLayout()
        self.show_api_btn = QPushButton("Show")
        self.show_api_btn.setMaximumWidth(80)
        self.show_api_btn.clicked.connect(self._toggle_api_key_visibility)
        api_btn_layout.addWidget(self.show_api_btn)
        api_btn_layout.addStretch(1)
        openai_layout.addLayout(api_btn_layout)

        # Vision backend and model
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Vision Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["openai", "paddle"])
        backend_layout.addWidget(self.backend_combo)

        backend_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o-mini", "gpt-4o"])
        backend_layout.addWidget(self.model_combo)
        backend_layout.addStretch(1)
        openai_layout.addLayout(backend_layout)

        layout.addWidget(openai_group)

        # Camera Settings
        camera_group = QGroupBox("Camera Configuration")
        camera_layout = QVBoxLayout(camera_group)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Camera Index:"))
        self.cam_index_spin = QSpinBox()
        self.cam_index_spin.setRange(0, 10)
        cam_row.addWidget(self.cam_index_spin)

        cam_row.addWidget(QLabel("Width:"))
        self.cam_width_spin = QSpinBox()
        self.cam_width_spin.setRange(160, 3840)
        cam_row.addWidget(self.cam_width_spin)

        cam_row.addWidget(QLabel("Height:"))
        self.cam_height_spin = QSpinBox()
        self.cam_height_spin.setRange(120, 2160)
        cam_row.addWidget(self.cam_height_spin)
        cam_row.addStretch(1)
        camera_layout.addLayout(cam_row)

        # Test camera button
        test_cam_btn = QPushButton("Test Camera")
        test_cam_btn.clicked.connect(self._test_camera)
        camera_layout.addWidget(test_cam_btn)

        layout.addWidget(camera_group)

        # Scale Settings
        scale_group = QGroupBox("Scale Configuration")
        scale_layout = QVBoxLayout(scale_group)

        scale_row1 = QHBoxLayout()
        scale_row1.addWidget(QLabel("Scale Port:"))
        self.scale_port_edit = QLineEdit()
        self.scale_port_edit.setPlaceholderText("COM3, /dev/ttyUSB0, etc.")
        scale_row1.addWidget(self.scale_port_edit, 1)

        scale_row1.addWidget(QLabel("Baudrate:"))
        self.scale_baudrate_spin = QSpinBox()
        self.scale_baudrate_spin.setRange(1200, 230400)
        scale_row1.addWidget(self.scale_baudrate_spin)
        scale_layout.addLayout(scale_row1)

        scale_row2 = QHBoxLayout()
        scale_row2.addWidget(QLabel("Weight Threshold (kg):"))
        self.weight_threshold_spin = QDoubleSpinBox()
        self.weight_threshold_spin.setRange(0.001, 10.0)
        self.weight_threshold_spin.setDecimals(3)
        scale_row2.addWidget(self.weight_threshold_spin)

        scale_row2.addWidget(QLabel("Stable Time (seconds):"))
        self.stable_time_spin = QDoubleSpinBox()
        self.stable_time_spin.setRange(0.1, 10.0)
        self.stable_time_spin.setDecimals(1)
        scale_row2.addWidget(self.stable_time_spin)
        scale_row2.addStretch(1)
        scale_layout.addLayout(scale_row2)

        # Test scale button
        test_scale_btn = QPushButton("Test Scale Connection")
        test_scale_btn.clicked.connect(self._test_scale)
        scale_layout.addWidget(test_scale_btn)

        layout.addWidget(scale_group)

        # Processing Settings
        processing_group = QGroupBox("Processing Configuration")
        processing_layout = QVBoxLayout(processing_group)

        proc_row1 = QHBoxLayout()
        proc_row1.addWidget(QLabel("Default Target:"))
        self.target_combo = QComboBox()
        self.target_combo.addItems(["auto", "vendor", "oem"])
        proc_row1.addWidget(self.target_combo)

        proc_row1.addWidget(QLabel("Min Fuzzy Score:"))
        self.min_fuzzy_spin = QSpinBox()
        self.min_fuzzy_spin.setRange(0, 100)
        proc_row1.addWidget(self.min_fuzzy_spin)
        proc_row1.addStretch(1)
        processing_layout.addLayout(proc_row1)

        layout.addWidget(processing_group)

        # Pricing Settings
        pricing_group = QGroupBox("Pricing Configuration")
        pricing_layout = QVBoxLayout(pricing_group)

        price_row = QHBoxLayout()
        price_row.addWidget(QLabel("Weight Price (per kg):"))
        self.price_per_kg_spin = QDoubleSpinBox()
        self.price_per_kg_spin.setRange(0, 1e9)
        self.price_per_kg_spin.setDecimals(3)
        self.price_per_kg_spin.setMaximumWidth(200)
        self.price_per_kg_spin.setGroupSeparatorShown(
            False
        )  # Disable thousand separators
        price_row.addWidget(self.price_per_kg_spin)
        price_row.addStretch(1)
        pricing_layout.addLayout(price_row)

        layout.addWidget(pricing_group)

        # Default Result File Settings
        result_file_group = QGroupBox("Default Result File")
        result_file_layout = QVBoxLayout(result_file_group)
        result_file_layout.setSpacing(8)

        result_file_layout.addWidget(
            QLabel("Default result file (used when no file is selected):")
        )

        result_file_row = QHBoxLayout()
        result_file_row.setSpacing(5)
        self.default_result_file_edit = QLineEdit()
        self.default_result_file_edit.setPlaceholderText(
            "Leave empty to auto-generate in app data directory"
        )
        result_file_row.addWidget(self.default_result_file_edit, 1)

        browse_result_btn = QPushButton("Browse…")
        browse_result_btn.setMaximumWidth(100)
        browse_result_btn.clicked.connect(self._browse_default_result_file)
        result_file_row.addWidget(browse_result_btn)

        reset_result_btn = QPushButton("Use Default")
        reset_result_btn.setMaximumWidth(120)
        reset_result_btn.setToolTip("Set to default location in app data directory")
        reset_result_btn.clicked.connect(self._reset_default_result_file)
        result_file_row.addWidget(reset_result_btn)

        result_file_layout.addLayout(result_file_row)

        from gearledger.desktop.settings_manager import APP_DIR

        default_data_dir = os.path.join(APP_DIR, "data")
        info_label = QLabel(
            f"If empty, files will be auto-generated in:\n{default_data_dir}"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            """
            QLabel {
                font-size: 9px;
                color: #7f8c8d;
                font-style: italic;
                padding: 5px;
                margin-top: 5px;
            }
        """
        )
        result_file_layout.addWidget(info_label)

        layout.addWidget(result_file_group)

        # Save/Cancel/Reset buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 16px;"
        )
        self.reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self.reset_btn)
        button_layout.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("padding: 8px 16px;")
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 8px 16px;"
        )
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.save_btn.clicked.connect(self._on_save)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.save_btn)
        layout.addLayout(button_layout)

        # Add some spacing at the bottom
        layout.addSpacing(10)

        # Set the scrollable content
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # Track if we're in a dialog (to close it on save)
        self._parent_dialog = None

    def _load_settings_to_ui(self):
        """Load current settings into UI fields."""
        s = self.settings
        self.api_key_edit.setText(s.openai_api_key)
        self.backend_combo.setCurrentText(s.vision_backend)
        self.model_combo.setCurrentText(s.openai_model)
        self.cam_index_spin.setValue(s.cam_index)
        self.cam_width_spin.setValue(s.cam_width)
        self.cam_height_spin.setValue(s.cam_height)
        self.scale_port_edit.setText(s.scale_port)
        self.scale_baudrate_spin.setValue(s.scale_baudrate)
        self.weight_threshold_spin.setValue(s.weight_threshold)
        self.stable_time_spin.setValue(s.stable_time)
        self.price_per_kg_spin.setValue(s.price_per_kg)
        self.target_combo.setCurrentText(s.default_target)
        self.min_fuzzy_spin.setValue(s.default_min_fuzzy)
        self.default_result_file_edit.setText(s.default_result_file or "")

    def _toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_api_btn.setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_api_btn.setText("Show")

    def _test_camera(self):
        """Test camera connection."""
        import cv2

        cam_index = self.cam_index_spin.value()
        try:
            cap = cv2.VideoCapture(cam_index)
            if cap and cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    QMessageBox.information(
                        self,
                        "Camera Test",
                        f"Camera {cam_index} is working!\n"
                        f"Frame size: {frame.shape[1]}x{frame.shape[0]}",
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Camera Test",
                        f"Camera {cam_index} opened but couldn't read frame.",
                    )
            else:
                QMessageBox.warning(
                    self, "Camera Test", f"Failed to open camera {cam_index}."
                )
        except Exception as e:
            QMessageBox.critical(self, "Camera Test", f"Error testing camera: {e}")

    def _browse_default_result_file(self):
        """Browse for default result file location."""
        from PyQt6.QtWidgets import QFileDialog

        current_path = self.default_result_file_edit.text().strip()
        fn, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Default Result File",
            current_path if current_path else "",
            filter="Excel (*.xlsx);;All files (*)",
        )
        if fn:
            self.default_result_file_edit.setText(fn)

    def _reset_default_result_file(self):
        """Reset to default location in app data directory."""
        from gearledger.desktop.settings_manager import get_default_result_file

        default_path = get_default_result_file()
        self.default_result_file_edit.setText(default_path)

    def _test_scale(self):
        """Test scale connection."""
        port = self.scale_port_edit.text().strip()
        baudrate = self.scale_baudrate_spin.value()

        if not port:
            QMessageBox.warning(self, "Scale Test", "Please enter a scale port.")
            return

        try:
            from gearledger.desktop.scale import read_weight_once

            weight = read_weight_once(port, baudrate, timeout=3.0)
            if weight is not None:
                QMessageBox.information(
                    self,
                    "Scale Test",
                    f"Scale connection successful!\nPort: {port}\nBaudrate: {baudrate}\nWeight: {weight}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Scale Test",
                    f"Connected to {port} but no weight data received.\n"
                    "This is normal if the scale is empty.",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Scale Test", f"Failed to connect to scale:\n{str(e)}"
            )

    def _on_save(self):
        """Save settings and apply them."""
        # Validate API key if OpenAI backend is selected
        if self.backend_combo.currentText() == "openai":
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                reply = QMessageBox.question(
                    self,
                    "Missing API Key",
                    "OpenAI API key is empty. You won't be able to use GPT vision.\n"
                    "Continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

        # Update settings object
        self.settings.openai_api_key = self.api_key_edit.text().strip()
        self.settings.vision_backend = self.backend_combo.currentText()
        self.settings.openai_model = self.model_combo.currentText()
        self.settings.cam_index = self.cam_index_spin.value()
        self.settings.cam_width = self.cam_width_spin.value()
        self.settings.cam_height = self.cam_height_spin.value()
        self.settings.scale_port = self.scale_port_edit.text().strip()
        self.settings.scale_baudrate = self.scale_baudrate_spin.value()
        self.settings.weight_threshold = self.weight_threshold_spin.value()
        self.settings.stable_time = self.stable_time_spin.value()
        self.settings.price_per_kg = self.price_per_kg_spin.value()
        self.settings.default_target = self.target_combo.currentText()
        self.settings.default_min_fuzzy = self.min_fuzzy_spin.value()
        self.settings.default_result_file = self.default_result_file_edit.text().strip()

        # Save to disk
        save_settings(self.settings)

        # Apply to environment (for compatibility with existing code)
        import os

        if self.settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.settings.openai_api_key
        os.environ["CAM_INDEX"] = str(self.settings.cam_index)
        os.environ["CAM_WIDTH"] = str(self.settings.cam_width)
        os.environ["CAM_HEIGHT"] = str(self.settings.cam_height)

        # Emit signal or call callback if needed
        if hasattr(self, "on_settings_saved"):
            self.on_settings_saved(self.settings)

        # Close parent dialog if exists
        if self._parent_dialog:
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully.\n"
                "Some changes may require restarting the application.",
            )
            self._parent_dialog.accept()
        else:
            # If not in a dialog, show message
            QMessageBox.information(
                self,
                "Settings Saved",
                "Settings have been saved successfully.\n"
                "Some changes may require restarting the application.",
            )

    def _on_reset(self):
        """Reset all settings to default values."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?\n\n"
            "This will clear your API key and all custom configurations.\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Create default settings
        from gearledger.desktop.settings_manager import Settings, save_settings

        default_settings = Settings()

        # Save defaults to disk
        save_settings(default_settings)

        # Reload settings
        self.settings = load_settings()

        # Update UI with default values
        self._load_settings_to_ui()

        QMessageBox.information(
            self,
            "Settings Reset",
            "All settings have been reset to default values.\n\n"
            "Remember to configure your API key and other settings before using the application.",
        )

    def _on_cancel(self):
        """Cancel and reload settings from disk."""
        self.settings = load_settings()
        self._load_settings_to_ui()
        if hasattr(self, "on_settings_cancelled"):
            self.on_settings_cancelled()
        # Close parent dialog if exists
        if self._parent_dialog:
            self._parent_dialog.reject()

    def get_settings(self) -> Settings:
        """Get current settings (from UI, not saved yet)."""
        s = Settings()
        s.openai_api_key = self.api_key_edit.text().strip()
        s.vision_backend = self.backend_combo.currentText()
        s.openai_model = self.model_combo.currentText()
        s.cam_index = self.cam_index_spin.value()
        s.cam_width = self.cam_width_spin.value()
        s.cam_height = self.cam_height_spin.value()
        s.scale_port = self.scale_port_edit.text().strip()
        s.scale_baudrate = self.scale_baudrate_spin.value()
        s.weight_threshold = self.weight_threshold_spin.value()
        s.stable_time = self.stable_time_spin.value()
        s.price_per_kg = self.price_per_kg_spin.value()
        s.default_target = self.target_combo.currentText()
        s.default_min_fuzzy = self.min_fuzzy_spin.value()
        s.default_result_file = self.default_result_file_edit.text().strip()
        return s
