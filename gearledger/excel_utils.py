# -*- coding: utf-8 -*-
import os
import pandas as pd

# ---------------------------------------------------------------------------
# Catalog cache — keyed by absolute path; invalidated when mtime changes.
# Each entry: {"mtime": float, "lookup": dict, "lookup_nodash": dict}
# lookup maps  space-normalised code  →  (client_str, orig_artikul_str)
# lookup_nodash maps the same codes with hyphens stripped → same value,
# so we can answer hyphen-variant queries without re-scanning.
# Protected by a lock because _ManualSearchWorker runs on a background thread.
# ---------------------------------------------------------------------------
import threading
from typing import Optional
_catalog_cache: dict = {}
_catalog_lock = threading.Lock()


class ExcelReadError(Exception):
    """Exception raised when Excel file cannot be read."""

    def __init__(self, excel_path: str, error_message: str):
        self.excel_path = excel_path
        self.error_message = error_message
        super().__init__(f"Failed to read Excel file: {error_message}")


def _space_norm(s) -> str:
    return str(s or "").replace(" ", "").upper()


def _detect_columns(df):
    """Return (artikul_col, client_col) from a DataFrame."""
    artikul_col = None
    client_col = None
    for c in df.columns:
        lc = str(c).strip().lower()
        if artikul_col is None and any(
            k in lc
            for k in ["номер", "арт", "artikul", "article", "part", "sku", "code", "number"]
        ):
            artikul_col = c
        if client_col is None and any(
            k in lc for k in ["клиент", "client", "name", "buyer", "vendor", "customer"]
        ):
            client_col = c
    # Exact-name overrides take priority
    if "Номер" in df.columns:
        artikul_col = "Номер"
    elif "Артикул" in df.columns:
        artikul_col = "Артикул"
    if "Клиент" in df.columns:
        client_col = "Клиент"
    return artikul_col, client_col


def _detect_stock_column(df) -> Optional[str]:
    """Return the column name that holds available stock count, or None."""
    # Prefer exact Russian names first
    for exact in ("Количество", "Остаток", "Наличие"):
        if exact in df.columns:
            return exact
    for c in df.columns:
        lc = str(c).strip().lower()
        if any(k in lc for k in [
            "количество", "кол-во", "кол.", "остаток", "наличие", "в наличии",
            "qty", "quantity", "stock", "count", "available",
        ]):
            return c
    return None


def _load_catalog(excel_path: str) -> dict:
    """
    Load Excel, build lookup dicts, cache the result.
    Raises ExcelReadError on read failure.
    Thread-safe: protected by _catalog_lock.
    """
    abs_path = os.path.abspath(excel_path)
    try:
        mtime = os.path.getmtime(abs_path)
    except OSError as e:
        raise ExcelReadError(excel_path, str(e))

    with _catalog_lock:
        cached = _catalog_cache.get(abs_path)
        if cached and cached["mtime"] == mtime:
            return cached

    # Read Excel outside the lock so we don't block other threads
    try:
        df = pd.read_excel(abs_path)
    except Exception as e:
        raise ExcelReadError(excel_path, str(e))

    artikul_col, client_col = _detect_columns(df)
    if not artikul_col:
        entry = {"mtime": mtime, "lookup": {}, "lookup_nodash": {}, "count_lookup": {}, "error": "no_artikul_col"}
        with _catalog_lock:
            _catalog_cache[abs_path] = entry
        return entry
    if not client_col:
        client_col = artikul_col

    stock_col = _detect_stock_column(df)

    lookup: dict = {}
    lookup_nodash: dict = {}
    count_lookup: dict = {}

    for _, row in df.iterrows():
        orig = str(row[artikul_col] or "")
        norm = _space_norm(orig)
        if not norm or norm == "NAN":
            continue
        client_val = str(row[client_col]) if client_col != artikul_col else ""
        if norm not in lookup:
            lookup[norm] = (client_val, orig)
        norm_nd = norm.replace("-", "").replace("—", "").replace("–", "")
        if norm_nd and norm_nd != norm and norm_nd not in lookup_nodash:
            lookup_nodash[norm_nd] = (client_val, orig)
        # Stock count
        if stock_col is not None and norm not in count_lookup:
            try:
                cnt = int(pd.to_numeric(row[stock_col], errors="coerce") or 0)
            except Exception:
                cnt = 0
            count_lookup[norm] = cnt
            if norm_nd and norm_nd != norm:
                count_lookup.setdefault(norm_nd, cnt)

    entry = {
        "mtime": mtime,
        "lookup": lookup,
        "lookup_nodash": lookup_nodash,
        "count_lookup": count_lookup,
        "stock_col": stock_col,
        "artikul_col": artikul_col,
        "client_col": client_col,
        "total_rows": len(df),
        "error": None,
    }
    with _catalog_lock:
        _catalog_cache[abs_path] = entry
    return entry


