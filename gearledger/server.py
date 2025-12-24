# -*- coding: utf-8 -*-
"""
REST API server for multi-device access to Gear Ledger.
"""
import threading
import socket
from typing import Optional, Callable
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.serving import make_server

from .database import get_database, Database


class GearLedgerServer:
    """REST API server for Gear Ledger."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        db_path: str = None,
        on_data_changed: Callable = None,
    ):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.on_data_changed = on_data_changed

        self.app = Flask(__name__)
        CORS(self.app)  # Enable cross-origin requests

        self._server: Optional[make_server] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        self._setup_routes()

    def _get_db(self) -> Database:
        """Get database instance."""
        return get_database(self.db_path)

    def _setup_routes(self):
        """Setup API routes."""

        # Track data version for sync
        self._data_version = 0

        @self.app.route("/api/status", methods=["GET"])
        def status():
            """Check server status."""
            return jsonify(
                {
                    "status": "ok",
                    "server": "Gear Ledger Server",
                    "version": "1.0.0",
                }
            )

        @self.app.route("/api/sync/version", methods=["GET"])
        def get_sync_version():
            """Get current data version for sync detection."""
            return jsonify({"ok": True, "version": self._data_version})

        @self.app.route("/api/results", methods=["GET"])
        def get_results():
            """Get all results."""
            client = request.args.get("client")
            db = self._get_db()
            results = db.get_all_results(client)
            return jsonify({"ok": True, "results": results})

        @self.app.route("/api/results", methods=["POST"])
        def add_result():
            """Add or update a result."""
            print("[SERVER] POST /api/results received")
            data = request.get_json()
            print(f"[SERVER] Request data: {data}")

            if not data:
                print("[SERVER] ERROR: No data provided")
                return jsonify({"ok": False, "error": "No data provided"}), 400

            artikul = data.get("artikul")
            client = data.get("client")

            if not artikul or not client:
                print(f"[SERVER] ERROR: Missing artikul or client")
                return (
                    jsonify({"ok": False, "error": "artikul and client required"}),
                    400,
                )

            print(f"[SERVER] Adding: artikul={artikul}, client={client}")
            db = self._get_db()
            print(f"[SERVER] Database: {db.db_path}")

            result = db.add_or_update_result(
                artikul=artikul,
                client=client,
                quantity=data.get("quantity", 1),
                weight=data.get("weight", 0),
                brand=data.get("brand", ""),
                description=data.get("description", ""),
                sale_price=data.get("sale_price", 0),
            )
            print(f"[SERVER] Database result: {result}")

            # Increment data version for sync
            self._data_version += 1
            print(f"[SERVER] Data version now: {self._data_version}")

            # Notify about data change
            if self.on_data_changed:
                self.on_data_changed()

            return jsonify(result)

        @self.app.route("/api/results/<int:result_id>", methods=["GET"])
        def get_result(result_id):
            """Get a single result."""
            db = self._get_db()
            result = db.get_result_by_id(result_id)
            if result:
                return jsonify({"ok": True, "result": result})
            return jsonify({"ok": False, "error": "Not found"}), 404

        @self.app.route("/api/results/<int:result_id>", methods=["PUT"])
        def update_result(result_id):
            """Update a result."""
            data = request.get_json()
            if not data:
                return jsonify({"ok": False, "error": "No data provided"}), 400

            db = self._get_db()
            success = db.update_result(result_id, **data)

            if self.on_data_changed:
                self.on_data_changed()

            return jsonify({"ok": success})

        @self.app.route("/api/results/<int:result_id>", methods=["DELETE"])
        def delete_result(result_id):
            """Delete a result."""
            db = self._get_db()
            success = db.delete_result(result_id)

            if self.on_data_changed:
                self.on_data_changed()

            return jsonify({"ok": success})

        @self.app.route("/api/results/clear", methods=["POST"])
        def clear_results():
            """Clear all results."""
            data = request.get_json() or {}
            client = data.get("client")

            db = self._get_db()
            count = db.clear_all_results(client)

            # Increment data version for sync
            self._data_version += 1

            if self.on_data_changed:
                self.on_data_changed()

            return jsonify({"ok": True, "deleted": count})

        @self.app.route("/api/clients", methods=["GET"])
        def get_clients():
            """Get list of clients."""
            db = self._get_db()
            clients = db.get_clients()
            return jsonify({"ok": True, "clients": clients})

    def start(self) -> bool:
        """Start the server in a background thread."""
        if self._running:
            return True

        try:
            self._server = make_server(self.host, self.port, self.app, threaded=True)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True
            )
            self._thread.start()
            self._running = True
            return True
        except Exception as e:
            print(f"[ERROR] Failed to start server: {e}")
            return False

    def stop(self):
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        self._running = False

    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    def get_local_ip(self) -> str:
        """Get local IP address for display."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def get_server_url(self) -> str:
        """Get full server URL."""
        ip = self.get_local_ip()
        return f"http://{ip}:{self.port}"


# Global server instance
_server_instance: Optional[GearLedgerServer] = None


def get_server() -> Optional[GearLedgerServer]:
    """Get current server instance."""
    return _server_instance


def start_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    db_path: str = None,
    on_data_changed: Callable = None,
) -> GearLedgerServer:
    """Start the server."""
    global _server_instance

    if _server_instance and _server_instance.is_running():
        _server_instance.stop()

    _server_instance = GearLedgerServer(host, port, db_path, on_data_changed)
    _server_instance.start()
    return _server_instance


def stop_server():
    """Stop the server."""
    global _server_instance
    if _server_instance:
        _server_instance.stop()
        _server_instance = None
