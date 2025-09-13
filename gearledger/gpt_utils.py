# -*- coding: utf-8 -*-
from __future__ import annotations
import base64, json, io
from typing import List, Tuple, Optional
from PIL import Image, ImageOps

# ---- simple price table you already had ----
PRICES = {
    # $ per 1K tokens
    "gpt-4o-mini": {"input": 0.000150, "output": 0.000600},
    "gpt-4o": {"input": 0.005000, "output": 0.015000},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICES.get(model, {"input": 0.0, "output": 0.0})
    return (prompt_tokens / 1000.0) * p["input"] + (completion_tokens / 1000.0) * p[
        "output"
    ]


# ---------- structured JSON helpers ----------
def build_prompt(candidates, target="auto"):
    payload = [{"text": t, "confidence": round(float(c), 4)} for (t, c) in candidates]
    if target == "vendor":
        goal = (
            "Choose the VENDOR article number (e.g., 'PK-5396'). "
            "Ignore OEM cross-references near 'REF'/'OEM'. Vendor codes are shorter."
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
        "Ignore dates, quantities, barcodes, and generic words.\n"
        "Return ONLY compact JSON (no code fences): "
        '{"best":"<original>","normalized":"<uppercase_no_spaces_dashes>","reason":"<short>","ranked":[...]}'
    )
    usr = (
        "Candidates (JSON array):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nChoose the best."
    )
    return sys, usr


def parse_compact_json(s: str):
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


# ---------- OpenAI client helpers ----------
def get_openai_client(api_key: Optional[str]):
    if not api_key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=api_key)
    except Exception:
        return None


def rank_with_gpt(client, model: str, filtered_pairs, target: str, top_k: int = 5):
    """
    Your existing text-only ranking (for Paddle path). Returns (raw, prompt_tokens, completion_tokens).
    """
    sys, usr = build_prompt(filtered_pairs[:top_k], target)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
        max_tokens=300,
    )
    raw = (resp.choices[0].message.content or "").strip()
    u = getattr(resp, "usage", None) or {}
    return (
        raw,
        int(getattr(u, "prompt_tokens", 0) or 0),
        int(getattr(u, "completion_tokens", 0) or 0),
    )


# ---------- Vision (image in, JSON out) ----------
def _encode_image_to_data_url(path: str, max_side: int = 1280) -> str:
    """
    EXIF-rotate + downscale to max_side + JPEG encode + base64 → data URL.
    """
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        scale = float(max_side) / float(max(w, h))
        if scale < 1.0:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"


def rank_with_gpt_vision(
    client,
    model: str,
    image_path: str,
    target: str = "auto",
    *,
    top_k: int = 5,
    max_side: int = 1280,
    max_tokens: int = 300,
):
    """
    Send the image directly to GPT-4o/mini. The model must output compact JSON:
    {
      "best": "...",
      "normalized": "...",
      "reason": "...",
      "ranked": [
        {"text":"...", "normalized":"...", "kind":"vendor|oem", "confidence":0.0},
        ...
      ]
    }
    Returns (raw_json_text, prompt_tokens, completion_tokens).
    """
    data_url = _encode_image_to_data_url(image_path, max_side)

    if target == "vendor":
        goal = (
            "Detect the VENDOR article number (e.g., 'PK-5396'). "
            "Prefer short 2–4 letters + 3–6 digits (optional dash). Ignore OEM refs."
        )
    elif target == "oem":
        goal = (
            "Detect the OEM/part number (e.g., 'A 221 501 26 91'). "
            "Normalize by removing spaces/dashes."
        )
    else:
        goal = "Detect car-part identifiers on the label. Prefer the vendor code over OEM if both appear."

    sys = (
        "You read a photo of an auto-part label and extract part identifiers.\n"
        f"{goal}\n"
        "Rules:\n"
        "- Ignore dates, quantities, barcodes, websites, marketing text, and pure numbers.\n"
        "- Teknorot-style vendor codes like 'O-450', 'VO-490', 'DE-310' are VALID (letter hyphen digits).\n"
        "- Return ONLY compact JSON (no markdown): "
        '{"best":"<visible>","normalized":"<UPPER_NO_SPACES_DASHES>",'
        '"reason":"<short>",'
        '"ranked":[{"text":"<visible>","normalized":"<...>","kind":"vendor|oem|unknown","confidence":0.0}]}\n'
        f"Return up to {top_k} candidates in 'ranked' sorted best-first."
    )

    user_text = (
        "Extract identifiers from this image and follow the JSON schema exactly."
    )
    messages = [
        {"role": "system", "content": sys},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    raw = (resp.choices[0].message.content or "").strip()
    u = getattr(resp, "usage", None) or {}
    return (
        raw,
        int(getattr(u, "prompt_tokens", 0) or 0),
        int(getattr(u, "completion_tokens", 0) or 0),
    )
