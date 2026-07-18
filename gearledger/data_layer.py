# -*- coding: utf-8 -*-
"""
Unified data layer that handles standalone, server, and client modes.
"""
from __future__ import annotations

import os
from typing import Dict, Any, Optional

from .desktop.settings_manager import load_settings


# Runtime state - tracks actual running mode (not just settings)
_runtime_mode: str = "standalone"  # "standalone", "server", or "client"


def set_runtime_mode(mode: str):
    """Set the runtime network mode."""
    global _runtime_mode
    print(f"[DATA_LAYER] Setting runtime mode: {mode}")
    _runtime_mode = mode


def get_runtime_mode() -> str:
    """Get the current runtime mode."""
    return _runtime_mode


def get_network_mode() -> str:
    """Get current network mode - prefers runtime mode over settings."""
    global _runtime_mode

    # If runtime mode is set to server/client, use that
    if _runtime_mode in ("server", "client"):
        # Removed verbose logging - this function is called frequently by timers
        return _runtime_mode

    # Otherwise check settings
    settings = load_settings()
    # Removed verbose logging - this function is called frequently by timers
    return settings.network_mode


def record_match_unified(
    path: str,
    artikul: str,
    client: str,
    qty_inc: int = 1,
    weight_inc: int = 1,
    catalog_path: str = None,
    weight_price: float = 0.0,
) -> Dict[str, Any]:
    """
    Record a match using the appropriate backend based on network mode.

    - standalone: Uses local Excel file (result_ledger.py)
    - server: Uses local SQLite database
    - client: Sends to remote server via API
    """
    mode = get_network_mode()
    print(f"[DATA_LAYER] record_match_unified called:")
    print(f"[DATA_LAYER]   mode={mode}, artikul={artikul}, client={client}")
    print(f"[DATA_LAYER]   qty={qty_inc}, weight={weight_inc}, path={path}")

    if mode == "client":
        print("[DATA_LAYER] Using CLIENT mode - sending to API")
        result = _record_via_api(
            artikul, client, qty_inc, weight_inc, catalog_path, weight_price
        )
        print(f"[DATA_LAYER] API result: {result}")
        return result
    elif mode == "server":
        print("[DATA_LAYER] Using SERVER mode - writing to database")
        result = _record_to_database(
            artikul, client, qty_inc, weight_inc, catalog_path, weight_price, path
        )
        print(f"[DATA_LAYER] Database result: {result}")
        return result
    else:  # standalone
        print("[DATA_LAYER] Using STANDALONE mode - writing to Excel")
        from .result_ledger import record_match

        result = record_match(
            path, artikul, client, qty_inc, weight_inc, catalog_path, weight_price
        )
        print(f"[DATA_LAYER] Excel result: {result}")
        return result


def _to_python_type(value):
    """Convert numpy/pandas types to native Python types for JSON serialization."""
    import numpy as np

    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    elif isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    elif isinstance(value, np.ndarray):
        return value.tolist()
    elif hasattr(value, "item"):  # Generic numpy scalar
        return value.item()
    return value


def _lookup_catalog_for_network(
    artikul: str, catalog_path: str = None, client: str = None
) -> Dict[str, Any]:
    """
    Look up catalog data for network modes.

    In server mode, ALWAYS checks for in-memory uploaded catalog first (even if catalog_path is provided).
    Falls back to file path if no in-memory catalog is available.

    `client` disambiguates catalog rows when the same artikul appears
    for multiple clients (e.g. different negotiated prices) — see
    result_ledger._lookup_catalog_data for details.
    """
    try:
        from .result_ledger import _lookup_catalog_data

        # Check if we're in server mode and have an uploaded catalog in memory
        mode = get_network_mode()
        catalog_bytes = None

        if mode == "server":
            from .server import get_server

            server = get_server()
            if server:
                if server.is_running():
                    catalog_bytes = server.get_uploaded_catalog_data()
                    if catalog_bytes:
                        print(
                            f"[DATA_LAYER] Using in-memory uploaded catalog for lookup (size: {len(catalog_bytes)} bytes)"
                        )
                    else:
                        print(
                            "[DATA_LAYER] No in-memory catalog, will use file path if provided"
                        )
                else:
                    print("[DATA_LAYER] Server instance found but not running")
            else:
                print("[DATA_LAYER] Server instance not found via get_server()")

        # ALWAYS prioritize in-memory catalog in server mode, even if catalog_path is provided
        # This ensures the server uses the uploaded catalog instead of the file
        if catalog_bytes is not None:
            print(
                f"[DATA_LAYER] Looking up {artikul} in in-memory catalog (ignoring catalog_path={catalog_path})"
            )
            data = _lookup_catalog_data(
                artikul, catalog_bytes=catalog_bytes, client=client
            )
        elif catalog_path and os.path.exists(catalog_path):
            print(
                f"[DATA_LAYER] No in-memory catalog available, looking up {artikul} in catalog file: {catalog_path}"
            )
            data = _lookup_catalog_data(
                artikul, catalog_path=catalog_path, client=client
            )
        else:
            print(
                f"[DATA_LAYER] No catalog available: catalog_path={catalog_path}, in_memory={catalog_bytes is not None}"
            )
            return {}

        # Convert numpy types to native Python types
        return {k: _to_python_type(v) for k, v in data.items()}
    except Exception as e:
        print(f"[ERROR] Catalog lookup failed: {e}")
        import traceback

        traceback.print_exc()
        return {}


