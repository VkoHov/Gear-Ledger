# -*- coding: utf-8 -*-
"""
Heuristics & regex helpers:
- normalization utilities
- vendor/OEM shape detectors
- quick pre-filter (looks_like_part)
- scoring (score_candidate) with OEM-context awareness
"""
from __future__ import annotations
import re
from typing import Optional, Set

# ---------------- Basic helpers ----------------


def normalize_code(s: str) -> str:
    """Uppercase and remove whitespace, dashes, dots, slashes, colons."""
    return re.sub(r"[ \t\n\r\-.:/]", "", s).upper()


def has_letters_and_digits(s: str) -> bool:
    return bool(re.search(r"[A-Z]", s)) and bool(re.search(r"\d", s))


def is_word_only(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]+", s))


def is_pure_digits(s: str) -> bool:
    return bool(re.fullmatch(r"\d+", s))


def is_barcode_like(raw: str) -> bool:
    """
    Treat as barcode-like only if, after removing separators, it is all-digits
    and long enough to plausibly be an EAN/UPC (>=12 digits).
    This prevents dropping vendor codes like '8 807 02961 02' (11 digits).
    """
    t = re.sub(r"[ /-]", "", raw)
    return is_pure_digits(t) and len(t) >= 12


def is_date_like(raw: str) -> bool:
    return bool(
        re.search(
            r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})(?:\s*\d{1,2}:\d{2})?\b",
            raw,
        )
    )


def is_time_like(raw: str) -> bool:
    return bool(re.search(r"\b\d{1,2}:\d{2}\b", raw))


def is_digits_plus_word(raw: str) -> bool:
    # e.g., "641678568 Miqo" — typical OCR noise, not a part code
    return bool(re.search(r"\b\d{3,}\s+[A-Za-z]{3,}\b", raw))


# --------------- Vendor / OEM shape detectors ---------------


def is_vendor_like(raw: str) -> bool:
    """
    Vendor shapes:
      1) Letters + digits (optional dash/space), e.g. "PK-5396", "ABC 12345"
      2) Numeric vendor codes used by some aftermarket brands (e.g., DPA):
         - "8 807 02961 02"  → 1–2 / 3 / 5 / 2
         - "8 8070296102"    → 1–2 / 6–9 / 2
    """
    s = raw.strip()

    # Classic vendor style (short letters + digits)
    if re.fullmatch(r"[A-Za-z]{2,4}[- ]?\d{3,6}[A-Za-z0-3]{0,2}", s):
        return True

    # Numeric vendor style (two variants)
    if re.fullmatch(r"\d{1,2}[- ]\d{6,9}[- ]\d{2}", s):
        return True
    if re.fullmatch(r"\d{1,2}[- ]\d{3}[- ]\d{5}[- ]\d{2}", s):
        return True

    return False


def is_oem_like(raw: str) -> bool:
    """
    OEM shapes:
      - Structured groups of digits (optionally with a leading letter) separated
        by spaces/dashes, e.g. "A 221 501 26 91", "5K6 807 393 C"
      - OR a compact alnum of reasonable length that mixes letters & digits
    """
    s = raw.strip()
    n = normalize_code(s)

    # Structured groups (very common for OEM)
    if re.fullmatch(
        r"[A-Za-z]?\d{2,3}[- ]\d{2,3}[- ]\d{2,4}([ -][A-Za-z0-9]{1,4})?", s
    ):
        return True

    # Compact alnum with both letters & digits, not too short/long
    if 8 <= len(n) <= 25 and has_letters_and_digits(n):
        return True

    return False


# --------------- Pre-filter + scoring ---------------


def looks_like_part(
    raw: str,
    target: str = "auto",
    oem_context: Optional[Set[str]] = None,  # accepted, currently not used
) -> bool:
    """
    Quick pre-filter: decide if a token is worth considering as a part code.
    Order matters: allow vendor/OEM shapes before barcode rejection.
    """
    n = normalize_code(raw)

    # obvious non-codes
    if is_date_like(raw) or is_time_like(raw):
        return False
    if is_word_only(n):
        return False
    if is_digits_plus_word(raw):
        return False

    # if it clearly looks like a code, accept early
    if is_vendor_like(raw) or is_oem_like(raw):
        return True

    # then block long pure-digit barcodes
    if is_barcode_like(raw):
        return False

    # general "long alnum" fallback
    if target == "vendor":
        return has_letters_and_digits(n) and len(n) >= 5
    if target == "oem":
        return is_oem_like(raw)

    return has_letters_and_digits(n) and len(n) >= 8


def score_candidate(
    raw: str,
    conf: float,
    target: str = "auto",
    oem_context: Optional[Set[str]] = None,
) -> float:
    """
    Score a candidate token. Higher = more likely to be the desired code.
    `oem_context` = tokens that appeared near "REF"/"OEM" hints.
    """
    oem_context = oem_context or set()
    n = normalize_code(raw)
    score = 0.0

    # Base positives
    if has_letters_and_digits(n):
        score += 6
    if n and n[0].isalpha():
        score += 2
    if len(n) >= 8:
        score += 2
    if len(n) >= 11:
        score += 1
    if " " not in raw and re.fullmatch(r"[A-Za-z0-9\-./]+", raw):
        score += 1.5
    if re.search(r"[A-Za-z].*\d", n) and re.search(r"\d.*[A-Za-z]", n):
        score += 2

    # Target-specific nudges
    if target == "vendor":
        if is_vendor_like(raw):
            score += 6
        if is_oem_like(raw):
            score -= 4
    elif target == "oem":
        if is_oem_like(raw):
            score += 6
        if is_vendor_like(raw):
            score -= 3
    else:  # auto → prefer vendor when both appear
        if is_vendor_like(raw):
            score += 4
        elif is_oem_like(raw):
            score += 1

    # OEM-context: anything that appears near REF/OEM hints is likely OEM
    if raw in oem_context:
        score -= 3
        if target == "oem":
            score += 2  # small recovery if we explicitly want OEM

    # General negatives
    if is_pure_digits(n):
        score -= 6
    if "/" in raw and not re.search(r"[A-Za-z]", raw):
        score -= 4
    if is_date_like(raw) or is_time_like(raw):
        score -= 10
    if is_digits_plus_word(raw):
        score -= 6

    # OCR confidence
    score += min(max(conf, 0.0), 1.0) * 1.5
    return score
