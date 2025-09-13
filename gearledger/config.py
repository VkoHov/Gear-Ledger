# -*- coding: utf-8 -*-
"""
Central config & sane defaults for GearLedger.
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
DEFAULT_LANGS = ["en", "ru"]  # used only if you switch to Paddle
DEFAULT_MAX_SIDE = 1280  # max image side before OCR/Vision (downscale if larger)
DEFAULT_MODEL = "gpt-4o-mini"  # OpenAI model for ranking/extraction
DEFAULT_TARGET = "auto"  # 'auto' | 'vendor' | 'oem'
DEFAULT_MIN_FUZZY = 70  # minimal fuzzy score to accept Excel match
DEFAULT_MAX_ITEMS = 30  # max OCR items to consider (Paddle path)

# ---- Vision backend selection ----
# "openai" → use GPT-4o/4o-mini Vision (no Paddle)
# "paddle" → use your existing PaddleOCR → GPT ranking flow
DEFAULT_VISION_BACKEND = os.getenv("VISION_BACKEND", "openai").strip().lower()

# Optional: max tokens for vision response (keep small; we only want compact JSON)
OPENAI_VISION_MAX_TOKENS = int(os.getenv("OPENAI_VISION_MAX_TOKENS", "300"))
