"""
Thin entrypoint for the Gear Ledger cloud backend.

All routes/business logic (results, catalog, invoice, etc.) live in the
gearledger package (installed from the Gear-Ledger repo's
web-app/installable-core branch — see requirements.txt). This repo only
adds what's genuinely new for the web app: auth, multi-tenancy, and any
web-only routes that don't belong in the desktop app's codebase.

Every existing gearledger route (results, catalog, clients, SSE events) now
requires a JWT and is scoped to the caller's tenant — see auth.py for the
before_request guard and tenant_server.py for how "which tenant" turns into
"which SQLite file" on every request.
"""
import os

from auth import init_auth
from tenant_server import TenantScopedServer

_server = TenantScopedServer()
app = _server.app
init_auth(app)

if __name__ == "__main__":
    # Local dev only — gunicorn (via requirements.txt) is the real entrypoint.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8081")), debug=True)
