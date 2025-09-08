# -*- coding: utf-8 -*-
import json
from typing import List, Tuple, Optional

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


# ---------- Pricing (USD per 1K tokens) ----------
PRICES = {
    "gpt-4o-mini": {"input": 0.000150, "output": 0.000600},
    "gpt-4o": {"input": 0.005000, "output": 0.015000},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICES.get(model, {"input": 0.0, "output": 0.0})
    return (prompt_tokens / 1000.0) * p["input"] + (completion_tokens / 1000.0) * p[
        "output"
    ]


# ---------- Client ----------
def get_openai_client(api_key: Optional[str]):
    if not api_key or OpenAI is None:
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


# ---------- Prompting ----------
def build_prompt(
    candidates: List[Tuple[str, float]], target: str = "auto", top_k: int = 5
) -> Tuple[str, str]:
    """
    Ask the model for a top-K ranking and include *normalized* form for each pick.
    """
    payload = [{"text": t, "confidence": float(c)} for (t, c) in candidates]

    if target == "vendor":
        goal = (
            "Select vendor article numbers (e.g., 'PK-5396', 'O-450'). "
            "Ignore long OEM cross-refs often near 'REF', 'OEM', or 'OE'. "
            "Vendor codes are usually short: 1–4 letters + 3–6 digits, optional dash/space."
        )
    elif target == "oem":
        goal = (
            "Select OEM/part numbers (e.g., 'A 221 501 26 91'). "
            "Normalize by removing spaces/dashes. Ignore short vendor catalog codes."
        )
    else:
        goal = (
            "Select the best car-part identifier(s). If both vendor and OEM appear, "
            "prefer the vendor code."
        )

    sys = (
        "You extract car-part identifiers from noisy OCR.\n"
        f"{goal}\n"
        "Ignore dates, quantities, barcodes, and generic words.\n"
        "Return ONLY compact JSON (no code fences) with this schema:\n"
        "{"
        '"best":"<original>",'
        '"normalized":"<uppercase_no_spaces_dashes>",'
        '"reason":"<short>",'
        '"ranked":['
        '{"text":"...","normalized":"...","why":"..."},'
        " ... up to TOP_K ..."
        "]"
        "}\n"
        f"TOP_K={top_k}"
    )
    usr = (
        "Candidates (JSON array):\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n\nRank up to TOP_K most plausible part codes. Fill 'ranked' with your top picks in order."
    )
    return sys, usr


def rank_with_gpt(
    client,
    model: str,
    candidates: List[Tuple[str, float]],
    target: str = "auto",
    top_k: int = 5,
):
    """
    Call chat.completions and return (raw_text, prompt_tokens, completion_tokens).
    """
    sys, usr = build_prompt(candidates, target=target, top_k=top_k)
    print(usr)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": usr}],
    )
    raw = (resp.choices[0].message.content or "").strip()
    print(raw)
    usage = getattr(resp, "usage", None)
    tin = getattr(usage, "prompt_tokens", 0) if usage else 0
    tout = getattr(usage, "completion_tokens", 0) if usage else 0
    return raw, tin, tout


# ---------- Robust JSON parse ----------
def parse_compact_json(s: str):
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)
