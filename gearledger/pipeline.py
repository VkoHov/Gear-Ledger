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
    is_oem_like,
    is_vendor_like,
)


# ---------------- Pipeline ----------------
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
    top_k: int = 5,  # <— how many GPT suggestions to try in Excel
    api_key: Optional[str] = OPENAI_API_KEY,
) -> Dict[str, Any]:
    logs: List[str] = []

    def log(fn, msg):
        fn(msg)
        logs.append(msg)

    langs = langs or DEFAULT_LANGS
    log(step, f"Using image: {image_path}")
    log(step, f"Using excel: {excel_path}")
    log(step, f"Languages: {langs}")
    log(step, f"Target: {target}")

    # OCR
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
        log(info, f"  - {t}  (conf {s:.2f})")

    # Pre-filter for plausible part tokens
    filtered = [(t, s) for (t, s) in pairs_sorted if looks_like_part(t, target, set())]
    log(step, f"Filtered for GPT ({len(filtered)}):")

    for t, s in filtered:
        log(info, f"  - {t}  (conf {s:.2f})")
    if not filtered:
        filtered = pairs_sorted[:]

    # GPT ranking (if available)
    client = get_openai_client(api_key)
    gpt_raw = ""
    gpt_cost: Optional[float] = None
    best_visible = ""
    best_norm = ""
    reason = ""

    gpt_ranked: List[Tuple[str, str]] = []  # (original, normalized)
    if client:
        raw, tin, tout = rank_with_gpt(client, model, pairs_sorted, target, top_k=top_k)
        gpt_raw = raw
        try:
            g = parse_compact_json(raw)
            # primary pick
            best_visible = (g.get("best") or "").strip()
            best_norm = normalize_code(g.get("normalized") or "")
            reason = g.get("reason", "")
            # ranked list
            ranked = g.get("ranked") or []
            for item in ranked:
                txt = (item.get("text") or "").strip()
                norm = normalize_code(item.get("normalized") or txt)
                if txt:
                    gpt_ranked.append((txt, norm))
        except Exception as e:
            log(warn, f"Failed to parse GPT JSON: {e}")

        gpt_cost = estimate_cost(model, tin, tout)
        if gpt_cost is not None:
            log(info, f"Approx GPT cost: ${gpt_cost:.6f}")

    # -------- Try Excel in GPT rank order (shortlist) --------
    # Build candidate order: GPT ranked → GPT best (if not already) → rest by local score
    seen = set()
    cand_order: List[Tuple[str, str]] = []

    for txt, norm in gpt_ranked:
        key = norm or normalize_code(txt)
        if key and key not in seen:
            cand_order.append((txt, key))
            seen.add(key)

    if best_visible:
        key = best_norm or normalize_code(best_visible)
        if key and key not in seen:
            cand_order.append((best_visible, key))
            seen.add(key)

    # add locally-scored remainder to give Excel more chances
    remainder = []
    for t, s in filtered:
        key = normalize_code(t)
        if key and key not in seen:
            remainder.append((t, s, score_candidate(t, s, target, set())))
    remainder.sort(key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True)
    cand_order.extend([(t, normalize_code(t)) for (t, _, _) in remainder])

    # Excel loop
    match_client = None
    match_artikul = None
    dbg_all = []
    log(info, f"Cand order: {cand_order}")
    for visible, norm in cand_order:
        log(info, f"Excel lookup try: {visible}  (→ {norm})")
        client_found, artikul_display, dbg = try_match_in_excel(
            excel_path, norm, min_fuzzy
        )
        dbg_all.append(dbg)
        if client_found:
            match_client, match_artikul = client_found, artikul_display
            # lock the chosen code to the one that matched in Excel
            best_visible = visible
            best_norm = norm
            reason = reason or "excel_first_match_in_rank_order"
            log(step, f"Excel MATCH → {artikul_display}  | Клиент: {client_found}")
            break

    # If nothing matched Excel, keep a best guess
    if not match_client:
        # If GPT gave nothing, fall back to local pick
        if not best_norm:
            log(info, "Local scoring fallback.")
            scored = [
                (t, s, score_candidate(t, s, target, set())) for (t, s) in filtered
            ]
            scored.sort(
                key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True
            )
            best_visible = scored[0][0]
            best_norm = normalize_code(scored[0][0])
            reason = "local_scoring_fallback"
        log(
            warn,
            "No acceptable match found in Excel. Consider lowering --min_fuzzy or adding the part.",
        )

    # Summary
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
        "pairs_sorted": pairs_sorted,
        "filtered": filtered,
        "best_visible": best_visible,
        "best_normalized": best_norm,
        "reason": reason,
        "gpt_raw": gpt_raw,
        "gpt_cost": gpt_cost,
        "match_client": match_client,
        "match_artikul": match_artikul,
        "match_debug": "\n\n".join(dbg_all),
        "logs": logs,
    }
