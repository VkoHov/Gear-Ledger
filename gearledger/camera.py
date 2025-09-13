# -*- coding: utf-8 -*-
import cv2


def open_camera(index: int = 0, width: int = 1280, height: int = 720):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return None
    # Try to set resolution (best-effort)
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    except Exception:
        pass
    return cap


def read_frame(cap):
    if cap is None:
        return None
    ok, frame = cap.read()
    if not ok:
        return None
    return frame  # BGR ndarray


def release_camera(cap):
    try:
        if cap is not None:
            cap.release()
    except Exception:
        pass
