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
    artikul: str, catalog_path: str = None
) -> Dict[str, Any]:
    """
    Look up catalog data for network modes.

    In server mode, checks for in-memory uploaded catalog first.
    Falls back to file path if no in-memory catalog is available.
    """
    try:
        from .result_ledger import _lookup_catalog_data

        # Check if we're in server mode and have an uploaded catalog in memory
        mode = get_network_mode()
        catalog_bytes = None

        if mode == "server":
            from .server import get_server

            server = get_server()
            if server and server.is_running():
                catalog_bytes = server.get_uploaded_catalog_data()
                if catalog_bytes:
                    print(
                        f"[DATA_LAYER] Using in-memory uploaded catalog for lookup (size: {len(catalog_bytes)} bytes)"
                    )
                else:
                    print(
                        f"[DATA_LAYER] No in-memory catalog, will use file path if provided"
                    )

        # Use in-memory catalog if available, otherwise use file path
        if catalog_bytes is not None:
            print(f"[DATA_LAYER] Looking up {artikul} in in-memory catalog")
            data = _lookup_catalog_data(artikul, catalog_bytes=catalog_bytes)
        elif catalog_path and os.path.exists(catalog_path):
            print(f"[DATA_LAYER] Looking up {artikul} in catalog file: {catalog_path}")
            data = _lookup_catalog_data(artikul, catalog_path=catalog_path)
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
    catalog_data = _lookup_catalog_for_network(artikul, catalog_path)
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
    # In server mode, will use in-memory uploaded catalog if available
    print(f"[DATA_LAYER] Catalog path for lookup: {catalog_path}")

    # In server mode, also check for in-memory catalog if catalog_path is empty
    mode = get_network_mode()
    if mode == "server" and (not catalog_path or catalog_path == ""):
        from .server import get_server

        server = get_server()
        if server and server.is_running():
            catalog_bytes = server.get_uploaded_catalog_data()
            if catalog_bytes:
                print(
                    f"[DATA_LAYER] Using in-memory uploaded catalog (size: {len(catalog_bytes)} bytes)"
                )
            else:
                print(f"[DATA_LAYER] No in-memory catalog, catalog_path is empty")

    brand = ""
    description = ""
    sale_price = 0.0

    # Try to look up catalog data (will use in-memory catalog in server mode if available)
    catalog_data = _lookup_catalog_for_network(artikul, catalog_path)
    if catalog_data:
        brand = catalog_data.get("бренд", "")
        description = catalog_data.get("описание", "")
        sale_price = catalog_data.get("цена", 0)
        print(f"[DATA_LAYER] Catalog data found: brand={brand}, price={sale_price}")
    else:
        print(
            f"[DATA_LAYER] WARNING: No catalog data found (no uploaded catalog or file path)"
        )
        print(
            f"[DATA_LAYER] Will write result without catalog data (brand/price will be empty)"
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


def get_all_results(client_filter: str = None) -> list:
    """Get all results from the appropriate backend."""
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
        # Standalone - not needed for now, results are read from Excel
        return []


def is_network_mode() -> bool:
    """Check if we're in a network mode (server or client)."""
    mode = get_network_mode()
    return mode in ("server", "client")
