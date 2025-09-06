# -*- coding: utf-8 -*-
from __future__ import annotations
import json
from typing import List, Tuple, Optional

from openai import OpenAI

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


def get_openai_client(api_key: Optional[str]) -> Optional[OpenAI]:
    if not api_key:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def build_prompt(candidates: List[Tuple[str, float]], target: str = "auto"):
    payload = [{"text": t, "confidence": round(float(c), 4)} for (t, c) in candidates]

    if target == "vendor":
        goal = (
            "Choose the VENDOR article number (e.g., 'PK-5396'). "
            "Ignore OEM cross-references near words like 'REF' or 'OEM'. "
            "Vendor codes are often: short letters+digits or numeric groups like '8 807 02961 02'."
        )
    elif target == "oem":
        goal = (
            "Choose the OEM/part number (e.g., 'A 221 501 26 91' or '5K6 807 393 C'). "
            "Normalize by removing spaces/dashes. Ignore short vendor catalog codes."
        )
    else:
        goal = (
            "Choose the single best car-part identifier.\n"
            "WHEN BOTH AN OEM-LIKE CODE (e.g., '5K6 807 393 C') AND A VENDOR-LIKE CODE "
            "(including numeric vendor formats like '8 807 02961 02') APPEAR, "
            "YOU MUST PREFER THE VENDOR CODE."
        )

    sys = (
        "You select a car-part identifier from OCR text.\n"
        f"{goal}\n"
        "Ignore dates, quantities, barcodes, and generic words. "
        "If a token is near words like 'REF' or 'OEM', treat that as an OEM code.\n"
        "Return ONLY compact JSON (no code fences): "
        '{"best":"<original>","normalized":"<uppercase_no_spaces_dashes>",'
        '"reason":"<short>","ranked":[{"text":"...","score":...}]}\n\n'
        "Normalization removes spaces and dashes only."
    )
    usr = "Candidates (JSON array):\n" + json.dumps(payload, ensure_ascii=False)

    return sys, usr


def rank_with_gpt(
    client: OpenAI, model: str, candidates: List[Tuple[str, float]], target: str
):
    sys, usr = build_prompt(candidates, target)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
    )
    raw = (resp.choices[0].message.content or "").strip()
    tin = (
        getattr(resp, "usage", None).prompt_tokens
        if getattr(resp, "usage", None)
        else 0
    )
    tout = (
        getattr(resp, "usage", None).completion_tokens
        if getattr(resp, "usage", None)
        else 0
    )
    return raw, int(tin or 0), int(tout or 0)


def parse_compact_json(s: str):
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)