def get_catalog_stock(excel_path: str, artikul: str) -> Optional[int]:
    """
    Return the available stock count for *artikul* from the catalog.
    Returns None if the catalog has no stock column or the file can't be read.
    Returns an int (possibly 0) if a stock column exists.
    """
    if not os.path.exists(excel_path):
        return None
    try:
        catalog = _load_catalog(excel_path)
    except ExcelReadError:
        return None
    count_lookup = catalog.get("count_lookup")
    if not count_lookup and catalog.get("stock_col") is None:
        return None  # Catalog has no stock column at all
    q = _space_norm(artikul)
    count = count_lookup.get(q)
    if count is None:
        q_nd = q.replace("-", "").replace("—", "").replace("–", "")
        count = count_lookup.get(q_nd)
    return count  # may be None if artikul not found


def invalidate_catalog_cache(excel_path: str = None):
    """Invalidate cached catalog. Pass None to clear everything."""
    with _catalog_lock:
        if excel_path is None:
            _catalog_cache.clear()
        else:
            _catalog_cache.pop(os.path.abspath(excel_path), None)


def try_match_in_excel(excel_path: str, query_raw: str, *_args, **_kwargs):
    """
    Space-stripped, UPPERCASE, EXACT equality only.
    Returns (client, artikul_display, debug).

    Uses an in-memory cache so the Excel file is only read once per
    session (or when the file changes on disk).
    """
    if not os.path.exists(excel_path):
        return (None, None, f"Excel not found: {excel_path}")

    catalog = _load_catalog(excel_path)  # may raise ExcelReadError

    if catalog.get("error") == "no_artikul_col":
        return (None, None, "Could not locate an artikul/part-code column.")

    lookup = catalog["lookup"]
    lookup_nodash = catalog["lookup_nodash"]
    total_rows = catalog.get("total_rows", "?")

    q = _space_norm(query_raw)
    debug_lines = [
        f"Query: ‘{query_raw}’ → ‘{q}’ | file: {os.path.basename(excel_path)} ({total_rows} rows)"
    ]

    # Try with original spaces-stripped form first
    hit = lookup.get(q)
    if hit:
        client_val, orig = hit
        debug_lines.append(f"✓ MATCH: ‘{q}’ → ‘{orig}’ | client: ‘{client_val}’")
        return (client_val, orig, "\n".join(debug_lines))

    # Try hyphen-stripped variant
    q_nd = q.replace("-", "").replace("—", "").replace("–", "")
    if q_nd and q_nd != q:
        debug_lines.append(f"Trying no-dash variant: ‘{q_nd}’")
        hit = lookup.get(q_nd) or lookup_nodash.get(q_nd)
        if hit:
            client_val, orig = hit
            debug_lines.append(f"✓ MATCH (no-dash): ‘{q_nd}’ → ‘{orig}’ | client: ‘{client_val}’")
            return (client_val, orig, "\n".join(debug_lines))

    debug_lines.append(f"✗ No match for ‘{q}’ ({len(lookup)} entries searched)")
    return (None, None, "\n".join(debug_lines))
