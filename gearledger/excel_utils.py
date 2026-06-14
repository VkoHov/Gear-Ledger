# -*- coding: utf-8 -*-
import os
import pandas as pd

# ---------------------------------------------------------------------------
# Catalog cache — keyed by absolute path; invalidated when mtime changes.
# Each entry: {"mtime": float, "lookup": dict, "lookup_nodash": dict}
# lookup maps  space-normalised code  →  (client_str, orig_artikul_str)
# lookup_nodash maps the same codes with hyphens stripped → same value,
# so we can answer hyphen-variant queries without re-scanning.
# ---------------------------------------------------------------------------
_catalog_cache: dict = {}


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


def _load_catalog(excel_path: str) -> dict:
    """
    Load Excel, build lookup dicts, cache the result.
    Raises ExcelReadError on read failure.
    """
    abs_path = os.path.abspath(excel_path)
    try:
        mtime = os.path.getmtime(abs_path)
    except OSError as e:
        raise ExcelReadError(excel_path, str(e))

    cached = _catalog_cache.get(abs_path)
    if cached and cached["mtime"] == mtime:
        return cached

    try:
        df = pd.read_excel(abs_path)
    except Exception as e:
        raise ExcelReadError(excel_path, str(e))

    artikul_col, client_col = _detect_columns(df)
    if not artikul_col:
        entry = {"mtime": mtime, "lookup": {}, "lookup_nodash": {}, "error": "no_artikul_col"}
        _catalog_cache[abs_path] = entry
        return entry
    if not client_col:
        client_col = artikul_col

    lookup: dict = {}
    lookup_nodash: dict = {}
    for _, row in df.iterrows():
        orig = str(row[artikul_col] or "")
        norm = _space_norm(orig)
        if not norm or norm == "NAN":
            continue
        client_val = str(row[client_col]) if client_col != artikul_col else ""
        if norm not in lookup:
            lookup[norm] = (client_val, orig)
        # Pre-index hyphen-stripped variant
        norm_nd = norm.replace("-", "").replace("—", "").replace("–", "")
        if norm_nd and norm_nd != norm and norm_nd not in lookup_nodash:
            lookup_nodash[norm_nd] = (client_val, orig)

    entry = {
        "mtime": mtime,
        "lookup": lookup,
        "lookup_nodash": lookup_nodash,
        "artikul_col": artikul_col,
        "client_col": client_col,
        "total_rows": len(df),
        "error": None,
    }
    _catalog_cache[abs_path] = entry
    return entry


def invalidate_catalog_cache(excel_path: str = None):
    """Invalidate cached catalog. Pass None to clear everything."""
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
