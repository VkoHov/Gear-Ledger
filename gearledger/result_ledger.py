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
    Ensure results sheet exists and either insert row(s) for (Артикул,
    Клиент) or increment existing row(s)' Количество. Matching is done
    on normalized Артикул + case-insensitive Клиент + Цена продажи —
    price is part of the row identity so that when the same client has
    multiple catalog lines for this artikul at different prices (e.g. 3
    units @ 1000, 2 units @ 3000), each price tier gets its own
    correctly-priced row instead of the whole recorded quantity being
    flattened to whichever price was looked up first. Tiers fill in
    catalog order — the first tier's ordered quantity is used up before
    any of this scan spills into the next tier's price. When there's
    only one price for this artikul+client (the common case), this
    behaves exactly as before: one row, incremented in place.

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

    # Look up catalog price tiers for this artikul+client (may be more
    # than one distinct-priced line — see allocate_tiered_quantity)
    catalog_bytes = None
    if not catalog_path or not os.path.exists(catalog_path):
        from gearledger.data_layer import get_network_mode
        mode = get_network_mode()
        if mode == "server":
            from gearledger.server import get_server
            server = get_server()
            if server and server.is_running():
                catalog_bytes = server.get_uploaded_catalog_data()

    if catalog_bytes is not None:
        tiers = _lookup_catalog_tiers(artikul, catalog_bytes=catalog_bytes, client=client)
    elif catalog_path and os.path.exists(catalog_path):
        tiers = _lookup_catalog_tiers(artikul, catalog_path=catalog_path, client=client)
    else:
        print(f"[INFO] No catalog file selected")
        tiers = []

    if tiers:
        print(
            f"[INFO] Found {len(tiers)} catalog line(s) for {artikul}/{client}: "
            f"{[(t['цена'], t['количество']) for t in tiers]}"
        )
    else:
        print(f"[INFO] No catalog data found for {artikul}")

    # Build match key components. Артикул + Клиент stay fixed for this
    # whole call; Цена продажи varies per allocation below.
    key_norm = _norm(artikul)
    client_upper = (client or "").upper()

    norm_col = "_NORM"
    df[norm_col] = df["Артикул"].astype(str).map(_norm)
    if "Клиент" in df.columns:
        client_match = df["Клиент"].astype(str).str.upper() == client_upper
    else:
        client_match = pd.Series([False] * len(df))

    def _existing_qty_at_price(price) -> int:
        """How much is already recorded for this artikul+client at this
        exact price — snapshot of df as of before this call's writes, so
        allocate_tiered_quantity sees a consistent picture across all
        tiers even though we haven't written anything yet."""
        if "Цена продажи" not in df.columns or len(df) == 0:
            return 0
        price_match = df["Цена продажи"].apply(price_key) == price_key(price)
        mask_price = (df[norm_col] == key_norm) & client_match & price_match
        return int(
            pd.to_numeric(df.loc[mask_price, "Количество"], errors="coerce")
            .fillna(0)
            .sum()
        )

    allocations = allocate_tiered_quantity(qty_inc, tiers, _existing_qty_at_price)

    def _to_int(v):
        try:
            return int(pd.to_numeric(v, errors="coerce") or 0)
        except Exception:
            return 0

    now = datetime.datetime.now()
    any_inserted = False
    any_updated = False

    for alloc in allocations:
        alloc_qty = alloc["qty"]
        if alloc_qty <= 0:
            continue
        alloc_price = alloc["цена"]
        alloc_brand = alloc["бренд"]
        alloc_desc = alloc["описание"]

        # Recompute against the current df each iteration — an earlier
        # allocation in this same call may have appended a new row.
        df[norm_col] = df["Артикул"].astype(str).map(_norm)
        cur_client_match = (
            df["Клиент"].astype(str).str.upper() == client_upper
            if "Клиент" in df.columns
            else pd.Series([False] * len(df))
        )
        price_match = (
            df["Цена продажи"].apply(price_key) == price_key(alloc_price)
            if "Цена продажи" in df.columns
            else pd.Series([False] * len(df))
        )
        mask = (df[norm_col] == key_norm) & cur_client_match & price_match

        if mask.any():
            idx = df.index[mask][0]
            # Only increment quantity, NOT weight (weight stays the same
            # for existing items — matches every other duplicate-scan row)
            df.loc[idx, "Количество"] = _to_int(df.loc[idx, "Количество"]) + alloc_qty
            df.loc[idx, "Последнее обновление"] = now

            if alloc_brand and (not df.loc[idx, "Брэнд"] or pd.isna(df.loc[idx, "Брэнд"])):
                df.loc[idx, "Брэнд"] = alloc_brand
            if alloc_desc and (
                not df.loc[idx, "Описание"] or pd.isna(df.loc[idx, "Описание"])
            ):
                df.loc[idx, "Описание"] = alloc_desc

            new_quantity = _to_int(df.loc[idx, "Количество"])
            if alloc_price > 0:
                df.loc[idx, "Цена продажи"] = alloc_price
                df.loc[idx, "Сумма продажи"] = alloc_price * new_quantity
            any_updated = True
        else:
            new_row = {
                "Артикул": artikul,
                "Клиент": client,
                "Количество": alloc_qty,
                "Вес": weight_inc,
                "Последнее обновление": now,
                "Брэнд": alloc_brand,
                "Описание": alloc_desc,
                "Цена продажи": alloc_price,
                "Сумма продажи": alloc_price * alloc_qty,
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True, sort=False)
            any_inserted = True

    action = "inserted" if any_inserted else "updated"

    # Drop temp column and save
    if norm_col in df.columns:
        df = df.drop(columns=[norm_col])

    from gearledger.logging_utils import get_logger
    _log = get_logger(__name__)

    base, ext = os.path.splitext(path)
    tmp_path = base + ".__tmp__" + ext  # e.g. results.__tmp__.xlsx
    try:
        df.to_excel(tmp_path, index=False)
        os.replace(tmp_path, path)
        _log.info("record_match %s: artikul=%s client=%s", action, artikul, client)
        return {"ok": True, "action": action, "path": path, "error": ""}
    except Exception as e:
        _log.error("record_match write failed: artikul=%s error=%s", artikul, e, exc_info=True)
        # Clean up incomplete temp file if it exists
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        return {"ok": False, "action": action, "path": path, "error": str(e)}


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


