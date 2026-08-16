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
        self._connect_worker = None
        self._search_worker = None

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

        # Server display name (shown to clients in the server picker instead
        # of raw IP:port)
        server_name_row = QHBoxLayout()
        self.server_name_label = QLabel(tr("server_display_name_label"))
        server_name_row.addWidget(self.server_name_label)
        self.server_name_edit = QLineEdit()
        self.server_name_edit.setPlaceholderText(
            tr("server_display_name_placeholder")
        )
        server_name_row.addWidget(self.server_name_edit, 1)
        network_layout.addLayout(server_name_row)

        # Server settings
        server_row = QHBoxLayout()
        self.server_port_label = QLabel(tr("server_port_label"))
        server_row.addWidget(self.server_port_label)
        self.server_port_spin = QSpinBox()
        self.server_port_spin.setRange(1024, 65535)
        self.server_port_spin.setValue(8081)
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

        # Client settings — by default this is just a single Connect button
        # (the one-touch flow: try the last-known server, then discover on
        # the LAN, auto-connecting or offering a name-only picker). A
        # warehouse worker should never need to see or type a network
        # address; the manual address field is still available for admin
        # use, but tucked behind "Advanced" and hidden by default.
        connect_row = QHBoxLayout()
        self.connect_btn = QPushButton(tr("connect"))
        self.connect_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.connect_btn.clicked.connect(self._toggle_connection)
        connect_row.addWidget(self.connect_btn)
        connect_row.addStretch(1)

        self.advanced_toggle_btn = QPushButton(tr("advanced_connection_options"))
        self.advanced_toggle_btn.setCheckable(True)
        self.advanced_toggle_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #3498db;
                border: none;
                padding: 4px 8px;
                font-size: 11px;
                text-decoration: underline;
            }
        """
        )
        self.advanced_toggle_btn.toggled.connect(self._on_advanced_toggled)
        connect_row.addWidget(self.advanced_toggle_btn)
        network_layout.addLayout(connect_row)

        # Advanced (hidden by default): manual server address entry + LAN
        # discovery, for the rare case an admin needs to point at a
        # specific address instead of the guided one-touch flow.
        client_row = QHBoxLayout()
        self.server_address_label = QLabel(tr("server_address_label"))
        client_row.addWidget(self.server_address_label)

        # Server discovery combo box (editable to allow manual entry)
        self.server_address_combo = QComboBox()
        self.server_address_combo.setEditable(True)
        self.server_address_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.server_address_combo.lineEdit().setPlaceholderText("192.168.1.100:8081")
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
        self.server_name_edit.setText(s.server_name)
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
        self.server_name_label.setVisible(is_server)
        self.server_name_edit.setVisible(is_server)
        self.server_port_label.setVisible(is_server)
        self.server_port_spin.setVisible(is_server)
        self.start_server_btn.setVisible(is_server)
        self.server_status_label.setVisible(is_server)

        # Show/hide client controls based on mode. The manual address
        # field + discovery button stay hidden unless "Advanced" is also
        # toggled on — the default is just the one-touch Connect button.
        is_advanced = self.advanced_toggle_btn.isChecked()
        self.advanced_toggle_btn.setVisible(is_client)
        self.server_address_label.setVisible(is_client and is_advanced)
        self.server_address_combo.setVisible(is_client and is_advanced)
        self.refresh_discovery_btn.setVisible(is_client and is_advanced)
        self.discovery_status_label.setVisible(is_client and is_advanced)
        self.connect_btn.setVisible(is_client)
        self.connection_status_label.setVisible(is_client)

        # Enable/disable based on mode
        self.server_port_spin.setEnabled(is_server)
        self.start_server_btn.setEnabled(is_server)

        self.server_address_combo.setEnabled(is_client)
        self.refresh_discovery_btn.setEnabled(is_client)
        self.connect_btn.setEnabled(is_client)

        # Update button states based on current connection status
        from gearledger.server import get_server
        from gearledger.api_client import get_client

        server = get_server()
        client = get_client()
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

        if is_client and client and client.is_connected():
            self.connect_btn.setText(tr("disconnect"))
            self.connect_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
            )
            display = (
                f"{client.server_name} ({client.server_url})"
                if getattr(client, "server_name", None)
                else client.server_url
            )
            self.connection_status_label.setText(
                tr("connection_status_connected", address=display)
            )
            self.connection_status_label.setStyleSheet(
                "color: #27ae60; font-weight: bold;"
            )
            self._client = client  # Keep in sync for _toggle_connection
        else:
            self.connect_btn.setText(tr("connect"))
            self.connect_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
            )
            if is_client:
                self.connection_status_label.setText(tr("connection_status_disconnected"))
                self.connection_status_label.setStyleSheet(
                    "color: #7f8c8d; font-style: italic;"
                )

    def _on_advanced_toggled(self, checked: bool):
        """Show/hide the manual address field + discovery button."""
        self.advanced_toggle_btn.setText(
            tr("advanced_connection_options_hide")
            if checked
            else tr("advanced_connection_options")
        )
        self._update_network_ui()

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
            server_name = self.server_name_edit.text().strip()
            # Persist the display name immediately so it survives even if
            # the dialog is closed without pressing the outer "Close"/accept.
            self.settings.server_name = server_name
            save_settings(self.settings)
            try:
                # Pass callback to refresh UI when data changes
                # Use QTimer.singleShot for thread-safe signal emission
                from PyQt6.QtCore import QTimer

                # Callback for client connection/disconnection events
                def on_client_changed(count):
                    """Called when client count changes."""
                    # Update server status in dialog
                    QTimer.singleShot(0, lambda: self._update_server_status())
                    # Also emit signal so main window can update its status
                    QTimer.singleShot(0, self.server_data_changed.emit)

                self._server = start_server(
                    port=port,
                    on_data_changed=lambda: QTimer.singleShot(
                        0, self.server_data_changed.emit
                    ),
                    on_client_changed=on_client_changed,
                    server_name=server_name or None,
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
        """Connect or disconnect from server.

        Connect defaults to the same one-touch flow as the main window
        (try the last-known server, then LAN discovery — auto-connect or
        a name-only picker). If "Advanced" is open with an address typed
        in, that takes priority as an explicit admin override.
        """
        from gearledger.api_client import disconnect_from_server, get_client
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
            return

        manual_address = ""
        if self.advanced_toggle_btn.isChecked():
            current_data = self.server_address_combo.currentData()
            if current_data:
                manual_address = current_data
            else:
                raw = self.server_address_combo.lineEdit().text().strip()
                manual_address = self._normalize_server_address(raw) or raw

        if manual_address:
            self._connect_to_address(manual_address)
        else:
            self._start_one_touch_connect()

    def _connect_to_address(self, address: str):
        """Connect directly to a specific address (the manual/advanced
        override path, or a server picked via discovery)."""
        from gearledger.api_client import connect_to_server, get_last_connect_error
        from gearledger.data_layer import set_runtime_mode

        if not address.startswith("http://") and not address.startswith("https://"):
            address = f"http://{address}"

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(tr("connecting"))
        try:
            self._client = connect_to_server(address)
        except Exception as e:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText(tr("connect"))
            QMessageBox.critical(
                self, tr("connection"), tr("connection_error", error=str(e))
            )
            return

        if self._client:
            set_runtime_mode("client")
            self._finish_successful_connect(address)
        else:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText(tr("connect"))
            detail = get_last_connect_error()
            print(f"[NETWORK_SETTINGS] Connection to {address} failed: {detail}")
            msg = tr("connection_failed", address=address)
            if detail:
                msg = f"{msg}\n\n{tr('connection_error', error=detail)}"
            QMessageBox.critical(self, tr("connection"), msg)

    def _finish_successful_connect(self, address: str):
        """Shared success-path UI update + settings persistence, used by
        both the manual/advanced connect and the one-touch flow."""
        from gearledger.desktop.settings_manager import load_settings, save_settings

        settings = load_settings()
        settings.server_address = address
        settings.network_mode = "client"
        save_settings(settings)
        self.settings = settings

        display = (
            f"{self._client.server_name} ({address})"
            if getattr(self._client, "server_name", None)
            else address
        )
        self.connection_status_label.setText(
            tr("connection_status_connected", address=display)
        )
        self.connection_status_label.setStyleSheet(
            "color: #27ae60; font-weight: bold;"
        )
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText(tr("disconnect"))
        self.connect_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.network_mode_changed.emit("client", address)
        QMessageBox.information(
            self, tr("connection"), tr("connected_msg", address=display)
        )

    def _start_one_touch_connect(self):
        """Kick off the shared background worker: try the saved address
        first, then fall back to LAN discovery — never blocks the UI."""
        from gearledger.desktop.settings_manager import load_settings
        from gearledger.desktop.client_connect_worker import ClientConnectWorker

        if getattr(self, "_connect_worker", None) is not None:
            return  # already in progress

        settings = load_settings()
        saved_address = (settings.server_address or "").strip()

        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(tr("connecting"))

        self._connect_worker = ClientConnectWorker(saved_address, self)
        self._connect_worker.connected.connect(self._on_one_touch_connected)
        self._connect_worker.discovery_finished.connect(
            self._on_one_touch_discovery_finished
        )
        self._connect_worker.finished.connect(self._on_connect_worker_finished)
        self._connect_worker.start()

    def _on_connect_worker_finished(self):
        worker = self._connect_worker
        self._connect_worker = None
        if worker:
            worker.deleteLater()

    def _on_one_touch_connected(self, address: str):
        from gearledger.api_client import get_client

        self._client = get_client()
        self.connect_btn.setEnabled(True)
        self._finish_successful_connect(address)

    def _on_one_touch_discovery_finished(self, servers: list):
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText(tr("connect"))

        if not servers:
            QMessageBox.warning(self, tr("connection"), tr("no_server_found_simple"))
            return

        if len(servers) == 1:
            self._connect_to_discovered_server(servers[0])
            return

        from .server_picker_dialog import ServerPickerDialog

        dlg = ServerPickerDialog(servers, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_server:
            self._connect_to_discovered_server(dlg.selected_server)

    def _connect_to_discovered_server(self, server):
        self._connect_to_address(server.get_url())

    def _update_server_status(self):
        """Update server status label with current connection count and SSE status."""
        from gearledger.server import get_server

        server = get_server()
        if server and server.is_running():
            raw_url = server.get_server_url()
            # Show the friendly name alongside the raw URL here — this is
            # the "Advanced" dialog, so admin-level detail is fine, unlike
            # the worker-facing picker which shows names only.
            url = f"{server.server_name} ({raw_url})" if server.server_name else raw_url
            count = server.get_connected_clients_count()
            sse_count = server.get_sse_clients_count()
            if count > 0:
                if sse_count > 0:
                    status_text = tr("server_status_running_with_clients", url=url, count=count)
                    status_text += f" ({sse_count} real-time)"
                    self.server_status_label.setText(status_text)
                    self.server_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                else:
                    status_text = tr("server_status_running_with_clients", url=url, count=count)
                    status_text += " (⚠️ no real-time sync)"
                    self.server_status_label.setText(status_text)
                    self.server_status_label.setStyleSheet("color: #e67e22; font-weight: bold;")
            else:
                self.server_status_label.setText(tr("server_status_running", url=url))
                self.server_status_label.setStyleSheet("color: #f39c12; font-weight: bold;")
        else:
            self.server_status_label.setText(tr("server_status_stopped"))
            self.server_status_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic;"
            )

    def _refresh_discovery(self):
        """Explicit "change server" action: forces a fresh LAN discovery
        search (bypassing the Connect button's fast-path reuse of the
        last-known server) and shows every result in a popup — including
        when the field/current connection already points somewhere, so
        this is how an admin switches to a different server, not just how
        they find one the first time. Works whether currently connected
        or not; picking a server in the popup connects to it directly."""
        from gearledger.desktop.client_connect_worker import ClientConnectWorker

        if not self.client_radio.isChecked():
            return
        if getattr(self, "_search_worker", None) is not None:
            return  # already searching

        self.refresh_discovery_btn.setEnabled(False)
        self.refresh_discovery_btn.setText("🔍 ...")
        self.discovery_status_label.setText(tr("discovering_servers"))
        self.discovery_status_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")

        # Empty saved_address forces the worker straight to the discovery
        # branch — it never tries a fast-path reconnect to a remembered
        # server, since the whole point here is finding *other* servers.
        self._search_worker = ClientConnectWorker("", self)
        self._search_worker.discovery_finished.connect(
            self._on_advanced_search_finished
        )
        self._search_worker.finished.connect(self._on_search_worker_finished)
        self._search_worker.start()

    def _on_search_worker_finished(self):
        worker = self._search_worker
        self._search_worker = None
        if worker:
            worker.deleteLater()

    def _on_advanced_search_finished(self, servers: list):
        self.refresh_discovery_btn.setEnabled(True)
        self.refresh_discovery_btn.setText("🔍")

        if not self.client_radio.isChecked():
            return  # user switched modes while the search was running

        if not servers:
            self.discovery_status_label.setText(tr("no_servers_found"))
            self.discovery_status_label.setStyleSheet(
                "color: #7f8c8d; font-size: 11px;"
            )
            QMessageBox.warning(self, tr("connection"), tr("no_server_found_simple"))
            return

        self.discovery_status_label.setText(tr("servers_found", count=len(servers)))
        self.discovery_status_label.setStyleSheet("color: #27ae60; font-size: 11px;")

        from .server_picker_dialog import ServerPickerDialog

        dlg = ServerPickerDialog(servers, self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_server:
            self._connect_to_discovered_server(dlg.selected_server)

    def _normalize_server_address(self, text: str) -> str:
        """Extract URL from text. Handles 'Name (ip:port)' or 'http://ip:port' format."""
        import re
        text = (text or "").strip()
        if not text:
            return ""
        # Already a URL
        if text.startswith("http://") or text.startswith("https://"):
            return text
        # Extract ip:port from "Name (ip:port)" format
        match = re.search(r"\(([^)]+)\)", text)
        if match:
            host_port = match.group(1).strip()
            if host_port and ":" in host_port:
                return f"http://{host_port}"
        # Plain ip:port
        if ":" in text and not text.startswith("http"):
            return f"http://{text}"
        return text

    def accept(self):
        """Save settings and close dialog."""
        # Save network settings - normalize server address to URL only
        self.settings.server_name = self.server_name_edit.text().strip()
        self.settings.server_port = self.server_port_spin.value()
        raw = self.server_address_combo.lineEdit().text().strip()
        self.settings.server_address = (
            self._normalize_server_address(raw) or raw
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
        """Handle dialog close event.

        If a background connect/search worker is still running, detach our
        signal handlers so it doesn't try to touch this dialog's widgets
        after it's gone — the thread itself is still allowed to finish and
        clean up via its Qt parent.
        """
        for worker in (self._connect_worker, self._search_worker):
            if worker:
                try:
                    worker.disconnect()
                except Exception:
                    pass
        super().closeEvent(event)
