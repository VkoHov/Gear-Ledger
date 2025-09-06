# -*- coding: utf-8 -*-
import os
import re
from typing import List, Tuple
from paddleocr import PaddleOCR
from .logging_utils import step, info, warn
from .image_utils import prepare_image_safe

Pairs = List[Tuple[str, float]]


def init_ocr_engines(lang_list):
    engines = []
    for lang in lang_list:
        step(f"Initializing PaddleOCR engine (lang={lang}) ...")
        try:
            engines.append((lang, PaddleOCR(lang=lang)))
            step(f"PaddleOCR ready for lang={lang}.")
        except Exception as e:
            warn(f"Could not init OCR for lang={lang}: {e}")
    return engines


def _run_engine_any(engine, safe_path, lang_tag) -> Pairs:
    pairs: Pairs = []
    try:
        page_list = engine.predict(safe_path)
        if not page_list:
            warn(f"[{lang_tag}] empty OCR result from predict().")
            return pairs
        page = page_list[0]
        if isinstance(page, dict) and "rec_texts" in page and "rec_scores" in page:
            texts, scores = page["rec_texts"], page["rec_scores"]
            info(f"[{lang_tag}] predict() pipeline → {len(texts)} items")
            for t, s in zip(texts, scores):
                info(f"  [{lang_tag}] {t}  (conf {float(s):.2f})")
                pairs.append((t, float(s)))
        elif isinstance(page, list):
            info(f"[{lang_tag}] predict() classic → {len(page)} items")
            for i, line in enumerate(page):
                try:
                    text, score = line[1][0], float(line[1][1])
                    info(f"  [{lang_tag}] {text}  (conf {score:.2f})")
                    pairs.append((text, score))
                except Exception as e:
                    warn(f"  [{lang_tag}] parse line {i} failed: {e}")
        else:
            warn(f"[{lang_tag}] predict() unrecognized; trying ocr().")
            raise TypeError("predict_format")
        return pairs
    except TypeError:
        info(f"[{lang_tag}] falling back to ocr(..., cls=False)")
        page = engine.ocr(safe_path, cls=False)
        if not page:
            warn(f"[{lang_tag}] empty OCR result from ocr().")
            return pairs
        page = page[0] if isinstance(page[0], list) else page
        info(f"[{lang_tag}] ocr() classic → {len(page)} items")
        for i, line in enumerate(page):
            try:
                text, score = line[1][0], float(line[1][1])
                info(f"  [{lang_tag}] {text}  (conf {score:.2f})")
                pairs.append((text, score))
            except Exception as e:
                warn(f"  [{lang_tag}] parse line {i} failed: {e}")
        return pairs


def ocr_extract_pairs_multi(image_path: str, ocr_engines, max_side: int) -> Pairs:
    safe_path = prepare_image_safe(image_path, max_side)
    all_pairs: Pairs = []
    try:
        for lang, engine in ocr_engines:
            step(f"OCR with lang={lang} on {safe_path}")
            all_pairs.extend(_run_engine_any(engine, safe_path, lang))
    finally:
        try:
            os.unlink(safe_path)
        except Exception:
            pass

    # Deduplicate by normalized key; keep highest confidence
    merged = {}
    for t, s in all_pairs:
        key = re.sub(r"[ .-]", "", t).upper()
        if not key:
            continue
        if key not in merged or s > merged[key][1]:
            merged[key] = (t, s)

    pairs = [(orig, conf) for _, (orig, conf) in merged.items()]
    return pairs
