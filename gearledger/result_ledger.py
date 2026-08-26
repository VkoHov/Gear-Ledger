# -*- coding: utf-8 -*-
from __future__ import annotations
import os, re, datetime
from typing import Dict, List, Callable, Optional
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
    """Uppercase, strip spaces/dashes/dots/slashes/colons to unify the key.

    Non-breaking spaces and em/en-dashes are canonicalized first — a code
    scanned from a label often comes back with these instead of a plain
    ASCII space/hyphen, so a manually-typed "correct" query wouldn't match
    the stored row otherwise (looks identical, isn't byte-identical).
    Apostrophes are dropped outright — Excel's "force text" convention
    (typing 'RJ30003 to keep a code as text) can leave a literal leading
    apostrophe baked into the value, so "RJ30003" and "'RJ30003" must key
    the same.
    """
    s = str(s or "").replace("\xa0", " ").replace("—", "-").replace("–", "-")
    s = s.replace("'", "").replace("’", "").replace("‘", "")
    return re.sub(r"[ \t\n\r\-.:/]", "", s).upper()


def unique_version_path(versions_dir: str) -> str:
    """Return a collision-safe path for a new results_<timestamp>.xlsx archive,
    so two versions created within the same second don't overwrite each other."""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(versions_dir, f"results_{stamp}.xlsx")
    suffix = 1
    while os.path.exists(path):
        path = os.path.join(versions_dir, f"results_{stamp}_{suffix}.xlsx")
        suffix += 1
    return path


def validate_ledger_columns(path: str) -> tuple[bool, list, "str | None"]:
    """Read just the header row of an Excel file and check it has the
    results-ledger's required columns. Shared by the manual "Import
    Results" action and the one-time legacy-storage migration, so both
    reject the same malformed files the same way.

    Returns (ok, missing_columns, read_error) — read_error is set (and
    missing_columns is empty) when the file couldn't even be opened as
    Excel, distinct from a readable file that's just missing columns.
    """
    required = ["Артикул", "Клиент", "Количество"]
    try:
        header_df = pd.read_excel(path, nrows=0)
    except Exception as e:
        return False, [], str(e)
    missing = [c for c in required if c not in header_df.columns]
    return not missing, missing, None


def rows_to_dataframe(rows) -> pd.DataFrame:
    """Map database result rows (dicts with artikul/client/quantity/... keys)
    to the standard results-ledger DataFrame shape, for archiving DB-backed
    (server/client mode) results to an Excel version file."""
    data = [
        {
            "Артикул": r.get("artikul", ""),
            "Клиент": r.get("client", ""),
            "Количество": r.get("quantity", 0),
            "Вес": r.get("weight", 0),
            "Последнее обновление": r.get("last_updated", ""),
            "Брэнд": r.get("brand", ""),
            "Описание": r.get("description", ""),
            "Цена продажи": r.get("sale_price", 0),
            "Сумма продажи": r.get("total_price", 0),
        }
        for r in rows
    ]
    return pd.DataFrame(data, columns=COLUMNS)


def cleanup_orphan_tmp(path: str):
    """Delete leftover .__tmp__.xlsx file from a previous crashed write, if it exists."""
    base, ext = os.path.splitext(path)
    tmp_path = base + ".__tmp__" + ext
    try:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            print(f"[INFO] Cleaned up orphan temp file: {tmp_path}")
    except OSError as e:
        print(f"[WARNING] Could not remove orphan temp file {tmp_path}: {e}")


def _safe_num(value, cast=float, default=0):
    """Coerce value to a number, defaulting on NaN — `X or default` doesn't
    work for this since NaN is truthy in Python, so a corrupted/non-numeric
    cell would otherwise raise instead of falling back."""
    num = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(num) else cast(num)


def get_all_results_excel(path: str) -> list:
    """Read every row from the results ledger Excel file as a list of dicts
    shaped like database result rows (artikul, client, quantity, ...), so
    standalone and server/client mode can be consumed the same way."""
    if not os.path.exists(path):
        return []
    try:
        df = pd.read_excel(path)
    except Exception:
        return []
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "artikul": str(row.get("Артикул", "") or ""),
                "client": str(row.get("Клиент", "") or ""),
                "quantity": _safe_num(row.get("Количество", 0), int, 0),
                "weight": _safe_num(row.get("Вес", 0), float, 0.0),
                "brand": str(row.get("Брэнд", "") or ""),
                "description": str(row.get("Описание", "") or ""),
                "sale_price": _safe_num(row.get("Цена продажи", 0), float, 0.0),
                "total_price": _safe_num(row.get("Сумма продажи", 0), float, 0.0),
                "last_updated": str(row.get("Последнее обновление", "") or ""),
            }
        )
    return rows


def rows_equal(rows_a, rows_b) -> bool:
    """Compare two lists of result-row dicts for equality, ignoring row
    order and last_updated timestamps (only the actual inventory data —
    artikul/client/quantity/weight/price — matters for "did anything
    change"). Used to skip archiving a redundant duplicate version when
    restoring/resetting back-to-back with nothing recorded in between.
    """

    def _key(r):
        return (
            str(r.get("artikul", "")).strip().upper(),
            str(r.get("client", "")).strip().upper(),
            r.get("quantity"),
            r.get("weight"),
            str(r.get("brand", "")).strip(),
            str(r.get("description", "")).strip(),
            r.get("sale_price"),
            r.get("total_price"),
        )

    return sorted(map(_key, rows_a)) == sorted(map(_key, rows_b))


