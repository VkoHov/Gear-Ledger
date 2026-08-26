# gearledger/desktop/client_connect_worker.py
# -*- coding: utf-8 -*-
"""Shared background worker for the one-touch client connect flow, used by
both the main window's Connect button and the Network Settings dialog's
Connect button — keeping the "try saved address, then discover" logic in
one place so both UIs behave identically."""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class ClientConnectWorker(QThread):
    """Tries the last-known server address first (fast path for the common
    "reopen the app on the same network" case); if that's unset or fails,
    falls back to LAN discovery and reports whatever it found so the caller
    can auto-connect (exactly one) or show a picker (more than one)."""

    connected = pyqtSignal(str)  # address
    discovery_finished = pyqtSignal(list)  # List[DiscoveredServer]

    def __init__(self, saved_address: str, parent=None, auth_token: str = ""):
        super().__init__(parent)
        self._saved_address = (saved_address or "").strip()
        # Empty string when there's no stored cloud login — connect_to_server
        # treats that the same as "no token", so this fast path behaves
        # identically to before for a plain LAN reconnect. When the saved
        # address is actually the cloud backend (from a prior "Log In to
        # Cloud"), this is what makes the reconnect authenticate instead of
        # 401ing and falling through to a pointless LAN discovery scan.
        self._auth_token = auth_token or ""

    def run(self):
        from gearledger.api_client import connect_to_server

        if self.isInterruptionRequested():
            return

        if self._saved_address:
            address = self._saved_address
            if not address.startswith("http://") and not address.startswith("https://"):
                address = f"http://{address}"
            # Short timeout: this is a best-effort fast path, not worth
            # blocking the worker (and thus the "Connecting..." state) for
            # the full default timeout if the saved server is gone.
            try:
                client = connect_to_server(
                    address, timeout=4, auth_token=self._auth_token
                )
            except Exception:
                client = None
            if client:
                self.connected.emit(address)
                return

        if self.isInterruptionRequested():
            return

        # Fall back to LAN discovery.
        import time
        from gearledger.network_discovery import ServerDiscovery

        discovery = ServerDiscovery()
        discovery.start()
        # Interruptible in small increments rather than a flat sleep(4) —
        # lets a shutdown mid-discovery return promptly instead of always
        # taking the full 4s.
        for _ in range(40):
            if self.isInterruptionRequested():
                break
            time.sleep(0.1)
        discovery.stop()
        if not self.isInterruptionRequested():
            self.discovery_finished.emit(discovery.get_discovered_servers())
