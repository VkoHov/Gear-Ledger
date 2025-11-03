# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, datetime
from typing import Dict
import pandas as pd

COLUMNS = [
    "Артикул",
    "Клиент",
    "Количество",
    "Вес",
    "Последнее обновление",
    "Брэнд",
    "Описание",
    "Цена продажи",
    "Сумма продажи",
]


def _norm(s: str) -> str:
    """Uppercase, strip spaces/dashes/dots/slashes/colons to unify the key."""
    return re.sub(r"[ \t\n\r\-.:/]", "", str(s or "")).upper()


def record_match(
    path: str,
    artikul: str,
    client: str,
    qty_inc: int = 1,
    weight_inc: int = 1,
    catalog_path: str = None,
    weight_price: float = 0.0,
) -> Dict[str, str]:
    """
    Ensure results sheet exists and either insert a row for (Артикул, Клиент)
    or increment Количество and Вес by +1 each when already present.
    Matching is done on normalized Артикул + case-insensitive Клиент.

    If catalog_path is provided, will look up additional fields (Брэнд, Описание, Цена продажи).
    If weight_price is provided, will calculate Цена продажи as weight * weight_price.
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

    # Look up additional fields from catalog if provided
    brand = ""
    description = ""
    catalog_price = 0  # Store catalog price separately from calculated price

    if catalog_path and os.path.exists(catalog_path):
        catalog_data = _lookup_catalog_data(artikul, catalog_path)
        if catalog_data:
            brand = catalog_data.get("бренд", "")
            description = catalog_data.get("описание", "")
            catalog_price = catalog_data.get("цена", 0)
            # Info: print what we found
            print(
                f"[INFO] Found catalog data for {artikul}: brand={brand}, catalog_price={catalog_price}"
            )
        else:
            print(f"[INFO] No catalog data found for {artikul}")
    else:
        print(f"[INFO] No catalog file selected")

    # Store only catalog price in results file (weight-based pricing applied only in invoice generation)
    final_price = catalog_price
    if final_price == 0:
        print(f"[INFO] No catalog price found for {artikul}, storing 0")
    else:
        print(
            f"[INFO] Storing catalog price for {artikul}: {final_price} (weight-based pricing will be applied in invoice)"
        )

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
        new_weight = _to_int(df.loc[idx, "Вес"]) + weight_inc
        df.loc[idx, "Вес"] = new_weight
        df.loc[idx, "Последнее обновление"] = now

        # Update catalog fields if they're empty and we have new data
        if brand and (not df.loc[idx, "Брэнд"] or pd.isna(df.loc[idx, "Брэнд"])):
            df.loc[idx, "Брэнд"] = brand
        if description and (
            not df.loc[idx, "Описание"] or pd.isna(df.loc[idx, "Описание"])
        ):
            df.loc[idx, "Описание"] = description

        # Store only catalog price in results file (weight-based pricing applied only in invoice generation)
        # Use catalog_price from lookup, or keep existing if no new lookup
        new_quantity = _to_int(df.loc[idx, "Количество"])

        if catalog_price > 0:
            # Update with new catalog price if found
            df.loc[idx, "Цена продажи"] = catalog_price
            df.loc[idx, "Сумма продажи"] = catalog_price * new_quantity
            print(
                f"[INFO] Updated catalog price for {artikul}: {catalog_price}, total={catalog_price * new_quantity}"
            )
        elif final_price > 0:
            # Use final_price (catalog price) if we have it
            df.loc[idx, "Цена продажи"] = final_price
            df.loc[idx, "Сумма продажи"] = final_price * new_quantity
        # Otherwise keep existing price if no new catalog price found

        action = "updated"
    else:
        new_row = {
            "Артикул": artikul,
            "Клиент": client,
            "Количество": qty_inc,
            "Вес": weight_inc,
            "Последнее обновление": now,
            "Брэнд": brand,
            "Описание": description,
            "Цена продажи": final_price,
            "Сумма продажи": final_price * qty_inc,
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


def _lookup_catalog_data(artikul: str, catalog_path: str) -> Dict[str, any]:
    """Look up additional data from catalog by artikul."""
    try:
        # Try to read with different engines for .xls and .xlsx files
        try:
            catalog_df = pd.read_excel(catalog_path, engine="openpyxl")
        except:
            try:
                catalog_df = pd.read_excel(catalog_path, engine="xlrd")
            except:
                catalog_df = pd.read_excel(catalog_path)

        # Detect column names
        col_mapping = {}
        for col in catalog_df.columns:
            col_lower = str(col).strip().lower()

            if "номер" in col_lower or "artikul" in col_lower or "арт" in col_lower:
                col_mapping["номер"] = col
            if "бренд" in col_lower or "brand" in col_lower or "брэнд" in col_lower:
                col_mapping["бренд"] = col
            if (
                "описание" in col_lower
                or "description" in col_lower
                or "наименование" in col_lower
            ):
                col_mapping["описание"] = col
            if "цена продажи" in col_lower or (
                "цена" in col_lower and "продажи" in col_lower
            ):
                col_mapping["цена"] = col

        # Fallback to exact names (prioritize Номер over Артикул for new format)
        if "Номер" in catalog_df.columns:
            col_mapping["номер"] = "Номер"
        elif "Артикул" in catalog_df.columns:
            col_mapping["номер"] = "Артикул"
        if "Брэнд" in catalog_df.columns:
            col_mapping["бренд"] = "Брэнд"
        if "Описание" in catalog_df.columns:
            col_mapping["описание"] = "Описание"
        if "Цена продажи" in catalog_df.columns:
            col_mapping["цена"] = "Цена продажи"

        # Check if we have the required columns
        missing_cols = []
        if not col_mapping.get("бренд"):
            missing_cols.append("Брэнд")
        if not col_mapping.get("описание"):
            missing_cols.append("Описание")
        if not col_mapping.get("цена"):
            missing_cols.append("Цена продажи")

        if missing_cols:
            print(f"[WARNING] Missing columns in catalog: {missing_cols}")
            print(
                f"[WARNING] Please use the full invoice.xlsx file that contains all product details"
            )

        номер_col = col_mapping.get("номер")
        if not номер_col:
            return {}

        # Normalize for matching
        def normalize(s: str) -> str:
            return (
                str(s or "").replace(" ", "").replace("-", "").replace(".", "").upper()
            )

        artikul_norm = normalize(artikul)
        print(f"[DEBUG] Looking for part: '{artikul}' -> normalized: '{artikul_norm}'")

        catalog_df["_NORM_TEMP"] = catalog_df[номер_col].astype(str).apply(normalize)

        # Show some examples from the catalog
        print(
            f"[DEBUG] First 5 parts in catalog: {catalog_df[номер_col].head().tolist()}"
        )
        print(f"[DEBUG] First 5 normalized: {catalog_df['_NORM_TEMP'].head().tolist()}")

        matches = catalog_df[catalog_df["_NORM_TEMP"] == artikul_norm]

        if matches.empty:
            print(f"[DEBUG] No exact match found. Checking if similar parts exist...")
            # Check if there are any similar parts
            similar = catalog_df[
                catalog_df["_NORM_TEMP"].str.contains(artikul_norm, na=False)
            ]
            if not similar.empty:
                print(f"[DEBUG] Found similar parts: {similar[номер_col].tolist()}")
            return {}

        row = matches.iloc[0]

        result = {}
        if col_mapping.get("бренд"):
            result["бренд"] = row.get(col_mapping["бренд"], "")
        if col_mapping.get("описание"):
            result["описание"] = row.get(col_mapping["описание"], "")
        if col_mapping.get("цена"):
            result["цена"] = row.get(col_mapping["цена"], 0)

        return result

    except Exception as e:
        print(f"[ERROR] Exception in catalog lookup: {e}")
        return {}
