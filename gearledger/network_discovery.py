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
            self._thread.join(timeout=1)
            self._thread = None
    
    def _broadcast_loop(self):
        """Broadcast loop running in background thread."""
        try:
            # Create UDP socket for broadcasting
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Get local IP
            local_ip = self._get_local_ip()
            
            # Broadcast message
            message = {
                "type": "gearledger_server",
                "ip": local_ip,
                "port": self.port,
                "name": self.server_name,
            }
            message_json = json.dumps(message).encode('utf-8')
            
            # Broadcast address
            broadcast_addr = ("255.255.255.255", DISCOVERY_PORT)
            
            while self._running:
                try:
                    self._socket.sendto(message_json, broadcast_addr)
                    time.sleep(BROADCAST_INTERVAL)
                except Exception as e:
                    if self._running:
                        print(f"[DISCOVERY] Broadcast error: {e}")
                    break
        except Exception as e:
            print(f"[DISCOVERY] Broadcast setup error: {e}")
        finally:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
    
    def _get_local_ip(self) -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


class ServerDiscovery:
    """Discovers Gear Ledger servers on the network."""
    
    def __init__(self, on_server_found: Optional[Callable[[DiscoveredServer], None]] = None):
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
                key for key, server in self._discovered_servers.items()
                if server.is_stale()
            ]
            for key in stale_keys:
                del self._discovered_servers[key]
            
            # Return list of active servers
            return list(self._discovered_servers.values())
    
    def _listen_loop(self):
        """Listen loop running in background thread."""
        try:
            # Create UDP socket for listening
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("", DISCOVERY_PORT))
            self._socket.settimeout(1.0)  # Timeout for checking _running flag
            
            while self._running:
                try:
                    data, addr = self._socket.recvfrom(1024)
                    try:
                        message = json.loads(data.decode('utf-8'))
                        if message.get("type") == "gearledger_server":
                            server = DiscoveredServer(
                                ip=message.get("ip", addr[0]),
                                port=message.get("port", 8080),
                                name=message.get("name", "Gear Ledger Server"),
                                last_seen=time.time()
                            )
                            
                            # Update discovered servers
                            server_key = f"{server.ip}:{server.port}"
                            with self._lock:
                                old_server = self._discovered_servers.get(server_key)
                                self._discovered_servers[server_key] = server
                            
                            # Notify callback if server is new or updated
                            if self.on_server_found and (not old_server or old_server.is_stale()):
                                self.on_server_found(server)
                    except (json.JSONDecodeError, KeyError) as e:
                        # Ignore invalid messages
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
