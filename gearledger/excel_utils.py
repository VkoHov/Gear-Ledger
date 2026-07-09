# -*- coding: utf-8 -*-
import os
import pandas as pd

# ---------------------------------------------------------------------------
# Catalog cache — keyed by absolute path; invalidated when mtime changes.
# Each entry: {"mtime": float, "lookup": dict, "lookup_nodash": dict}
# lookup maps  space-normalised code  →  list of (client_str, orig_artikul_str),
# one entry per distinct client sharing that exact code (e.g. two different
# customers both ordering "336758J") — first-seen orig kept per client, so
# repeat order-lines for the same client don't create duplicate entries.
# lookup_nodash maps the same codes with hyphens stripped → list of
# (client_str, orig_artikul_str), since multiple dashed catalog entries
# can share the same hyphen-stripped form (e.g. "70-06-5-5" and "700-655"
# both strip to "700655"). So we can answer hyphen-variant queries
# without re-scanning, and still surface every candidate for the picker.
# Protected by a lock because _ManualSearchWorker runs on a background thread.
# ---------------------------------------------------------------------------
import threading
from typing import Any, Dict, List, Optional, Tuple
_catalog_cache: dict = {}
_catalog_lock = threading.Lock()


class ExcelReadError(Exception):
    """Exception raised when Excel file cannot be read."""

    def __init__(self, excel_path: str, error_message: str):
        self.excel_path = excel_path
        self.error_message = error_message
        super().__init__(f"Failed to read Excel file: {error_message}")


def _space_norm(s) -> str:
    # Trim edges, uppercase, then normalize all dash variants to a regular
    # hyphen so em-dash / en-dash in Excel cells match user-typed hyphens.
    # Internal spaces and dots are kept as-is (not stripped) so catalog
    # entries that differ only by separator style — e.g. "75.5", "75 5",
    # "755" — get distinct lookup keys instead of silently colliding into
    # one; _strip_seps() below provides the separator-agnostic fallback
    # that cross-matches them and feeds the multi-match picker.
    s = str(s or "").strip().upper()
    return s.replace("—", "-").replace("–", "-")


def _strip_seps(s: str) -> str:
    """Remove all separator characters (-, ., space) for fallback matching."""
    return s.replace("-", "").replace(".", "").replace(" ", "")


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
        entry = {
            "mtime": mtime,
            "lookup": {},
            "lookup_nodash": {},
            "stock_rows": {},
            "demand_by_group": {},
            "error": "no_artikul_col",
        }
        with _catalog_lock:
            _catalog_cache[abs_path] = entry
        return entry
    if not client_col:
        client_col = artikul_col

    stock_col = _detect_stock_column(df)

    lookup: dict = {}
    lookup_nodash: dict = {}
    # stock_rows: separator-stripped code → list of every (client, qty) row
    # sharing that identity, regardless of dash/dot/space style. Lets
    # get_catalog_stock sum all order-lines for one client instead of only
    # ever seeing the first row (e.g. the same client ordering the same
    # part across several separate order lines).
    stock_rows: dict = {}
    # demand_by_group: (norm_nd, CLIENT_UPPER) → {"client", "artikul", "qty"}
    # One entry per distinct client+code combo, qty summed across every
    # order-line/dash-variant row for that combo. Powers the completeness
    # check (ordered vs. recorded), which needs every demand line, not just
    # a single queried code.
    demand_by_group: dict = {}
    # Tracks which clients have already been added to `lookup` per norm key,
    # so a client with 5 order-lines of the same exact code contributes one
    # picker entry, not five — but a *different* client with the identical
    # code still gets their own entry instead of being silently shadowed.
    _lookup_seen_clients: dict = {}

    for _, row in df.iterrows():
        orig = str(row[artikul_col] or "")
        norm = _space_norm(orig)
        if not norm or norm == "NAN":
            continue
        client_val = str(row[client_col]) if client_col != artikul_col else ""
        client_key = client_val.strip().upper()
        seen_for_norm = _lookup_seen_clients.setdefault(norm, set())
        if client_key not in seen_for_norm:
            seen_for_norm.add(client_key)
            lookup.setdefault(norm, []).append((client_val, orig))
        norm_nd = _strip_seps(norm)
        if norm_nd and norm_nd != norm:
            lookup_nodash.setdefault(norm_nd, []).append((client_val, orig))
        # Stock count
        if stock_col is not None:
            try:
                cnt = int(pd.to_numeric(row[stock_col], errors="coerce") or 0)
            except Exception:
                cnt = 0
            key_nd = norm_nd or norm
            stock_rows.setdefault(key_nd, []).append((client_val, cnt))

            group_key = (key_nd, client_val.strip().upper())
            group = demand_by_group.setdefault(
                group_key, {"client": client_val, "artikul": orig, "qty": 0}
            )
            group["qty"] += cnt

    entry = {
        "mtime": mtime,
        "lookup": lookup,
        "lookup_nodash": lookup_nodash,
        "stock_rows": stock_rows,
        "demand_by_group": demand_by_group,
        "stock_col": stock_col,
        "artikul_col": artikul_col,
        "client_col": client_col,
        "total_rows": len(df),
        "error": None,
    }
    with _catalog_lock:
        _catalog_cache[abs_path] = entry
    return entry


