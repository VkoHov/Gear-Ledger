# -*- coding: utf-8 -*-
"""
API client for connecting to Gear Ledger server.
"""
import requests
from typing import List, Dict, Any, Optional


class APIClient:
    """Client for connecting to Gear Ledger server."""

    def __init__(self, server_url: str, timeout: int = 10):
        """
        Initialize API client.

        Args:
            server_url: Server URL (e.g., "http://192.168.1.100:8080")
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._connected = False

    def check_connection(self) -> bool:
        """Check if server is reachable and register as connected client."""
        try:
            # First check server status
            response = requests.get(
                f"{self.server_url}/api/status",
                timeout=self.timeout,
            )
            if response.status_code != 200:
                self._connected = False
                return False

            # Register as connected client by calling sync/version endpoint
            # This allows server to track connected clients
            try:
                requests.get(
                    f"{self.server_url}/api/sync/version",
                    timeout=self.timeout,
                )
            except Exception:
                pass  # Ignore errors, but still mark as connected if status worked

            self._connected = True
            return True
        except Exception:
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
            response = requests.post(
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
            return response.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_all_results(self, client: str = None) -> List[Dict[str, Any]]:
        """Get all results from server."""
        try:
            params = {"client": client} if client else {}
            response = requests.get(
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
            response = requests.get(
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
            response = requests.put(
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
            response = requests.delete(
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
            response = requests.post(
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
            response = requests.get(
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
            response = requests.get(
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


def connect_to_server(server_url: str, timeout: int = 10) -> Optional[APIClient]:
    """Connect to a server."""
    global _client_instance

    client = APIClient(server_url, timeout)
    if client.check_connection():
        _client_instance = client
        return client
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
            response = requests.get(
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
            response = requests.get(
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
                response = requests.post(
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
