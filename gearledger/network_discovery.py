# -*- coding: utf-8 -*-
"""
Network discovery for Gear Ledger servers using UDP broadcast.
"""
import socket
import json
import threading
import time
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass


DISCOVERY_PORT = 8888  # UDP port for discovery
BROADCAST_INTERVAL = 3  # Broadcast every 3 seconds
DISCOVERY_TIMEOUT = 5  # Consider server offline after 5 seconds


@dataclass
class DiscoveredServer:
    """Information about a discovered server."""

    ip: str
    port: int
    name: str
    last_seen: float

    def get_url(self) -> str:
        """Get full server URL."""
        return f"http://{self.ip}:{self.port}"

    def is_stale(self) -> bool:
        """Check if server info is stale."""
        return time.time() - self.last_seen > DISCOVERY_TIMEOUT


class ServerBroadcaster:
    """Broadcasts server presence on the network."""

    def __init__(self, port: int, server_name: str = "Gear Ledger Server"):
        self.port = port
        self.server_name = server_name
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None

    def start(self):
        """Start broadcasting server presence."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop broadcasting."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _broadcast_loop(self):
        """Broadcast loop running in background thread."""
        sockets = []
        try:
            # Get all local IPs (both LAN and WiFi)
            local_ips = self._get_all_local_ips()

            if not local_ips:
                print("[DISCOVERY] No network interfaces found")
                return

            # Create a socket for each interface and bind to it
            for ip in local_ips:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    # Bind to the specific interface
                    sock.bind((ip, 0))
                    sockets.append((sock, ip))
                    print(f"[DISCOVERY] Broadcasting on interface: {ip}")
                except Exception as e:
                    print(f"[DISCOVERY] Failed to bind to {ip}: {e}")

            if not sockets:
                print("[DISCOVERY] No sockets available for broadcasting")
                return

            # Broadcast message with all IPs
            message = {
                "type": "gearledger_server",
                "ips": local_ips,  # Send all IPs so client can try any
                "ip": local_ips[0],  # Primary IP for backward compatibility
                "port": self.port,
                "name": self.server_name,
            }
            message_json = json.dumps(message).encode("utf-8")

            # Broadcast on each interface
            # Log once on startup, then reduce verbosity
            logged_startup = False
            # Track failed sockets to remove them
            failed_sockets = {}
            last_error_log = {}  # Rate limit error messages
            error_log_interval = 30  # Log errors at most once per 30 seconds

            while self._running:
                try:
                    # Remove failed sockets that have been failing for too long
                    current_time = time.time()
                    sockets_to_remove = []
                    for (sock, ip), fail_time in failed_sockets.items():
                        if (
                            current_time - fail_time > 60
                        ):  # Remove after 60 seconds of failures
                            sockets_to_remove.append((sock, ip))

                    for sock, ip in sockets_to_remove:
                        try:
                            sock.close()
                        except Exception:
                            pass
                        sockets.remove((sock, ip))
                        failed_sockets.pop((sock, ip), None)
                        last_error_log.pop(ip, None)
                        print(f"[DISCOVERY] Removed failed interface: {ip}")

                    if not sockets:
                        print(
                            "[DISCOVERY] No working interfaces, will retry network detection"
                        )
                        time.sleep(BROADCAST_INTERVAL)
                        # Re-detect network interfaces
                        try:
                            local_ips = self._get_all_local_ips()
                            for ip in local_ips:
                                # Check if we already have a socket for this IP
                                if not any(sock_ip == ip for _, sock_ip in sockets):
                                    try:
                                        sock = socket.socket(
                                            socket.AF_INET, socket.SOCK_DGRAM
                                        )
                                        sock.setsockopt(
                                            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
                                        )
                                        sock.setsockopt(
                                            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                                        )
                                        sock.bind((ip, 0))
                                        sockets.append((sock, ip))
                                        print(f"[DISCOVERY] Added interface: {ip}")
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        continue

                    for sock, ip in sockets:
                        try:
                            # Get broadcast address for this network
                            broadcast_ip = self._get_broadcast_ip(ip)
                            broadcast_addr = (broadcast_ip, DISCOVERY_PORT)
                            sock.sendto(message_json, broadcast_addr)
                            # Only log on first broadcast to reduce spam
                            if not logged_startup:
                                print(
                                    f"[DISCOVERY] Broadcasting server presence from {ip}"
                                )
                            # Clear failure tracking on success
                            failed_sockets.pop((sock, ip), None)
                        except (OSError, socket.error) as e:
                            # Track failed socket
                            if (sock, ip) not in failed_sockets:
                                failed_sockets[(sock, ip)] = current_time

                            # Rate limit error messages (log at most once per 30 seconds per IP)
                            if (
                                ip not in last_error_log
                                or (current_time - last_error_log[ip])
                                > error_log_interval
                            ):
                                if self._running:
                                    # Only log specific errors, not all of them
                                    err_msg = str(e)
                                    if (
                                        "Can't assign requested address" not in err_msg
                                        or ip not in last_error_log
                                    ):
                                        print(
                                            f"[DISCOVERY] Broadcast error on {ip}: {e}"
                                        )
                                    last_error_log[ip] = current_time
                        except Exception as e:
                            # Track failed socket
                            if (sock, ip) not in failed_sockets:
                                failed_sockets[(sock, ip)] = current_time

                            # Rate limit error messages
                            if (
                                ip not in last_error_log
                                or (current_time - last_error_log[ip])
                                > error_log_interval
                            ):
                                if self._running:
                                    print(f"[DISCOVERY] Broadcast error on {ip}: {e}")
                                    last_error_log[ip] = current_time

                    if not logged_startup:
                        logged_startup = True
                    time.sleep(BROADCAST_INTERVAL)
                except Exception as e:
                    if self._running:
                        print(f"[DISCOVERY] Broadcast error: {e}")
                    time.sleep(BROADCAST_INTERVAL)  # Continue instead of breaking
        except Exception as e:
            print(f"[DISCOVERY] Broadcast setup error: {e}")
        finally:
            for sock, _ in sockets:
                try:
                    sock.close()
                except Exception:
                    pass

    def _get_all_local_ips(self) -> List[str]:
        """Get all local IP addresses (LAN and WiFi)."""
        ips = []
        try:
            import platform

            if platform.system() == "Windows":
                # Windows: use ipconfig equivalent
                import subprocess

                result = subprocess.run(
                    ["ipconfig"], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "IPv4" in line or "IP Address" in line:
                        parts = line.split(":")
                        if len(parts) > 1:
                            ip = parts[1].strip().split()[0]
                            if (
                                ip
                                and ip != "127.0.0.1"
                                and not ip.startswith("169.254")
                            ):
                                ips.append(ip)
            else:
                # Unix/Mac: use ifconfig or ip
                import subprocess

                try:
                    # Try 'ip' command first (Linux)
                    result = subprocess.run(
                        ["ip", "addr", "show"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    import re

                    for line in result.stdout.split("\n"):
                        match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
                        if match:
                            ip = match.group(1)
                            if ip != "127.0.0.1" and not ip.startswith("169.254"):
                                ips.append(ip)
                except Exception:
                    # Fallback to ifconfig (Mac)
                    try:
                        result = subprocess.run(
                            ["ifconfig"], capture_output=True, text=True, timeout=5
                        )
                        import re

                        for line in result.stdout.split("\n"):
                            match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
                            if match:
                                ip = match.group(1)
                                if ip != "127.0.0.1" and not ip.startswith("169.254"):
                                    ips.append(ip)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[DISCOVERY] Error getting IPs: {e}")

        # Fallback: try connecting method
        if not ips:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                if ip and ip != "127.0.0.1":
                    ips.append(ip)
            except Exception:
                pass

        # Remove duplicates and sort
        unique_ips = list(set(ips))
        unique_ips.sort()
        return unique_ips if unique_ips else ["127.0.0.1"]

    def _get_broadcast_ip(self, ip: str) -> str:
        """Get broadcast IP for a given network IP."""
        try:
            parts = ip.split(".")
            if len(parts) == 4:
                # For most home networks, broadcast is .255
                return f"{parts[0]}.{parts[1]}.{parts[2]}.255"
        except Exception:
            pass
        # Fallback to global broadcast
        return "255.255.255.255"


class ServerDiscovery:
    """Discovers Gear Ledger servers on the network."""

    def __init__(
        self, on_server_found: Optional[Callable[[DiscoveredServer], None]] = None
    ):
        self.on_server_found = on_server_found
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None
        self._discovered_servers: Dict[str, DiscoveredServer] = {}
        self._lock = threading.Lock()

    def start(self):
        """Start listening for server broadcasts."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listening."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def get_discovered_servers(self) -> List[DiscoveredServer]:
        """Get list of currently discovered servers (non-stale)."""
        with self._lock:
            # Remove stale servers
            stale_keys = [
                key
                for key, server in self._discovered_servers.items()
                if server.is_stale()
            ]
            for key in stale_keys:
                del self._discovered_servers[key]

            # Return list of active servers
            return list(self._discovered_servers.values())

    def _listen_loop(self):
        """Listen loop running in background thread."""
        try:
            # Create UDP socket for listening (bind to all interfaces)
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.bind(("0.0.0.0", DISCOVERY_PORT))
            self._socket.settimeout(1.0)  # Timeout for checking _running flag

            print(f"[DISCOVERY] Listening on port {DISCOVERY_PORT}")

            while self._running:
                try:
                    data, addr = self._socket.recvfrom(1024)
                    print(f"[DISCOVERY] Received broadcast from {addr[0]}:{addr[1]}")
                    try:
                        message = json.loads(data.decode("utf-8"))
                        if message.get("type") == "gearledger_server":
                            # Get all IPs from message (supports both old and new format)
                            ips = message.get("ips", [])
                            if not ips:
                                # Fallback to single IP for backward compatibility
                                single_ip = message.get("ip", addr[0])
                                ips = [single_ip]

                            print(
                                f"[DISCOVERY] Server IPs: {ips}, Port: {message.get('port', 8080)}"
                            )

                            # Create server entry for each IP
                            for ip in ips:
                                server = DiscoveredServer(
                                    ip=ip,
                                    port=message.get("port", 8080),
                                    name=message.get("name", "Gear Ledger Server"),
                                    last_seen=time.time(),
                                )

                                # Update discovered servers
                                server_key = f"{server.ip}:{server.port}"
                                with self._lock:
                                    old_server = self._discovered_servers.get(
                                        server_key
                                    )
                                    self._discovered_servers[server_key] = server

                                    # Notify callback if server is new or updated
                                    if self.on_server_found and (
                                        not old_server or old_server.is_stale()
                                    ):
                                        print(
                                            f"[DISCOVERY] New server discovered: {server.ip}:{server.port}"
                                        )
                                        self.on_server_found(server)
                    except (json.JSONDecodeError, KeyError) as e:
                        # Ignore invalid messages
                        print(f"[DISCOVERY] Invalid message from {addr}: {e}")
                        pass
                except socket.timeout:
                    # Timeout is expected, continue listening
                    continue
                except Exception as e:
                    if self._running:
                        print(f"[DISCOVERY] Listen error: {e}")
                    break
        except Exception as e:
            print(f"[DISCOVERY] Discovery setup error: {e}")
        finally:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
