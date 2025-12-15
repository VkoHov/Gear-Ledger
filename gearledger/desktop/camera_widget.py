# gearledger/desktop/camera_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import tempfile
import numpy as np
from typing import Callable

# cv2 will be imported lazily when camera is actually used

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
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

# Import low-level camera utilities (consistent with scale_widget.py structure)
from gearledger.desktop.camera import open_camera, read_frame, release_camera
from gearledger.desktop.translations import tr


# Camera defaults - will be loaded from settings
def get_camera_settings():
    """Get camera settings from settings manager."""
    try:
        from gearledger.desktop.settings_manager import load_settings

        settings = load_settings()
        return settings.cam_index, settings.cam_width, settings.cam_height
    except Exception:
        # Fallback to environment variables
        return (
            int(os.getenv("CAM_INDEX", "0")),
            int(os.getenv("CAM_WIDTH", "1280")),
            int(os.getenv("CAM_HEIGHT", "720")),
        )


class CameraWidget(QGroupBox):
    """Camera preview and control widget."""

    # Signals
    manual_code_submitted = pyqtSignal(str)  # Emitted when manual code is submitted

    def __init__(self, parent=None):
        super().__init__(tr("item_input"), parent)

        # Camera state
        self.cap = None
        self.timer: QTimer | None = None
        self._last_frame: np.ndarray | None = None
        self._captured_image_path: str | None = None  # Path to captured image
        self._camera_thread: QThread | None = None  # For async camera opening

        # Mode state
        self.is_manual_mode = False
        self.manual_code_value = ""

        # Callbacks
        self.on_capture_callback: Callable[[str], None] | None = None
        self.on_manual_code_callback: Callable[[str], None] | None = None

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Mode toggle buttons
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(0)

        self.btn_camera_mode = QPushButton(tr("camera"))
        self.btn_manual_code_mode = QPushButton(tr("manual"))

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

        self.btn_camera_mode.setStyleSheet(
            active_style
            + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
        )
        self.btn_manual_code_mode.setStyleSheet(
            inactive_style
            + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
        )

        mode_layout.addWidget(self.btn_camera_mode)
        mode_layout.addWidget(self.btn_manual_code_mode)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Stacked widget for different modes
        self.mode_stack = QStackedWidget()

        # === Camera mode page ===
        camera_page = QWidget()
        camera_layout = QVBoxLayout(camera_page)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(5)

        # Camera preview container (to support overlay)
        self.preview_container = QWidget()
        self.preview_container.setFixedHeight(400)
        # Minimum width for camera preview - allow it to shrink but maintain usability
        self.preview_container.setMinimumWidth(480)
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Camera preview
        self.preview = QLabel(tr("camera_preview"))
        self.preview.setFixedHeight(400)
        self.preview.setMinimumWidth(480)  # Minimum width to maintain aspect ratio
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setScaledContents(True)  # Allow image to scale with widget size
        self.preview.setStyleSheet(
            """
            QLabel {
                background-color: #2c3e50;
                color: #bdc3c7;
                border: 2px solid #34495e;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
        """
        )
        preview_layout.addWidget(self.preview)

        # Processing overlay (will be shown during processing)
        # Set as child of preview label so it overlays directly on top
        self.processing_overlay = QLabel(tr("processing"), self.preview)
        self.processing_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.processing_overlay.setStyleSheet(
            """
            QLabel {
                background-color: rgba(44, 62, 80, 0.9);
                color: #ffffff;
                border: 3px solid #3498db;
                border-radius: 8px;
                font-size: 20px;
                font-weight: bold;
                padding: 30px;
            }
        """
        )
        self.processing_overlay.hide()
        self.processing_overlay.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        # Ensure overlay is positioned absolutely (not in layout)
        # Set initial position (will be updated in _update_overlay_position)
        self.processing_overlay.setGeometry(0, 0, 350, 120)

        camera_layout.addWidget(self.preview_container)

        # Control buttons
        self.btn_start = QPushButton(tr("start_camera"))
        self.btn_capture = QPushButton(tr("capture_run"))
        self.btn_stop_cancel = QPushButton(tr("stop_cancel"))
        self.btn_capture.setEnabled(False)
        self.btn_stop_cancel.setEnabled(False)

        # Button layout - ensure buttons don't get too cramped
        button_layout = QHBoxLayout()
        button_layout.setSpacing(5)  # Add spacing between buttons
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_capture)
        button_layout.addWidget(self.btn_stop_cancel)
        button_layout.addStretch(1)

        camera_layout.addLayout(button_layout)
        self.mode_stack.addWidget(camera_page)

        # === Manual mode page ===
        manual_page = QWidget()
        manual_layout = QVBoxLayout(manual_page)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(12)

        # Manual code input area
        manual_layout.addStretch()

        # Icon/illustration
        icon_label = QLabel("🏷️")
        icon_label.setStyleSheet("font-size: 48px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        manual_layout.addWidget(icon_label)

        # Instruction label
        instruction_label = QLabel(tr("enter_part_code"))
        instruction_label.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #2c3e50;
            }
        """
        )
        instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        manual_layout.addWidget(instruction_label)

        # Manual part code input
        self.manual_code_input = QLineEdit()
        self.manual_code_input.setPlaceholderText(tr("part_code_placeholder"))
        self.manual_code_input.setStyleSheet(
            """
            QLineEdit {
                font-size: 18px;
                padding: 12px;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """
        )
        self.manual_code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.manual_code_input.setMaximumWidth(400)

        # Center the input
        input_container = QHBoxLayout()
        input_container.addStretch()
        input_container.addWidget(self.manual_code_input)
        input_container.addStretch()
        manual_layout.addLayout(input_container)

        # Search button
        self.btn_search_code = QPushButton(tr("search_add"))
        self.btn_search_code.setStyleSheet(
            """
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """
        )
        self.btn_search_code.setMaximumWidth(200)

        # Center the button
        btn_container = QHBoxLayout()
        btn_container.addStretch()
        btn_container.addWidget(self.btn_search_code)
        btn_container.addStretch()
        manual_layout.addLayout(btn_container)

        # Result display
        self.manual_result_label = QLabel("")
        self.manual_result_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                padding: 8px;
            }
        """
        )
        self.manual_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.manual_result_label.setWordWrap(True)
        manual_layout.addWidget(self.manual_result_label)

        manual_layout.addStretch()
        self.mode_stack.addWidget(manual_page)

        layout.addWidget(self.mode_stack)

        # Set minimum width for the entire widget to ensure buttons are visible
        self.setMinimumWidth(480)  # Match preview container minimum

    def _setup_connections(self):
        """Set up signal connections."""
        # Mode toggle
        self.btn_camera_mode.clicked.connect(lambda: self._set_mode(False))
        self.btn_manual_code_mode.clicked.connect(lambda: self._set_mode(True))

        # Camera mode connections
        self.btn_start.clicked.connect(self.start_camera)
        self.btn_capture.clicked.connect(self.capture_and_run)
        self.btn_stop_cancel.clicked.connect(self.stop_camera)

        # Manual mode connections
        self.btn_search_code.clicked.connect(self._submit_manual_code)
        self.manual_code_input.returnPressed.connect(self._submit_manual_code)

    def _set_mode(self, manual: bool):
        """Switch between camera and manual mode."""
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
            self.btn_camera_mode.setStyleSheet(
                inactive_style
                + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            )
            self.btn_manual_code_mode.setStyleSheet(
                active_style
                + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            )
            self.mode_stack.setCurrentIndex(1)
        else:
            self.btn_camera_mode.setStyleSheet(
                active_style
                + "border-top-left-radius: 4px; border-bottom-left-radius: 4px;"
            )
            self.btn_manual_code_mode.setStyleSheet(
                inactive_style
                + "border-top-right-radius: 4px; border-bottom-right-radius: 4px;"
            )
            self.mode_stack.setCurrentIndex(0)

    def _submit_manual_code(self):
        """Submit manual part code."""
        code = self.manual_code_input.text().strip()
        if not code:
            self.manual_result_label.setText(tr("please_enter_code"))
            self.manual_result_label.setStyleSheet(
                """
                QLabel {
                    font-size: 14px;
                    color: #e74c3c;
                    padding: 8px;
                }
            """
            )
            return

        self.manual_code_value = code
        self.manual_result_label.setText(tr("searching"))
        self.manual_result_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #f39c12;
                padding: 8px;
            }
        """
        )

        # Emit signal and call callback
        self.manual_code_submitted.emit(code)
        if self.on_manual_code_callback:
            self.on_manual_code_callback(code)

    def set_manual_code_callback(self, callback: Callable[[str], None]):
        """Set the callback function for manual code submission."""
        self.on_manual_code_callback = callback

    def show_manual_result(self, success: bool, message: str):
        """Show the result of manual code search."""
        if success:
            self.manual_result_label.setText(message)
            self.manual_result_label.setStyleSheet(
                """
                QLabel {
                    font-size: 14px;
                    color: #27ae60;
                    padding: 8px;
                    font-weight: bold;
                }
            """
            )
            # Clear the input on success
            self.manual_code_input.clear()
        else:
            self.manual_result_label.setText(message)
            self.manual_result_label.setStyleSheet(
                """
                QLabel {
                    font-size: 14px;
                    color: #e74c3c;
                    padding: 8px;
                }
            """
            )

    def set_capture_callback(self, callback: Callable[[str], None]):
        """Set the callback function for when capture is requested."""
        self.on_capture_callback = callback

    def start_camera(self):
        """Start the camera (asynchronously to avoid blocking UI)."""
        if self.cap or self._camera_thread:
            return

        # Clear captured image when starting camera
        self._captured_image_path = None

        # Show loading indicator
        self.preview.setText(tr("opening_camera"))
        self.preview.setStyleSheet(
            """
            QLabel {
                background-color: #2c3e50;
                color: #f39c12;
                border: 2px solid #34495e;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
        """
        )

        # Get camera settings from settings manager
        cam_index, cam_width, cam_height = get_camera_settings()

        # Create worker thread for camera opening (non-blocking)
        class CameraWorker(QThread):
            finished = pyqtSignal(object, int)  # cap, cam_index
            error = pyqtSignal(str, int)  # error_msg, cam_index

            def __init__(self, cam_index, cam_width, cam_height):
                super().__init__()
                self.cam_index = cam_index
                self.cam_width = cam_width
                self.cam_height = cam_height

            def run(self):
                try:
                    cap = open_camera(self.cam_index, self.cam_width, self.cam_height)
                    if cap:
                        self.finished.emit(cap, self.cam_index)
                    else:
                        self.error.emit("Failed to open camera", self.cam_index)
                except Exception as e:
                    self.error.emit(str(e), self.cam_index)

        # Start camera opening in background thread
        self._camera_thread = CameraWorker(cam_index, cam_width, cam_height)
        self._camera_thread.finished.connect(self._on_camera_opened)
        self._camera_thread.error.connect(self._on_camera_error)
        self._camera_thread.start()

    def _on_camera_opened(self, cap, cam_index):
        """Handle successful camera opening (called from worker thread)."""
        self.cap = cap
        self._camera_thread = None

        # Restore preview styling
        self.preview.setStyleSheet(
            """
            QLabel {
                background-color: #2c3e50;
                color: #bdc3c7;
                border: 2px solid #34495e;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
        """
        )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_and_show)
        self.timer.start(30)
        self._update_controls()

    def _on_camera_error(self, error_msg, cam_index):
        """Handle camera opening error (called from worker thread)."""
        self._camera_thread = None
        self.preview.setText(tr("camera_preview"))
        self.preview.setStyleSheet(
            """
            QLabel {
                background-color: #2c3e50;
                color: #bdc3c7;
                border: 2px solid #34495e;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
        """
        )
        QMessageBox.critical(
            self,
            tr("camera_title"),
            tr("camera_failed_open_msg", index=cam_index, error=error_msg),
        )

    def reset_to_live_feed(self):
        """Reset camera to show live feed (after processing is done)."""
        # Clear captured image
        self._captured_image_path = None

        # Resume live feed if camera is still open
        if self.cap:
            # Restart timer if it exists but is stopped, or create new one
            if self.timer:
                # Timer exists, just restart it
                if not self.timer.isActive():
                    self.timer.start(30)
            else:
                # Timer doesn't exist, create new one
                self.timer = QTimer(self)
                self.timer.timeout.connect(self._grab_and_show)
                self.timer.start(30)
            # Force immediate update to show live feed
            self._grab_and_show()

    def stop_camera(self):
        """Stop the camera."""
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.cap:
            release_camera(self.cap)
            self.cap = None
        # Clear captured image
        self._captured_image_path = None
        self.preview.setText(tr("camera_preview"))
        self._update_controls()

    def capture_and_run(self):
        """Capture current frame and run processing."""
        if self._last_frame is None:
            QMessageBox.information(self, tr("camera_title"), tr("no_frame_yet"))
            return

        if not self.on_capture_callback:
            return

        # Save frame to temporary file
        import cv2  # Lazy import

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        try:
            cv2.imwrite(tmp.name, self._last_frame)
            self._captured_image_path = tmp.name

            # Stop live preview timer (but keep camera open)
            if self.timer:
                self.timer.stop()
                # Don't delete timer, just stop it so we can restart later

            # Display the captured image
            self._show_captured_image(tmp.name)

            # Call the callback
            self.on_capture_callback(tmp.name)
        except Exception as e:
            QMessageBox.critical(self, tr("error"), tr("failed_save_capture", error=e))

    def _grab_and_show(self):
        """Grab frame from camera and display it."""
        # Don't show live feed if we have a captured image
        if self._captured_image_path:
            return

        frame = read_frame(self.cap)
        if frame is None:
            return

        self._last_frame = frame
        import cv2  # Lazy import

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview.width(),
            self.preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pix)

    def _show_captured_image(self, image_path: str):
        """Display the captured image in the preview."""
        try:
            import cv2  # Lazy import

            # Read the captured image
            img = cv2.imread(image_path)
            if img is None:
                return

            # Convert to RGB
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(
                self.preview.width(),
                self.preview.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(pix)

            # Update overlay position
            self._update_overlay_position()
        except Exception as e:
            print(f"[ERROR] Failed to display captured image: {e}")

    def _update_overlay_position(self):
        """Update processing overlay position to center of preview."""
        if self.processing_overlay and self.preview:
            # Get the preview label size (overlay is child of preview)
            preview_width = self.preview.width()
            preview_height = self.preview.height()

            if preview_width > 0 and preview_height > 0:
                overlay_width = 350
                overlay_height = 120
                x = (preview_width - overlay_width) // 2
                y = (preview_height - overlay_height) // 2
                # Position overlay absolutely within the preview label
                # Use move() and resize() separately to ensure proper positioning
                self.processing_overlay.move(x, y)
                self.processing_overlay.resize(overlay_width, overlay_height)
                # Ensure it's on top
                self.processing_overlay.raise_()
                # Force update to ensure visibility
                self.processing_overlay.update()
                self.processing_overlay.repaint()

    def showEvent(self, event):
        """Handle show events to update overlay position."""
        super().showEvent(event)
        # Update overlay position after widget is shown
        if hasattr(self, "processing_overlay") and self.processing_overlay:
            QTimer.singleShot(100, self._update_overlay_position)

    def resizeEvent(self, event):
        """Handle resize events to update overlay position."""
        super().resizeEvent(event)
        # Update overlay position
        if (
            hasattr(self, "processing_overlay")
            and self.processing_overlay
            and self.processing_overlay.isVisible()
        ):
            self._update_overlay_position()

    def show_processing(self):
        """Show processing indicator."""
        if self.processing_overlay:
            # Update position first
            self._update_overlay_position()
            # Then show it
            self.processing_overlay.show()
            # Ensure it's raised above all other widgets in the container
            self.processing_overlay.raise_()
            # Update position again after showing (in case geometry wasn't ready)
            QTimer.singleShot(50, self._update_overlay_position)
            # Force a repaint
            self.processing_overlay.repaint()

    def hide_processing(self):
        """Hide processing indicator."""
        if self.processing_overlay:
            self.processing_overlay.hide()

    def _update_controls(self):
        """Update button states based on camera status."""
        cam_open = self.cap is not None
        self.btn_start.setEnabled(not cam_open)
        self.btn_capture.setEnabled(cam_open)
        self.btn_stop_cancel.setEnabled(cam_open)

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable camera controls."""
        self.btn_start.setEnabled(enabled and not self.cap)
        self.btn_capture.setEnabled(enabled and self.cap is not None)
        self.btn_stop_cancel.setEnabled(
            enabled and (self.cap is not None or not enabled)
        )

    def cleanup(self):
        """Clean up camera resources."""
        self.stop_camera()
