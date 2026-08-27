# -*- coding: utf-8 -*-
"""
API client for connecting to Gear Ledger server.
"""
import socket
import requests
from typing import List, Dict, Any, Optional


def has_network_connection() -> bool:
    """Cheap, independent check for "is this machine on any network at
    all" — separate from whether a specific server is reachable.

    Opens a UDP socket and calls connect() toward an arbitrary external
    address. UDP is connectionless, so this sends no actual packets over
    the wire and works even without internet access (or if that address
    is unreachable) — it only fails if the OS has no network route at
    all, e.g. WiFi/Ethernet is disconnected. This is the same technique
    already used by GearLedgerServer.get_local_ip().
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        try:
            s.connect(("8.8.8.8", 80))
            return True
        finally:
            s.close()
    except OSError:
        return False


class APIClient:
    """Client for connecting to Gear Ledger server."""

    def __init__(
        self,
        server_url: str,
        timeout: int = 10,
        auth_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        """
        Initialize API client.

        Args:
            server_url: Server URL (e.g., "http://192.168.1.100:8080")
            timeout: Request timeout in seconds
            auth_token: Short-lived (30 min) access JWT to send as
                "Authorization: Bearer <token>" on every request. In-memory
                only — never persisted. Only meaningful against the cloud
                backend (server/) — a plain LAN gearledger.server.GearLedgerServer
                has no auth and just ignores the header. Optional: if
                omitted (e.g. reconnecting from a stored refresh token
                after an app restart, with no access token to hand),
                the first request 401s and _on_response's silent-refresh
                path mints one — see there.
            refresh_token: Long-lived (30 days) token, exchanged at
                {server_url}/api/auth/refresh for a new access+refresh
                pair whenever the access token dies. This is the only
                one of the two actually persisted (settings_manager's
                keyring storage) — the desktop client never writes an
                access token to disk.
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.refresh_token = refresh_token
        self._connected = False
        # Human-readable reason the last check_connection() call failed, if
        # any — check_connection() itself must never raise (callers rely on
        # a plain bool), so this is the only way to surface *why* a
        # connection attempt failed instead of just "it didn't work".
        self.last_error: Optional[str] = None
        # Friendly display name the server reports about itself (e.g.
        # "Warehouse Server") — set on successful check_connection() so the
        # UI can show who we're connected to instead of a raw IP:port,
        # regardless of whether the connection came from a saved address,
        # single-server discovery, or the picker.
        self.server_name: Optional[str] = None
        # Set only when a 401 survives a silent-refresh attempt (or there
        # was no refresh token to try) — callers (network_settings_dialog)
        # poll this to tell "the cloud session is actually dead" apart from
        # a generic connection failure, so they can clear the stored token
        # and re-prompt login instead of just showing a dead-end error. A
        # dead *access* token alone (the common case, every 30 min) never
        # sets this — it's refreshed transparently in _on_response.
        self.needs_reauth = False

        self.session = requests.Session()
        if auth_token:
            self.session.headers["Authorization"] = f"Bearer {auth_token}"
        self.session.hooks["response"].append(self._on_response)

    def _on_response(self, response, *args, **kwargs):
        if response.status_code != 401:
            return None

        # Only ever retry once per original request — this flag lives on
        # the request itself (not self), so it can't block unrelated
        # concurrent requests from also getting their one retry.
        if getattr(response.request, "_gearledger_retried", False) or not self.refresh_token:
            self.needs_reauth = True
            self.last_error = "UNAUTHORIZED"
            return None

        new_access_token = self._try_refresh()
        if new_access_token is None:
            self.needs_reauth = True
            self.last_error = "UNAUTHORIZED"
            return None

        response.request.headers["Authorization"] = f"Bearer {new_access_token}"
        response.request._gearledger_retried = True
        return self.session.send(response.request)

    def _try_refresh(self) -> Optional[str]:
        """One-shot, synchronous: POST /api/auth/refresh with the stored
        refresh token. Uses a bare requests.post (not self.session) so
        this call's own response never re-enters _on_response — a failed
        refresh should surface as "refresh failed" directly, not recurse
        through the retry logic meant for ordinary API calls. Returns the
        new access token on success (and updates self.refresh_token /
        persists it, since refresh rotates the refresh token too), or
        None on any failure."""
        try:
            response = requests.post(
                f"{self.server_url}/api/auth/refresh",
                headers={"Authorization": f"Bearer {self.refresh_token}"},
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException:
            return None
        if response.status_code != 200:
            return None
        try:
            data = response.json()
        except ValueError:
            return None

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        if not access_token or not refresh_token:
            return None

        self.session.headers["Authorization"] = f"Bearer {access_token}"
        self.refresh_token = refresh_token

        # Persist the rotated refresh token immediately, not just at
        # connect time — rotation revokes the old one server-side, so if
        # the app closed before this were saved, the next launch would
        # try a refresh token the server already knows is dead.
        from gearledger.desktop import settings_manager

        settings = settings_manager.load_settings()
        settings_manager.save_auth(
            refresh_token, settings.auth_tenant_id, settings.auth_email, self.server_url
        )

        return access_token

    def logout(self) -> None:
        """Best-effort server-side session revocation. Uses a bare
        requests.post (not self.session) since this authenticates with
        the refresh token, not the access token every other call uses —
        and deliberately swallows failures: local logout (clearing the
        stored token) should proceed either way, this is just "also tell
        the server," not something that should block logging out if the
        server happens to be unreachable."""
        if not self.refresh_token:
            return
        try:
            requests.post(
                f"{self.server_url}/api/auth/logout",
                headers={"Authorization": f"Bearer {self.refresh_token}"},
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException:
            pass

    def check_connection(self) -> bool:
        """Check if server is reachable and register as connected client."""
        try:
            # First check server status
            response = self.session.get(
                f"{self.server_url}/api/status",
                timeout=self.timeout,
            )
            if response.status_code != 200:
                self._connected = False
                self.last_error = (
                    f"Server responded with HTTP {response.status_code} "
                    f"at {self.server_url}/api/status"
                )
                print(f"[API_CLIENT] check_connection failed: {self.last_error}")
                return False

            try:
                self.server_name = (response.json() or {}).get("name") or None
            except Exception:
                self.server_name = None

            # Register as connected client by calling sync/version endpoint.
            # This also doubles as the auth check: /api/status is
            # deliberately public (auth.py's _PUBLIC_PATHS), so it alone
            # would report "connected" even with a dead/expired cloud
            # token — /api/sync/version isn't public, so a 401 here is
            # what actually catches that case.
            try:
                sync_response = self.session.get(
                    f"{self.server_url}/api/sync/version",
                    timeout=self.timeout,
                )
                if sync_response.status_code == 401:
                    self._connected = False
                    self.last_error = "UNAUTHORIZED"
                    return False
            except Exception:
                pass  # network hiccup on this secondary call — status check already succeeded

            self._connected = True
            self.last_error = None
            return True
        except requests.exceptions.ConnectTimeout:
            if not has_network_connection():
                self.last_error = "NO_NETWORK"
            else:
                self.last_error = (
                    f"Timed out connecting to {self.server_url} "
                    f"(server unreachable or wrong IP/port — check the address "
                    f"and that the server machine is on the same network)"
                )
        except requests.exceptions.ConnectionError as e:
            # A dead network (WiFi/Ethernet disconnected) surfaces here as
            # the exact same requests.exceptions.ConnectionError as "server
            # not running" or "wrong address" — check independently so the
            # user gets told the actual cause instead of a generic message
            # that points them at the wrong things to check.
            if not has_network_connection():
                self.last_error = "NO_NETWORK"
            else:
                self.last_error = (
                    f"Could not reach {self.server_url}: {e} "
                    f"(server not running, wrong IP/port, or blocked by a firewall)"
                )
        except requests.exceptions.Timeout as e:
            self.last_error = f"Request to {self.server_url} timed out: {e}"
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"

        print(f"[API_CLIENT] check_connection failed for {self.server_url}: {self.last_error}")
        self._connected = False
        return False

    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._connected

    def add_or_update_result(
        self,
        artikul: str,
        client: str,
        quantity: int = 1,
        weight: float = 0,
        brand: str = "",
        description: str = "",
        sale_price: float = 0,
    ) -> Dict[str, Any]:
        """Add or update a result on the server."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/results",
                json={
                    "artikul": artikul,
                    "client": client,
                    "quantity": quantity,
                    "weight": weight,
                    "brand": brand,
                    "description": description,
                    "sale_price": sale_price,
                },
                timeout=self.timeout,
            )
            # Check response status and content type
            if response.status_code != 200:
                return {
                    "ok": False,
                    "error": f"Server returned status {response.status_code}: {response.text[:200]}",
                }
            
            # Check if response has content
            if not response.text or not response.text.strip():
                return {
                    "ok": False,
                    "error": "Server returned empty response",
                }
            
            # Try to parse JSON
            try:
                return response.json()
            except ValueError as e:
                # Response is not valid JSON
                return {
                    "ok": False,
                    "error": f"Invalid JSON response: {str(e)}. Response: {response.text[:200]}",
                }
        except requests.exceptions.RequestException as e:
            return {"ok": False, "error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_all_results(self, client: str = None) -> List[Dict[str, Any]]:
        """Get all results from server."""
        try:
            params = {"client": client} if client else {}
            response = self.session.get(
                f"{self.server_url}/api/results",
                params=params,
                timeout=self.timeout,
            )
            data = response.json()
            if data.get("ok"):
                return data.get("results", [])
            return []
        except Exception:
            return []

    def get_result_by_id(self, result_id: int) -> Optional[Dict[str, Any]]:
        """Get a single result by ID."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/results/{result_id}",
                timeout=self.timeout,
            )
            data = response.json()
            if data.get("ok"):
                return data.get("result")
            return None
        except Exception:
            return None

    def update_result(self, result_id: int, **kwargs) -> bool:
        """Update specific fields of a result."""
        try:
            response = self.session.put(
                f"{self.server_url}/api/results/{result_id}",
                json=kwargs,
                timeout=self.timeout,
            )
            data = response.json()
            return data.get("ok", False)
        except Exception:
            return False

    def delete_result(self, result_id: int) -> bool:
        """Delete a result by ID."""
        try:
            response = self.session.delete(
                f"{self.server_url}/api/results/{result_id}",
                timeout=self.timeout,
            )
            data = response.json()
            return data.get("ok", False)
        except Exception:
            return False

    def clear_all_results(self, client: str = None) -> int:
        """Clear all results."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/results/clear",
                json={"client": client} if client else {},
                timeout=self.timeout,
            )
            data = response.json()
            return data.get("deleted", 0)
        except Exception:
            return 0

    def get_sync_version(self) -> int:
        """Get current sync version from server."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/sync/version",
                timeout=self.timeout,
            )
            data = response.json()
            if data.get("ok"):
                return data.get("version", 0)
            return -1
        except Exception:
            return -1

    def get_clients(self) -> List[str]:
        """Get list of unique clients."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/clients",
                timeout=self.timeout,
            )
            data = response.json()
            if data.get("ok"):
                return data.get("clients", [])
            return []
        except Exception:
            return []


# Global client instance
_client_instance: Optional[APIClient] = None


def get_client() -> Optional[APIClient]:
    """Get current client instance."""
    return _client_instance


_last_connect_error: Optional[str] = None


def get_last_connect_error() -> Optional[str]:
    """Return why the most recent connect_to_server() call failed, if it did."""
    return _last_connect_error


def connect_to_server(
    server_url: str,
    timeout: int = 10,
    auth_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
) -> Optional[APIClient]:
    """Connect to a server."""
    global _client_instance, _last_connect_error

    client = APIClient(server_url, timeout, auth_token=auth_token, refresh_token=refresh_token)
    if client.check_connection():
        _client_instance = client
        _last_connect_error = None
        return client
    _last_connect_error = client.last_error
    return None


def disconnect_from_server():
    """Disconnect from server."""
    global _client_instance
    _client_instance = None


def is_connected() -> bool:
    """Check if connected to a server."""
    return _client_instance is not None and _client_instance.is_connected()


# Add catalog methods to APIClient
def _add_catalog_methods():
    """Add catalog methods to APIClient class."""
    import os

    def get_catalog_info(self) -> Dict[str, Any]:
        """Get catalog metadata from server."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/catalog/info",
                timeout=self.timeout,
            )
            data = response.json()
            if data.get("ok"):
                return data
            return {"ok": False, "error": "Failed to get catalog info"}
        except Exception as e:
            return {"ok": False, "error": str(e), "exists": False}

    def download_catalog(self, local_path: str) -> Dict[str, Any]:
        """Download catalog file from server to local path."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/catalog",
                timeout=self.timeout,
                stream=True,
            )
            if response.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return {"ok": True, "path": local_path}
            else:
                data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                return {
                    "ok": False,
                    "error": data.get("error", "Failed to download catalog"),
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def upload_catalog(self, file_path: str) -> Dict[str, Any]:
        """Upload a catalog file to the server."""
        try:
            if not os.path.exists(file_path):
                return {"ok": False, "error": "File not found"}

            with open(file_path, "rb") as f:
                files = {
                    "file": (
                        os.path.basename(file_path),
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                }
                response = self.session.post(
                    f"{self.server_url}/api/catalog",
                    files=files,
                    timeout=30,
                )
            return response.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # Add methods to APIClient class
    APIClient.get_catalog_info = get_catalog_info
    APIClient.download_catalog = download_catalog
    APIClient.upload_catalog = upload_catalog


# Initialize catalog methods
_add_catalog_methods()
