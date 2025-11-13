# gearledger/desktop/scale_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import time
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QMessageBox,
)

from gearledger.desktop.scale import read_weight_once, parse_weight


class ScaleWidget(QGroupBox):
    """Scale integration widget for automatic weight reading."""

    # Signals
    weight_ready = pyqtSignal(float)  # Emitted when weight is stable
    weight_changed = pyqtSignal(float)  # Emitted when weight changes

    def __init__(self, parent=None):
        super().__init__("Scale Integration", parent)

        # Scale settings
        self.scale_port = os.getenv("SCALE_PORT", "")
        self.scale_baudrate = int(os.getenv("SCALE_BAUDRATE", "9600"))
        self.weight_threshold = float(os.getenv("WEIGHT_THRESHOLD", "0.1"))  # kg
        self.stable_time = float(os.getenv("STABLE_TIME", "2.0"))  # seconds

        # State
        self.current_weight = 0.0
        self.last_stable_weight = 0.0
        self.stable_start_time = None
        self.is_monitoring = False

        # Callbacks
        self.on_weight_ready: Callable[[float], None] | None = None

        self._setup_ui()
        self._setup_connections()
        self._setup_timers()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Scale settings
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Scale Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.addItems(
            ["", "/dev/ttyUSB0", "/dev/ttyUSB1", "COM1", "COM2", "COM3"]
        )
        if self.scale_port:
            self.port_combo.setCurrentText(self.scale_port)
        settings_layout.addWidget(self.port_combo, 1)

        settings_layout.addWidget(QLabel("Baudrate:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText(str(self.scale_baudrate))
        settings_layout.addWidget(self.baudrate_combo)
        layout.addLayout(settings_layout)

        # Weight display
        weight_layout = QVBoxLayout()
        self.weight_label = QLabel("Weight: -- kg")
        self.weight_label.setStyleSheet(
            """
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: #ffffff;
                text-align: center;
            }
        """
        )
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weight_layout.addWidget(self.weight_label)

        # Status
        self.status_label = QLabel("Status: Disconnected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                padding: 5px;
            }
        """
        )
        weight_layout.addWidget(self.status_label)
        layout.addLayout(weight_layout)

        # Controls
        controls_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect Scale")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)
        self.btn_tare = QPushButton("Tare")
        self.btn_tare.setEnabled(False)

        controls_layout.addWidget(self.btn_connect)
        controls_layout.addWidget(self.btn_disconnect)
        controls_layout.addWidget(self.btn_tare)
        controls_layout.addStretch(1)
        layout.addLayout(controls_layout)

        # Auto-capture settings
        auto_layout = QHBoxLayout()
        self.auto_capture_checkbox = QLabel("Auto-capture when weight stabilizes")
        self.auto_capture_checkbox.setStyleSheet(
            """
            QLabel {
                font-size: 11px;
                color: #34495e;
                font-style: italic;
            }
        """
        )
        auto_layout.addWidget(self.auto_capture_checkbox)
        auto_layout.addStretch(1)
        layout.addLayout(auto_layout)

    def _setup_connections(self):
        """Set up signal connections."""
        self.btn_connect.clicked.connect(self.connect_scale)
        self.btn_disconnect.clicked.connect(self.disconnect_scale)
        self.btn_tare.clicked.connect(self.tare_scale)

        # Connect weight signals
        self.weight_ready.connect(self._on_weight_ready)
        self.weight_changed.connect(self._on_weight_changed)

    def _setup_timers(self):
        """Set up monitoring timers."""
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_weight)
        self.monitor_timer.setInterval(500)  # Check every 500ms

    def set_weight_ready_callback(self, callback: Callable[[float], None]):
        """Set callback for when weight is ready."""
        self.on_weight_ready = callback

    def connect_scale(self):
        """Connect to the scale."""
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(
                self,
                "Scale Connection",
                "Please select a scale port.",
            )
            return

        try:
            baudrate = int(self.baudrate_combo.currentText())
        except ValueError:
            QMessageBox.warning(
                self,
                "Scale Connection",
                "Invalid baudrate selected.",
            )
            return

        # Try to open the port *and* read once, but do NOT fail if no data yet.
        try:
            # just a quick “ping” to check we can open the port
            test = read_weight_once(port, baudrate, timeout=3.0)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Scale Connection",
                f"Failed to open port {port}.\n\nError: {e}",
            )
            return

        # If we got here, the port is OK – even if test is None.
        self.scale_port = port
        self.scale_baudrate = baudrate
        self.is_monitoring = True

        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.btn_tare.setEnabled(True)

        if test is not None:
            self.weight_label.setText(f"Weight: {test}")
            msg = f"Successfully connected to scale on {port}.\nCurrent weight: {test}"
        else:
            msg = (
                f"Successfully connected to scale on {port}, "
                "but no weight data was received yet.\n\n"
                "This is normal if the scale is empty or only sends data when weight changes."
            )

        self.status_label.setText("Status: Connected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #27ae60;
                padding: 5px;
            }
            """
        )

        # start monitoring timer – it will poll regularly and update weight when data appears
        self.monitor_timer.start()

        QMessageBox.information(self, "Scale Connected", msg)


    def disconnect_scale(self):
        """Disconnect from the scale."""
        self.is_monitoring = False
        self.monitor_timer.stop()

        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_tare.setEnabled(False)

        self.status_label.setText("Status: Disconnected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                padding: 5px;
            }
        """
        )

        self.weight_label.setText("Weight: -- kg")
        self.current_weight = 0.0
        self.last_stable_weight = 0.0
        self.stable_start_time = None

    def tare_scale(self):
        """Tare the scale (zero it)."""
        if not self.is_monitoring:
            return

        # Read current weight and use it as tare offset
        weight = read_weight_once(self.scale_port, self.scale_baudrate, timeout=2.0)
        if weight is not None:
            parsed = parse_weight(weight)
            if parsed:
                try:
                    tare_value = float(parsed.split()[0])
                    self.last_stable_weight = tare_value
                    self.append_logs([f"Scale tared: {tare_value} kg"])
                except (ValueError, IndexError):
                    pass

    def _monitor_weight(self):
        """Monitor weight changes."""
        if not self.is_monitoring:
            return

        weight = read_weight_once(self.scale_port, self.scale_baudrate, timeout=0.5)
        if weight is None:
            return

        parsed = parse_weight(weight)
        if not parsed:
            return

        try:
            new_weight = float(parsed.split()[0])
            self.current_weight = new_weight

            # Update display
            self.weight_label.setText(f"Weight: {new_weight:.3f} kg")
            self.weight_changed.emit(new_weight)

            # Check for stability
            if abs(new_weight - self.last_stable_weight) <= self.weight_threshold:
                if self.stable_start_time is None:
                    self.stable_start_time = time.time()
                elif time.time() - self.stable_start_time >= self.stable_time:
                    # Weight is stable
                    self.last_stable_weight = new_weight
                    self.stable_start_time = None
                    self.weight_ready.emit(new_weight)
            else:
                # Weight changed, reset stability timer
                self.stable_start_time = None

        except (ValueError, IndexError):
            pass

    def _on_weight_ready(self, weight: float):
        """Handle weight ready signal."""
        if self.on_weight_ready:
            self.on_weight_ready(weight)

    def _on_weight_changed(self, weight: float):
        """Handle weight changed signal."""
        # Update status to show weight is changing
        if self.stable_start_time is None:
            self.status_label.setText("Status: Weight changing...")
            self.status_label.setStyleSheet(
                """
                QLabel {
                    font-size: 12px;
                    color: #f39c12;
                    padding: 5px;
                }
            """
            )
        else:
            self.status_label.setText("Status: Stabilizing...")
            self.status_label.setStyleSheet(
                """
                QLabel {
                    font-size: 12px;
                    color: #e67e22;
                    padding: 5px;
                }
            """
            )

    def get_current_weight(self) -> float:
        """Get the current weight reading."""
        return self.current_weight

    def is_connected(self) -> bool:
        """Check if scale is connected."""
        return self.is_monitoring

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable controls."""
        if not self.is_monitoring:
            self.btn_connect.setEnabled(enabled)
        self.btn_disconnect.setEnabled(enabled and self.is_monitoring)
        self.btn_tare.setEnabled(enabled and self.is_monitoring)
        self.port_combo.setEnabled(enabled and not self.is_monitoring)
        self.baudrate_combo.setEnabled(enabled and not self.is_monitoring)

    def append_logs(self, lines):
        """Append log lines (placeholder for compatibility)."""
        pass  # This will be connected to the main log system

    def set_log_callback(self, callback):
        """Set callback for logging."""
        self.append_logs = callback

    def cleanup(self):
        """Clean up scale resources."""
        self.disconnect_scale()
