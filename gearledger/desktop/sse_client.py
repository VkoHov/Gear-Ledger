# -*- coding: utf-8 -*-
"""
Server-Sent Events (SSE) client for receiving real-time notifications from server.
"""
import requests
import json
from typing import Optional, Callable
from PyQt6.QtCore import QThread, pyqtSignal


class SSEClientThread(QThread):
    """Thread-based SSE client that receives events from server without blocking UI."""

    # Signals emitted when events are received
    event_received = pyqtSignal(dict)  # Emitted when any event is received
    catalog_uploaded = pyqtSignal(dict)  # Emitted when catalog is uploaded
    results_changed = pyqtSignal(dict)  # Emitted when results change
    connected = pyqtSignal()  # Emitted when connection is established
    disconnected = pyqtSignal()  # Emitted when connection is lost
    error_occurred = pyqtSignal(str)  # Emitted when an error occurs

    def __init__(self, server_url: str, timeout: int = 60):
        """
        Initialize SSE client.

        Args:
            server_url: Server URL (e.g., "http://192.168.1.100:8080")
            timeout: Request timeout in seconds (default 60, must be longer than server keepalive interval of 30s)
        """
        super().__init__()
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._running = False
        self._should_stop = False

    def run(self):
        """Run the SSE client in background thread."""
        self._running = True
        self._should_stop = False

        while not self._should_stop:
            try:
                # Connect to SSE endpoint
                url = f"{self.server_url}/api/events"
                print(f"[SSE_CLIENT] Connecting to {url}")

                response = requests.get(
                    url,
                    stream=True,
                    timeout=self.timeout,
                    headers={
                        "Accept": "text/event-stream",
                        "Cache-Control": "no-cache",
                    },
                )

                if response.status_code != 200:
                    print(f"[SSE_CLIENT] Connection failed: {response.status_code}")
                    self.error_occurred.emit(
                        f"Connection failed: {response.status_code}"
                    )
                    # Wait before retrying
                    if not self._should_stop:
                        self.msleep(5000)  # Wait 5 seconds before retry
                    continue

                print("[SSE_CLIENT] Connected to SSE stream")
                self.connected.emit()

                # Read events from stream
                buffer = ""
                for line in response.iter_lines(decode_unicode=True):
                    if self._should_stop:
                        break

                    if not line:
                        # Empty line indicates end of event
                        if buffer.strip():
                            self._process_event(buffer.strip())
                            buffer = ""
                        continue

                    buffer += line + "\n"

                # Connection closed
                print("[SSE_CLIENT] Connection closed")
                self.disconnected.emit()

            except requests.exceptions.Timeout:
                if not self._should_stop:
                    print("[SSE_CLIENT] Connection timeout, will retry")
                    # Don't emit error for timeout - disconnected signal will handle it
                    self.msleep(5000)  # Wait 5 seconds before retry
            except requests.exceptions.ConnectionError as e:
                if not self._should_stop:
                    print(f"[SSE_CLIENT] Connection error: {e}, will retry")
                    # Don't emit error for connection errors - disconnected signal will handle it
                    self.msleep(5000)  # Wait 5 seconds before retry
            except Exception as e:
                if not self._should_stop:
                    print(f"[SSE_CLIENT] Error: {e}, will retry")
                    # Only emit error for unexpected errors
                    if "Read timed out" not in str(e) and "Connection" not in str(e):
                        self.error_occurred.emit(f"Unexpected error: {e}")
                    self.msleep(5000)  # Wait 5 seconds before retry

        self._running = False
        print("[SSE_CLIENT] SSE client stopped")

    def _process_event(self, event_data: str):
        """Process a received SSE event."""
        try:
            # Parse SSE format: "data: {...}"
            if event_data.startswith("data: "):
                json_str = event_data[6:]  # Remove "data: " prefix
                event = json.loads(json_str)

                # Emit general event signal
                self.event_received.emit(event)

                # Emit specific signals based on event type
                event_type = event.get("type")
                if event_type == "catalog_uploaded":
                    self.catalog_uploaded.emit(event)
                elif event_type == "results_changed":
                    self.results_changed.emit(event)
                elif event_type == "connected":
                    # Initial connection event - may include catalog info
                    if "catalog" in event:
                        # Server has a catalog, emit as catalog_uploaded event
                        # so the UI can update to show the catalog filename
                        catalog_event = {
                            "type": "catalog_uploaded",
                            "filename": event["catalog"].get("filename", "catalog"),
                            "size": event["catalog"].get("size", 0),
                            "version": event["catalog"].get(
                                "version", event.get("version", 0)
                            ),
                        }
                        self.catalog_uploaded.emit(catalog_event)
                else:
                    print(f"[SSE_CLIENT] Unknown event type: {event_type}")
        except json.JSONDecodeError as e:
            print(f"[SSE_CLIENT] Failed to parse event JSON: {e}, data: {event_data}")
        except Exception as e:
            print(f"[SSE_CLIENT] Error processing event: {e}")

    def stop(self):
        """Stop the SSE client."""
        self._should_stop = True
        self.wait(2000)  # Wait up to 2 seconds for thread to stop

    def is_connected(self) -> bool:
        """Check if SSE client is running and connected."""
        return self._running and not self._should_stop
