import cv2

def open_camera(index=0):
    cam = cv2.VideoCapture(index, cv2.CAP_DSHOW) if hasattr(cv2, "CAP_DSHOW") else cv2.VideoCapture(index)
    if not cam.isOpened():
        return None
    # optional: set resolution
    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    return cam

def grab_frame(cam):
    return cam.read()
