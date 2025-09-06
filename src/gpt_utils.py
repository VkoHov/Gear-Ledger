# -*- coding: utf-8 -*-
import json

PRICES = {
    # $ per 1K tokens
    "gpt-4o-mini": {"input": 0.000150, "output": 0.000600},
    "gpt-4o": {"input": 0.005000, "output": 0.015000},
}


def estimate_cost(model, prompt_tokens, completion_tokens):
    """
    Estimate USD cost for a single chat.completions call.

    model: str (e.g., 'gpt-4o-mini', 'gpt-4o')
    prompt_tokens: int
    completion_tokens: int
    """
    p = PRICES.get(model, {"input": 0.0, "output": 0.0})
    return (prompt_tokens / 1000.0) * p["input"] + (completion_tokens / 1000.0) * p[
        "output"
    ]


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


def parse_compact_json(s: str):
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)
