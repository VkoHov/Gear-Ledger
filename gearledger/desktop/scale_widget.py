# gearledger/desktop/scale_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import time
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QMessageBox,
    QLineEdit,
    QStackedWidget,
)

from gearledger.desktop.scale import read_weight_once, parse_weight


class ScaleWidget(QGroupBox):
    """Scale integration widget for automatic weight reading."""

    # Signals
    weight_ready = pyqtSignal(float)  # Emitted when weight is stable
    weight_changed = pyqtSignal(float)  # Emitted when weight changes
    manual_weight_set = pyqtSignal(float)  # Emitted when manual weight is set

    def __init__(self, parent=None):
        super().__init__("Weight Input", parent)

        # Load scale settings from settings manager (if available)
        try:
            from gearledger.desktop.settings_manager import load_settings

            settings = load_settings()
            self.scale_port = settings.scale_port or os.getenv("SCALE_PORT", "")
            self.scale_baudrate = settings.scale_baudrate
            self.weight_threshold = settings.weight_threshold
            self.stable_time = settings.stable_time
        except Exception:
            # Fallback to environment variables
            self.scale_port = os.getenv("SCALE_PORT", "")
            self.scale_baudrate = int(os.getenv("SCALE_BAUDRATE", "9600"))
            self.weight_threshold = float(os.getenv("WEIGHT_THRESHOLD", "0.1"))  # kg
            self.stable_time = float(os.getenv("STABLE_TIME", "2.0"))  # seconds

        # State
        self.current_weight = 0.0
        self.last_stable_weight = None  # None means no stable weight yet
        self.stable_start_time = None
        self.is_monitoring = False
        self._connection_thread: QThread | None = None  # For async connection
        self._serial_port = None  # Persistent serial connection
        self._monitor_thread: QThread | None = None  # Continuous reading thread

        # Callbacks
        self.on_weight_ready: Callable[[float], None] | None = None

        # Mode state
        self.is_manual_mode = False
        self.manual_weight_value = 0.0

        self._setup_ui()
        self._setup_connections()
        self._setup_timers()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # Mode toggle buttons
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(0)

        self.btn_scale_mode = QPushButton("⚖️ Scale")
        self.btn_manual_mode = QPushButton("✏️ Manual")

        # Style for toggle buttons
        active_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #ecf0f1;
                color: #7f8c8d;
                border: none;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #bdc3c7;
            }
        """

        self.btn_scale_mode.setStyleSheet(
            active_style
            + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
        )
        self.btn_manual_mode.setStyleSheet(
            inactive_style
            + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
        )

        mode_layout.addWidget(self.btn_scale_mode)
        mode_layout.addWidget(self.btn_manual_mode)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Stacked widget for different modes
        self.mode_stack = QStackedWidget()

        # === Scale mode page ===
        scale_page = QWidget()
        scale_layout = QVBoxLayout(scale_page)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.setSpacing(4)

        # Weight display (compact)
        self.weight_label = QLabel("-- kg")
        self.weight_label.setStyleSheet(
            """
            QLabel {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
                padding: 8px 12px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """
        )
        self.weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_layout.addWidget(self.weight_label)

        # Status (compact)
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 11px;
                color: #7f8c8d;
                padding: 2px;
            }
        """
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_layout.addWidget(self.status_label)

        # Controls (compact row)
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(4)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setStyleSheet("padding: 6px 10px; font-size: 10px;")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setStyleSheet("padding: 6px 10px; font-size: 10px;")
        self.btn_disconnect.setEnabled(False)
        self.btn_tare = QPushButton("Tare")
        self.btn_tare.setStyleSheet("padding: 6px 10px; font-size: 10px;")
        self.btn_tare.setEnabled(False)

        controls_layout.addWidget(self.btn_connect)
        controls_layout.addWidget(self.btn_disconnect)
        controls_layout.addWidget(self.btn_tare)
        scale_layout.addLayout(controls_layout)

        # Auto-capture note (compact)
        auto_label = QLabel("⚡ Auto-capture on stable weight")
        auto_label.setStyleSheet(
            """
            QLabel {
                font-size: 9px;
                color: #7f8c8d;
                font-style: italic;
                padding: 2px 0;
            }
        """
        )
        auto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_layout.addWidget(auto_label)

        self.mode_stack.addWidget(scale_page)

        # === Manual mode page ===
        manual_page = QWidget()
        manual_layout = QVBoxLayout(manual_page)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)

        # Manual weight input
        self.manual_weight_input = QLineEdit()
        self.manual_weight_input.setPlaceholderText("Enter weight (kg)")
        self.manual_weight_input.setStyleSheet(
            """
            QLineEdit {
                font-size: 18px;
                padding: 10px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """
        )
        self.manual_weight_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        manual_layout.addWidget(self.manual_weight_input)

        # Manual weight display (shows confirmed weight)
        self.manual_weight_display = QLabel("Weight: -- kg")
        self.manual_weight_display.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #27ae60;
                padding: 4px;
                font-weight: bold;
            }
        """
        )
        self.manual_weight_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        manual_layout.addWidget(self.manual_weight_display)

        # Set weight button
        self.btn_set_weight = QPushButton("Set Weight")
        self.btn_set_weight.setStyleSheet(
            """
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """
        )
        manual_layout.addWidget(self.btn_set_weight)

        manual_layout.addStretch()
        self.mode_stack.addWidget(manual_page)

        layout.addWidget(self.mode_stack)

        # Set compact minimum width
        self.setMinimumWidth(200)

    def _setup_connections(self):
        """Set up signal connections."""
        # Mode toggle
        self.btn_scale_mode.clicked.connect(lambda: self._set_mode(False))
        self.btn_manual_mode.clicked.connect(lambda: self._set_mode(True))

        # Scale mode connections
        self.btn_connect.clicked.connect(self.connect_scale)
        self.btn_disconnect.clicked.connect(self.disconnect_scale)
        self.btn_tare.clicked.connect(self.tare_scale)

        # Manual mode connections
        self.btn_set_weight.clicked.connect(self._set_manual_weight)
        self.manual_weight_input.returnPressed.connect(self._set_manual_weight)

        # Connect weight signals
        self.weight_ready.connect(self._on_weight_ready)
        self.weight_changed.connect(self._on_weight_changed)

    def _set_mode(self, manual: bool):
        """Switch between scale and manual mode."""
        self.is_manual_mode = manual

        # Update toggle button styles
        active_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #ecf0f1;
                color: #7f8c8d;
                border: none;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #bdc3c7;
            }
        """

        if manual:
            self.btn_scale_mode.setStyleSheet(
                inactive_style
                + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            )
            self.btn_manual_mode.setStyleSheet(
                active_style
                + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            )
            self.mode_stack.setCurrentIndex(1)
        else:
            self.btn_scale_mode.setStyleSheet(
                active_style
                + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            )
            self.btn_manual_mode.setStyleSheet(
                inactive_style
                + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            )
            self.mode_stack.setCurrentIndex(0)

    def _set_manual_weight(self):
        """Set weight from manual input."""
        try:
            weight_text = self.manual_weight_input.text().strip()
            if not weight_text:
                return

            weight = float(weight_text)
            if weight <= 0:
                QMessageBox.warning(
                    self, "Invalid Weight", "Weight must be greater than 0."
                )
                return

            self.manual_weight_value = weight
            self.manual_weight_display.setText(f"Weight: {weight:.3f} kg")
            self.manual_weight_display.setStyleSheet(
                """
                QLabel {
                    font-size: 14px;
                    color: #27ae60;
                    padding: 4px;
                    font-weight: bold;
                }
            """
            )
            self.manual_weight_set.emit(weight)

        except ValueError:
            QMessageBox.warning(self, "Invalid Weight", "Please enter a valid number.")

    def _setup_timers(self):
        """Set up monitoring timers."""
        # No longer using timer-based polling - using continuous thread-based reading instead
        pass

    def set_weight_ready_callback(self, callback: Callable[[float], None]):
        """Set callback for when weight is ready."""
        self.on_weight_ready = callback

    def connect_scale(self):
        """Connect to the scale (asynchronously to avoid blocking UI)."""
        # Load port/baudrate from settings
        try:
            from gearledger.desktop.settings_manager import load_settings

            settings = load_settings()
            port = settings.scale_port or self.scale_port
            baudrate = settings.scale_baudrate or self.scale_baudrate
        except Exception:
            port = self.scale_port
            baudrate = self.scale_baudrate

        if not port:
            QMessageBox.warning(
                self,
                "Scale Connection",
                "Please configure the scale port in Settings.",
            )
            return

        # Disable connect button and show connecting status
        self.btn_connect.setEnabled(False)
        self.status_label.setText("Connecting...")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #f39c12;
                padding: 5px;
            }
            """
        )

        # Create worker thread for connection (non-blocking)
        class ConnectionWorker(QThread):
            finished = pyqtSignal(object, str, int)  # result, port, baudrate
            error = pyqtSignal(str, str, int)  # error_msg, port, baudrate

            def __init__(self, port, baudrate):
                super().__init__()
                self.port = port
                self.baudrate = baudrate

            def run(self):
                try:
                    # Reduced timeout from 3.0 to 1.5 seconds for faster connection
                    test = read_weight_once(self.port, self.baudrate, timeout=1.5)
                    self.finished.emit(test, self.port, self.baudrate)
                except Exception as e:
                    self.error.emit(str(e), self.port, self.baudrate)

        # Start connection in background thread
        self._connection_thread = ConnectionWorker(port, baudrate)
        self._connection_thread.finished.connect(self._on_scale_connected)
        self._connection_thread.error.connect(self._on_scale_connection_error)
        self._connection_thread.start()

    def _on_scale_connected(self, test, port, baudrate):
        """Handle successful scale connection (called from worker thread)."""
        # If we got here, the port is OK – even if test is None.
        self.scale_port = port
        self.scale_baudrate = baudrate
        self.is_monitoring = True

        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.btn_tare.setEnabled(True)

        if test is not None:
            self.weight_label.setText(f"{test}")
            msg = f"Successfully connected to scale on {port}.\nCurrent weight: {test}"
        else:
            msg = (
                f"Successfully connected to scale on {port}, "
                "but no weight data was received yet.\n\n"
                "This is normal if the scale is empty or only sends data when weight changes."
            )

        self.status_label.setText("Connected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #27ae60;
                padding: 5px;
            }
            """
        )

        # Open persistent serial connection
        try:
            import serial

            self._serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=1.0,  # 1 second timeout for readline
            )

            # Start continuous monitoring thread
            self._start_monitoring_thread()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Scale Connection",
                f"Failed to open persistent connection: {e}",
            )
            self.is_monitoring = False
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self._connection_thread = None
            return

        QMessageBox.information(self, "Scale Connected", msg)
        self._connection_thread = None

    def _on_scale_connection_error(self, error_msg, port, baudrate):
        """Handle scale connection error (called from worker thread)."""
        self.btn_connect.setEnabled(True)
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                padding: 5px;
            }
            """
        )
        QMessageBox.critical(
            self,
            "Scale Connection",
            f"Failed to open port {port}.\n\nError: {error_msg}",
        )
        self._connection_thread = None

    def disconnect_scale(self):
        """Disconnect from the scale."""
        self.is_monitoring = False

        # Stop monitoring thread
        if self._monitor_thread:
            if hasattr(self._monitor_thread, "stop"):
                self._monitor_thread.stop()
            if self._monitor_thread.isRunning():
                self._monitor_thread.terminate()
                self._monitor_thread.wait(1000)  # Wait up to 1 second
            self._monitor_thread = None

        # Close serial port
        if self._serial_port:
            try:
                self._serial_port.close()
            except Exception:
                pass
            self._serial_port = None

        self.btn_connect.setEnabled(True)
        self.btn_disconnect.setEnabled(False)
        self.btn_tare.setEnabled(False)

        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet(
            """
            QLabel {
                font-size: 12px;
                color: #7f8c8d;
                padding: 5px;
            }
        """
        )

        self.weight_label.setText("-- kg")
        self.current_weight = 0.0
        self.last_stable_weight = None  # Reset to None
        self.stable_start_time = None

    def tare_scale(self):
        """Tare the scale (zero it)."""
        if not self.is_monitoring or not self._serial_port:
            return

        # Use current weight as tare offset
        if self.current_weight != 0.0:
            self.last_stable_weight = self.current_weight
            if hasattr(self, "append_logs"):
                self.append_logs([f"Scale tared: {self.current_weight:.3f} kg"])

    def _start_monitoring_thread(self):
        """Start continuous monitoring thread for scale reading."""
        if self._monitor_thread and self._monitor_thread.isRunning():
            return

        class ScaleMonitorThread(QThread):
            weight_received = pyqtSignal(str)  # Emit raw weight string
            connection_lost = pyqtSignal()  # Emit when connection is lost

            def __init__(self, serial_port, parent=None):
                super().__init__(parent)
                self.serial_port = serial_port
                self._stop = False

            def stop(self):
                self._stop = True

            def run(self):
                """Continuously read from serial port."""
                import serial

                while not self._stop:
                    try:
                        if not self.serial_port or not self.serial_port.is_open:
                            self.connection_lost.emit()
                            break

                        # Read a line (blocking with timeout)
                        raw = (
                            self.serial_port.readline().decode(errors="ignore").strip()
                        )

                        if raw:
                            print(f"Scale raw: {raw}")
                            # Skip invalid lines
                            if "/" in raw:
                                continue

                            # Parse and emit if valid
                            parsed = parse_weight(raw)
                            if parsed:
                                self.weight_received.emit(parsed)

                    except serial.SerialException as e:
                        print(f"Scale serial error: {e}")
                        self.connection_lost.emit()
                        break
                    except Exception as e:
                        print(f"Scale monitoring error: {e}")
                        # Continue reading despite errors
                        time.sleep(0.1)

        # Create and start monitoring thread
        self._monitor_thread = ScaleMonitorThread(self._serial_port, self)
        self._monitor_thread.weight_received.connect(self._on_weight_received)
        self._monitor_thread.connection_lost.connect(self._on_connection_lost)
        self._monitor_thread.start()

    def _on_weight_received(self, weight_str: str):
        """Handle weight data received from monitoring thread."""
        if not self.is_monitoring:
            return

        try:
            new_weight = float(weight_str.split()[0])

            # Ignore zero values completely if we have a meaningful weight (> 0.01 kg)
            # This prevents oscillation between 0.00 and actual weight
            if new_weight < 0.01:
                if self.current_weight > 0.01:
                    print(
                        f"[DEBUG] Ignoring zero value (current weight: {self.current_weight:.3f} kg)"
                    )
                    return
                # If current weight is also zero, just update display but don't check stability
                self.current_weight = new_weight
                self.weight_label.setText(f"{new_weight:.3f} kg")
                return

            # Only update display/emit signal if weight changed significantly (to avoid noise)
            # But still check stability even if weight hasn't changed
            weight_diff = abs(new_weight - self.current_weight)
            if weight_diff >= 0.001:  # Weight changed by at least 1 gram
                self.current_weight = new_weight
                # Update display
                self.weight_label.setText(f"{new_weight:.3f} kg")
                self.weight_changed.emit(new_weight)
            # If weight hasn't changed, we still need to check stability below

            # Initialize last_stable_weight if this is the first meaningful weight
            if self.last_stable_weight is None:
                self.last_stable_weight = new_weight
                self.stable_start_time = time.time()
                print(
                    f"[DEBUG] First meaningful weight: {new_weight:.3f} kg - starting stability check"
                )
                return

            # Check for stability (only for non-zero weights)
            # Use the actual new_weight for stability checking
            if abs(new_weight - self.last_stable_weight) <= self.weight_threshold:
                if self.stable_start_time is None:
                    self.stable_start_time = time.time()
                    print(
                        f"[DEBUG] Weight stabilizing: {new_weight:.3f} kg (threshold: {self.weight_threshold} kg, diff from stable: {abs(new_weight - self.last_stable_weight):.3f} kg)"
                    )
                elif time.time() - self.stable_start_time >= self.stable_time:
                    # Weight is stable
                    print(
                        f"[DEBUG] Weight STABILIZED: {new_weight:.3f} kg - emitting weight_ready signal"
                    )
                    self.last_stable_weight = new_weight
                    self.stable_start_time = None
                    self.weight_ready.emit(new_weight)
            else:
                # Weight changed significantly, update reference and reset stability timer
                if self.stable_start_time is not None:
                    print(
                        f"[DEBUG] Weight changed: {new_weight:.3f} kg (was {self.last_stable_weight:.3f} kg, diff: {abs(new_weight - self.last_stable_weight):.3f} kg) - resetting stability timer"
                    )
                # Update reference to new weight and reset timer
                self.last_stable_weight = new_weight
                self.stable_start_time = None

        except (ValueError, IndexError):
            pass

    def _on_connection_lost(self):
        """Handle connection loss."""
        if self.is_monitoring:
            if hasattr(self, "append_logs") and self.append_logs:
                self.append_logs(["[WARNING] Scale connection lost."])
            # Disconnect and update UI
            self.is_monitoring = False
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.status_label.setText("Connection Lost")
            self.status_label.setStyleSheet(
                """
                QLabel {
                    font-size: 12px;
                    color: #e74c3c;
                    padding: 5px;
                }
                """
            )

    def _on_weight_ready(self, weight: float):
        """Handle weight ready signal."""
        print(
            f"[DEBUG] ScaleWidget._on_weight_ready called with weight: {weight:.3f} kg"
        )
        print(f"[DEBUG] Callback exists: {self.on_weight_ready is not None}")
        if self.on_weight_ready:
            print(f"[DEBUG] Calling weight_ready callback...")
            self.on_weight_ready(weight)
        else:
            print(f"[DEBUG] WARNING: No weight_ready callback set!")

    def _on_weight_changed(self, weight: float):
        """Handle weight changed signal."""
        # Update status to show weight is changing
        if self.stable_start_time is None:
            self.status_label.setText("Changing...")
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
            self.status_label.setText("Stabilizing...")
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
        """Get the current weight reading (from scale or manual input)."""
        if self.is_manual_mode:
            return self.manual_weight_value
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

    def append_logs(self, lines):
        """Append log lines (placeholder for compatibility)."""
        pass  # This will be connected to the main log system

    def set_log_callback(self, callback):
        """Set callback for logging."""
        self.append_logs = callback

    def cleanup(self):
        """Clean up scale resources."""
        self.disconnect_scale()
