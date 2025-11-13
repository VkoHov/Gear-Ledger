# -*- coding: utf-8 -*-
"""
Central config & sane defaults for GearLedger.
"""
import os
from pathlib import Path

# Prevent some macOS/BLAS issues (MPS/Accelerate)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Try to load settings from settings manager (preferred)
# Fall back to environment variables for backward compatibility
try:
    from gearledger.desktop.settings_manager import load_settings

    _settings = load_settings()
    OPENAI_API_KEY = _settings.openai_api_key
    DEFAULT_MODEL = _settings.openai_model
    DEFAULT_VISION_BACKEND = _settings.vision_backend
    DEFAULT_TARGET = _settings.default_target
    DEFAULT_MIN_FUZZY = _settings.default_min_fuzzy
except Exception:
    # Fallback to environment variables (for backward compatibility or non-UI usage)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    DEFAULT_VISION_BACKEND = os.getenv("VISION_BACKEND", "openai").strip().lower()
    DEFAULT_TARGET = os.getenv("DEFAULT_TARGET", "auto")
    DEFAULT_MIN_FUZZY = int(os.getenv("DEFAULT_MIN_FUZZY", "70"))

# ---- OCR / GPT defaults (used by pipeline & UI) ----
DEFAULT_LANGS = ["en", "ru"]  # used only if you switch to Paddle
DEFAULT_MAX_SIDE = 1280  # max image side before OCR/Vision (downscale if larger)
DEFAULT_MAX_ITEMS = 30  # max OCR items to consider (Paddle path)

# Optional: max tokens for vision response (keep small; we only want compact JSON)
OPENAI_VISION_MAX_TOKENS = int(os.getenv("OPENAI_VISION_MAX_TOKENS", "300"))

ROOT_DIR = Path(__file__).resolve().parents[1]  # .../Gear-Ledger
LEDGER_PATH = str(ROOT_DIR / "result.xlsx")  # your existing file at repo root
