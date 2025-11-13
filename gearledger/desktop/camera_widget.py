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

# Camera defaults via env
CAM_INDEX = int(os.getenv("CAM_INDEX", "1"))
CAM_W = int(os.getenv("CAM_WIDTH", "1280"))
CAM_H = int(os.getenv("CAM_HEIGHT", "720"))


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

        # Callbacks
        self.on_capture_callback: Callable[[str], None] | None = None

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

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

        # Main layout
        layout.addWidget(self.preview)
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

        self.cap = open_camera(CAM_INDEX, CAM_W, CAM_H)
        if not self.cap:
            QMessageBox.critical(
                self,
                "Camera",
                "Failed to open camera. Try a different CAM_INDEX in .env",
            )
            return

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_and_show)
        self.timer.start(30)
        self._update_controls()

    def stop_camera(self):
        """Stop the camera."""
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.cap:
            release_camera(self.cap)
            self.cap = None
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
            self.on_capture_callback(tmp.name)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save capture: {e}")

    def _grab_and_show(self):
        """Grab frame from camera and display it."""
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
