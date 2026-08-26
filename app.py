"""
Thin entrypoint for the Gear Ledger cloud backend.

All routes/business logic (results, catalog, invoice, etc.) live in the
gearledger package (installed from the Gear-Ledger repo's
web-app/installable-core branch — see requirements.txt). This repo only
adds what's genuinely new for the web app: auth, multi-tenancy, and any
web-only routes that don't belong in the desktop app's codebase.

Nothing auth-related exists yet — this first version just proves the
dependency works end-to-end by booting the existing Flask app unmodified.
"""
import os

from gearledger.server import GearLedgerServer

_server = GearLedgerServer(db_path=os.getenv("GEARLEDGER_DB_PATH", "gear_ledger.db"))
app = _server.app

if __name__ == "__main__":
    # Local dev only — gunicorn (via requirements.txt) is the real entrypoint.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8081")), debug=True)
