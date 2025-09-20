# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional
import re

from .logging_utils import step, info, warn, err
from .config import (
    OPENAI_API_KEY,
    DEFAULT_LANGS,
    DEFAULT_MODEL,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
    DEFAULT_TARGET,
    DEFAULT_VISION_BACKEND,
    OPENAI_VISION_MAX_TOKENS,
)
from .excel_utils import try_match_in_excel
from .gpt_utils import (
    get_openai_client,
    rank_with_gpt,
    rank_with_gpt_vision,
    parse_compact_json,
    estimate_cost,
)
from .heuristics import (
    normalize_code,
    looks_like_part,
    score_candidate,
    is_oem_like,
    is_vendor_like,
)

# Optional Paddle imports (used only if backend == "paddle")
try:
    from .ocr_utils import init_ocr_engines, ocr_extract_pairs_multi
except Exception:
    init_ocr_engines = None
    ocr_extract_pairs_multi = None


# ---------------------------------------------------------------------------


def _space_norm(s: str) -> str:
    """Uppercase and remove only whitespace (keep hyphens/dots untouched)."""
    return re.sub(r"\s+", "", s or "").upper()


# ---------------------------------------------------------------------------


def process_image(
    image_path: str,
    excel_path: str,
    *,
    langs: Optional[List[str]] = None,
    model: str = DEFAULT_MODEL,
    min_fuzzy: int = DEFAULT_MIN_FUZZY,
    max_items: int = DEFAULT_MAX_ITEMS,
    max_side: int = DEFAULT_MAX_SIDE,
    target: str = DEFAULT_TARGET,
    top_k: int = 5,
    api_key: Optional[str] = OPENAI_API_KEY,
) -> Dict[str, Any]:
    logs: List[str] = []

    def log(fn, msg: str):
        fn(msg)
        logs.append(msg)

    log(step, f"Using image: {image_path}")
    log(step, f"Using excel: {excel_path}")
    log(step, f"Target: {target}")
    log(info, f"Vision backend: {DEFAULT_VISION_BACKEND}")

    client = get_openai_client(api_key)

    # ------------------- OPENAI VISION PATH -------------------
    if DEFAULT_VISION_BACKEND == "openai":
        if not client:
            log(err, "Missing OPENAI_API_KEY for vision.")
            return {"ok": False, "error": "no_api_key", "logs": logs}

        # Ask GPT-4o-mini (or chosen model) to read codes from the image
        raw, tin, tout = rank_with_gpt_vision(
            client,
            model,
            image_path,
            target=target,
            top_k=top_k,
            max_tokens=OPENAI_VISION_MAX_TOKENS,
        )
        gpt_cost = estimate_cost(model, tin, tout)
        if gpt_cost is not None:
            log(info, f"Approx GPT cost: ${gpt_cost:.6f}")

        # Parse JSON from model
        best_visible = ""
        best_norm = ""
        reason = ""
        ranked_pairs: List[Tuple[str, float]] = (
            []
        )  # for UI display: (text, pseudo-conf)
        ranked_norms: List[Tuple[str, str]] = (
            []
        )  # for Excel sweep: (visible, normalized)

        try:
            g = parse_compact_json(raw)
            best_visible = (g.get("best") or "").strip()
            best_norm = normalize_code(g.get("normalized") or best_visible)
            reason = g.get("reason", "")
            ranked = g.get("ranked") or []
            for item in ranked[: max(top_k, 5)]:
                vis = (item.get("text") or "").strip()
                norm = normalize_code(item.get("normalized") or vis)
                conf = float(item.get("confidence") or 0.0)
                if vis:
                    ranked_pairs.append((vis, conf))
                    ranked_norms.append((vis, norm))
        except Exception as e:
            log(warn, f"Failed to parse GPT vision JSON: {e}")

        # Main pass: exact Excel lookup with *space-only* normalization of the *visible* token
        to_try: List[Tuple[str, str]] = ranked_norms[:] if ranked_norms else []
        if best_visible:
            to_try.append((best_visible, best_norm))  # ensure best is in the list

        match_client = None
        match_artikul = None
        dbg_all: List[str] = []

        for vis, _norm_ignored in to_try:
            q = _space_norm(vis)  # exact compare after removing spaces
            if not q:
                continue
            log(info, f"Excel exact (space) try: {vis}  (→ {q})")

            # Expect simple exact-compare helper (no fuzzy)
            client_found, artikul_display, dbg = try_match_in_excel(excel_path, q)
            if dbg:
                dbg_all.append(dbg)

            if client_found:
                match_client, match_artikul = client_found, artikul_display
                best_visible = vis
                best_norm = q  # keep what we actually matched against
                reason = reason or "excel_space_exact"
                log(step, f"Excel MATCH → {artikul_display}  | Клиент: {client_found}")
                break

        # Prepare fuzzy prompt/candidates for the UI if no match
        prompt_fuzzy = False
        cand_order: List[Tuple[str, str]] = []
        if not match_client:
            prompt_fuzzy = True
            if ranked_norms:
                # Use (visible, normalized) from model
                cand_order = ranked_norms[:10]
            else:
                # Fallback to visible list
                cand_order = [
                    (vis, normalize_code(vis)) for (vis, _c) in ranked_pairs[:10]
                ]
            log(
                warn,
                "No exact (space-only) match. Ready to start fuzzy if user confirms.",
            )

        # Final logs
        log(step, f"BEST (visible): {best_visible}")
        log(step, f"BEST (normalized): {best_norm}")
        logs.append("[MATCH DEBUG] ------------------")
        for chunk in dbg_all:
            if chunk:
                logs.append(chunk)
        logs.append("---------- end MATCH DEBUG -----")

        return {
            "ok": True,
            "image": image_path,
            "excel": excel_path,
            "target": target,
            "pairs_sorted": [],  # not used in vision path
            "filtered": ranked_pairs,  # what the model proposed (for UI)
            "best_visible": best_visible,
            "best_normalized": best_norm,
            "reason": reason,
            "gpt_raw": raw,
            "gpt_cost": gpt_cost,
            "match_client": match_client,
            "match_artikul": match_artikul,
            "match_debug": "\n\n".join(dbg_all),
            "logs": logs,
            "prompt_fuzzy": prompt_fuzzy,
            "cand_order": cand_order,
        }

    # ------------------- PADDLE → GPT PATH -------------------
    # Kept for fallback or experimentation
    langs = langs or DEFAULT_LANGS or ["en", "ru"]
    log(step, f"Languages: {langs}")
    if not init_ocr_engines or not ocr_extract_pairs_multi:
        log(err, "PaddleOCR not available in this environment.")
        return {"ok": False, "error": "ocr_unavailable", "logs": logs}

    engines = init_ocr_engines(langs)
    if not engines:
        log(err, "No OCR engines initialized.")
        return {"ok": False, "error": "ocr_init_failed", "logs": logs}

    pairs = ocr_extract_pairs_multi(image_path, engines, max_side)
    if not pairs:
        log(err, "No OCR text found.")
        return {"ok": False, "error": "no_ocr", "logs": logs}

    pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)[:max_items]
    log(step, f"Merged top {len(pairs_sorted)} texts (raw):")
    for t, s in pairs_sorted:
        logs.append(f"  - {t}  (conf {s:.2f})")

    filtered = [(t, s) for (t, s) in pairs_sorted if looks_like_part(t, target, set())]
    log(step, f"Filtered for GPT ({len(filtered)}):")
    for t, s in filtered:
        logs.append(f"  - {t}  (conf {s:.2f})")
    if not filtered:
        filtered = pairs_sorted[:]

    if not client:
        log(err, "Missing OPENAI_API_KEY.")
        return {"ok": False, "error": "no_api_key", "logs": logs}

    raw, tin, tout = rank_with_gpt(client, model, filtered, target, top_k=top_k)
    gpt_cost = estimate_cost(model, tin, tout)
    if gpt_cost is not None:
        log(info, f"Approx GPT cost: ${gpt_cost:.6f}")

    best_visible = ""
    best_norm = ""
    reason = ""
    try:
        g = parse_compact_json(raw)
        best_visible = (g.get("best") or "").strip()
        best_norm = normalize_code(g.get("normalized") or "")
        reason = g.get("reason", "")
    except Exception as e:
        log(warn, f"Failed to parse GPT JSON: {e}")

    if not best_norm:
        # Local fallback
        scored = [(t, s, score_candidate(target, set(), t, s)) for (t, s) in filtered]
        scored.sort(key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True)
        best_visible = scored[0][0]
        best_norm = normalize_code(scored[0][0])
        reason = "local_scoring_fallback"

    log(step, f"BEST (visible): {best_visible}")
    log(step, f"BEST (normalized): {best_norm}")
    log(step, "Matching in Excel using selected artikul ...")
    match_client, match_artikul, dbg = try_match_in_excel(
        excel_path, best_norm, min_fuzzy
    )
    logs.append("[MATCH DEBUG] ------------------")
    logs.append(dbg or "")
    logs.append("---------- end MATCH DEBUG -----")
    if match_client:
        log(step, f"MATCH FOUND → Артикул: {match_artikul}  | Клиент: {match_client}")
    else:
        log(
            warn,
            "No acceptable match found in Excel. Consider lowering --min_fuzzy or adding the part.",
        )

    return {
        "ok": True,
        "image": image_path,
        "excel": excel_path,
        "target": target,
        "pairs_sorted": pairs_sorted,
        "filtered": filtered,
        "best_visible": best_visible,
        "best_normalized": best_norm,
        "reason": reason,
        "gpt_raw": raw,
        "gpt_cost": gpt_cost,
        "match_client": match_client,
        "match_artikul": match_artikul,
        "match_debug": dbg,
        "logs": logs,
        "prompt_fuzzy": not bool(match_client),
        "cand_order": [(t, normalize_code(t)) for (t, _s) in filtered[:10]],
    }


