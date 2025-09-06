# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv

# Prevent some macOS/BLAS issues (MPS/Accelerate)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
