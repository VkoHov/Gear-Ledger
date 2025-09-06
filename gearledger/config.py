# -*- coding: utf-8 -*-
"""
Central config & sane defaults for GearLedger.
Pulled in by pipeline/app to avoid hardcoding in multiple places.
"""
import os
from dotenv import load_dotenv

# Prevent some macOS/BLAS issues (MPS/Accelerate)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Load .env from project root
load_dotenv()

# ---- Secrets / API keys ----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

# ---- OCR / GPT defaults (used by pipeline & UI) ----
DEFAULT_LANGS = ["en", "ru"]  # PaddleOCR languages to try
DEFAULT_MAX_SIDE = 1280  # max image side before OCR (downscale if larger)
DEFAULT_MODEL = "gpt-4o-mini"  # OpenAI model for ranking candidates
DEFAULT_TARGET = "auto"  # 'auto' | 'vendor' | 'oem'
DEFAULT_MIN_FUZZY = 70  # minimal fuzzy score to accept Excel match
DEFAULT_MAX_ITEMS = 30  # max OCR items to consider/send to GPT

# (Optional) tweakables
# DEFAULT_EXCEL_SHEET = None         # e.g., sheet name if you need one
# DEFAULT_TIME_LIMIT_S = 30          # any timeouts you want to enforce
