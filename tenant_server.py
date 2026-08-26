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

The same class of bug exists for the uploaded catalog: GearLedgerServer
keeps it as a single self._catalog_data blob (info/GET/POST routes, the
SSE status blurb, and get_uploaded_catalog_data() all read/write it
directly as a plain attribute) — one shared blob for every tenant, and
wiped on every restart. Overriding _catalog_data/_catalog_filename/
_catalog_upload_time as properties backed by CatalogStore fixes every one
of those call sites at once, since they all go through `self.<attr>`,
without duplicating any of that route logic here.

A third instance of the same bug lives in gearledger.data_layer: five
functions there (get_all_results, _record_to_database, etc.) call the bare
get_database() singleton directly — not through GearLedgerServer._get_db()
at all — so overriding _get_db() alone doesn't reach them. This matters
today for GET /api/completeness (wraps check_catalog_completeness, which
calls data_layer.get_all_results internally) and will matter for whatever
Phase 2's /api/scan route ends up needing from data_layer/pipeline.py.
Since every one of those call sites does `from .database import
get_database` *inside* the function body (not once at module import time),
patching the gearledger.database.get_database *function itself* — done
once below — is enough to fix all of them, present and future, without
touching gearledger's source or special-casing each call site as it's
discovered.
"""
import os
import re
import threading

import flask

from catalog_store import get_catalog_store
from gearledger.database import Database
from gearledger.server import GearLedgerServer
import gearledger.database as _gearledger_database

_SAFE_TENANT_ID = re.compile(r"^[a-f0-9]{32}$")


class TenantScopedServer(GearLedgerServer):
    def __init__(self, *args, **kwargs):
        # Set before super().__init__(): the base class's __init__ assigns
        # self._catalog_data = None etc, which — once those are properties
        # below — routes through _catalog_store immediately.
        self._catalog_store = get_catalog_store()

        # Base class's db_path is unused here — each request supplies its
        # own tenant db_path via _get_db() below.
        kwargs.setdefault("db_path", None)
        super().__init__(*args, **kwargs)
        self._tenant_dbs: dict[str, Database] = {}
        self._tenant_dbs_lock = threading.Lock()
        self._patch_database_singleton()

    def _patch_database_singleton(self) -> None:
        def tenant_aware_get_database(db_path: str = None) -> Database:
            tenant_id = self._current_tenant_id()
            if tenant_id is None:
                raise RuntimeError(
                    "gearledger.database.get_database() called with no "
                    "tenant in context — every caller reachable from an "
                    "authenticated request should resolve via "
                    "flask.g.tenant_id. This means either a route is "
                    "missing the auth guard, or DB code is running outside "
                    "a request."
                )
            return self._get_db()

        _gearledger_database.get_database = tenant_aware_get_database

    def _current_tenant_id(self):
        # Guard against access outside a request (e.g. during __init__,
        # before any Flask app/request context exists) — flask.g raises
        # RuntimeError if touched there rather than just returning empty.
        if not flask.has_app_context():
            return None
        return getattr(flask.g, "tenant_id", None)

    @property
    def _catalog_data(self):
        tenant_id = self._current_tenant_id()
        if tenant_id is None:
            return None
        row = self._catalog_store.get(tenant_id)
        return row["data"] if row else None

    @_catalog_data.setter
    def _catalog_data(self, value):
        tenant_id = self._current_tenant_id()
        if tenant_id is None:
            return
        self._catalog_store.set_data(tenant_id, value)

    @property
    def _catalog_filename(self):
        tenant_id = self._current_tenant_id()
        if tenant_id is None:
            return None
        row = self._catalog_store.get(tenant_id)
        return row["filename"] if row else None

    @_catalog_filename.setter
    def _catalog_filename(self, value):
        tenant_id = self._current_tenant_id()
        if tenant_id is None:
            return
        self._catalog_store.set_filename(tenant_id, value)

    @property
    def _catalog_upload_time(self):
        tenant_id = self._current_tenant_id()
        if tenant_id is None:
            return None
        row = self._catalog_store.get(tenant_id)
        return row["uploaded_at"] if row else None

    @_catalog_upload_time.setter
    def _catalog_upload_time(self, value):
        tenant_id = self._current_tenant_id()
        if tenant_id is None:
            return
        self._catalog_store.set_uploaded_at(tenant_id, value)

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
