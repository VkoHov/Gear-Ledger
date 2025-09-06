# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Optional, Set

from .logging_utils import step, info, warn, err
from .config import (
    OPENAI_API_KEY,
    DEFAULT_LANGS,
    DEFAULT_MODEL,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
    DEFAULT_TARGET,
)
from .ocr_utils import init_ocr_engines, ocr_extract_pairs_multi
from .excel_utils import try_match_in_excel
from .gpt_utils import (
    get_openai_client,
    rank_with_gpt,
    parse_compact_json,
    estimate_cost,
)
from .heuristics import (
    normalize_code,
    looks_like_part,
    score_candidate,
    is_vendor_like,
    is_oem_like,
)


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
    api_key: Optional[str] = OPENAI_API_KEY,
) -> Dict[str, Any]:
    """Run the full pipeline and return a result dict for UI/CLI."""
    logs: List[str] = []

    def log(fn, msg):
        fn(msg)
        logs.append(msg)

    langs = langs or DEFAULT_LANGS
    log(step, f"Using image: {image_path}")
    log(step, f"Using excel: {excel_path}")
    log(step, f"Languages: {langs}")
    log(step, f"Target: {target}")

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

    # simple filter (no context used here)
    filtered = [(t, s) for (t, s) in pairs_sorted if looks_like_part(t, target, set())]
    log(step, f"Filtered for GPT ({len(filtered)}):")
    for t, s in filtered:
        logs.append(f"  - {t}  (conf {s:.2f})")
    if not filtered:
        filtered = pairs_sorted[:]

    # GPT (if key present)
    client = get_openai_client(api_key)
    best_visible = ""
    best_norm = ""
    reason = ""
    gpt_raw = ""
    gpt_cost = None
    if client:
        raw, tin, tout = rank_with_gpt(client, model, filtered, target)
        gpt_raw = raw
        try:
            g = parse_compact_json(raw)
            best_visible = (g.get("best") or "").strip()
            best_norm = normalize_code(g.get("normalized") or "")
            reason = g.get("reason", "")
        except Exception as e:
            log(warn, f"Failed to parse GPT JSON: {e}")
        gpt_cost = estimate_cost(model, tin, tout)
        if gpt_cost is not None:
            log(info, f"Approx GPT cost: ${gpt_cost:.6f}")

    # --- Auto-mode vendor override if GPT chose OEM ---
    if target == "auto" and best_visible:
        if is_oem_like(best_visible):
            vendor_cands = [(t, s) for (t, s) in filtered if is_vendor_like(t)]
            if vendor_cands:
                scored = [
                    (t, s, score_candidate(t, s, "auto", set()))
                    for (t, s) in vendor_cands
                ]
                scored.sort(
                    key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True
                )
                top_vendor = scored[0][0]
                if top_vendor and normalize_code(top_vendor) != best_norm:
                    log(
                        info,
                        f"Auto-mode: overriding OEM '{best_visible}' with vendor '{top_vendor}'.",
                    )
                    best_visible = top_vendor
                    best_norm = normalize_code(top_vendor)
                    reason = "vendor_override_auto"

    # Local fallback if still nothing
    if not best_norm:
        log(info, "Local scoring fallback.")
        scored = [(t, s, score_candidate(t, s, target, set())) for (t, s) in filtered]
        scored.sort(key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True)
        best_visible = scored[0][0]
        best_norm = normalize_code(scored[0][0])
        reason = "local_scoring_fallback"

    log(step, f"BEST (visible): {best_visible}")
    log(step, f"BEST (normalized): {best_norm}")

    # Excel match
    log(step, "Matching in Excel using selected artikul ...")
    client_found, artikul_display, dbg = try_match_in_excel(
        excel_path, best_norm, min_fuzzy
    )
    logs.append("[MATCH DEBUG] ------------------")
    logs.append(dbg)
    logs.append("---------- end MATCH DEBUG -----")
    if client_found:
        log(step, f"MATCH FOUND → Артикул: {artikul_display}  | Клиент: {client_found}")
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
        "gpt_raw": gpt_raw,
        "gpt_cost": gpt_cost,
        "match_client": client_found,
        "match_artikul": artikul_display,
        "match_debug": dbg,
        "logs": logs,
    }
