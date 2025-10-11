# -*- coding: utf-8 -*-
import os
import pandas as pd


def try_match_in_excel(excel_path: str, query_raw: str, *_args, **_kwargs):
    """
    Space-stripped, UPPERCASE, EXACT equality only.
    Returns (client, artikul_display, debug).
    """
    debug = []
    if not os.path.exists(excel_path):
        debug.append(f"Excel not found: {excel_path}")
        return (None, None, "\n".join(debug))

    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        debug.append(f"Failed to read Excel: {e}")
        return (None, None, "\n".join(debug))

    # Try to locate columns
    artikul_col = None
    client_col = None
    for c in df.columns:
        lc = str(c).strip().lower()
        if artikul_col is None and any(
            k in lc
            for k in [
                "номер",
                "арт",
                "artikul",
                "article",
                "part",
                "sku",
                "code",
                "number",
            ]
        ):
            artikul_col = c
        if client_col is None and any(
            k in lc for k in ["клиент", "client", "name", "buyer", "vendor", "customer"]
        ):
            client_col = c

    # Fallback to exact names if present (prioritize Номер over Артикул for new format)
    if "Номер" in df.columns:
        artikul_col = "Номер"
    elif "Артикул" in df.columns:
        artikul_col = "Артикул"
    if "Клиент" in df.columns:
        client_col = "Клиент"

    if not artikul_col:
        debug.append("Could not locate an artikul/part-code column.")
        return (None, None, "\n".join(debug))
    if not client_col:
        # allow missing client; we’ll return None for client if not found
        client_col = artikul_col

    def space_norm(s: str) -> str:
        return (str(s or "")).replace(" ", "").upper()

    q = space_norm(query_raw)
    debug.append(f"Excel rows: {len(df)}")
    debug.append(f"Looking for space-exact: {q}")

    # Build normalized column (space stripped, uppercase)
    norm_col = "_GL_SPACE_NORM_"
    df[norm_col] = df[artikul_col].astype(str).map(space_norm)

    exact = df[df[norm_col] == q]
    if not exact.empty:
        row = exact.iloc[0]
        debug.append("Exact (space-stripped) match found.")
        return (
            str(row.get(client_col, "")),
            str(row.get(artikul_col, "")),
            "\n".join(debug),
        )

    debug.append("No exact (space-stripped) match.")
    return (None, None, "\n".join(debug))
