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
    QRadioButton,
    QButtonGroup,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject

from .settings_manager import (
    Settings,
    save_settings,
    load_settings,
    get_speech_engine,
    set_speech_engine,
    get_piper_voice,
    set_piper_voice,
    get_piper_binary_path,
    set_piper_binary_path,
)
from .translations import tr


class SettingsPage(QWidget):
    """Comprehensive settings page for all application configuration."""

    # Signal emitted when network mode changes
    network_mode_changed = pyqtSignal(str, str)  # mode, address
    # Signal emitted when server receives data (to refresh UI)
    server_data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self._server = None
        self._client = None
        self._discovery = None
        self._last_speech_engine = None
        self._setup_ui()
        self._load_settings_to_ui()

        # Timer to update connected clients count (for server mode)
        self._client_count_timer = QTimer(self)
        self._client_count_timer.timeout.connect(self._update_client_count)
        self._client_count_timer.start(2000)  # Check every 2 seconds

        # Timer to update discovered servers list
        self._discovery_timer = QTimer(self)
        self._discovery_timer.timeout.connect(self._update_discovered_servers)
        self._discovery_timer.start(1000)  # Update every 1 second

        # Start discovery when in client mode
        self._start_discovery()

    def _setup_ui(self):
        """Set up the settings page UI."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title (fixed at top)
        title = QLabel(tr("application_settings"))
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
        openai_group = QGroupBox(tr("openai_api_configuration"))
        openai_layout = QVBoxLayout(openai_group)

        openai_layout.addWidget(QLabel(tr("openai_api_key_label")))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-...")
        openai_layout.addWidget(self.api_key_edit)

        # Show/Hide API key button
        api_btn_layout = QHBoxLayout()
        self.show_api_btn = QPushButton(tr("show"))
        self.show_api_btn.setMaximumWidth(80)
        self.show_api_btn.clicked.connect(self._toggle_api_key_visibility)
        api_btn_layout.addWidget(self.show_api_btn)
        api_btn_layout.addStretch(1)
        openai_layout.addLayout(api_btn_layout)

        # Vision backend and model
        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel(tr("vision_backend")))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["openai", "paddle"])
        backend_layout.addWidget(self.backend_combo)

        backend_layout.addWidget(QLabel(tr("model")))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["gpt-4o-mini", "gpt-4o"])
        backend_layout.addWidget(self.model_combo)
        backend_layout.addStretch(1)
        openai_layout.addLayout(backend_layout)

        layout.addWidget(openai_group)

        # Camera Settings
        camera_group = QGroupBox(tr("camera_configuration"))
        camera_layout = QVBoxLayout(camera_group)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel(tr("camera_index")))
        self.cam_index_spin = QSpinBox()
        self.cam_index_spin.setRange(0, 10)
        cam_row.addWidget(self.cam_index_spin)

        cam_row.addWidget(QLabel(tr("width")))
        self.cam_width_spin = QSpinBox()
        self.cam_width_spin.setRange(160, 3840)
        cam_row.addWidget(self.cam_width_spin)

        cam_row.addWidget(QLabel(tr("height")))
        self.cam_height_spin = QSpinBox()
        self.cam_height_spin.setRange(120, 2160)
        cam_row.addWidget(self.cam_height_spin)
        cam_row.addStretch(1)
        camera_layout.addLayout(cam_row)

        # Test camera button
        test_cam_btn = QPushButton(tr("test_camera"))
        test_cam_btn.clicked.connect(self._test_camera)
        camera_layout.addWidget(test_cam_btn)

        layout.addWidget(camera_group)

        # Scale Settings
        scale_group = QGroupBox(tr("scale_configuration"))
        scale_layout = QVBoxLayout(scale_group)

        scale_row1 = QHBoxLayout()
        scale_row1.addWidget(QLabel(tr("scale_port")))
        self.scale_port_edit = QLineEdit()
        self.scale_port_edit.setPlaceholderText(tr("scale_port_placeholder"))
        scale_row1.addWidget(self.scale_port_edit, 1)

        scale_row1.addWidget(QLabel(tr("baudrate")))
        self.scale_baudrate_spin = QSpinBox()
        self.scale_baudrate_spin.setRange(1200, 230400)
        scale_row1.addWidget(self.scale_baudrate_spin)
        scale_layout.addLayout(scale_row1)

        scale_row2 = QHBoxLayout()
        scale_row2.addWidget(QLabel(tr("weight_threshold")))
        self.weight_threshold_spin = QDoubleSpinBox()
        self.weight_threshold_spin.setRange(0.001, 10.0)
        self.weight_threshold_spin.setDecimals(3)
        scale_row2.addWidget(self.weight_threshold_spin)

        scale_row2.addWidget(QLabel(tr("stable_time")))
        self.stable_time_spin = QDoubleSpinBox()
        self.stable_time_spin.setRange(0.1, 10.0)
        self.stable_time_spin.setDecimals(1)
        scale_row2.addWidget(self.stable_time_spin)
        scale_row2.addStretch(1)
        scale_layout.addLayout(scale_row2)

        # Test scale button
        test_scale_btn = QPushButton(tr("test_scale_connection"))
        test_scale_btn.clicked.connect(self._test_scale)
        scale_layout.addWidget(test_scale_btn)

        layout.addWidget(scale_group)

        # Processing Settings
        processing_group = QGroupBox(tr("processing_configuration"))
        processing_layout = QVBoxLayout(processing_group)

        proc_row1 = QHBoxLayout()
        proc_row1.addWidget(QLabel(tr("default_target")))
        self.target_combo = QComboBox()
        self.target_combo.addItems(["auto", "vendor", "oem"])
        proc_row1.addWidget(self.target_combo)

        proc_row1.addWidget(QLabel(tr("min_fuzzy_score")))
        self.min_fuzzy_spin = QSpinBox()
        self.min_fuzzy_spin.setRange(0, 100)
        proc_row1.addWidget(self.min_fuzzy_spin)
        proc_row1.addStretch(1)
        processing_layout.addLayout(proc_row1)

        layout.addWidget(processing_group)

        # UI Settings
        ui_group = QGroupBox(tr("ui_configuration"))
        ui_layout = QVBoxLayout(ui_group)

        # Language selection
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(tr("language_label")))
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.setMaximumWidth(150)
        lang_row.addWidget(self.language_combo)
        lang_row.addStretch(1)
        ui_layout.addLayout(lang_row)

        self.show_logs_checkbox = QCheckBox(tr("show_logs_widget"))
        self.show_logs_checkbox.setToolTip(tr("show_logs_tooltip"))
        ui_layout.addWidget(self.show_logs_checkbox)

        # OpenAI TTS toggle
        layout.addWidget(ui_group)

        # Voice Support
        voice_group = QGroupBox(tr("voice_support"))
        voice_layout = QVBoxLayout(voice_group)

        # Speech engine selection (OS or Piper only)
        engine_row = QHBoxLayout()
        engine_row.addWidget(QLabel(tr("speech_engine_label")))
        self.speech_engine_combo = QComboBox()
        self.speech_engine_combo.addItem(tr("speech_engine_os"), "os")
        self.speech_engine_combo.addItem(tr("speech_engine_piper"), "piper")
        engine_row.addWidget(self.speech_engine_combo)
        engine_row.addStretch(1)
        voice_layout.addLayout(engine_row)
        self.speech_engine_combo.currentIndexChanged.connect(
            self._on_speech_engine_changed
        )

        # Piper voice model id
        piper_voice_row = QHBoxLayout()
        piper_voice_row.addWidget(QLabel(tr("piper_voice_label")))
        self.piper_voice_edit = QLineEdit()
        self.piper_voice_edit.setPlaceholderText("hy_AM-gor-medium")
        piper_voice_row.addWidget(self.piper_voice_edit, 1)
        voice_layout.addLayout(piper_voice_row)

        # Piper voice help text
        piper_voice_help = QLabel(tr("piper_voice_help"))
        piper_voice_help.setWordWrap(True)
        piper_voice_help.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        voice_layout.addWidget(piper_voice_help)

        # Piper binary status + path
        # Detected path (read-only)
        detected_row = QHBoxLayout()
        detected_row.addWidget(QLabel(tr("piper_binary_path_label")))
        self.piper_binary_detect_label = QLabel()
        self.piper_binary_detect_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        detected_row.addWidget(self.piper_binary_detect_label, 1)
        voice_layout.addLayout(detected_row)

        # Override path
        piper_bin_row = QHBoxLayout()
        override_label = QLabel(tr("piper_binary_path_label"))
        piper_bin_row.addWidget(override_label)
        self.piper_binary_edit = QLineEdit()
        piper_bin_row.addWidget(self.piper_binary_edit, 1)
        browse_piper_btn = QPushButton("...")
        browse_piper_btn.setFixedWidth(30)
        browse_piper_btn.clicked.connect(self._on_browse_piper_binary)
        piper_bin_row.addWidget(browse_piper_btn)
        voice_layout.addLayout(piper_bin_row)

        # Status chips: binary + model
        status_row = QHBoxLayout()
        self.piper_binary_status = QLabel()
        self.piper_model_status = QLabel()
        for lbl in (self.piper_binary_status, self.piper_model_status):
            lbl.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 2px 6px;")
        status_row.addWidget(self.piper_binary_status)
        status_row.addWidget(self.piper_model_status)
        status_row.addStretch(1)
        voice_layout.addLayout(status_row)

        # Download + Test buttons
        buttons_row = QHBoxLayout()
        self.piper_download_btn = QPushButton(tr("download_armenian_voice"))
        self.piper_download_btn.clicked.connect(self._on_download_piper_voice)
        buttons_row.addWidget(self.piper_download_btn)

        self.piper_test_btn = QPushButton(tr("test_voice"))
        self.piper_test_btn.clicked.connect(self._on_test_voice)
        buttons_row.addWidget(self.piper_test_btn)

        buttons_row.addStretch(1)
        voice_layout.addLayout(buttons_row)

        layout.addWidget(voice_group)

        # Network Configuration
        network_group = QGroupBox(tr("network_configuration"))
        network_layout = QVBoxLayout(network_group)

        # Mode selection
        mode_label = QLabel(tr("network_mode_label"))
        network_layout.addWidget(mode_label)

        self.mode_button_group = QButtonGroup(self)
        mode_row = QHBoxLayout()

        self.standalone_radio = QRadioButton(tr("standalone_mode"))
        self.standalone_radio.setToolTip(tr("standalone_tooltip"))
        self.server_radio = QRadioButton(tr("server_mode"))
        self.server_radio.setToolTip(tr("server_tooltip"))
        self.client_radio = QRadioButton(tr("client_mode"))
        self.client_radio.setToolTip(tr("client_tooltip"))

        self.mode_button_group.addButton(self.standalone_radio, 0)
        self.mode_button_group.addButton(self.server_radio, 1)
        self.mode_button_group.addButton(self.client_radio, 2)

        mode_row.addWidget(self.standalone_radio)
        mode_row.addWidget(self.server_radio)
        mode_row.addWidget(self.client_radio)
        mode_row.addStretch(1)
        network_layout.addLayout(mode_row)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        network_layout.addWidget(separator)

        # Server settings
        server_row = QHBoxLayout()
        self.server_port_label = QLabel(tr("server_port_label"))
        server_row.addWidget(self.server_port_label)
        self.server_port_spin = QSpinBox()
        self.server_port_spin.setRange(1024, 65535)
        self.server_port_spin.setValue(8080)
        server_row.addWidget(self.server_port_spin)

        self.start_server_btn = QPushButton(tr("start_server"))
        self.start_server_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.start_server_btn.clicked.connect(self._toggle_server)
        server_row.addWidget(self.start_server_btn)

        server_row.addStretch(1)
        network_layout.addLayout(server_row)

        # Server status
        self.server_status_label = QLabel(tr("server_status_stopped"))
        self.server_status_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        network_layout.addWidget(self.server_status_label)

        # Client settings
        client_row = QHBoxLayout()
        self.server_address_label = QLabel(tr("server_address_label"))
        client_row.addWidget(self.server_address_label)

        # Server discovery combo box (editable to allow manual entry)
        self.server_address_combo = QComboBox()
        self.server_address_combo.setEditable(True)
        self.server_address_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.server_address_combo.lineEdit().setPlaceholderText("192.168.1.100:8080")
        self.server_address_combo.lineEdit().setText("")
        client_row.addWidget(self.server_address_combo, 1)

        # Refresh discovery button
        self.refresh_discovery_btn = QPushButton("🔍")
        self.refresh_discovery_btn.setToolTip(tr("refresh_server_discovery"))
        self.refresh_discovery_btn.setStyleSheet(
            "background-color: #95a5a6; color: white; font-weight: bold; padding: 6px 10px;"
        )
        self.refresh_discovery_btn.clicked.connect(self._refresh_discovery)
        client_row.addWidget(self.refresh_discovery_btn)

        self.connect_btn = QPushButton(tr("connect"))
        self.connect_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.connect_btn.clicked.connect(self._toggle_connection)
        client_row.addWidget(self.connect_btn)
        network_layout.addLayout(client_row)

        # Discovery status
        self.discovery_status_label = QLabel(tr("discovering_servers"))
        self.discovery_status_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        network_layout.addWidget(self.discovery_status_label)

        # Connection status
        self.connection_status_label = QLabel(tr("connection_status_disconnected"))
        self.connection_status_label.setStyleSheet(
            "color: #7f8c8d; font-style: italic;"
        )
        network_layout.addWidget(self.connection_status_label)

        # Connect mode radio buttons to update UI
        self.standalone_radio.toggled.connect(self._update_network_ui)
        self.server_radio.toggled.connect(self._update_network_ui)
        self.client_radio.toggled.connect(self._update_network_ui)

        layout.addWidget(network_group)

        # Pricing Settings
        pricing_group = QGroupBox(tr("pricing_configuration"))
        pricing_layout = QVBoxLayout(pricing_group)

        price_row = QHBoxLayout()
        price_row.addWidget(QLabel(tr("weight_price_per_kg")))
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
        result_file_group = QGroupBox(tr("default_result_file"))
        result_file_layout = QVBoxLayout(result_file_group)
        result_file_layout.setSpacing(8)

        result_file_layout.addWidget(QLabel(tr("default_result_file_label")))

        result_file_row = QHBoxLayout()
        result_file_row.setSpacing(5)
        self.default_result_file_edit = QLineEdit()
        self.default_result_file_edit.setPlaceholderText(
            tr("leave_empty_auto_generate")
        )
        result_file_row.addWidget(self.default_result_file_edit, 1)

        browse_result_btn = QPushButton(tr("browse"))
        browse_result_btn.setMaximumWidth(100)
        browse_result_btn.clicked.connect(self._browse_default_result_file)
        result_file_row.addWidget(browse_result_btn)

        reset_result_btn = QPushButton(tr("use_default"))
        reset_result_btn.setMaximumWidth(120)
        reset_result_btn.setToolTip(tr("use_default_tooltip"))
        reset_result_btn.clicked.connect(self._reset_default_result_file)
        result_file_row.addWidget(reset_result_btn)

        result_file_layout.addLayout(result_file_row)

        from gearledger.desktop.settings_manager import APP_DIR

        default_data_dir = os.path.join(APP_DIR, "data")
        info_label = QLabel(tr("if_empty_files_auto_generated", path=default_data_dir))
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
        self.reset_btn = QPushButton(tr("reset_to_defaults"))
        self.reset_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; padding: 8px 16px;"
        )
        self.reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self.reset_btn)
        button_layout.addStretch(1)
        self.cancel_btn = QPushButton(tr("cancel"))
        self.cancel_btn.setStyleSheet("padding: 8px 16px;")
        self.save_btn = QPushButton(tr("save_settings"))
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
        self.show_logs_checkbox.setChecked(s.show_logs)

        # Voice / speech settings
        # Engine (only 'os' or 'piper' are supported now)
        engine = getattr(s, "speech_engine", "os")
        if engine not in ("os", "piper"):
            engine = "os"
        idx = self.speech_engine_combo.findData(engine)
        if idx >= 0:
            self.speech_engine_combo.setCurrentIndex(idx)
        self._last_speech_engine = engine
        # Piper voice and binary
        self.piper_voice_edit.setText(getattr(s, "piper_voice", "hy_AM-gor-medium"))
        self.piper_binary_edit.setText(getattr(s, "piper_binary_path", ""))
        self._update_piper_status()
        # Set language combo by data value
        lang_index = self.language_combo.findData(s.language)
        if lang_index >= 0:
            self.language_combo.setCurrentIndex(lang_index)

        # Network settings
        self.server_port_spin.setValue(s.server_port)
        if s.server_address:
            self.server_address_combo.lineEdit().setText(s.server_address)

        # Set network mode radio
        if s.network_mode == "server":
            self.server_radio.setChecked(True)
        elif s.network_mode == "client":
            self.client_radio.setChecked(True)
        else:
            self.standalone_radio.setChecked(True)

        self._update_network_ui()

    def _toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_key_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_api_btn.setText(tr("hide"))
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_api_btn.setText(tr("show"))

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
                        tr("camera_test"),
                        tr(
                            "camera_working",
                            index=cam_index,
                            width=frame.shape[1],
                            height=frame.shape[0],
                        ),
                    )
                else:
                    QMessageBox.warning(
                        self,
                        tr("camera_test"),
                        tr("camera_no_frame", index=cam_index),
                    )
            else:
                QMessageBox.warning(
                    self, tr("camera_test"), tr("camera_failed_open", index=cam_index)
                )
        except Exception as e:
            QMessageBox.critical(
                self, tr("camera_test"), tr("camera_test_error", error=e)
            )

    def _browse_default_result_file(self):
        """Browse for default result file location."""
        from PyQt6.QtWidgets import QFileDialog

        current_path = self.default_result_file_edit.text().strip()
        fn, _ = QFileDialog.getSaveFileName(
            self,
            tr("choose_default_result_file"),
            current_path if current_path else "",
            filter=tr("excel_filter"),
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
            QMessageBox.warning(self, tr("scale_test"), tr("enter_scale_port"))
            return

        try:
            from gearledger.desktop.scale import read_weight_once

            weight = read_weight_once(port, baudrate, timeout=3.0)
            if weight is not None:
                QMessageBox.information(
                    self,
                    tr("scale_test"),
                    tr(
                        "scale_connection_success",
                        port=port,
                        baudrate=baudrate,
                        weight=weight,
                    ),
                )
            else:
                QMessageBox.warning(
                    self,
                    tr("scale_test"),
                    tr("scale_connected_no_data", port=port),
                )
        except Exception as e:
            QMessageBox.critical(
                self, tr("scale_test"), tr("scale_connection_failed", error=str(e))
            )

    def _validate_openai_api_key(self, api_key: str) -> tuple[bool, str]:
        """
        Validate OpenAI API key by making a test API call.
        Returns (is_valid, error_message).
        """
        if not api_key:
            return False, "API key is empty"

        # Basic format check
        if not api_key.startswith("sk-"):
            return False, "API key format is invalid (should start with 'sk-')"

        # Test API key by making a simple request
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            # Make a minimal API call to validate the key
            # Using models.list() without limit for better compatibility
            # This is lightweight and doesn't consume credits
            try:
                # Try with limit first (newer API versions)
                list(client.models.list(limit=1))
            except (TypeError, AttributeError):
                # If limit is not supported, try without it
                list(client.models.list())
            return True, ""
        except Exception as e:
            error_msg = str(e)
            if "Invalid API key" in error_msg or "Incorrect API key" in error_msg:
                return False, "Invalid API key. Please check your key and try again."
            elif "rate limit" in error_msg.lower():
                # Rate limit is OK - key is valid but we hit rate limit
                return True, ""
            elif "authentication" in error_msg.lower() or "401" in error_msg:
                return False, "Authentication failed. Please check your API key."
            else:
                # Other errors (network, etc.) - assume key might be valid
                # Don't block saving, but warn user
                return True, f"Warning: Could not verify API key ({error_msg[:100]})"

    def _on_save(self):
        """Save settings and apply them."""
        # Validate API key if OpenAI backend is selected
        if self.backend_combo.currentText() == "openai":
            api_key = self.api_key_edit.text().strip()
            if not api_key:
                reply = QMessageBox.question(
                    self,
                    tr("missing_api_key"),
                    tr("missing_api_key_msg"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            else:
                # Validate the API key
                from PyQt6.QtWidgets import QMessageBox, QProgressDialog

                # Show progress dialog while validating
                progress = QProgressDialog(tr("validating_api_key"), None, 0, 0, self)
                progress.setWindowTitle(tr("validating_api_key_title"))
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setCancelButton(None)  # Can't cancel
                progress.setMinimumDuration(0)
                progress.show()

                # Process events to show progress dialog
                from PyQt6.QtWidgets import QApplication

                QApplication.processEvents()

                is_valid, error_msg = self._validate_openai_api_key(api_key)
                progress.close()

                if not is_valid:
                    QMessageBox.critical(
                        self,
                        tr("invalid_api_key"),
                        tr("invalid_api_key_msg", error=error_msg),
                    )
                    return
                elif error_msg:  # Warning but valid
                    reply = QMessageBox.warning(
                        self,
                        tr("api_key_validation_warning"),
                        tr("api_key_warning_msg", error=error_msg),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                else:
                    # Success
                    QMessageBox.information(
                        self,
                        tr("api_key_valid"),
                        tr("api_key_valid_msg"),
                    )

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
        self.settings.show_logs = self.show_logs_checkbox.isChecked()
        # Voice / speech
        self.settings.speech_engine = self.speech_engine_combo.currentData()
        # Keep legacy flag in sync
        self.settings.use_openai_tts = self.settings.speech_engine == "openai"
        self.settings.piper_voice = (
            self.piper_voice_edit.text().strip() or "hy_AM-gor-medium"
        )
        self.settings.piper_binary_path = self.piper_binary_edit.text().strip()
        self.settings.language = self.language_combo.currentData()

        # Network settings
        self.settings.server_port = self.server_port_spin.value()
        self.settings.server_address = (
            self.server_address_combo.lineEdit().text().strip()
        )
        if self.server_radio.isChecked():
            self.settings.network_mode = "server"
        elif self.client_radio.isChecked():
            self.settings.network_mode = "client"
        else:
            self.settings.network_mode = "standalone"

        # Update global language and speech
        from gearledger.desktop.translations import set_current_language
        from gearledger.speech import set_speech_language

        set_current_language(self.settings.language)
        set_speech_language(self.settings.language)

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
                tr("settings_saved"),
                tr("settings_saved_msg"),
            )
            self._parent_dialog.accept()
        else:
            # If not in a dialog, show message
            QMessageBox.information(
                self,
                tr("settings_saved"),
                tr("settings_saved_msg"),
            )

    def _on_reset(self):
        """Reset all settings to default values."""
        reply = QMessageBox.question(
            self,
            tr("reset_settings"),
            tr("reset_settings_msg"),
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
            tr("settings_reset_title"),
            tr("settings_reset_msg"),
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

    def _update_network_ui(self):
        """Update network UI based on selected mode."""
        is_server = self.server_radio.isChecked()
        is_client = self.client_radio.isChecked()
        is_standalone = self.standalone_radio.isChecked()

        # Show/hide server controls based on mode
        self.server_port_label.setVisible(is_server)
        self.server_port_spin.setVisible(is_server)
        self.start_server_btn.setVisible(is_server)
        self.server_status_label.setVisible(is_server)

        # Show/hide client controls based on mode
        self.server_address_label.setVisible(is_client)
        self.server_address_combo.setVisible(is_client)
        self.refresh_discovery_btn.setVisible(is_client)
        self.connect_btn.setVisible(is_client)
        self.connection_status_label.setVisible(is_client)
        self.discovery_status_label.setVisible(is_client)

        # Enable/disable based on mode
        self.server_port_spin.setEnabled(is_server)
        self.start_server_btn.setEnabled(is_server)

        self.server_address_combo.setEnabled(is_client)
        self.refresh_discovery_btn.setEnabled(is_client)
        self.connect_btn.setEnabled(is_client)

        # Start/stop discovery based on mode
        if is_client:
            self._start_discovery()
        else:
            self._stop_discovery()

        # Update button states based on current connection status
        from gearledger.server import get_server

        server = get_server()
        if is_server and server and server.is_running():
            self.start_server_btn.setText(tr("stop_server"))
            self.start_server_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
            )
            # Update server status immediately
            self._update_server_status()
        else:
            self.start_server_btn.setText(tr("start_server"))
            self.start_server_btn.setStyleSheet(
                "background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px;"
            )
            if is_standalone or not is_server:
                self.server_status_label.setText(tr("server_status_stopped"))
                self.server_status_label.setStyleSheet(
                    "color: #7f8c8d; font-style: italic;"
                )

        if is_client and self._client and self._client.is_connected():
            self.connect_btn.setText(tr("disconnect"))
            self.connect_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
            )
        else:
            self.connect_btn.setText(tr("connect"))
            self.connect_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
            )

    def _toggle_server(self):
        """Start or stop the server."""
        from gearledger.server import start_server, stop_server, get_server
        from gearledger.data_layer import set_runtime_mode

        self._server = get_server()

        if self._server and self._server.is_running():
            # Stop server
            stop_server()
            self._server = None
            set_runtime_mode("standalone")  # Reset runtime mode
            # Update UI to hide server controls
            self._update_network_ui()
            self.network_mode_changed.emit("standalone", "")
            QMessageBox.information(self, tr("server"), tr("server_stopped_msg"))
        else:
            # Start server
            port = self.server_port_spin.value()
            try:
                # Pass callback to refresh UI when data changes
                # Use QTimer.singleShot for thread-safe signal emission
                from PyQt6.QtCore import QTimer

                self._server = start_server(
                    port=port,
                    on_data_changed=lambda: QTimer.singleShot(
                        0, self.server_data_changed.emit
                    ),
                )
                if self._server and self._server.is_running():
                    set_runtime_mode("server")  # Set runtime mode to server
                    url = self._server.get_server_url()
                    # Update UI to show server controls
                    self._update_network_ui()
                    # Update status immediately
                    self._update_server_status()
                    self.network_mode_changed.emit("server", url)
                    QMessageBox.information(
                        self,
                        tr("server"),
                        tr("server_started_msg", url=url),
                    )
                else:
                    QMessageBox.critical(self, tr("server"), tr("server_start_failed"))
            except Exception as e:
                QMessageBox.critical(
                    self, tr("server"), tr("server_error", error=str(e))
                )

    def _toggle_connection(self):
        """Connect or disconnect from server."""
        from gearledger.api_client import (
            connect_to_server,
            disconnect_from_server,
            get_client,
        )
        from gearledger.data_layer import set_runtime_mode

        self._client = get_client()

        if self._client and self._client.is_connected():
            # Disconnect
            disconnect_from_server()
            self._client = None
            set_runtime_mode("standalone")  # Reset runtime mode
            self.connection_status_label.setText(tr("connection_status_disconnected"))
            self.connection_status_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic;"
            )
            self.connect_btn.setText(tr("connect"))
            self.connect_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
            )
            self.network_mode_changed.emit("standalone", "")
            QMessageBox.information(self, tr("connection"), tr("disconnected_msg"))
        else:
            # Connect
            # Check if a server is selected from dropdown
            current_data = self.server_address_combo.currentData()
            if current_data:
                address = current_data
            else:
                address = self.server_address_combo.lineEdit().text().strip()

            if not address:
                QMessageBox.warning(self, tr("connection"), tr("enter_server_address"))
                return

            # Add http:// if not present
            if not address.startswith("http://") and not address.startswith("https://"):
                address = f"http://{address}"

            try:
                self._client = connect_to_server(address)
                if self._client:
                    set_runtime_mode("client")  # Set runtime mode to client
                    self.connection_status_label.setText(
                        tr("connection_status_connected", address=address)
                    )
                    self.connection_status_label.setStyleSheet(
                        "color: #27ae60; font-weight: bold;"
                    )
                    self.connect_btn.setText(tr("disconnect"))
                    self.connect_btn.setStyleSheet(
                        "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
                    )
                    self.network_mode_changed.emit("client", address)
                    QMessageBox.information(
                        self,
                        tr("connection"),
                        tr("connected_msg", address=address),
                    )
                else:
                    QMessageBox.critical(
                        self,
                        tr("connection"),
                        tr("connection_failed", address=address),
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, tr("connection"), tr("connection_error", error=str(e))
                )

    def _update_client_count(self):
        """Update connected clients count display (called by timer)."""
        if self.server_radio.isChecked():
            # Get server instance (it might not be stored in self._server)
            from gearledger.server import get_server

            server = get_server()
            if server and server.is_running():
                self._update_server_status()

    def _update_server_status(self):
        """Update server status label with current connection count."""
        from gearledger.server import get_server

        server = get_server()
        if server and server.is_running():
            url = server.get_server_url()
            count = server.get_connected_clients_count()
            if count > 0:
                self.server_status_label.setText(
                    tr("server_status_running_with_clients", url=url, count=count)
                )
            else:
                self.server_status_label.setText(tr("server_status_running", url=url))
            self.server_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.server_status_label.setText(tr("server_status_stopped"))
            self.server_status_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic;"
            )

    def _start_discovery(self):
        """Start server discovery."""
        if self._discovery:
            return

        from gearledger.network_discovery import ServerDiscovery

        def on_server_found(server):
            """Called when a server is discovered."""
            self._update_discovered_servers()

        self._discovery = ServerDiscovery(on_server_found=on_server_found)
        self._discovery.start()

    def _stop_discovery(self):
        """Stop server discovery."""
        if self._discovery:
            self._discovery.stop()
            self._discovery = None

    def _refresh_discovery(self):
        """Manually refresh server discovery."""
        self._update_discovered_servers()
        if self._discovery:
            # Restart discovery to force refresh
            self._stop_discovery()
            self._start_discovery()

    def _update_discovered_servers(self):
        """Update the combo box with discovered servers."""
        if not self.client_radio.isChecked():
            return

        if not self._discovery:
            return

        discovered = self._discovery.get_discovered_servers()

        # Get current selection
        current_text = self.server_address_combo.lineEdit().text()

        # Update combo box items
        self.server_address_combo.clear()

        if discovered:
            for server in discovered:
                display_text = f"{server.name} ({server.ip}:{server.port})"
                self.server_address_combo.addItem(display_text, server.get_url())

            # Restore selection if it matches a discovered server
            for i in range(self.server_address_combo.count()):
                if self.server_address_combo.itemData(i) == current_text:
                    self.server_address_combo.setCurrentIndex(i)
                    break
            else:
                # If current text doesn't match, keep it as custom entry
                self.server_address_combo.lineEdit().setText(current_text)

            self.discovery_status_label.setText(
                tr("servers_found", count=len(discovered))
            )
            self.discovery_status_label.setStyleSheet(
                "color: #27ae60; font-size: 11px;"
            )
        else:
            # No servers found
            if current_text:
                self.server_address_combo.lineEdit().setText(current_text)
            self.discovery_status_label.setText(tr("no_servers_found"))
            self.discovery_status_label.setStyleSheet(
                "color: #7f8c8d; font-size: 11px;"
            )

    def _on_openai_tts_toggled(self, state):
        """Handle OpenAI TTS checkbox toggle."""
        enabled = state == Qt.CheckState.Checked.value
        api_key = os.environ.get("OPENAI_API_KEY") or self.api_key_edit.text().strip()

        if enabled and not api_key:
            # Warn user and uncheck
            QMessageBox.warning(
                self,
                tr("openai_tts_requires_key"),
                tr("openai_tts_requires_key_msg"),
            )
            self.use_openai_tts_checkbox.setChecked(False)
            return

        # Keep engine combo in sync
        if enabled:
            idx = self.speech_engine_combo.findData("openai")
            if idx >= 0:
                self.speech_engine_combo.setCurrentIndex(idx)
        else:
            # Only revert to OS if engine was openai
            if self.speech_engine_combo.currentData() == "openai":
                idx = self.speech_engine_combo.findData("os")
                if idx >= 0:
                    self.speech_engine_combo.setCurrentIndex(idx)

        # Update setting immediately (backwards compatibility)
        from gearledger.desktop.settings_manager import set_use_openai_tts

        set_use_openai_tts(enabled)
        self.settings.use_openai_tts = enabled

    def _update_piper_status(self):
        """Update Piper binary/model status chips and detected path."""
        try:
            from gearledger.piper_tts import resolve_piper_binary, get_voice_files
            from gearledger.desktop.settings_manager import get_piper_voice
        except Exception:
            return

        # Binary
        binary_path = resolve_piper_binary()
        if binary_path:
            self.piper_binary_detect_label.setText(binary_path)
            self.piper_binary_status.setText("Piper: Found")
            self.piper_binary_status.setStyleSheet(
                "color: #155724; background-color: #d4edda; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
            )
        else:
            self.piper_binary_detect_label.setText("-")
            self.piper_binary_status.setText("Piper: Not found")
            self.piper_binary_status.setStyleSheet(
                "color: #721c24; background-color: #f8d7da; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
            )

        # Model
        voice_id = self.piper_voice_edit.text().strip() or get_piper_voice()
        model_path, config_path = get_voice_files(voice_id)
        if os.path.isfile(model_path) and os.path.isfile(config_path):
            self.piper_model_status.setText("Model: Installed")
            self.piper_model_status.setStyleSheet(
                "color: #155724; background-color: #d4edda; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
            )
        else:
            self.piper_model_status.setText("Model: Not installed")
            self.piper_model_status.setStyleSheet(
                "color: #856404; background-color: #fff3cd; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
            )

    def _on_browse_piper_binary(self):
        """Select custom Piper binary path."""
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("piper_binary_path_label"),
            "",
        )
        if path:
            self.piper_binary_edit.setText(path)
            # Update status to reflect new override
            self._update_piper_status()

    def _on_download_piper_voice(self):
        """Download Armenian Piper voice model."""
        from PyQt6.QtWidgets import QProgressDialog

        voice_id = self.piper_voice_edit.text().strip() or "hy_AM-gor-medium"

        progress = QProgressDialog(tr("piper_download_started"), None, 0, 0, self)
        progress.setWindowTitle(tr("piper_download_title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.show()

        def worker():
            try:
                from gearledger.piper_tts import download_piper_voice_model

                download_piper_voice_model(voice_id)
                QTimer.singleShot(0, self._update_piper_status)
                QTimer.singleShot(
                    0,
                    lambda: QMessageBox.information(
                        self,
                        tr("piper_download_title"),
                        tr("piper_download_success"),
                    ),
                )
            except Exception as e:
                QTimer.singleShot(
                    0,
                    lambda: QMessageBox.critical(
                        self,
                        tr("piper_download_title"),
                        tr("piper_download_failed", error=str(e)),
                    ),
                )
            finally:
                QTimer.singleShot(0, progress.close)

        # Run download in background thread
        import threading

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_voice(self):
        """Test the currently selected voice engine."""
        try:
            from gearledger.piper_tts import speak_with_piper
        except Exception:
            speak_with_piper = None

        # Armenian sample with a few names
        text = "Բարեւ ձեզ։ Արմեն Մկրտչյան։ " "Անահիտ Սարգսյան։ Տիգրան Հովհաննիսյան։"

        used_piper = False
        if speak_with_piper is not None:
            try:
                used_piper = speak_with_piper(text)
            except Exception:
                used_piper = False

        if not used_piper:
            # Fallback to generic speech engine
            try:
                from gearledger.speech import speak

                speak(text)
            except Exception:
                pass

    def _on_speech_engine_changed(self, index: int):
        """Handle changes to the speech engine combo (OS / Piper)."""
        engine = self.speech_engine_combo.itemData(index)
        if engine not in ("os", "piper"):
            engine = "os"
        self._last_speech_engine = engine

    def closeEvent(self, event):
        """Clean up when widget is closed."""
        self._stop_discovery()
        if hasattr(self, "_client_count_timer"):
            self._client_count_timer.stop()
        if hasattr(self, "_discovery_timer"):
            self._discovery_timer.stop()
        super().closeEvent(event) if hasattr(super(), "closeEvent") else None

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
