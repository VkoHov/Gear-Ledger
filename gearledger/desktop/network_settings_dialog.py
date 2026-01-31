# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QComboBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QRadioButton,
    QButtonGroup,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from .settings_manager import (
    Settings,
    save_settings,
    load_settings,
)
from .translations import tr


class NetworkSettingsDialog(QDialog):
    """Dialog for network/server settings."""

    # Signal emitted when network mode changes
    network_mode_changed = pyqtSignal(str, str)  # mode, address
    # Signal emitted when server receives data (to refresh UI)
    server_data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("network_configuration"))
        self.resize(600, 500)
        self.settings = load_settings()
        self._server = None
        self._client = None
        self._discovery = None

        # Initialize timers before setup (needed by _stop_discovery)
        # Timer for one-time discovery timeout (no continuous polling)
        self._discovery_timer = QTimer(self)
        self._discovery_timer.setSingleShot(True)  # One-time timer
        self._discovery_timer.timeout.connect(self._on_discovery_timeout)

        self._setup_ui()
        self._load_settings_to_ui()

    def _setup_ui(self):
        """Set up the network settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Network Configuration
        network_group = QGroupBox(tr("network_configuration"))
        network_layout = QVBoxLayout(network_group)

        # Mode selection
        mode_label = QLabel(tr("network_mode_label"))
        network_layout.addWidget(mode_label)

        self.mode_button_group = QButtonGroup(self)
        mode_row = QHBoxLayout()

        self.standalone_radio = QRadioButton(tr("standalone_mode"))
        self.standalone_radio.setToolTip(tr("standalone_tooltip"))
        self.server_radio = QRadioButton(tr("server_mode"))
        self.server_radio.setToolTip(tr("server_tooltip"))
        self.client_radio = QRadioButton(tr("client_mode"))
        self.client_radio.setToolTip(tr("client_tooltip"))

        self.mode_button_group.addButton(self.standalone_radio, 0)
        self.mode_button_group.addButton(self.server_radio, 1)
        self.mode_button_group.addButton(self.client_radio, 2)

        mode_row.addWidget(self.standalone_radio)
        mode_row.addWidget(self.server_radio)
        mode_row.addWidget(self.client_radio)
        mode_row.addStretch(1)
        network_layout.addLayout(mode_row)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        network_layout.addWidget(separator)

        # Server settings
        server_row = QHBoxLayout()
        self.server_port_label = QLabel(tr("server_port_label"))
        server_row.addWidget(self.server_port_label)
        self.server_port_spin = QSpinBox()
        self.server_port_spin.setRange(1024, 65535)
        self.server_port_spin.setValue(8080)
        server_row.addWidget(self.server_port_spin)

        self.start_server_btn = QPushButton(tr("start_server"))
        self.start_server_btn.setStyleSheet(
            "background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.start_server_btn.clicked.connect(self._toggle_server)
        server_row.addWidget(self.start_server_btn)

        server_row.addStretch(1)
        network_layout.addLayout(server_row)

        # Server status
        self.server_status_label = QLabel(tr("server_status_stopped"))
        self.server_status_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        network_layout.addWidget(self.server_status_label)

        # Client settings
        client_row = QHBoxLayout()
        self.server_address_label = QLabel(tr("server_address_label"))
        client_row.addWidget(self.server_address_label)

        # Server discovery combo box (editable to allow manual entry)
        self.server_address_combo = QComboBox()
        self.server_address_combo.setEditable(True)
        self.server_address_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.server_address_combo.lineEdit().setPlaceholderText("192.168.1.100:8080")
        self.server_address_combo.lineEdit().setText("")
        client_row.addWidget(self.server_address_combo, 1)

        # Refresh discovery button (manual discovery - click to start/stop)
        self.refresh_discovery_btn = QPushButton("🔍")
        self.refresh_discovery_btn.setToolTip(tr("refresh_server_discovery"))
        self.refresh_discovery_btn.setStyleSheet(
            "background-color: #95a5a6; color: white; font-weight: bold; padding: 6px 10px;"
        )
        self.refresh_discovery_btn.clicked.connect(self._refresh_discovery)
        client_row.addWidget(self.refresh_discovery_btn)

        self.connect_btn = QPushButton(tr("connect"))
        self.connect_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.connect_btn.clicked.connect(self._toggle_connection)
        client_row.addWidget(self.connect_btn)
        network_layout.addLayout(client_row)

        # Discovery status
        self.discovery_status_label = QLabel(tr("discovering_servers"))
        self.discovery_status_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        network_layout.addWidget(self.discovery_status_label)

        # Connection status
        self.connection_status_label = QLabel(tr("connection_status_disconnected"))
        self.connection_status_label.setStyleSheet(
            "color: #7f8c8d; font-style: italic;"
        )
        network_layout.addWidget(self.connection_status_label)

        # Connect mode radio buttons to update UI
        self.standalone_radio.toggled.connect(self._update_network_ui)
        self.server_radio.toggled.connect(self._update_network_ui)
        self.client_radio.toggled.connect(self._update_network_ui)

        layout.addWidget(network_group)

        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)

        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(
            "background-color: #95a5a6; color: white; font-weight: bold; padding: 8px 16px;"
        )
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_btn)

        layout.addLayout(buttons_layout)

    def _load_settings_to_ui(self):
        """Load current settings into UI fields."""
        s = self.settings

        # Network settings
        self.server_port_spin.setValue(s.server_port)
        if s.server_address:
            self.server_address_combo.lineEdit().setText(s.server_address)

        # Set network mode radio
        if s.network_mode == "server":
            self.server_radio.setChecked(True)
        elif s.network_mode == "client":
            self.client_radio.setChecked(True)
        else:
            self.standalone_radio.setChecked(True)

        self._update_network_ui()

    def _update_network_ui(self):
        """Update network UI based on selected mode."""
        is_server = self.server_radio.isChecked()
        is_client = self.client_radio.isChecked()
        is_standalone = self.standalone_radio.isChecked()

        # Show/hide server controls based on mode
        self.server_port_label.setVisible(is_server)
        self.server_port_spin.setVisible(is_server)
        self.start_server_btn.setVisible(is_server)
        self.server_status_label.setVisible(is_server)

        # Show/hide client controls based on mode
        self.server_address_label.setVisible(is_client)
        self.server_address_combo.setVisible(is_client)
        self.refresh_discovery_btn.setVisible(is_client)
        self.connect_btn.setVisible(is_client)
        self.connection_status_label.setVisible(is_client)
        self.discovery_status_label.setVisible(is_client)

        # Enable/disable based on mode
        self.server_port_spin.setEnabled(is_server)
        self.start_server_btn.setEnabled(is_server)

        self.server_address_combo.setEnabled(is_client)
        self.refresh_discovery_btn.setEnabled(is_client)
        self.connect_btn.setEnabled(is_client)

        # Stop discovery when switching away from client mode
        # In client mode, discovery is manual (user clicks refresh button)
        if not is_client:
            self._stop_discovery()

        # Update button states based on current connection status
        from gearledger.server import get_server

        server = get_server()
        if is_server and server and server.is_running():
            self.start_server_btn.setText(tr("stop_server"))
            self.start_server_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
            )
            # Update server status immediately (client count will update on connect/disconnect events)
            self._update_server_status()
        else:
            self.start_server_btn.setText(tr("start_server"))
            self.start_server_btn.setStyleSheet(
                "background-color: #27ae60; color: white; font-weight: bold; padding: 6px 12px;"
            )
            if is_standalone or not is_server:
                self.server_status_label.setText(tr("server_status_stopped"))
                self.server_status_label.setStyleSheet(
                    "color: #7f8c8d; font-style: italic;"
                )

        if is_client and self._client and self._client.is_connected():
            self.connect_btn.setText(tr("disconnect"))
            self.connect_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
            )
        else:
            self.connect_btn.setText(tr("connect"))
            self.connect_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
            )

    def _toggle_server(self):
        """Start or stop the server."""
        from gearledger.server import start_server, stop_server, get_server
        from gearledger.data_layer import set_runtime_mode

        self._server = get_server()

        if self._server and self._server.is_running():
            # Stop server
            stop_server()
            self._server = None
            set_runtime_mode("standalone")  # Reset runtime mode
            # Update UI to hide server controls
            self._update_network_ui()
            self.network_mode_changed.emit("standalone", "")
            QMessageBox.information(self, tr("server"), tr("server_stopped_msg"))
        else:
            # Start server
            port = self.server_port_spin.value()
            try:
                # Pass callback to refresh UI when data changes
                # Use QTimer.singleShot for thread-safe signal emission
                from PyQt6.QtCore import QTimer

                self._server = start_server(
                    port=port,
                    on_data_changed=lambda: QTimer.singleShot(
                        0, self.server_data_changed.emit
                    ),
                )
                if self._server and self._server.is_running():
                    set_runtime_mode("server")  # Set runtime mode to server
                    url = self._server.get_server_url()
                    # Update UI to show server controls
                    self._update_network_ui()
                    # Update status immediately (client count will update on connect/disconnect events)
                    self._update_server_status()
                    self.network_mode_changed.emit("server", url)
                    QMessageBox.information(
                        self,
                        tr("server"),
                        tr("server_started_msg", url=url),
                    )
                else:
                    QMessageBox.critical(self, tr("server"), tr("server_start_failed"))
            except Exception as e:
                QMessageBox.critical(
                    self, tr("server"), tr("server_error", error=str(e))
                )

    def _toggle_connection(self):
        """Connect or disconnect from server."""
        from gearledger.api_client import (
            connect_to_server,
            disconnect_from_server,
            get_client,
        )
        from gearledger.data_layer import set_runtime_mode

        self._client = get_client()

        if self._client and self._client.is_connected():
            # Disconnect
            disconnect_from_server()
            self._client = None
            set_runtime_mode("standalone")  # Reset runtime mode
            self.connection_status_label.setText(tr("connection_status_disconnected"))
            self.connection_status_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic;"
            )
            self.connect_btn.setText(tr("connect"))
            self.connect_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
            )
            self.network_mode_changed.emit("standalone", "")
            QMessageBox.information(self, tr("connection"), tr("disconnected_msg"))
        else:
            # Connect
            # Check if a server is selected from dropdown
            current_data = self.server_address_combo.currentData()
            if current_data:
                address = current_data
            else:
                address = self.server_address_combo.lineEdit().text().strip()

            if not address:
                QMessageBox.warning(self, tr("connection"), tr("enter_server_address"))
                return

            # Add http:// if not present
            if not address.startswith("http://") and not address.startswith("https://"):
                address = f"http://{address}"

            try:
                self._client = connect_to_server(address)
                if self._client:
                    set_runtime_mode("client")  # Set runtime mode to client
                    self.connection_status_label.setText(
                        tr("connection_status_connected", address=address)
                    )
                    self.connection_status_label.setStyleSheet(
                        "color: #27ae60; font-weight: bold;"
                    )
                    self.connect_btn.setText(tr("disconnect"))
                    self.connect_btn.setStyleSheet(
                        "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
                    )
                    self.network_mode_changed.emit("client", address)
                    QMessageBox.information(
                        self,
                        tr("connection"),
                        tr("connected_msg", address=address),
                    )
                else:
                    QMessageBox.critical(
                        self,
                        tr("connection"),
                        tr("connection_failed", address=address),
                    )
            except Exception as e:
                QMessageBox.critical(
                    self, tr("connection"), tr("connection_error", error=str(e))
                )

    def _update_server_status(self):
        """Update server status label with current connection count."""
        from gearledger.server import get_server

        server = get_server()
        if server and server.is_running():
            url = server.get_server_url()
            count = server.get_connected_clients_count()
            if count > 0:
                self.server_status_label.setText(
                    tr("server_status_running_with_clients", url=url, count=count)
                )
            else:
                self.server_status_label.setText(tr("server_status_running", url=url))
            self.server_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.server_status_label.setText(tr("server_status_stopped"))
            self.server_status_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic;"
            )

    def _start_discovery(self):
        """Start one-time server discovery."""
        print("[DISCOVERY] _start_discovery() called - starting one-time server search")
        # Stop any existing discovery first
        if self._discovery:
            self._stop_discovery()

        from gearledger.network_discovery import ServerDiscovery

        def on_server_found(server):
            """Called when a server is discovered - update list immediately."""
            print(
                f"[DISCOVERY] Server found: {server.ip}:{server.port} - updating list"
            )
            # Update UI on main thread (callback is called from background thread)
            # Use a small delay to allow multiple servers to be discovered before updating
            QTimer.singleShot(100, self._update_discovered_servers)

        self._discovery = ServerDiscovery(on_server_found=on_server_found)
        self._discovery.start()
        print("[DISCOVERY] Discovery started, will run for 5 seconds")

        # Update button appearance to show discovery is active
        self.refresh_discovery_btn.setText("🔍 ...")
        self.refresh_discovery_btn.setStyleSheet(
            "background-color: #f39c12; color: white; font-weight: bold; padding: 6px 10px;"
        )
        self.refresh_discovery_btn.setEnabled(False)  # Disable while searching

        # Start one-time timer to stop discovery after 5 seconds
        self._discovery_timer.start(5000)  # Search for 5 seconds then stop
        print("[DISCOVERY] Timer started - will stop discovery in 5 seconds")

    def _stop_discovery(self):
        """Stop server discovery."""
        # Stop the timeout timer (if it exists)
        if hasattr(self, "_discovery_timer") and self._discovery_timer.isActive():
            self._discovery_timer.stop()

        if self._discovery:
            print("[DISCOVERY] Stopping active server discovery")
            self._discovery.stop()
            self._discovery = None

        # Final update of discovered servers list
        if hasattr(self, "refresh_discovery_btn"):
            self._update_discovered_servers()

            # Update button appearance to show discovery is stopped
            self.refresh_discovery_btn.setText("🔍")
            self.refresh_discovery_btn.setStyleSheet(
                "background-color: #95a5a6; color: white; font-weight: bold; padding: 6px 10px;"
            )
            self.refresh_discovery_btn.setEnabled(True)  # Re-enable button

    def _refresh_discovery(self):
        """Manually trigger one-time server discovery."""
        if not self.client_radio.isChecked():
            return

        # If discovery is already running, stop it first
        if self._discovery:
            self._stop_discovery()
            # Small delay to ensure cleanup before starting new search
            QTimer.singleShot(200, self._start_discovery)
        else:
            # Start one-time discovery
            self._start_discovery()

    def _on_discovery_timeout(self):
        """Called when discovery timeout expires - stop discovery and update list."""
        print(
            "[TIMER] _on_discovery_timeout() called - discovery timeout reached, stopping discovery"
        )
        self._stop_discovery()

    def _update_discovered_servers(self):
        """Update the combo box with discovered servers."""
        if not self.client_radio.isChecked():
            return

        if not self._discovery:
            return

        discovered = self._discovery.get_discovered_servers()
        print(
            f"[DISCOVERY] _update_discovered_servers() - checking for servers, found: {len(discovered) if discovered else 0}"
        )

        # Get current selection
        current_text = self.server_address_combo.lineEdit().text().strip()
        print(f"[DISCOVERY] Current field text: '{current_text}'")

        # Update combo box items
        self.server_address_combo.clear()
        print(
            f"[DISCOVERY] Cleared combo box, now adding {len(discovered) if discovered else 0} server(s)"
        )

        if discovered:
            for server in discovered:
                display_text = f"{server.name} ({server.ip}:{server.port})"
                server_url = server.get_url()
                print(
                    f"[DISCOVERY] Adding server to combo: {display_text} -> {server_url}"
                )
                self.server_address_combo.addItem(display_text, server_url)

            # Auto-select first server if field is empty, otherwise restore selection
            if not current_text:
                # Field is empty - auto-select first discovered server
                first_server_url = discovered[0].get_url()
                self.server_address_combo.setCurrentIndex(0)
                # Explicitly set the text in the lineEdit to ensure it updates
                self.server_address_combo.lineEdit().setText(first_server_url)
                if len(discovered) == 1:
                    print(f"[DISCOVERY] Auto-selected server: {first_server_url}")
                else:
                    print(
                        f"[DISCOVERY] Auto-selected first server ({len(discovered)} found): {first_server_url}"
                    )
                    print(f"[DISCOVERY] Other servers available in dropdown")
            else:
                # Try to restore selection if it matches a discovered server
                found_match = False
                for i in range(self.server_address_combo.count()):
                    if self.server_address_combo.itemData(i) == current_text:
                        self.server_address_combo.setCurrentIndex(i)
                        found_match = True
                        break

                if not found_match:
                    # If current text doesn't match, keep it as custom entry
                    self.server_address_combo.lineEdit().setText(current_text)

            self.discovery_status_label.setText(
                tr("servers_found", count=len(discovered))
            )
            self.discovery_status_label.setStyleSheet(
                "color: #27ae60; font-size: 11px;"
            )
        else:
            # No servers found
            if current_text:
                self.server_address_combo.lineEdit().setText(current_text)
            self.discovery_status_label.setText(tr("no_servers_found"))
            self.discovery_status_label.setStyleSheet(
                "color: #7f8c8d; font-size: 11px;"
            )

    def accept(self):
        """Save settings and close dialog."""
        # Save network settings
        self.settings.server_port = self.server_port_spin.value()
        self.settings.server_address = (
            self.server_address_combo.lineEdit().text().strip()
        )
        if self.server_radio.isChecked():
            self.settings.network_mode = "server"
        elif self.client_radio.isChecked():
            self.settings.network_mode = "client"
        else:
            self.settings.network_mode = "standalone"

        save_settings(self.settings)
        super().accept()

    def closeEvent(self, event):
        """Handle dialog close event."""
        # Stop discovery when closing
        self._stop_discovery()
        if hasattr(self, "_discovery_timer"):
            self._discovery_timer.stop()
        super().closeEvent(event)