def delete_result_excel(
    path: str, artikul: str, client: str, price: float = None
) -> Dict[str, any]:
    """Remove the row(s) matching (artikul, client) from the results
    ledger. When `price` is given, only the row at that exact price tier
    is removed (the same artikul+client can now have several rows at
    different prices — see allocate_tiered_quantity); price=None deletes
    every row for that artikul+client regardless of price, which is what
    the Check Order "not in catalog" cleanup wants (it operates on
    totals, not a specific tier).
    Returns {"ok", "deleted", "error"} — deleted is the number of rows removed.
    """
    if not os.path.exists(path):
        return {"ok": False, "deleted": 0, "error": "File not found"}
    try:
        df = pd.read_excel(path)
    except Exception as e:
        return {"ok": False, "deleted": 0, "error": str(e)}

    if "Артикул" not in df.columns or "Клиент" not in df.columns:
        return {"ok": False, "deleted": 0, "error": "Missing Артикул/Клиент columns"}

    key_norm = _norm(artikul)
    client_upper = (client or "").strip().upper()
    mask = (df["Артикул"].astype(str).map(_norm) == key_norm) & (
        df["Клиент"].astype(str).str.strip().str.upper() == client_upper
    )
    if price is not None and "Цена продажи" in df.columns:
        mask = mask & (df["Цена продажи"].apply(price_key) == price_key(price))
    deleted = int(mask.sum())
    if deleted == 0:
        return {"ok": True, "deleted": 0, "error": ""}

    df = df.loc[~mask].reset_index(drop=True)

    base, ext = os.path.splitext(path)
    tmp_path = base + ".__tmp__" + ext
    try:
        df.to_excel(tmp_path, index=False)
        os.replace(tmp_path, path)
        return {"ok": True, "deleted": deleted, "error": ""}
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        return {"ok": False, "deleted": 0, "error": str(e)}


def set_result_quantity_excel(
    path: str, artikul: str, client: str, new_quantity: int, target_price: float = None
) -> Dict[str, any]:
    """Set the recorded quantity for the row matching (artikul, client),
    recomputing Сумма продажи from the existing per-unit Цена продажи.
    `target_price=None` (the default) affects every row for that
    artikul+client regardless of price — used by the Check Order
    "over-recorded" fix, which corrects a total, not one specific price
    tier. Pass target_price to affect only that one tier's row instead.
    Returns {"ok", "updated", "error"} — updated is the number of rows changed.
    """
    if not os.path.exists(path):
        return {"ok": False, "updated": 0, "error": "File not found"}
    try:
        df = pd.read_excel(path)
    except Exception as e:
        return {"ok": False, "updated": 0, "error": str(e)}

    if "Артикул" not in df.columns or "Клиент" not in df.columns:
        return {"ok": False, "updated": 0, "error": "Missing Артикул/Клиент columns"}

    key_norm = _norm(artikul)
    client_upper = (client or "").strip().upper()
    mask = (df["Артикул"].astype(str).map(_norm) == key_norm) & (
        df["Клиент"].astype(str).str.strip().str.upper() == client_upper
    )
    if target_price is not None and "Цена продажи" in df.columns:
        mask = mask & (df["Цена продажи"].apply(price_key) == price_key(target_price))
    updated = int(mask.sum())
    if updated == 0:
        return {"ok": True, "updated": 0, "error": ""}

    df.loc[mask, "Количество"] = new_quantity
    if "Цена продажи" in df.columns:
        price = pd.to_numeric(df.loc[mask, "Цена продажи"], errors="coerce").fillna(0)
        if "Сумма продажи" in df.columns:
            df.loc[mask, "Сумма продажи"] = price * new_quantity
    if "Последнее обновление" in df.columns:
        df["Последнее обновление"] = df["Последнее обновление"].astype(object)
        df.loc[mask, "Последнее обновление"] = datetime.datetime.now().isoformat()

    base, ext = os.path.splitext(path)
    tmp_path = base + ".__tmp__" + ext
    try:
        df.to_excel(tmp_path, index=False)
        os.replace(tmp_path, path)
        return {"ok": True, "updated": updated, "error": ""}
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        return {"ok": False, "updated": 0, "error": str(e)}


def get_results_quantity(path: str, artikul: str, client: str) -> int:
    """Return the quantity already recorded in results for (artikul, client). 0 if not found."""
    if not os.path.exists(path):
        return 0
    try:
        df = pd.read_excel(path)
        if "Артикул" not in df.columns or "Количество" not in df.columns:
            return 0
        key_norm = _norm(artikul)
        client_upper = (client or "").upper()
        norm_col = "_NORM"
        df[norm_col] = df["Артикул"].astype(str).map(_norm)
        if "Клиент" in df.columns:
            client_match = df["Клиент"].astype(str).str.upper() == client_upper
        else:
            client_match = pd.Series([False] * len(df))
        mask = (df[norm_col] == key_norm) & client_match
        if mask.any():
            val = df.loc[df.index[mask][0], "Количество"]
            try:
                return int(pd.to_numeric(val, errors="coerce") or 0)
            except Exception:
                return 0
        return 0
    except Exception:
        return 0


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
