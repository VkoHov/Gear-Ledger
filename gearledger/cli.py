# -*- coding: utf-8 -*-

import os, argparse, re
from openai import OpenAI

from .config import OPENAI_API_KEY
from .logging_utils import step, info, warn, err
from .ocr_utils import init_ocr_engines, ocr_extract_pairs_multi
from .heuristics import (
    normalize_code,
    looks_like_part,
    staged_pick_best,
)
from .gpt_utils import build_prompt, parse_compact_json, estimate_cost
from .excel_utils import try_match_in_excel


def parse_args():
    p = argparse.ArgumentParser(
        description="OCR -> GPT choose target code (vendor/OEM/auto) -> Excel match"
    )
    p.add_argument("--image", required=True, help="Path to image file (jpg/png/heic).")
    p.add_argument(
        "--excel", required=True, help="Path to invoice.xlsx (Артикул, Клиент)."
    )
    p.add_argument(
        "--langs",
        default="en,ru",
        help='Comma-separated OCR langs: "en,ru" or just "en".',
    )
    p.add_argument(
        "--min_fuzzy",
        type=int,
        default=70,
        help="Min fuzzy score to accept Excel match.",
    )
    p.add_argument(
        "--max_items", type=int, default=30, help="Max OCR items to send to GPT."
    )
    p.add_argument("--model", default="gpt-4o-mini", help="OpenAI model for ranking.")
    p.add_argument(
        "--max_side", type=int, default=1280, help="Max image side before OCR."
    )
    p.add_argument(
        "--target",
        choices=["auto", "vendor", "oem"],
        default="auto",
        help="Prefer vendor (e.g. PK-5396), OEM (e.g. A 221 501 26 91), or auto.",
    )
    return p.parse_args()


def main():
    args = parse_args()

    IMAGE_PATH = args.image
    EXCEL_PATH = args.excel
    LANG_LIST = [
        s.strip() for s in args.langs.replace("+", ",").split(",") if s.strip()
    ]
    MIN_FUZZY_SCORE = args.min_fuzzy
    MAX_ITEMS_FOR_GPT = args.max_items
    OPENAI_MODEL = args.model
    MAX_SIDE = args.max_side
    TARGET = args.target

    step(f"Using image: {IMAGE_PATH}")
    step(f"Using excel: {EXCEL_PATH}")
    step(f"Languages: {LANG_LIST}")
    step(f"Target: {TARGET}")

    if not os.path.exists(IMAGE_PATH):
        err(f"Image not found: {IMAGE_PATH}")
        raise SystemExit(1)
    if not os.path.exists(EXCEL_PATH):
        err(f"Excel not found: {EXCEL_PATH}")
        raise SystemExit(1)

    client = None
    if not OPENAI_API_KEY:
        warn("OPENAI_API_KEY not set → GPT selection will be skipped.")
    else:
        step("Initializing OpenAI client ...")
        client = OpenAI(api_key=OPENAI_API_KEY)
        step("OpenAI client ready.")

    # OCR init
    engines = init_ocr_engines(LANG_LIST)
    if not engines:
        err("No OCR engines initialized. Check --langs and PaddleOCR install.")
        raise SystemExit(1)

    # OCR
    pairs = ocr_extract_pairs_multi(IMAGE_PATH, engines, MAX_SIDE)
    if not pairs:
        err("No OCR text found. Exiting.")
        raise SystemExit(1)

    pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)[:MAX_ITEMS_FOR_GPT]
    step(f"Merged top {len(pairs_sorted)} texts (raw):")
    for t, s in pairs_sorted:
        print(f"  - {t}  (conf {s:.2f})")

    # OEM context (simple heuristic from ordered list)
    ordered_texts = [t for t, _ in pairs_sorted]
    oem_context = set()
    for i, t in enumerate(ordered_texts):
        tt = normalize_code(t)
        if tt in {"REF", "OEM", "OE"}:
            for j in range(max(0, i - 1), min(len(ordered_texts), i + 3)):
                oem_context.add(ordered_texts[j])

    # Filter for GPT
    filtered = [(t, s) for (t, s) in pairs_sorted if looks_like_part(t, TARGET)]
    step(f"Filtered for GPT ({len(filtered)}):")
    for t, s in filtered:
        print(f"  - {t}  (conf {s:.2f})")
    if not filtered:
        filtered = pairs_sorted[:]

    # GPT pick (optional)
    best_visible = ""
    best_norm = ""
    reason = ""
    ranked = []

    if client:
        sys_prompt, user_prompt = build_prompt(filtered, TARGET)
        step("Sending OCR candidates to GPT for best match selection...")
        gpt_resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = (gpt_resp.choices[0].message.content or "").strip()
        print("[GPT RAW] ----------------------")
        print(raw)
        print("----------- end GPT RAW --------")

        usage = getattr(gpt_resp, "usage", None)
        prompt_toks = getattr(usage, "prompt_tokens", 0) or 0
        completion_toks = getattr(usage, "completion_tokens", 0) or 0
        total_toks = prompt_toks + completion_toks
        est_cost = estimate_cost(OPENAI_MODEL, prompt_toks, completion_toks)

        print(
            f"[USAGE] model={OPENAI_MODEL} prompt={prompt_toks} completion={completion_toks} total={total_toks}"
        )
        print(f"[COST]  estimated: ${est_cost:.6f}")

        try:
            g = parse_compact_json(raw)
            best_visible = (g.get("best") or "").strip()
            best_norm = normalize_code(g.get("normalized") or "")
            reason = g.get("reason", "")
            ranked = g.get("ranked", [])
        except Exception as e:
            err(f"Failed to parse GPT JSON: {e}")

    # Fallback / staged heuristic
    if not best_norm:
        info("Falling back to local heuristic (staged selection).")
        best_visible, best_norm = staged_pick_best(filtered, TARGET, oem_context)

    step(f"GPT BEST (visible) : {best_visible}")
    step(f"GPT BEST (normalized): {best_norm}")
    info(f"Reason: {reason}")

    # Excel match
    step("Matching in Excel using selected artikul ...")
    client_found, artikul_display, dbg = try_match_in_excel(
        EXCEL_PATH, best_norm, MIN_FUZZY_SCORE
    )
    print("[MATCH DEBUG] ------------------")
    print(dbg)
    print("---------- end MATCH DEBUG -----")

    if client_found:
        step(f"MATCH FOUND → Артикул: {artikul_display}  | Клиент: {client_found}")
    else:
        warn(
            "No acceptable match found in Excel. Consider lowering --min_fuzzy or adding the part."
        )

    # Summary
    print("\n====== SUMMARY ======")
    print(f"Image: {IMAGE_PATH}")
    print(f"Top OCR candidates ({len(pairs_sorted)}):")
    for t, s in pairs_sorted:
        print(f"  - {t} (conf {s:.2f})")
    print(f"\nTarget: {TARGET}")
    print(f"BEST (visible): {best_visible}")
    print(f"BEST (normalized): {best_norm}")
    print(f"Excel: {EXCEL_PATH}")
    print(
        f"→ MATCH: {artikul_display}  | Клиент: {client_found}"
        if client_found
        else "→ MATCH: not found"
    )
    print("======================")
