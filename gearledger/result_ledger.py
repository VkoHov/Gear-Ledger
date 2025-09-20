# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, datetime
from typing import Dict
import pandas as pd

COLUMNS = ["Артикул", "Клиент", "Количество", "Вес", "Последнее обновление"]


def _norm(s: str) -> str:
    """Uppercase, strip spaces/dashes/dots/slashes/colons to unify the key."""
    return re.sub(r"[ \t\n\r\-.:/]", "", str(s or "")).upper()


def record_match(
    path: str,
    artikul: str,
    client: str,
    qty_inc: int = 1,
    weight_inc: int = 1,
) -> Dict[str, str]:
    """
    Ensure results sheet exists and either insert a row for (Артикул, Клиент)
    or increment Количество and Вес by +1 each when already present.
    Matching is done on normalized Артикул + case-insensitive Клиент.
    """
    # Make parent dir if needed
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

    # Load (or create) dataframe
    if os.path.exists(path):
        try:
            df = pd.read_excel(path)
        except Exception:
            df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(columns=COLUMNS)

    # Ensure required columns exist
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")

    # Build match key
    key_norm = _norm(artikul)
    client_upper = (client or "").upper()

    # Add temp normalized column for matching
    norm_col = "_NORM"
    df[norm_col] = df["Артикул"].astype(str).map(_norm)

    # Case-insensitive client match
    if "Клиент" in df.columns:
        client_match = df["Клиент"].astype(str).str.upper() == client_upper
    else:
        client_match = False

    mask = (df[norm_col] == key_norm) & client_match

    now = datetime.datetime.now()
    action = "inserted"

    if mask.any():
        idx = df.index[mask][0]

        # safe numeric increments
        def _to_int(v):
            try:
                return int(pd.to_numeric(v, errors="coerce") or 0)
            except Exception:
                return 0

        df.loc[idx, "Количество"] = _to_int(df.loc[idx, "Количество"]) + qty_inc
        df.loc[idx, "Вес"] = _to_int(df.loc[idx, "Вес"]) + weight_inc
        df.loc[idx, "Последнее обновление"] = now
        action = "updated"
    else:
        new_row = {
            "Артикул": artikul,
            "Клиент": client,
            "Количество": qty_inc,
            "Вес": weight_inc,
            "Последнее обновление": now,
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Drop temp column and save
    if norm_col in df.columns:
        df = df.drop(columns=[norm_col])

    try:
        df.to_excel(path, index=False)
        return {"ok": True, "action": action, "path": path, "error": ""}
    except Exception as e:
        return {"ok": False, "action": action, "path": path, "error": str(e)}
