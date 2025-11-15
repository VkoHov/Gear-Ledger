# gearledger/desktop/camera_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import tempfile
import cv2
import numpy as np
from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QMessageBox,
)


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


def open_camera(index: int, w: int, h: int):
    """Open camera with specified settings."""
    cap = cv2.VideoCapture(index)
    if not cap or not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def read_frame(cap) -> np.ndarray | None:
    """Read a frame from the camera."""
    ok, frame = cap.read()
    return frame if ok else None


def release_camera(cap):
    """Release camera resources."""
    try:
        cap.release()
    except Exception:
        pass


class CameraWidget(QGroupBox):
    """Camera preview and control widget."""

    def __init__(self, parent=None):
        super().__init__("Camera", parent)

        # Camera state
        self.cap = None
        self.timer: QTimer | None = None
        self._last_frame: np.ndarray | None = None
        self._captured_image_path: str | None = None  # Path to captured image

        # Callbacks
        self.on_capture_callback: Callable[[str], None] | None = None

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Camera preview container (to support overlay)
        self.preview_container = QWidget()
        self.preview_container.setFixedHeight(430)
        self.preview_container.setMinimumWidth(640)  # Minimum width for camera preview
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Camera preview
        self.preview = QLabel("Camera preview")
        self.preview.setFixedHeight(430)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.processing_overlay = QLabel("⏳ Processing...\nPlease wait", self.preview)
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

        layout.addWidget(self.preview_container)

        # Control buttons
        self.btn_start = QPushButton("Start camera")
        self.btn_capture = QPushButton("Capture & Run")
        self.btn_stop_cancel = QPushButton("Stop / Cancel")
        self.btn_capture.setEnabled(False)
        self.btn_stop_cancel.setEnabled(False)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.btn_start)
        button_layout.addWidget(self.btn_capture)
        button_layout.addWidget(self.btn_stop_cancel)
        button_layout.addStretch(1)

        # Main layout - only add button layout, preview_container already added
        layout.addLayout(button_layout)

    def _setup_connections(self):
        """Set up signal connections."""
        self.btn_start.clicked.connect(self.start_camera)
        self.btn_capture.clicked.connect(self.capture_and_run)
        self.btn_stop_cancel.clicked.connect(self.stop_camera)

    def set_capture_callback(self, callback: Callable[[str], None]):
        """Set the callback function for when capture is requested."""
        self.on_capture_callback = callback

    def start_camera(self):
        """Start the camera."""
        if self.cap:
            return

        # Clear captured image when starting camera
        self._captured_image_path = None

        # Get camera settings from settings manager
        cam_index, cam_width, cam_height = get_camera_settings()

        self.cap = open_camera(cam_index, cam_width, cam_height)
        if not self.cap:
            QMessageBox.critical(
                self,
                "Camera",
                f"Failed to open camera (index {cam_index}).\n\n"
                "Please check:\n"
                "1. Camera is connected and not in use by another application\n"
                "2. Camera index is correct (open Settings ⚙️ to change it)\n"
                "3. Camera permissions are granted",
            )
            return

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_and_show)
        self.timer.start(30)
        self._update_controls()

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
        self.preview.setText("Camera preview")
        self._update_controls()

    def capture_and_run(self):
        """Capture current frame and run processing."""
        if self._last_frame is None:
            QMessageBox.information(self, "Camera", "No frame yet. Try again.")
            return

        if not self.on_capture_callback:
            return

        # Save frame to temporary file
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
            QMessageBox.critical(self, "Error", f"Failed to save capture: {e}")

    def _grab_and_show(self):
        """Grab frame from camera and display it."""
        # Don't show live feed if we have a captured image
        if self._captured_image_path:
            return

        frame = read_frame(self.cap)
        if frame is None:
            return

        self._last_frame = frame
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
