# -*- coding: utf-8 -*-
"""
Tenant-scoped subclassing of GearLedgerServer.

gearledger.database.get_database() (what GearLedgerServer._get_db() calls
by default) is a process-wide singleton: the first db_path it's called
with wins, and every later call silently ignores its db_path argument and
returns that same cached instance. That's fine for the desktop app (one
process, one db_path, forever) but would be a cross-tenant data leak here
— tenant B's requests would silently read/write tenant A's database.

Rather than patch that shared singleton (out of scope for this repo — see
CLAUDE.md-equivalent context: never modify the gearledger package from
here), this subclass bypasses it entirely and keeps its own per-tenant
cache of gearledger.database.Database instances, which is a plain,
self-contained, thread-safe class with no shared state of its own.
"""
import os
import re
import threading

import flask

from gearledger.database import Database
from gearledger.server import GearLedgerServer

_SAFE_TENANT_ID = re.compile(r"^[a-f0-9]{32}$")


class TenantScopedServer(GearLedgerServer):
    def __init__(self, *args, **kwargs):
        # Base class's db_path is unused here — each request supplies its
        # own tenant db_path via _get_db() below.
        kwargs.setdefault("db_path", None)
        super().__init__(*args, **kwargs)
        self._tenant_dbs: dict[str, Database] = {}
        self._tenant_dbs_lock = threading.Lock()

    def _tenant_db_path(self, tenant_id: str) -> str:
        if not _SAFE_TENANT_ID.match(tenant_id):
            # tenant_id always comes from our own accounts store (uuid4().hex)
            # or a verified JWT claim minted from one — never raw user input.
            # This guards against a malformed/forged claim turning into a
            # path-traversal write outside the tenant data directory.
            raise ValueError(f"invalid tenant_id: {tenant_id!r}")
        base = os.getenv("GEARLEDGER_TENANT_DATA_DIR", "./tenant_data")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, f"tenant_{tenant_id}.db")

    def _get_db(self) -> Database:
        tenant_id = getattr(flask.g, "tenant_id", None)
        if tenant_id is None:
            raise RuntimeError(
                "_get_db() called outside an authenticated request context "
                "(no flask.g.tenant_id set — auth.py's before_request guard "
                "should have rejected this request before it got here)"
            )
        with self._tenant_dbs_lock:
            db = self._tenant_dbs.get(tenant_id)
            if db is None:
                db = Database(self._tenant_db_path(tenant_id))
                self._tenant_dbs[tenant_id] = db
            return db
