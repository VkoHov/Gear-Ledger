# -*- coding: utf-8 -*-
import os
import pandas as pd
from fuzzywuzzy import fuzz


def try_match_in_excel(excel_path: str, clean_artikul: str, min_score: int = 70):
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

    exact = df[df["Артикул_Очистка"] == clean_artikul]
    if not exact.empty:
        row = exact.iloc[0]
        debug.append("Exact match found.")
        return (str(row["Клиент"]), str(row["Артикул"]), "\n".join(debug))

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
