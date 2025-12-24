# -*- coding: utf-8 -*-
"""
Unified data layer that handles standalone, server, and client modes.
"""
from __future__ import annotations

import os
from typing import Dict, Any, Optional

from .desktop.settings_manager import load_settings


def get_network_mode() -> str:
    """Get current network mode from settings."""
    settings = load_settings()
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

    if mode == "client":
        return _record_via_api(
            artikul, client, qty_inc, weight_inc, catalog_path, weight_price
        )
    elif mode == "server":
        return _record_to_database(
            artikul, client, qty_inc, weight_inc, catalog_path, weight_price, path
        )
    else:  # standalone
        from .result_ledger import record_match

        return record_match(
            path, artikul, client, qty_inc, weight_inc, catalog_path, weight_price
        )


def _lookup_catalog_for_network(artikul: str, catalog_path: str) -> Dict[str, Any]:
    """Look up catalog data for network modes."""
    if not catalog_path or not os.path.exists(catalog_path):
        return {}

    try:
        from .result_ledger import _lookup_catalog_data

        return _lookup_catalog_data(artikul, catalog_path)
    except Exception as e:
        print(f"[ERROR] Catalog lookup failed: {e}")
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
    from .api_client import get_client

    api_client = get_client()
    if not api_client or not api_client.is_connected():
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

    try:
        result = api_client.add_or_update_result(
            artikul=artikul,
            client=client,
            quantity=qty_inc,
            weight=weight_inc,
            brand=brand,
            description=description,
            sale_price=sale_price,
        )

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
    from .database import get_database

    db = get_database()

    # Look up catalog data
    catalog_data = _lookup_catalog_for_network(artikul, catalog_path)
    brand = catalog_data.get("бренд", "")
    description = catalog_data.get("описание", "")
    sale_price = catalog_data.get("цена", 0)

    try:
        result = db.add_or_update_result(
            artikul=artikul,
            client=client,
            quantity=qty_inc,
            weight=weight_inc,
            brand=brand,
            description=description,
            sale_price=sale_price,
        )

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
