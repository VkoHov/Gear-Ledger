# gearledger/desktop/camera.py
# -*- coding: utf-8 -*-
"""
Low-level camera utility functions.
Separated from camera_widget.py for consistency with scale.py structure.
"""
# cv2 will be imported lazily when camera is actually used
from typing import Optional


def open_camera(index: int = 0, width: int = 1280, height: int = 720):
    """
    Open camera with specified settings.

    Args:
        index: Camera index (0 for default)
        width: Desired frame width
        height: Desired frame height

    Returns:
        cv2.VideoCapture object or None if failed
    """
    import cv2  # Lazy import - only load when camera is used

    cap = cv2.VideoCapture(index)
    if not cap or not cap.isOpened():
        return None
    # Try to set resolution (best-effort)
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    except Exception:
        pass
    return cap


def read_frame(cap):
    """
    Read a frame from the camera.

    Args:
        cap: cv2.VideoCapture object

    Returns:
        BGR ndarray frame or None if failed
    """
    if cap is None:
        return None
    ok, frame = cap.read()
    if not ok:
        return None
    return frame  # BGR ndarray


def release_camera(cap):
    """
    Release camera resources.

    Args:
        cap: cv2.VideoCapture object
    """
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass
