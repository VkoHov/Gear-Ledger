# -*- coding: utf-8 -*-

import os, re, json, argparse, tempfile
import pandas as pd
from fuzzywuzzy import fuzz
from paddleocr import PaddleOCR
from openai import OpenAI
from PIL import Image, ImageOps
from dotenv import load_dotenv

load_dotenv()

# Optional HEIC/HEIF support (no error if not installed)
try:
    from pillow_heif import register_heif

    register_heif()
except Exception:
    pass

# --- stability for macOS/BLAS (prevents some segfaults on MPS/Accelerate) ---
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


# =============== Pretty logging ===============
def step(msg):
    print(f"[STEP] {msg}")


def info(msg):
    print(f"[INFO] {msg}")


def warn(msg):
    print(f"[WARN] {msg}")


def err(msg):
    print(f"[ERROR] {msg}")


# =============== Regex / scoring helpers ===============
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
    # e.g., "641678568 Miqo"
    return bool(re.search(r"\b\d{3,}\s+[A-Za-z]{3,}\b", raw))


# Vendor vs OEM patterns / hints
VENDOR_HINT_WORDS = {"ART", "ART.", "ARTICLE", "ITEM", "PART", "QTY", "PCS", "EAC"}
OEM_HINT_WORDS = {"OEM", "O.E.M", "REF", "REF:", "CROSS", "CROSSREF", "CROSS-REF"}


def is_vendor_like(raw: str) -> bool:
    # Common vendor style: 2–4 letters + optional dash/space + 3–6 digits (+ optional 1–2 alnum)
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


# =============== CLI args ===============
parser = argparse.ArgumentParser(
    description="OCR -> GPT choose target code (vendor/OEM/auto) -> Excel match"
)
parser.add_argument("--image", required=True, help="Path to image file (jpg/png/heic).")
parser.add_argument(
    "--excel", required=True, help="Path to invoice.xlsx (Артикул, Клиент)."
)
parser.add_argument(
    "--langs", default="en,ru", help='Comma-separated OCR langs: "en,ru" or just "en".'
)
parser.add_argument(
    "--min_fuzzy", type=int, default=70, help="Min fuzzy score to accept Excel match."
)
parser.add_argument(
    "--max_items", type=int, default=30, help="Max OCR items to send to GPT."
)
parser.add_argument(
    "--model",
    default="gpt-4o-mini",
    help="OpenAI model for ranking (e.g. gpt-4o-mini).",
)
parser.add_argument(
    "--max_side", type=int, default=1280, help="Max image side before OCR."
)
parser.add_argument(
    "--target",
    choices=["auto", "vendor", "oem"],
    default="auto",
    help="Which code to prefer: vendor (e.g. PK-5396), oem (e.g. A 221 501 26 91), or auto.",
)
args = parser.parse_args()

IMAGE_PATH = args.image
EXCEL_PATH = args.excel
LANG_LIST = [s.strip() for s in args.langs.replace("+", ",").split(",") if s.strip()]
MIN_FUZZY_SCORE = args.min_fuzzy
MAX_ITEMS_FOR_GPT = args.max_items
OPENAI_MODEL = args.model
MAX_SIDE = args.max_side
TARGET = args.target

# =============== Init checks ===============
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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
if not OPENAI_API_KEY:
    warn("OPENAI_API_KEY not set → GPT selection will be skipped.")

# Initialize PaddleOCR engines
ocr_engines = []
for lang in LANG_LIST:
    step(f"Initializing PaddleOCR engine (lang={lang}) ...")
    try:
        ocr_engines.append((lang, PaddleOCR(lang=lang)))
        step(f"PaddleOCR ready for lang={lang}.")
    except Exception as e:
        warn(f"Could not init OCR for lang={lang}: {e}")
if not ocr_engines:
    err("No OCR engines initialized. Check --langs and PaddleOCR install.")
    raise SystemExit(1)

client = None
if OPENAI_API_KEY:
    step("Initializing OpenAI client ...")
    client = OpenAI(api_key=OPENAI_API_KEY)
    step("OpenAI client ready.")


# =============== Image prep (EXIF rotate + downscale) ===============
def prepare_image_safe(path, max_side=1280):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        info(f"Original image size: {w}x{h}")
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            new_size = (int(w * scale), int(h * scale))
            im = im.resize(new_size, Image.LANCZOS)
            info(f"Downscaled to: {im.size[0]}x{im.size[1]} (scale {scale:.3f})")
        else:
            info("Downscale not needed.")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        im.convert("RGB").save(tmp.name, quality=92)
        step(f"Prepared image saved to temp: {tmp.name}")
        return tmp.name


# =============== OCR (predict() with ocr() fallback) ===============
def run_engine_any(engine, safe_path, lang_tag):
    pairs = []
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


def ocr_extract_pairs_multi(image_path):
    safe_path = prepare_image_safe(image_path, MAX_SIDE)
    all_pairs = []
    try:
        for lang, engine in ocr_engines:
            step(f"OCR with lang={lang} on {safe_path}")
            all_pairs.extend(run_engine_any(engine, safe_path, lang))
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


# =============== Do OCR ===============
pairs = ocr_extract_pairs_multi(IMAGE_PATH)
if not pairs:
    err("No OCR text found. Exiting.")
    raise SystemExit(1)

pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)[:MAX_ITEMS_FOR_GPT]
step(f"Merged top {len(pairs_sorted)} texts (raw):")
for t, s in pairs_sorted:
    print(f"  - {t}  (conf {s:.2f})")

# Build “context” list for OEM hints (tokens near REF/OEM words)
ordered_texts = [t for t, _ in pairs_sorted]
oem_context = set()
for i, t in enumerate(ordered_texts):
    tt = normalize_code(t)
    if tt in {"REF", "OEM", "OE"}:
        for j in range(max(0, i - 1), min(len(ordered_texts), i + 3)):
            oem_context.add(ordered_texts[j])


# =============== Target-aware filtering & scoring ===============
def looks_like_part(raw: str) -> bool:
    n = normalize_code(raw)
    if is_date_like(raw) or is_time_like(raw):
        return False
    if is_barcode_like(raw):
        return False
    if is_word_only(n):
        return False
    if is_digits_plus_word(raw):
        return False

    if TARGET == "vendor":
        return is_vendor_like(raw) or (has_letters_and_digits(n) and len(n) >= 5)
    if TARGET == "oem":
        return is_oem_like(raw)
    # auto
    return (
        is_vendor_like(raw)
        or is_oem_like(raw)
        or (has_letters_and_digits(n) and len(n) >= 8)
    )


def score_candidate(raw: str, conf: float) -> float:
    n = normalize_code(raw)
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
    if " " not in raw and re.fullmatch(r"[A-Za-z0-9\-./]+", raw):
        score += 1.5
    if re.search(r"[A-Za-z].*\d", n) and re.search(r"\d.*[A-Za-z]", n):
        score += 2

    # target-specific boosts/penalties
    if TARGET == "vendor":
        if is_vendor_like(raw):
            score += 6
        if is_oem_like(raw):
            score -= 4
        if raw in oem_context:
            score -= 3
        if has_any(OEM_HINT_WORDS, raw):
            score -= 2
    elif TARGET == "oem":
        if is_oem_like(raw):
            score += 6
        if is_vendor_like(raw):
            score -= 3
        if raw in oem_context:
            score += 2
        if has_any(OEM_HINT_WORDS, raw):
            score += 2

    # general negatives
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


# Filter for GPT
filtered = [(t, s) for (t, s) in pairs_sorted if looks_like_part(t)]
step(f"Filtered for GPT ({len(filtered)}):")
for t, s in filtered:
    print(f"  - {t}  (conf {s:.2f})")

# If nothing passes filter, fall back to raw list to avoid empty prompt
if not filtered:
    filtered = pairs_sorted[:]


# =============== GPT ranking (target-aware) ===============
def build_prompt(candidates, target="auto"):
    payload = [{"text": t, "confidence": round(float(c), 4)} for (t, c) in candidates]
    if target == "vendor":
        goal = (
            "Choose the VENDOR article number (e.g., 'PK-5396'). "
            "Ignore OEM cross-references often shown near words like 'REF' or 'OEM'. "
            "Vendor codes are typically shorter: 2–4 letters + 3–6 digits, optional dash/space."
        )
    elif target == "oem":
        goal = (
            "Choose the OEM/part number (e.g., 'A 221 501 26 91'). "
            "Normalize by removing spaces/dashes. Ignore short vendor catalog codes."
        )
    else:
        goal = (
            "Choose the single best car-part identifier. If both vendor and OEM appear, "
            "prefer the vendor code."
        )

    sys = (
        "You are an assistant that selects a car-part identifier from OCR text.\n"
        f"{goal}\n"
        "Ignore dates, quantities, barcodes, country codes, and generic words. "
        "If a token is near words like 'REF' or 'OEM', treat that token as an OEM code.\n"
        "Return ONLY compact JSON (no code fences): "
        '{"best":"<original>","normalized":"<uppercase_no_spaces_dashes>","reason":"<short>","ranked":[...]}'
    )
    usr = (
        "Candidates (JSON array):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nChoose the best."
    )
    return sys, usr


def parse_compact_json(s):
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


best_visible = ""
best_norm = ""
reason = ""
ranked = []

if client:
    sys, usr = build_prompt(filtered, TARGET)
    step("Sending OCR candidates to GPT for best match selection...")
    gpt_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.0,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
    )
    raw = (gpt_resp.choices[0].message.content or "").strip()
    print("[GPT RAW] ----------------------")
    print(raw)
    print("----------- end GPT RAW --------")
    try:
        g = parse_compact_json(raw)
        best_visible = (g.get("best") or "").strip()
        best_norm = normalize_code(g.get("normalized") or "")
        reason = g.get("reason", "")
        ranked = g.get("ranked", [])
    except Exception as e:
        err(f"Failed to parse GPT JSON: {e}")

# =============== Target-aware staged fallback ===============
if not best_norm:
    info("Falling back to local heuristic (staged selection).")
    scored = [(t, s, score_candidate(t, s)) for (t, s) in filtered]

    def pick_best(cands):
        cands.sort(key=lambda x: (x[2], x[1], len(normalize_code(x[0]))), reverse=True)
        return cands[0][0], normalize_code(cands[0][0])

    chosen = False
    if TARGET == "vendor":
        stage = [(t, s, sc) for (t, s, sc) in scored if is_vendor_like(t)]
        if stage:
            best_visible, best_norm = pick_best(stage)
            chosen = True

    if TARGET == "oem" and not chosen:
        stage = [(t, s, sc) for (t, s, sc) in scored if is_oem_like(t)]
        if stage:
            best_visible, best_norm = pick_best(stage)
            chosen = True

    if not chosen:
        stage = [(t, s, sc) for (t, s, sc) in scored if looks_like_part(t)]
        if stage:
            best_visible, best_norm = pick_best(stage)
            chosen = True

    if not chosen:
        for t, s in sorted(
            filtered, key=lambda ts: len(normalize_code(ts[0])), reverse=True
        ):
            n = normalize_code(t)
            if re.search(r"[A-Z]", n) and len(n) >= 4:
                best_visible, best_norm = t, n
                break

step(f"GPT BEST (visible) : {best_visible}")
step(f"GPT BEST (normalized): {best_norm}")
info(f"Reason: {reason}")


# =============== Excel match (exact → variants → fuzzy) ===============
def try_match_in_excel(excel_path, clean_artikul, min_score=70):
    debug = []
    if not os.path.exists(excel_path):
        debug.append(f"Excel not found: {excel_path}")
        return (None, None, "\n".join(debug))

    df = pd.read_excel(excel_path)
    if "Артикул" not in df.columns or "Клиент" not in df.columns:
        debug.append("Excel must have columns 'Артикул' and 'Клиент'.")
        return (None, None, "\n".join(debug))

    df["Артикул_Очистка"] = (
        df["Артикул"]
        .astype(str)
        .str.replace(" ", "", regex=False)
        .str.replace("-", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.upper()
    )

    debug.append(f"Excel rows: {len(df)}")
    debug.append(f"Looking for exact match of: {clean_artikul}")

    # 1) Exact
    exact = df[df["Артикул_Очистка"] == clean_artikul]
    if not exact.empty:
        row = exact.iloc[0]
        debug.append("Exact match found.")
        return (str(row["Клиент"]), str(row["Артикул"]), "\n".join(debug))

    # 2) Common OCR swaps
    variants = {clean_artikul}
    swaps = [
        ("O", "0"),
        ("0", "O"),
        ("I", "1"),
        ("1", "I"),
        ("S", "5"),
        ("5", "S"),
        ("B", "8"),
        ("8", "B"),
    ]
    for a, b in swaps:
        variants.add(clean_artikul.replace(a, b))
    for v in list(variants):
        exact_v = df[df["Артикул_Очистка"] == v]
        if not exact_v.empty:
            row = exact_v.iloc[0]
            debug.append(f"Exact match via variant: {v}")
            return (str(row["Клиент"]), str(row["Артикул"]), "\n".join(debug))

    # 3) Fuzzy
    debug.append("No exact match. Trying fuzzy ...")
    df["Сходство"] = df["Артикул_Очистка"].apply(
        lambda x: fuzz.partial_ratio(x, clean_artikul)
    )
    best = df.loc[df["Сходство"].idxmax()]
    debug.append(
        f"Best fuzzy: {best['Артикул']} → {best['Клиент']} (score {best['Сходство']})"
    )
    if best["Сходство"] >= min_score:
        return (str(best["Клиент"]), str(best["Артикул"]), "\n".join(debug))
    else:
        return (None, None, "\n".join(debug))


BEST_NORM = normalize_code(best_norm or "")

step("Matching in Excel using selected artikul ...")
client_found, artikul_display, dbg = try_match_in_excel(
    EXCEL_PATH, BEST_NORM, MIN_FUZZY_SCORE
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

# =============== Summary ===============
print("\n====== SUMMARY ======")
print(f"Image: {IMAGE_PATH}")
print(f"Top OCR candidates ({len(pairs_sorted)}):")
for t, s in pairs_sorted:
    print(f"  - {t} (conf {s:.2f})")
print(f"\nTarget: {TARGET}")
print(f"BEST (visible): {best_visible}")
print(f"BEST (normalized): {BEST_NORM}")
print(f"Excel: {EXCEL_PATH}")
print(
    f"→ MATCH: {artikul_display}  | Клиент: {client_found}"
    if client_found
    else "→ MATCH: not found"
)
print("======================")