def list_catalog_demand(excel_path: str) -> List[Dict[str, Any]]:
    """
    Return every distinct (client, artikul) demand line in the catalog, with
    quantity summed across every order-line/dash-variant row sharing that
    client+code. Used by the completeness check (ordered vs. recorded).

    Returns [] if the file doesn't exist, can't be read, has no artikul
    column, or has no quantity/stock column (nothing to compare against).
    """
    if not os.path.exists(excel_path):
        return []
    try:
        catalog = _load_catalog(excel_path)
    except ExcelReadError:
        return []
    if catalog.get("error") == "no_artikul_col" or catalog.get("stock_col") is None:
        return []
    return [
        {"client": g["client"], "artikul": g["artikul"], "ordered_qty": g["qty"]}
        for g in catalog["demand_by_group"].values()
    ]


def get_catalog_stock(
    excel_path: str, artikul: str, client: str = None
) -> Optional[Tuple[int, List[int]]]:
    """
    Return the available stock for *artikul* from the catalog, summed across
    every order-line that matches it (same client can appear on several rows,
    e.g. repeat orders). Returns (total, breakdown) where breakdown is the
    list of individual row quantities that were summed (len > 1 means the
    total was combined from multiple order-lines).

    If *client* is given, only rows for that client (case/space-insensitive)
    are counted. If *client* is None, all rows for the code are summed.

    Returns None if the catalog has no stock column, the file can't be read,
    or no matching rows have a stock value.
    """
    if not os.path.exists(excel_path):
        return None
    try:
        catalog = _load_catalog(excel_path)
    except ExcelReadError:
        return None
    stock_rows = catalog.get("stock_rows")
    if not stock_rows and catalog.get("stock_col") is None:
        return None  # Catalog has no stock column at all
    q_nd = _strip_seps(_space_norm(artikul))
    rows = stock_rows.get(q_nd) or []
    if client is not None:
        client_key = client.strip().upper()
        rows = [r for r in rows if r[0].strip().upper() == client_key]
    breakdown = [cnt for _client, cnt in rows]
    if not breakdown:
        return None
    return sum(breakdown), breakdown


def invalidate_catalog_cache(excel_path: str = None):
    """Invalidate cached catalog. Pass None to clear everything."""
    with _catalog_lock:
        if excel_path is None:
            _catalog_cache.clear()
        else:
            _catalog_cache.pop(os.path.abspath(excel_path), None)


def find_all_matches_in_excel(excel_path: str, query_raw: str) -> List[Tuple[str, str]]:
    """
    Return every (client, orig_artikul) pair in the catalog that the query
    could reasonably mean — both exact and dash-normalized variants.

    Examples (catalog has "713" AND "7-1-3"):
      query "713"   → [("ClientA", "713"), ("ClientB", "7-1-3")]
      query "7-1-3" → [("ClientB", "7-1-3"), ("ClientA", "713")]
      query "713"   (catalog has only "7-1-3") → [("ClientB", "7-1-3")]

    Returns [] when nothing matches or the file doesn't exist.
    Raises ExcelReadError on read failure.
    """
    if not os.path.exists(excel_path):
        return []
    catalog = _load_catalog(excel_path)
    if catalog.get("error") == "no_artikul_col":
        return []

    lookup = catalog["lookup"]
    lookup_nodash = catalog["lookup_nodash"]

    q = _space_norm(query_raw)
    q_nd = _strip_seps(q)

    seen: set = set()
    results: list = []

    def _add(hit):
        if hit:
            client_val, orig = hit
            # Dedup by (client, orig) — not orig alone — so two different
            # clients who happen to use the exact same code text aren't
            # silently collapsed into a single picker entry.
            key = (client_val.strip().upper(), orig)
            if key not in seen:
                seen.add(key)
                results.append((client_val, orig))

    def _add_all(hits):
        for hit in hits or []:
            _add(hit)

    _add_all(lookup.get(q))            # exact matches (one per distinct client)
    _add_all(lookup_nodash.get(q))     # dashed catalog entries that strip to q  (e.g. "7-1-3" when q="713")
    if q_nd != q:
        _add_all(lookup.get(q_nd))         # exact catalog entries equal to dash-stripped query (e.g. "713" when q="7-1-3")
        _add_all(lookup_nodash.get(q_nd))  # dashed entries that strip to q_nd

    return results


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
    q_hits = lookup.get(q)
    hit = q_hits[0] if q_hits else None
    if hit:
        client_val, orig = hit
        debug_lines.append(f"✓ MATCH: ‘{q}’ → ‘{orig}’ | client: ‘{client_val}’")
        return (client_val, orig, "\n".join(debug_lines))

    # Try hyphen-stripped variant
    q_nd = _strip_seps(q)
    if q_nd and q_nd != q:
        debug_lines.append(f"Trying no-dash variant: ‘{q_nd}’")
        q_nd_hits = lookup.get(q_nd)
        nd_hits = lookup_nodash.get(q_nd)
        hit = (q_nd_hits[0] if q_nd_hits else None) or (nd_hits[0] if nd_hits else None)
        if hit:
            client_val, orig = hit
            debug_lines.append(f"✓ MATCH (no-dash): ‘{q_nd}’ → ‘{orig}’ | client: ‘{client_val}’")
            return (client_val, orig, "\n".join(debug_lines))

    debug_lines.append(f"✗ No match for ‘{q}’ ({len(lookup)} entries searched)")
    return (None, None, "\n".join(debug_lines))
