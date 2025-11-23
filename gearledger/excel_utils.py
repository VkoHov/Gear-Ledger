# -*- coding: utf-8 -*-
import os
import pandas as pd


class ExcelReadError(Exception):
    """Exception raised when Excel file cannot be read."""

    def __init__(self, excel_path: str, error_message: str):
        self.excel_path = excel_path
        self.error_message = error_message
        super().__init__(f"Failed to read Excel file: {error_message}")


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
        error_msg = str(e)
        debug.append(f"Failed to read Excel: {error_msg}")
        # Raise custom exception so UI can show popup
        raise ExcelReadError(excel_path, error_msg)

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
    debug.append(f"═══════════════════════════════════════")
    debug.append(f"EXCEL MATCH DEBUG")
    debug.append(f"═══════════════════════════════════════")
    debug.append(f"Query (original): '{query_raw}'")
    debug.append(f"Query (normalized): '{q}'")
    debug.append(f"Excel file: {os.path.basename(excel_path)}")
    debug.append(f"Total rows in Excel: {len(df)}")
    debug.append(f"Artikul column: '{artikul_col}'")
    debug.append(f"Client column: '{client_col}'")

    # Build normalized column (space stripped, uppercase)
    norm_col = "_GL_SPACE_NORM_"
    df[norm_col] = df[artikul_col].astype(str).map(space_norm)

    # Show sample of values in Excel
    debug.append(f"\nSample values from Excel (first 20):")
    for idx, row in df.head(20).iterrows():
        orig_val = str(row[artikul_col])
        norm_val = str(row[norm_col])
        debug.append(f"  [{idx}] Original: '{orig_val}' → Normalized: '{norm_val}'")

    # If query contains hyphen/dash, try both with and without
    queries_to_try = [q]
    if "-" in q or "—" in q or "–" in q:
        q_no_dash = q.replace("-", "").replace("—", "").replace("–", "")
        if q_no_dash and q_no_dash != q:
            queries_to_try.append(q_no_dash)
            debug.append(
                f"\nQuery contains hyphen - will try both: '{q}' and '{q_no_dash}'"
            )

    # Try each query variation
    for query_variant in queries_to_try:
        debug.append(f"\nTrying query variant: '{query_variant}'")

        # Check for exact match
        exact = df[df[norm_col] == query_variant]
        if not exact.empty:
            row = exact.iloc[0]
            orig_matched = str(row[artikul_col])
            norm_matched = str(row[norm_col])
            client_matched = str(row.get(client_col, ""))
            debug.append(f"\n✓ MATCH FOUND!")
            debug.append(f"  Query variant that matched: '{query_variant}'")
            debug.append(f"  Original value: '{orig_matched}'")
            debug.append(f"  Normalized value: '{norm_matched}'")
            debug.append(f"  Client: '{client_matched}'")
            debug.append(f"═══════════════════════════════════════")
            return (
                client_matched,
                orig_matched,
                "\n".join(debug),
            )
        else:
            debug.append(f"  No match for variant: '{query_variant}'")

    # No match found with any variant - use the original query for debugging
    q = queries_to_try[0]  # Use original for rest of debug output

    # No exact match - provide detailed debugging
    debug.append(f"\n✗ NO EXACT MATCH FOUND")
    debug.append(f"  Searched for: '{q}'")

    # Check if query exists with different normalization
    all_norms = df[norm_col].unique()
    debug.append(f"\nAll unique normalized values in Excel ({len(all_norms)} total):")
    if len(all_norms) <= 100:
        for norm_val in sorted(all_norms):
            # Find original value for this normalized value
            orig_example = df[df[norm_col] == norm_val].iloc[0][artikul_col]
            debug.append(f"  '{norm_val}' (from '{orig_example}')")
    else:
        debug.append(f"  (Too many to list - showing first 50)")
        for norm_val in sorted(all_norms)[:50]:
            orig_example = df[df[norm_col] == norm_val].iloc[0][artikul_col]
            debug.append(f"  '{norm_val}' (from '{orig_example}')")

    # Find closest matches (by length and character similarity)
    debug.append(f"\nClosest matches (by length):")
    query_len = len(q)
    closest_by_len = sorted(all_norms, key=lambda x: abs(len(x) - query_len))[:5]
    for norm_val in closest_by_len:
        orig_example = df[df[norm_col] == norm_val].iloc[0][artikul_col]
        len_diff = abs(len(norm_val) - query_len)
        debug.append(f"  '{norm_val}' (from '{orig_example}', length diff: {len_diff})")

    # Check if query is a substring of any value
    contains_query = df[df[norm_col].str.contains(q, na=False, case=False)]
    if not contains_query.empty:
        debug.append(
            f"\nValues containing '{q}' as substring ({len(contains_query)} found):"
        )
        for idx, row in contains_query.head(10).iterrows():
            orig_val = str(row[artikul_col])
            norm_val = str(row[norm_col])
            debug.append(f"  '{norm_val}' (from '{orig_val}')")

    # Check if any value is a substring of query
    query_contains = df[
        df[norm_col].apply(
            lambda x: q in str(x) if x is not None and str(x) != "nan" else False
        )
    ]
    if not query_contains.empty:
        debug.append(
            f"\nValues that are substrings of '{q}' ({len(query_contains)} found):"
        )
        for idx, row in query_contains.head(10).iterrows():
            orig_val = str(row[artikul_col])
            norm_val = str(row[norm_col])
            debug.append(f"  '{norm_val}' (from '{orig_val}')")

    # Character-by-character comparison for very similar strings
    if len(q) > 0:
        debug.append(f"\nCharacter analysis:")
        debug.append(f"  Query length: {len(q)}")
        debug.append(f"  Query characters: {set(q)}")

        # Find values with similar character sets
        query_chars = set(q)
        similar_chars = []
        for norm_val in all_norms[:50]:  # Check first 50 for performance
            val_chars = set(str(norm_val))
            common_chars = query_chars & val_chars
            if len(common_chars) >= min(3, len(query_chars) * 0.5):
                orig_example = df[df[norm_col] == norm_val].iloc[0][artikul_col]
                similar_chars.append((norm_val, orig_example, len(common_chars)))

        if similar_chars:
            similar_chars.sort(key=lambda x: x[2], reverse=True)
            debug.append(f"  Values with similar characters (top 5):")
            for norm_val, orig_example, common_count in similar_chars[:5]:
                debug.append(
                    f"    '{norm_val}' (from '{orig_example}', {common_count} common chars)"
                )

    debug.append(f"═══════════════════════════════════════")
    return (None, None, "\n".join(debug))
