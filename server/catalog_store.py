# -*- coding: utf-8 -*-
"""
Per-tenant catalog storage — genuinely new, web-only persistence.

gearledger.server.GearLedgerServer keeps the uploaded catalog as a single
in-memory `self._catalog_data` blob on the server instance (fine for a LAN
server with one client base and rare restarts). In this multi-tenant
deployment that's two bugs at once: it's wiped on every redeploy, and —
more urgently — it's *shared across every tenant*, since there's only one
GearLedgerServer instance for the whole process. Tenant B's
GET /api/catalog would download tenant A's file.

This module is the persistent, per-tenant replacement backing store;
tenant_server.py wires it in via property overrides so gearledger's
existing catalog routes keep working completely unmodified.
"""
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional, TypedDict


class CatalogRow(TypedDict):
    data: bytes
    filename: str
    uploaded_at: float


def _default_db_path() -> str:
    return os.getenv("GEARLEDGER_CATALOGS_DB_PATH", "catalogs.db")


class CatalogStore:
    """Thread-safe SQLite store: one row per tenant, upserted field-by-field
    to match GearLedgerServer's existing upload_catalog route, which sets
    _catalog_data / _catalog_filename / _catalog_upload_time as three
    separate attribute assignments rather than one atomic write."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _default_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path, check_same_thread=False, timeout=30.0
            )
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS catalogs (
                tenant_id TEXT PRIMARY KEY,
                data BLOB,
                filename TEXT,
                uploaded_at REAL
            )
            """
        )
        conn.commit()

    def get(self, tenant_id: str) -> Optional[CatalogRow]:
        conn = self._get_connection()
        row = conn.execute(
            "SELECT data, filename, uploaded_at FROM catalogs WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "data": row["data"],
            "filename": row["filename"],
            "uploaded_at": row["uploaded_at"],
        }

    def _upsert(self, tenant_id: str, column: str, value) -> None:
        conn = self._get_connection()
        conn.execute(f"INSERT INTO catalogs (tenant_id) VALUES (?) "
                     f"ON CONFLICT(tenant_id) DO NOTHING", (tenant_id,))
        conn.execute(
            f"UPDATE catalogs SET {column} = ? WHERE tenant_id = ?", (value, tenant_id)
        )
        conn.commit()

    def set_data(self, tenant_id: str, data: Optional[bytes]) -> None:
        self._upsert(tenant_id, "data", data)

    def set_filename(self, tenant_id: str, filename: Optional[str]) -> None:
        self._upsert(tenant_id, "filename", filename)

    def set_uploaded_at(self, tenant_id: str, uploaded_at: Optional[float]) -> None:
        self._upsert(tenant_id, "uploaded_at", uploaded_at)


_store: Optional[CatalogStore] = None
_store_lock = threading.Lock()


def get_catalog_store() -> CatalogStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = CatalogStore()
    return _store