def _read_catalog_matches(
    artikul: str,
    catalog_path: str = None,
    catalog_bytes: bytes = None,
    client: str = None,
):
    """
    Shared catalog-reading core for _lookup_catalog_data and
    _lookup_catalog_tiers: reads the catalog, detects columns (including
    quantity, needed for tier-fill pricing), finds every row matching
    artikul, and narrows to `client`'s rows when a client column is
    detectable and that client has at least one row — otherwise falls
    back to every match regardless of client (preserves old behavior for
    catalogs without a client column, or a client not present for this
    artikul).

    Returns (used_df, col_mapping) — used_df is the DataFrame of matching
    rows to consider (client-narrowed, or all matches as a fallback), and
    col_mapping maps logical field names ("номер", "бренд", "описание",
    "цена", "клиент", "количество") to the actual column labels found.
    Returns (None, {}) if nothing could be read or nothing matched.
    """
    try:
        # Read from bytes if provided, otherwise from file path
        if catalog_bytes is not None:
            from io import BytesIO
            catalog_file = BytesIO(catalog_bytes)
            # Try to read with different engines for .xls and .xlsx files
            try:
                catalog_df = pd.read_excel(catalog_file, engine="openpyxl")
            except:
                try:
                    catalog_file.seek(0)  # Reset for next attempt
                    catalog_df = pd.read_excel(catalog_file, engine="xlrd")
                except:
                    catalog_file.seek(0)  # Reset for next attempt
                    catalog_df = pd.read_excel(catalog_file)
        elif catalog_path:
            # Try to read with different engines for .xls and .xlsx files
            try:
                catalog_df = pd.read_excel(catalog_path, engine="openpyxl")
            except:
                try:
                    catalog_df = pd.read_excel(catalog_path, engine="xlrd")
                except:
                    catalog_df = pd.read_excel(catalog_path)
        else:
            return None, {}

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
            if any(
                k in col_lower
                for k in ["клиент", "client", "customer", "buyer", "vendor"]
            ):
                col_mapping["клиент"] = col
            # Quantity/stock column — needed to know each catalog line's
            # capacity for tier-fill pricing (see _allocate_tiered_quantity).
            # Same keyword set as excel_utils._detect_stock_column, kept in
            # sync manually since this module intentionally has its own
            # independent catalog-reading path.
            if any(
                k in col_lower
                for k in [
                    "количество", "кол-во", "кол.", "остаток", "наличие",
                    "в наличии", "qty", "quantity", "stock", "count", "available",
                ]
            ):
                col_mapping["количество"] = col

        # Fallback to exact names (prioritize Номер over Артикул for new format)
        if "Клиент" in catalog_df.columns:
            col_mapping["клиент"] = "Клиент"
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
        for exact in ("Количество", "Остаток", "Наличие"):
            if exact in catalog_df.columns:
                col_mapping["количество"] = exact
                break

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
            return None, {}

        # Normalize for matching
        artikul_norm = _norm(artikul)
        print(f"[DEBUG] Looking for part: '{artikul}' -> normalized: '{artikul_norm}'")

        catalog_df["_NORM_TEMP"] = catalog_df[номер_col].astype(str).apply(_norm)

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
            return None, {}

        used = matches
        client_col = col_mapping.get("клиент")
        if client and client_col:
            client_upper = str(client).strip().upper()
            client_matches = matches[
                matches[client_col].astype(str).str.strip().str.upper() == client_upper
            ]
            if not client_matches.empty:
                used = client_matches
            else:
                print(
                    f"[DEBUG] No catalog row for client '{client}' with this artikul — "
                    f"falling back to all matches"
                )

        return used, col_mapping

    except Exception as e:
        print(f"[ERROR] Exception in catalog lookup: {e}")
        return None, {}


def _lookup_catalog_data(
    artikul: str,
    catalog_path: str = None,
    catalog_bytes: bytes = None,
    client: str = None,
) -> Dict[str, any]:
    """
    Look up additional data from catalog by artikul (and, when given, client).

    The same artikul can appear on multiple catalog rows for different
    clients (e.g. different negotiated prices per customer). Without a
    client filter, this always returned whichever row happened to be
    first in the file — silently giving every client the same
    price/brand/description as that first row. When `client` is given
    and the catalog has a detectable client column, rows for that
    client are preferred; otherwise falls back to the first match
    (preserves old behavior for catalogs without a client column, or a
    client not present for this artikul).

    Only ever returns the *first* matching row's price — when the same
    client has multiple catalog lines for this artikul at different
    prices, use _lookup_catalog_tiers instead so callers can price a
    recorded quantity correctly across tiers instead of flattening
    everything to one line's price.

    Accepts either a file path (catalog_path) or in-memory bytes (catalog_bytes).
    If both are provided, catalog_bytes takes precedence.
    """
    used, col_mapping = _read_catalog_matches(artikul, catalog_path, catalog_bytes, client)
    if used is None or used.empty:
        return {}

    row = used.iloc[0]
    result = {}
    if col_mapping.get("бренд"):
        result["бренд"] = row.get(col_mapping["бренд"], "")
    if col_mapping.get("описание"):
        result["описание"] = row.get(col_mapping["описание"], "")
    if col_mapping.get("цена"):
        result["цена"] = row.get(col_mapping["цена"], 0)

    return result


