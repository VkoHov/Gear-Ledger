# -*- coding: utf-8 -*-
"""
REST API server for multi-device access to Gear Ledger.
"""
import threading
import socket
import time
import os
from pathlib import Path
from typing import Optional, Callable
from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS
from werkzeug.serving import make_server
import queue
import json

from .database import get_database, Database
from .network_discovery import ServerBroadcaster
from .desktop.settings_manager import APP_DIR


class GearLedgerServer:
    """REST API server for Gear Ledger."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        db_path: str = None,
        on_data_changed: Callable = None,
        on_client_changed: Callable = None,
    ):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.on_data_changed = on_data_changed
        # Support multiple client change callbacks
        self._client_changed_callbacks = []
        if on_client_changed:
            self._client_changed_callbacks.append(on_client_changed)

        self.app = Flask(__name__)
        CORS(self.app)  # Enable cross-origin requests

        self._server: Optional[make_server] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # Track connected clients: {client_ip: last_seen_timestamp}
        self._connected_clients = {}
        self._last_client_count = 0
        self._client_timeout = (
            10  # Consider client disconnected after 10 seconds of inactivity
        )
        # Timer to periodically check for stale clients and notify
        self._stale_check_timer = None

        # Network discovery broadcaster
        self._broadcaster: Optional[ServerBroadcaster] = None

        # In-memory catalog storage (no permanent file storage)
        self._catalog_data: Optional[bytes] = None
        self._catalog_filename: Optional[str] = None
        self._catalog_upload_time: Optional[float] = None

        # SSE event system: track connected clients for event streaming
        self._sse_clients: list = []  # List of client queues for SSE events
        self._sse_lock = threading.Lock()  # Lock for thread-safe access to _sse_clients

        self._setup_routes()

    def _get_db(self) -> Database:
        """Get database instance."""
        return get_database(self.db_path)

    def _cleanup_stale_clients(self):
        """Remove clients that haven't been seen recently."""
        current_time = time.time()
        stale_clients = [
            ip
            for ip, last_seen in self._connected_clients.items()
            if current_time - last_seen > self._client_timeout
        ]
        old_count = len(self._connected_clients)
        if stale_clients:
            print(
                f"[SERVER] Cleaning up {len(stale_clients)} stale client(s): {stale_clients}"
            )
        for ip in stale_clients:
            del self._connected_clients[ip]

        # Notify if client count changed
        new_count = len(self._connected_clients)
        if old_count != new_count:
            print(
                f"[SERVER] Client count changed from {old_count} to {new_count} (cleanup)"
            )
            self._notify_client_changed(new_count)

    def get_connected_clients_count(self) -> int:
        """Get count of currently connected clients."""
        self._cleanup_stale_clients()
        count = len(self._connected_clients)

        # Notify if client count changed
        if count != self._last_client_count:
            self._notify_client_changed(count)
        self._last_client_count = count

        return count

    def get_sse_clients_count(self) -> int:
        """Get count of currently connected SSE clients."""
        with self._sse_lock:
            return len(self._sse_clients)

    def _notify_client_changed(self, count: int):
        """Notify all registered callbacks about client count change."""
        # Only log if there are callbacks to avoid spam
        if self._client_changed_callbacks:
            print(
                f"[SERVER] Client count changed to {count}, notifying {len(self._client_changed_callbacks)} callback(s)"
            )
        for callback in self._client_changed_callbacks:
            try:
                callback(count)
            except Exception as e:
                print(f"[SERVER] Error in client_changed callback: {e}")

    def add_client_changed_callback(self, callback: Callable):
        """Add a callback to be notified when client count changes."""
        if callback and callback not in self._client_changed_callbacks:
            self._client_changed_callbacks.append(callback)
            print(
                f"[SERVER] Added client_changed callback (total: {len(self._client_changed_callbacks)})"
            )
        else:
            print(
                f"[SERVER] Callback already registered or invalid (total: {len(self._client_changed_callbacks)})"
            )

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
            # Track client connection
            client_ip = request.remote_addr
            was_new_client = client_ip not in self._connected_clients
            self._connected_clients[client_ip] = time.time()
            # Clean up stale clients
            self._cleanup_stale_clients()

            current_count = len(self._connected_clients)
            print(
                f"[SERVER] /api/sync/version - Client {client_ip}, was_new={was_new_client}, total_clients={current_count}, callbacks={len(self._client_changed_callbacks)}"
            )

            # Notify if new client connected
            if was_new_client:
                print(f"[SERVER] New client connected! Total: {current_count}")
                self._notify_client_changed(current_count)

            return jsonify({"ok": True, "version": self._data_version})

        @self.app.route("/api/events", methods=["GET"])
        def stream_events():
            """Server-Sent Events endpoint for real-time notifications."""

            def event_stream():
                # Create a queue for this client
                client_queue = queue.Queue()

                # Add client to list
                with self._sse_lock:
                    self._sse_clients.append(client_queue)
                    print(
                        f"[SERVER] SSE client connected. Total clients: {len(self._sse_clients)}"
                    )

                try:
                    # Send initial connection event
                    yield f"data: {json.dumps({'type': 'connected', 'version': self._data_version})}\n\n"

                    # Keep connection alive and send events
                    while True:
                        try:
                            # Wait for event with timeout to keep connection alive
                            event = client_queue.get(timeout=30)
                            yield f"data: {json.dumps(event)}\n\n"
                        except queue.Empty:
                            # Send keepalive ping
                            yield ": keepalive\n\n"
                except GeneratorExit:
                    # Client disconnected
                    pass
                finally:
                    # Remove client from list
                    with self._sse_lock:
                        if client_queue in self._sse_clients:
                            self._sse_clients.remove(client_queue)
                            print(
                                f"[SERVER] SSE client disconnected. Total clients: {len(self._sse_clients)}"
                            )

            return Response(
                event_stream(),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.app.route("/api/clients/count", methods=["GET"])
        def get_connected_clients_count():
            """Get count of currently connected clients."""
            self._cleanup_stale_clients()
            count = len(self._connected_clients)
            return jsonify({"ok": True, "count": count})

        @self.app.route("/api/results", methods=["GET"])
        def get_results():
            """Get all results."""
            # Track client connection
            client_ip = request.remote_addr
            was_new_client = client_ip not in self._connected_clients
            self._connected_clients[client_ip] = time.time()

            # Notify if new client connected
            if was_new_client:
                self._notify_client_changed(len(self._connected_clients))

            client = request.args.get("client")
            db = self._get_db()
            results = db.get_all_results(client)
            return jsonify({"ok": True, "results": results})

        @self.app.route("/api/results", methods=["POST"])
        def add_result():
            """Add or update a result."""
            # Track client connection
            client_ip = request.remote_addr
            was_new_client = client_ip not in self._connected_clients
            self._connected_clients[client_ip] = time.time()

            # Notify if new client connected
            if was_new_client:
                self._notify_client_changed(len(self._connected_clients))
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

            # Look up catalog data to enrich the result
            # Use in-memory uploaded catalog if available, otherwise try file from settings
            from gearledger.result_ledger import _lookup_catalog_data
            from gearledger.data_layer import _to_python_type

            catalog_data = {}
            catalog_bytes = self.get_uploaded_catalog_data()

            if catalog_bytes:
                print(
                    f"[SERVER] Using in-memory catalog (size: {len(catalog_bytes)} bytes)"
                )
                data = _lookup_catalog_data(artikul, catalog_bytes=catalog_bytes)
                if data:
                    # Convert numpy types to native Python types
                    catalog_data = {k: _to_python_type(v) for k, v in data.items()}
                    print(f"[SERVER] Found catalog data: {catalog_data}")
                else:
                    print(f"[SERVER] No catalog entry found for artikul: {artikul}")
            else:
                # Try to get catalog path from settings as fallback
                from gearledger.desktop.settings_widget import get_settings_widget

                settings_widget = get_settings_widget()
                if settings_widget:
                    catalog_path = settings_widget.get_catalog_path()
                    if catalog_path and os.path.exists(catalog_path):
                        print(f"[SERVER] Using catalog file: {catalog_path}")
                        data = _lookup_catalog_data(artikul, catalog_path=catalog_path)
                        if data:
                            catalog_data = {
                                k: _to_python_type(v) for k, v in data.items()
                            }
                            print(f"[SERVER] Found catalog data: {catalog_data}")
                        else:
                            print(
                                f"[SERVER] No catalog entry found for artikul: {artikul}"
                            )
                    else:
                        print("[SERVER] No catalog file available")
                else:
                    print(
                        "[SERVER] No settings widget available, cannot get catalog path"
                    )

            print(f"[SERVER] Catalog lookup result: {catalog_data}")

            # Use catalog data to populate fields (prefer catalog data over client-provided data)
            brand = (
                catalog_data.get("бренд", "") if catalog_data else data.get("brand", "")
            )
            description = (
                catalog_data.get("описание", "")
                if catalog_data
                else data.get("description", "")
            )
            sale_price = (
                catalog_data.get("цена", 0)
                if catalog_data
                else data.get("sale_price", 0)
            )

            # If catalog provided data, log it
            if catalog_data:
                print(f"[SERVER] Using catalog data: brand={brand}, price={sale_price}")
            else:
                print("[SERVER] No catalog data found, using client-provided data")

            result = db.add_or_update_result(
                artikul=artikul,
                client=client,
                quantity=data.get("quantity", 1),
                weight=data.get("weight", 0),
                brand=brand,
                description=description,
                sale_price=sale_price,
            )
            print(f"[SERVER] Database result: {result}")

            # Increment data version for sync
            self._data_version += 1
            print(f"[SERVER] Data version now: {self._data_version}")

            # Send SSE event to all connected clients
            self._broadcast_sse_event(
                {
                    "type": "results_changed",
                    "version": self._data_version,
                }
            )

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

            # Send SSE event to all connected clients
            self._broadcast_sse_event(
                {
                    "type": "results_changed",
                    "version": self._data_version,
                }
            )

            if self.on_data_changed:
                self.on_data_changed()

            return jsonify({"ok": True, "deleted": count})

        @self.app.route("/api/clients", methods=["GET"])
        def get_clients():
            """Get list of clients."""
            db = self._get_db()
            clients = db.get_clients()
            return jsonify({"ok": True, "clients": clients})

        @self.app.route("/api/catalog/info", methods=["GET"])
        def get_catalog_info():
            """Get catalog metadata (filename, size, date)."""
            if self._catalog_data is not None:
                return jsonify(
                    {
                        "ok": True,
                        "filename": self._catalog_filename,
                        "size": len(self._catalog_data),
                        "modified": self._catalog_upload_time or time.time(),
                        "exists": True,
                    }
                )
            return jsonify({"ok": True, "exists": False})

        @self.app.route("/api/catalog", methods=["GET"])
        def get_catalog():
            """Download the catalog file from memory."""
            if self._catalog_data is None:
                return jsonify({"ok": False, "error": "Catalog not found"}), 404

            from io import BytesIO

            # Create a BytesIO object from the in-memory catalog data
            catalog_file = BytesIO(self._catalog_data)
            catalog_file.seek(0)

            return send_file(
                catalog_file,
                as_attachment=True,
                download_name=self._catalog_filename or "catalog.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        @self.app.route("/api/catalog", methods=["POST"])
        def upload_catalog():
            """Upload a catalog file to the server (stored in memory, not on disk)."""
            if "file" not in request.files:
                return jsonify({"ok": False, "error": "No file provided"}), 400

            file = request.files["file"]
            if file.filename == "":
                return jsonify({"ok": False, "error": "No file selected"}), 400

            try:
                # Read file into memory
                catalog_bytes = file.read()
                filename = file.filename or "catalog.xlsx"

                # Store in memory only (no disk storage)
                self._catalog_data = catalog_bytes
                self._catalog_filename = filename
                self._catalog_upload_time = time.time()

                print(
                    f"[SERVER] Catalog uploaded to memory: {filename} ({len(catalog_bytes)} bytes)"
                )

                # Increment data version to notify clients
                self._data_version += 1
                print(
                    f"[SERVER] Catalog uploaded, data version now: {self._data_version}"
                )

                # Send SSE event to all connected clients
                self._broadcast_sse_event(
                    {
                        "type": "catalog_uploaded",
                        "filename": filename,
                        "size": len(catalog_bytes),
                        "version": self._data_version,
                    }
                )

                # Notify about data change (catalog uploaded)
                if self.on_data_changed:
                    self.on_data_changed()

                return jsonify(
                    {
                        "ok": True,
                        "filename": filename,
                        "size": len(catalog_bytes),
                        "version": self._data_version,
                    }
                )
            except Exception as e:
                print(f"[SERVER] Error uploading catalog: {e}")
                return jsonify({"ok": False, "error": str(e)}), 500

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

            # Start broadcasting server presence
            self._broadcaster = ServerBroadcaster(self.port)
            self._broadcaster.start()

            # Start periodic stale client check
            self._start_stale_client_check()

            return True
        except Exception as e:
            print(f"[ERROR] Failed to start server: {e}")
            return False

    def get_uploaded_catalog_data(self) -> Optional[bytes]:
        """
        Get in-memory catalog data (bytes) for server-side use.

        Returns the catalog file as bytes, or None if no catalog is uploaded.
        """
        return self._catalog_data

    def _get_catalog_path(self) -> Optional[str]:
        """
        Get path to stored catalog file (deprecated).

        Catalogs are now stored in memory only. Returns None.
        """
        return None

    def _start_stale_client_check(self):
        """Start periodic check for stale clients."""

        def check_stale():
            if self._running:
                self._cleanup_stale_clients()
                # Restart timer to continue checking
                if self._running:
                    self._stale_check_timer = threading.Timer(2.0, check_stale)
                    self._stale_check_timer.daemon = True
                    self._stale_check_timer.start()

        if self._running:
            self._stale_check_timer = threading.Timer(2.0, check_stale)
            self._stale_check_timer.daemon = True
            self._stale_check_timer.start()

    def _broadcast_sse_event(self, event: dict):
        """Broadcast SSE event to all connected clients."""
        with self._sse_lock:
            # Send event to all connected clients
            for client_queue in self._sse_clients[
                :
            ]:  # Copy list to avoid modification during iteration
                try:
                    client_queue.put_nowait(event)
                except queue.Full:
                    # Queue is full, remove client (likely disconnected)
                    if client_queue in self._sse_clients:
                        self._sse_clients.remove(client_queue)
                except Exception as e:
                    # Error sending to client, remove it
                    print(f"[SERVER] Error sending SSE event to client: {e}")
                    if client_queue in self._sse_clients:
                        self._sse_clients.remove(client_queue)

    def stop(self):
        """Stop the server."""
        # Stop broadcasting
        if self._broadcaster:
            self._broadcaster.stop()
            self._broadcaster = None

        # Stop stale client check timer
        if self._stale_check_timer:
            self._stale_check_timer.cancel()
            self._stale_check_timer = None

        # Clear SSE clients
        with self._sse_lock:
            self._sse_clients.clear()

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
    on_client_changed: Callable = None,
) -> GearLedgerServer:
    """Start the server."""
    global _server_instance

    if _server_instance and _server_instance.is_running():
        _server_instance.stop()

    _server_instance = GearLedgerServer(
        host, port, db_path, on_data_changed, on_client_changed
    )
    _server_instance.start()
    return _server_instance


def stop_server():
    """Stop the server."""
    global _server_instance
    if _server_instance:
        _server_instance.stop()
        _server_instance = None
