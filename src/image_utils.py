# -*- coding: utf-8 -*-
import tempfile
from PIL import Image, ImageOps
from .logging_utils import step, info

# Optional HEIC/HEIF support (no error if not installed)
try:
    from pillow_heif import register_heif

    register_heif()
except Exception:
    pass


def prepare_image_safe(path: str, max_side: int = 1280) -> str:
    """
    EXIF-rotate + optional downscale + save to temp JPEG.
    Returns path to temp file (must be cleaned by caller if desired).
    """
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        info(f"Original image size: {w}x{h}")
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            new_size = (int(w * scale), int(h * scale))
            im = im.resize(new_size, Image.LANCZOS)
            info(f"Downscaled to: {im.size[0]}x{im.size[1]} (scale {scale:.3f})")
        else:
            info("Downscale not needed.")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        im.convert("RGB").save(tmp.name, quality=92)
        step(f"Prepared image saved to temp: {tmp.name}")
        return tmp.name