def price_key(value) -> float:
    """Round a price to a stable comparison key, avoiding float-drift
    false-mismatches (e.g. 1000.0000001 != 1000) when matching a results
    row's price back to the catalog tier it came from."""
    try:
        num = pd.to_numeric(value, errors="coerce")
        return round(float(num), 2) if not pd.isna(num) else 0.0
    except Exception:
        return 0.0


def _lookup_catalog_tiers(
    artikul: str,
    catalog_path: str = None,
    catalog_bytes: bytes = None,
    client: str = None,
) -> List[Dict[str, any]]:
    """
    Return every catalog LINE matching (artikul, client) — not merged or
    reduced to a single row — each as {"цена", "количество", "бренд",
    "описание"}, in catalog row order. "количество" is the line's own
    ordered quantity (None if no quantity/stock column is detectable).

    This is what lets record_match price a scan correctly when the same
    client ordered the same article across multiple catalog lines at
    different prices (e.g. 3 units @ 1000, 2 units @ 3000) instead of
    always using the first line's price for the whole recorded quantity.
    """
    used, col_mapping = _read_catalog_matches(artikul, catalog_path, catalog_bytes, client)
    if used is None or used.empty:
        return []

    qty_col = col_mapping.get("количество")
    tiers = []
    for _, row in used.iterrows():
        price = row.get(col_mapping["цена"], 0) if col_mapping.get("цена") else 0
        price = price_key(price)

        qty = None
        if qty_col:
            qv = pd.to_numeric(row.get(qty_col), errors="coerce")
            qty = None if pd.isna(qv) else int(qv)

        tiers.append(
            {
                "цена": price,
                "количество": qty,
                "бренд": row.get(col_mapping.get("бренд"), "") if col_mapping.get("бренд") else "",
                "описание": row.get(col_mapping.get("описание"), "") if col_mapping.get("описание") else "",
            }
        )
    return tiers


def allocate_tiered_quantity(
    qty_inc: int,
    tiers: List[Dict[str, any]],
    existing_qty_by_price: Callable[[float], int],
) -> List[Dict[str, any]]:
    """
    Split qty_inc units across catalog price tiers, filling each tier's
    ordered quantity — based on how much is already recorded at that
    tier's price — before spilling into the next tier. Backend-agnostic
    pure logic: existing_qty_by_price is a callback so the caller can
    source "how much is already recorded at this price" from a
    DataFrame (Excel/standalone) or a database query (server mode)
    without this function needing to know about either.

    Degrades to the old single-price behavior (first tier's price for
    the whole quantity) whenever there's nothing meaningful to split:
    no catalog match, only one distinct price among the tiers, or any
    tier's capacity is unknown (no quantity/stock column) — in that
    last case fill-order can't be determined safely, so guessing would
    be worse than the old flat behavior.

    Returns a list of {"qty", "цена", "бренд", "описание"} allocations,
    already merged so each distinct price appears at most once.
    """
    if not tiers:
        return [{"qty": qty_inc, "цена": 0.0, "бренд": "", "описание": ""}]

    distinct_prices = {t["цена"] for t in tiers}
    if len(distinct_prices) <= 1 or any(t["количество"] is None for t in tiers):
        first = tiers[0]
        return [
            {
                "qty": qty_inc,
                "цена": first["цена"],
                "бренд": first["бренд"],
                "описание": first["описание"],
            }
        ]

    allocations: List[Dict[str, any]] = []
    remaining = qty_inc
    for tier in tiers:
        if remaining <= 0:
            break
        already = int(existing_qty_by_price(tier["цена"]) or 0)
        capacity_left = max(0, (tier["количество"] or 0) - already)
        take = min(remaining, capacity_left)
        if take > 0:
            allocations.append(
                {
                    "qty": take,
                    "цена": tier["цена"],
                    "бренд": tier["бренд"],
                    "описание": tier["описание"],
                }
            )
            remaining -= take

    if remaining > 0:
        # Over-recorded beyond every tier's combined capacity — attach the
        # overflow to the last tier's price. The Check Order completeness
        # check still catches this at the total-recorded-vs-demanded level.
        last = tiers[-1]
        allocations.append(
            {
                "qty": remaining,
                "цена": last["цена"],
                "бренд": last["бренд"],
                "описание": last["описание"],
            }
        )

    merged: Dict[float, Dict[str, any]] = {}
    for a in allocations:
        key = a["цена"]
        if key in merged:
            merged[key]["qty"] += a["qty"]
        else:
            merged[key] = dict(a)
    return list(merged.values())
