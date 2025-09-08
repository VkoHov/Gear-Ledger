# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Optional, Set, List
from .logging_utils import info, warn, err, step


# ---------------- Basic helpers ----------------


def normalize_code(s: str) -> str:
    """Uppercase and remove whitespace, dashes, dots, slashes, and colons."""
    return re.sub(r"[ \t\n\r\-.:/]", "", s or "").upper()


def has_letters_and_digits(s: str) -> bool:
    return bool(re.search(r"[A-Z]", s)) and bool(re.search(r"\d", s))


def is_word_only(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]+", s or ""))


def is_pure_digits(s: str) -> bool:
    return bool(re.fullmatch(r"\d+", s or ""))


def is_barcode_like(raw: str) -> bool:
    t = re.sub(r"[ /]", "", raw or "")
    return is_pure_digits(t) and len(t) >= 7


def is_date_like(raw: str) -> bool:
    return bool(
        re.search(
            r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})(?:\s*\d{1,2}:\d{2})?\b",
            raw or "",
        )
    )


def is_time_like(raw: str) -> bool:
    return bool(re.search(r"\b\d{1,2}:\d{2}\b", raw or ""))


def is_digits_plus_word(raw: str) -> bool:
    # e.g., "641678568 Miqo"
    return bool(re.search(r"\b\d{3,}\s+[A-Za-z]{3,}\b", raw or ""))


# ---------------- Vendor / OEM recognizers ----------------

# Teknorot-style codes like O-450 / O450 (LETTER 'O', not zero)
_VENDOR_O450 = re.compile(r"^O[\s-]?\d{3,4}$", re.IGNORECASE)


def is_vendor_like(raw: str) -> bool:
    """
    Common vendor style + specific short form seen on Teknorot labels (O-450).
    """
    if not raw:
        return False
    txt = raw.strip()
    if re.fullmatch(r"[A-Za-z]{2,4}[- ]?\d{3,6}[A-Za-z0-3]{0,2}", txt):
        return True
    if _VENDOR_O450.fullmatch(txt):
        return True
    return False


def is_oem_like(raw: str) -> bool:
    """
    OEMs are often longer alphanumerics or grouped digits (with spaces/dashes).
    """
    if not raw:
        return False
    n = normalize_code(raw)
    if len(n) >= 8 and has_letters_and_digits(n):
        return True
    return bool(
        re.fullmatch(
            r"[A-Za-z]?\d{2,3}[- ]\d{2,3}[- ]\d{2,4}([ -]\d{2,4})?",
            raw.strip(),
        )
    )


def is_two_long_chunks(raw: str) -> bool:
    """
    Heuristic for junk like '076E81950 00006109P0T8' -> two long alnum chunks.
    """
    if not raw:
        return False
    chunks = re.split(r"[\s\-/_.]+", raw.strip())
    longish = [
        c
        for c in chunks
        if len(normalize_code(c)) >= 6 and re.search(r"[A-Za-z0-9]", c)
    ]
    return len(longish) >= 2


# ---------------- Filter + scoring ----------------


def looks_like_part(
    raw: str,
    target: str = "auto",
    oem_context: Optional[Set[str]] = None,  # accepted but not required
) -> bool:
    """
    Quick pre-filter: decide if a token is worth considering as a part code.
    """
    logs: List[str] = []

    def log(fn, msg):
        fn(msg)
        logs.append(msg)

    if not raw:
        return False

    n = normalize_code(raw)
    if is_pure_digits(raw):  # <- NEW: drop pure numbers like "0006"
        log(info, f"Dropping pure numbers like {raw}")
        return False
    if is_date_like(raw) or is_time_like(raw):
        log(info, f"Dropping date or time like {raw}")
        return False
    if is_barcode_like(raw):
        log(info, f"Dropping barcode like {raw}")
        return False
    if is_word_only(n):
        log(info, f"Dropping word only like {raw}")
        return False  # single word like BRAND, COUNTRY
    if is_digits_plus_word(raw):
        log(info, f"Dropping digits plus word like {raw}")
        return False  # "1234 WORD" noise

    if target == "vendor":
        return is_vendor_like(raw) or (has_letters_and_digits(n) and len(n) >= 5)
    if target == "oem":
        return is_oem_like(raw)

    # auto → accept either vendor-like or OEM-like or any long-ish alnum
    return (
        is_vendor_like(raw)
        or is_oem_like(raw)
        or (has_letters_and_digits(n) and len(n) >= 8)
    )


def score_candidate(
    target: str,
    oem_context: Optional[Set[str]],
    raw: str,
    conf: float,
) -> float:
    """
    Assign a numeric score to a token. Higher is better.
    Signature matches how pipeline calls it: (target, oem_context, raw, conf).
    """
    n = normalize_code(raw or "")
    score = 0.0

    # base positives
    if has_letters_and_digits(n):
        score += 6
    if n and n[0].isalpha():
        score += 2
    if len(n) >= 8:
        score += 2
    if len(n) >= 11:
        score += 1
    if " " not in (raw or "") and re.fullmatch(r"[A-Za-z0-9\-./]+", raw or ""):
        score += 1.5
    if re.search(r"[A-Za-z].*\d", n) and re.search(r"\d.*[A-Za-z]", n):
        score += 2

    # target-specific boosts/penalties
    ctx = oem_context or set()
    if target == "vendor":
        if is_vendor_like(raw):
            score += 6
        if is_oem_like(raw):
            score -= 4
        if raw in ctx:
            score -= 3
    elif target == "oem":
        if is_oem_like(raw):
            score += 6
        if is_vendor_like(raw):
            score -= 3
        if raw in ctx:
            score += 2

    # general negatives
    if is_pure_digits(n):
        score -= 12  # stronger penalty so "0006" can’t win as fallback
    if "/" in (raw or "") and not re.search(r"[A-Za-z]", raw or ""):
        score -= 4
    if is_date_like(raw) or is_time_like(raw):
        score -= 10
    if is_digits_plus_word(raw):
        score -= 6
    if is_two_long_chunks(raw):
        score -= 4  # suppress junk like two long alnum chunks

    # OCR confidence
    try:
        c = float(conf)
    except Exception:
        c = 0.0
    score += max(0.0, min(c, 1.0)) * 1.5
    return score
