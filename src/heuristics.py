# -*- coding: utf-8 -*-
import re
from typing import List, Tuple
from .logging_utils import info

Pairs = List[Tuple[str, float]]

VENDOR_HINT_WORDS = {"ART", "ART.", "ARTICLE", "ITEM", "PART", "QTY", "PCS", "EAC"}
OEM_HINT_WORDS = {"OEM", "O.E.M", "REF", "REF:", "CROSS", "CROSSREF", "CROSS-REF"}


def normalize_code(s: str) -> str:
    return re.sub(r"[ \t\n\r\-.:/]", "", s).upper()


def has_letters_and_digits(s: str) -> bool:
    return bool(re.search(r"[A-Z]", s)) and bool(re.search(r"\d", s))


def is_word_only(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]+", s))


def is_pure_digits(s: str) -> bool:
    return bool(re.fullmatch(r"\d+", s))


def is_barcode_like(raw: str) -> bool:
    t = re.sub(r"[ /]", "", raw)
    return is_pure_digits(t) and len(t) >= 7


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
    return bool(re.search(r"\b\d{3,}\s+[A-Za-z]{3,}\b", raw))


def is_vendor_like(raw: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]{2,4}[- ]?\d{3,6}[A-Za-z0-3]{0,2}", raw.strip()))


def is_oem_like(raw: str) -> bool:
    t = normalize_code(raw)
    if len(t) >= 8 and has_letters_and_digits(t):
        return True
    return bool(
        re.fullmatch(
            r"[A-Za-z]?\d{2,3}[- ]\d{2,3}[- ]\d{2,4}([ -]\d{2,4})?", raw.strip()
        )
    )


def has_any(words: set, token: str) -> bool:
    tok = normalize_code(token)
    norm = {w.replace(".", "") for w in words}
    return tok in norm


def looks_like_part(raw: str, target: str = "auto") -> bool:
    n = normalize_code(raw)
    if is_date_like(raw) or is_time_like(raw):
        return False
    if is_barcode_like(raw):
        return False
    if is_word_only(n):
        return False
    if is_digits_plus_word(raw):
        return False

    if target == "vendor":
        return is_vendor_like(raw) or (has_letters_and_digits(n) and len(n) >= 5)
    if target == "oem":
        return is_oem_like(raw)
    return (
        is_vendor_like(raw)
        or is_oem_like(raw)
        or (has_letters_and_digits(n) and len(n) >= 8)
    )


def score_candidate(raw: str, conf: float, target: str, oem_context: set) -> float:
    n = normalize_code(raw)
    score = 0.0
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

    if target == "vendor":
        if is_vendor_like(raw):
            score += 6
        if is_oem_like(raw):
            score -= 4
        if raw in oem_context:
            score -= 3
        if has_any(OEM_HINT_WORDS, raw):
            score -= 2
    elif target == "oem":
        if is_oem_like(raw):
            score += 6
        if is_vendor_like(raw):
            score -= 3
        if raw in oem_context:
            score += 2
        if has_any(OEM_HINT_WORDS, raw):
            score += 2

    if is_pure_digits(n):
        score -= 6
    if "/" in raw and not re.search(r"[A-Za-z]", raw):
        score -= 4
    if is_date_like(raw) or is_time_like(raw):
        score -= 10
    if is_digits_plus_word(raw):
        score -= 6

    score += min(max(conf, 0.0), 1.0) * 1.5
    return score


def staged_pick_best(filtered: Pairs, target: str, oem_context: set):
    # score all
    scored = [(t, s, score_candidate(t, s, target, oem_context)) for (t, s) in filtered]

    def pick_best(cands):
        cands.sort(key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True)
        return cands[0][0], normalize_code(cands[0][0])

    chosen = False
    if target == "vendor":
        stage = [(t, s, sc) for (t, s, sc) in scored if is_vendor_like(t)]
        if stage:
            return pick_best(stage)

    if target == "oem":
        stage = [(t, s, sc) for (t, s, sc) in scored if is_oem_like(t)]
        if stage:
            return pick_best(stage)

    stage = [(t, s, sc) for (t, s, sc) in scored if looks_like_part(t, target)]
    if stage:
        return pick_best(stage)

    for t, s in sorted(
        filtered, key=lambda ts: len(normalize_code(ts[0])), reverse=True
    ):
        n = normalize_code(t)
        if re.search(r"[A-Z]", n) and len(n) >= 4:
            return t, n

    return "", ""