def _record_via_api(
    artikul: str,
    client: str,
    qty_inc: int,
    weight_inc: int,
    catalog_path: str,
    weight_price: float,  # noqa: ARG001 - kept for API compatibility
) -> Dict[str, Any]:
    """Record match via API to remote server."""
    print("[DATA_LAYER] _record_via_api called")
    from .api_client import get_client

    api_client = get_client()
    print(f"[DATA_LAYER] API client: {api_client}")
    if api_client:
        print(f"[DATA_LAYER] API client connected: {api_client.is_connected()}")

    if not api_client or not api_client.is_connected():
        print("[DATA_LAYER] ERROR: Not connected to server")
        return {
            "ok": False,
            "action": "failed",
            "path": "",
            "error": "Not connected to server",
        }

    # Look up catalog data locally (catalog is local)
    catalog_data = _lookup_catalog_for_network(artikul, catalog_path, client=client)
    brand = catalog_data.get("бренд", "")
    description = catalog_data.get("описание", "")
    sale_price = catalog_data.get("цена", 0)
    print(f"[DATA_LAYER] Catalog data: brand={brand}, price={sale_price}")

    try:
        print(
            f"[DATA_LAYER] Sending to API: artikul={artikul}, client={client}, qty={qty_inc}, weight={weight_inc}"
        )
        result = api_client.add_or_update_result(
            artikul=str(artikul),
            client=str(client),
            quantity=int(qty_inc),
            weight=float(weight_inc) if weight_inc else 0.0,
            brand=str(brand) if brand else "",
            description=str(description) if description else "",
            sale_price=float(sale_price) if sale_price else 0.0,
        )
        print(f"[DATA_LAYER] API response: {result}")

        if result.get("ok"):
            return {
                "ok": True,
                "action": result.get("action", "updated"),
                "path": "server",
                "error": "",
            }
        else:
            return {
                "ok": False,
                "action": "failed",
                "path": "server",
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        print(f"[DATA_LAYER] API exception: {e}")
        return {"ok": False, "action": "failed", "path": "server", "error": str(e)}


def _record_to_database(
    artikul: str,
    client: str,
    qty_inc: int,
    weight_inc: int,
    catalog_path: str,
    weight_price: float,  # noqa: ARG001 - kept for API compatibility
    path: str,  # noqa: ARG001 - kept for API compatibility
) -> Dict[str, Any]:
    """Record match to local SQLite database (server mode)."""
    print("[DATA_LAYER] _record_to_database called")
    from .database import get_database

    db = get_database()
    print(f"[DATA_LAYER] Database path: {db.db_path}")

    # Look up catalog data (even if catalog_path is empty, we still write the result)
    # In server mode, ALWAYS prioritize in-memory uploaded catalog, even if catalog_path is provided
    print(f"[DATA_LAYER] Catalog path for lookup: {catalog_path}")

    # In server mode, ALWAYS check for in-memory catalog first (regardless of catalog_path)
    # This ensures the server uses the uploaded catalog instead of the file
    mode = get_network_mode()
    if mode == "server":
        from .server import get_server

        server = get_server()
        if server and server.is_running():
            catalog_bytes = server.get_uploaded_catalog_data()
            if catalog_bytes:
                print(
                    f"[DATA_LAYER] Server mode: Found in-memory catalog (size: {len(catalog_bytes)} bytes), will use it instead of file path"
                )
                # Override catalog_path to empty to force use of in-memory catalog
                catalog_path = ""
            else:
                print(
                    "[DATA_LAYER] Server mode: No in-memory catalog available, will use file path if provided"
                )
        else:
            print("[DATA_LAYER] Server mode: Server instance not found or not running")

    brand = ""
    description = ""
    sale_price = 0.0

    # Try to look up catalog data (will use in-memory catalog in server mode if available)
    catalog_data = _lookup_catalog_for_network(artikul, catalog_path, client=client)
    if catalog_data:
        brand = catalog_data.get("бренд", "")
        description = catalog_data.get("описание", "")
        sale_price = catalog_data.get("цена", 0)
        print(f"[DATA_LAYER] Catalog data found: brand={brand}, price={sale_price}")
    else:
        print(
            "[DATA_LAYER] WARNING: No catalog data found (no uploaded catalog or file path)"
        )
        print(
            "[DATA_LAYER] Will write result without catalog data (brand/price will be empty)"
        )

    try:
        print(
            f"[DATA_LAYER] Writing to DB: artikul={artikul}, client={client}, qty={qty_inc}, weight={weight_inc}"
        )
        result = db.add_or_update_result(
            artikul=str(artikul),
            client=str(client),
            quantity=int(qty_inc),
            weight=float(weight_inc) if weight_inc else 0.0,
            brand=str(brand) if brand else "",
            description=str(description) if description else "",
            sale_price=float(sale_price) if sale_price else 0.0,
        )
        print(f"[DATA_LAYER] Database result: {result}")

        if result.get("ok"):
            return {
                "ok": True,
                "action": result.get("action", "updated"),
                "path": db.db_path,
                "error": "",
            }
        else:
            return {
                "ok": False,
                "action": "failed",
                "path": db.db_path,
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        print(f"[DATA_LAYER] Database exception: {e}")
        import traceback

        traceback.print_exc()
        return {"ok": False, "action": "failed", "path": "", "error": str(e)}


def get_results_quantity(results_path: str, artikul: str, client: str) -> int:
    """
    Return the quantity already recorded for (artikul, client) in the current backend.
    Standalone → reads results Excel. Server/client → filters get_all_results().

    Previously server/client mode each hand-rolled their own separate
    artikul-normalization (missing em/en-dash and non-breaking-space
    handling), and the server-mode SQL query didn't even strip separators
    from the *stored* column — only from the query parameter — so it could
    fail to match almost any code containing a dash or space. Routing
    through get_all_results() + the single shared, already-fixed normalizer
    keeps this consistent with every other artikul-matching path.
    """
    mode = get_network_mode()
    if mode == "standalone":
        from .result_ledger import get_results_quantity as _excel_qty
        return _excel_qty(results_path, artikul, client)

    try:
        from .result_ledger import _norm

        target_key = _norm(artikul)
        total = 0
        for row in get_all_results(client_filter=client):
            if _norm(row.get("artikul", "")) == target_key:
                total += int(row.get("quantity", 0) or 0)
        return total
    except Exception:
        return 0


def get_all_results(client_filter: str = None, results_path: str = None) -> list:
    """Get all results from the appropriate backend.

    results_path is only used in standalone mode, to read the local Excel
    ledger (server/client mode ignore it, they have their own source).
    """
    mode = get_network_mode()

    if mode == "client":
        from .api_client import get_client

        api_client = get_client()
        if api_client and api_client.is_connected():
            return api_client.get_all_results(client_filter)
        return []
    elif mode == "server":
        from .database import get_database

        db = get_database()
        return db.get_all_results(client_filter)
    else:
        # Standalone - read from the local Excel ledger
        if not results_path:
            return []
        from .result_ledger import get_all_results_excel

        rows = get_all_results_excel(results_path)
        if client_filter:
            client_upper = client_filter.strip().upper()
            rows = [
                r for r in rows if str(r.get("client", "")).strip().upper() == client_upper
            ]
        return rows


def is_network_mode() -> bool:
    """Check if we're in a network mode (server or client)."""
    mode = get_network_mode()
    return mode in ("server", "client")


def delete_result_unified(artikul: str, client: str, results_path: str = None) -> bool:
    """Delete a recorded (artikul, client) result from the appropriate backend.

    Only standalone and server mode are supported (matches where the
    Check Order / Generate Invoice actions are available in the UI).
    """
    mode = get_network_mode()

    if mode == "server":
        from .database import get_database

        db = get_database()
        return db.delete_result_by_key(artikul, client) > 0
    elif mode == "standalone":
        if not results_path:
            return False
        from .result_ledger import delete_result_excel

        result = delete_result_excel(results_path, artikul, client)
        return bool(result.get("ok")) and result.get("deleted", 0) > 0
    else:
        return False


def set_result_quantity_unified(
    artikul: str, client: str, new_quantity: int, results_path: str = None
) -> bool:
    """Correct a recorded (artikul, client) result's quantity in the
    appropriate backend (e.g. fixing an over-recorded item).

    Only standalone and server mode are supported (matches where the
    Check Order / Generate Invoice actions are available in the UI).
    """
    mode = get_network_mode()

    if mode == "server":
        from .database import get_database

        db = get_database()
        return db.update_result_quantity_by_key(artikul, client, new_quantity)
    elif mode == "standalone":
        if not results_path:
            return False
        from .result_ledger import set_result_quantity_excel

        result = set_result_quantity_excel(results_path, artikul, client, new_quantity)
        return bool(result.get("ok")) and result.get("updated", 0) > 0
    else:
        return False


def check_catalog_completeness(catalog_path: str, results_path: str = None) -> dict:
    """
    Compare every (client, artikul) demand line in the catalog against what's
    actually been recorded, so the user can catch anything they forgot
    before finishing a session.

    Matching uses the same separator-stripped normalization as the rest of
    the catalog code (dash/dot/space variants of a code are treated as the
    same item), and exact (trimmed, case-insensitive) client-name matching.

    Returns {
        "ok": bool,
        "error": Optional[str],           # "no_quantity_column" if catalog has none
        "not_started": [{"client", "artikul", "ordered"}],
        "partial": [{"client", "artikul", "ordered", "recorded", "missing"}],
        "over_recorded": [{"client", "artikul", "ordered", "recorded", "excess"}],
        "not_in_catalog": [{"client", "artikul", "recorded"}],
        "complete_count": int,
        "total_count": int,
    }
    """
    from .excel_utils import list_catalog_demand, _space_norm, _strip_seps

    demand = list_catalog_demand(catalog_path)
    if not demand:
        return {
            "ok": False,
            "error": "no_quantity_column",
            "not_started": [],
            "partial": [],
            "over_recorded": [],
            "not_in_catalog": [],
            "complete_count": 0,
            "total_count": 0,
        }

    results_rows = get_all_results(results_path=results_path)

    recorded_lookup: dict = {}
    recorded_display: dict = {}
    for r in results_rows:
        artikul_r = r.get("artikul", "")
        client_r = r.get("client", "")
        key = (_strip_seps(_space_norm(artikul_r)), str(client_r).strip().upper())
        recorded_lookup[key] = recorded_lookup.get(key, 0) + int(r.get("quantity", 0) or 0)
        recorded_display.setdefault(key, (client_r, artikul_r))

    not_started = []
    partial = []
    over_recorded = []
    complete_count = 0
    catalog_keys = set()
    for d in demand:
        key = (_strip_seps(_space_norm(d["artikul"])), d["client"].strip().upper())
        catalog_keys.add(key)
        recorded = recorded_lookup.get(key, 0)
        ordered = d["ordered_qty"]
        if recorded <= 0:
            not_started.append(
                {"client": d["client"], "artikul": d["artikul"], "ordered": ordered}
            )
        elif recorded < ordered:
            partial.append(
                {
                    "client": d["client"],
                    "artikul": d["artikul"],
                    "ordered": ordered,
                    "recorded": recorded,
                    "missing": ordered - recorded,
                }
            )
        elif recorded > ordered:
            over_recorded.append(
                {
                    "client": d["client"],
                    "artikul": d["artikul"],
                    "ordered": ordered,
                    "recorded": recorded,
                    "excess": recorded - ordered,
                }
            )
        else:
            complete_count += 1

    not_in_catalog = []
    for key, qty in recorded_lookup.items():
        if key not in catalog_keys and qty > 0:
            client_disp, artikul_disp = recorded_display[key]
            not_in_catalog.append(
                {"client": client_disp, "artikul": artikul_disp, "recorded": qty}
            )

    return {
        "ok": True,
        "error": None,
        "not_started": not_started,
        "partial": partial,
        "over_recorded": over_recorded,
        "not_in_catalog": not_in_catalog,
        "complete_count": complete_count,
        "total_count": len(demand),
    }