# ------------------- FUZZY PASS ---------------------------------------------


def run_fuzzy_match(
    excel_path: str,
    cand_order: List[Tuple[str, str]],
    min_fuzzy: int = DEFAULT_MIN_FUZZY,
) -> Dict[str, Any]:
    """
    Second pass: try fuzzy matching across the provided (visible, normalized) candidates.
    Returns a dict with ok, match_client, match_artikul, logs.
    """
    logs: List[str] = []

    def log(fn, msg: str):
        fn(msg)
        logs.append(msg)

    log(step, "Starting FUZZY pass on candidate list …")

    dbg_all: List[str] = []

    for visible, normalized in cand_order or []:
        if not normalized:
            continue
        log(info, f"Fuzzy Excel try: {visible}  (→ {normalized})")

        # Support both versions of try_match_in_excel:
        #   (excel_path, normalized, min_fuzzy, allow_fuzzy=True)
        #   (excel_path, normalized, min_fuzzy)
        try:
            c, a, dbg = try_match_in_excel(
                excel_path, normalized, min_fuzzy, allow_fuzzy=True
            )
        except TypeError:
            c, a, dbg = try_match_in_excel(excel_path, normalized, min_fuzzy)

        if dbg:
            dbg_all.append(dbg)

        if c:
            log(step, f"FUZZY MATCH → {a}  | Клиент: {c}")
            logs.append("[FUZZY DEBUG] ------------------")
            logs.extend(dbg_all)
            logs.append("---------- end FUZZY DEBUG -----")
            return {
                "ok": True,
                "match_client": c,
                "match_artikul": a,
                "logs": logs,
            }

    log(warn, "Fuzzy pass did not find a match.")
    logs.append("[FUZZY DEBUG] ------------------")
    logs.extend(dbg_all)
    logs.append("---------- end FUZZY DEBUG -----")
    return {
        "ok": True,
        "match_client": None,
        "match_artikul": None,
        "logs": logs,
    }
