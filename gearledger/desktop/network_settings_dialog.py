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
from .button_spinner import ButtonSpinner


class NetworkSettingsDialog(QDialog):
    """Dialog for network/server settings."""

    # Signal emitted when network mode changes
    network_mode_changed = pyqtSignal(str, str)  # mode, address
    # Signal emitted when server receives data (to refresh UI)
    server_data_changed = pyqtSignal()
    # Signal emitted when the client disconnects but stays in Client mode
    # (as opposed to network_mode_changed, which means the mode itself
    # changed) — lets the main window stop its SSE client etc. without
    # main_window._on_network_mode_changed() treating this as a switch
    # away from Client mode.
    client_disconnected = pyqtSignal()
    # Emitted when the user logs out. This dialog doesn't own app
    # lifecycle decisions — it just reports "logout happened" and closes
    # itself; MainWindow decides what that means (close itself so
    # app_desktop.py's main() loop can drop back to the login gate).
    logout_requested = pyqtSignal()

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
        self._load_settings_to_ui()  # ends by calling _update_network_ui(), which also refreshes the account status label

        # Live-refresh while the dialog is open: connection/sharing state
        # can change from outside this dialog (e.g. Disconnect/Share-on-
        # Network clicked on the main window toolbar, or an auto-connect
        # completing after this dialog was already opened) — without this,
        # the dialog silently goes stale, still showing a mode/connection
        # state that no longer matches what the rest of the app is doing.
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_network_ui)
        self._status_timer.start(3000)

    def _setup_ui(self):
        """Set up the network settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Cloud account — deliberately outside the Server/Client mode
        # groupbox below: the account/session is orthogonal to which mode
        # you're using for data (see login_dialog.py's required-gate
        # docstring), so this stays visible and usable regardless of which
        # radio is selected.
        account_row = QHBoxLayout()
        self.account_status_label = QLabel("")
        self.account_status_label.setStyleSheet("color: #7f8c8d;")
        account_row.addWidget(self.account_status_label)
        account_row.addStretch(1)
        self.logout_btn = QPushButton(tr("logout"))
        self.logout_btn.setStyleSheet(
            "background-color: #95a5a6; color: white; font-weight: bold; padding: 4px 12px;"
        )
        self.logout_btn.clicked.connect(self._on_logout_clicked)
        account_row.addWidget(self.logout_btn)
        layout.addLayout(account_row)

        # Network Configuration
        network_group = QGroupBox(tr("network_configuration"))
        network_layout = QVBoxLayout(network_group)

        # Mode selection
        mode_label = QLabel(tr("network_mode_label"))
        network_layout.addWidget(mode_label)

        self.mode_button_group = QButtonGroup(self)
        mode_row = QHBoxLayout()

        self.server_radio = QRadioButton(tr("server_mode"))
        self.server_radio.setToolTip(tr("server_tooltip"))
        self.client_radio = QRadioButton(tr("client_mode"))
        self.client_radio.setToolTip(tr("client_tooltip"))

        self.mode_button_group.addButton(self.server_radio, 0)
        self.mode_button_group.addButton(self.client_radio, 1)

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

        # Client settings — by default this is just Connect + Change Server
        # (the one-touch flow: try the last-known server, then discover on
        # the LAN, auto-connecting or offering a name-only picker; Change
        # Server always forces a fresh search + picker, for switching to a
        # different server on demand). A warehouse worker should never need
        # to see or type a network address; the manual address field is
        # still available for admin use, but tucked behind "Advanced" and
        # hidden by default.
        connect_row = QHBoxLayout()
        self.connect_btn = QPushButton(tr("connect"))
        self.connect_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.connect_btn.clicked.connect(self._toggle_connection)
        connect_row.addWidget(self.connect_btn)

        self.change_server_btn = QPushButton(tr("change_server"))
        self.change_server_btn.setStyleSheet(
            "background-color: #8e44ad; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.change_server_btn.clicked.connect(self._refresh_discovery)
        connect_row.addWidget(self.change_server_btn)

        # Separate from LAN Connect/Change Server: this skips discovery
        # entirely and goes straight to a fixed cloud URL, either reusing a
        # stored token or opening LoginDialog to get one.
        self.cloud_login_btn = QPushButton(tr("log_in_to_cloud"))
        self.cloud_login_btn.setStyleSheet(
            "background-color: #16a085; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.cloud_login_btn.clicked.connect(self._open_cloud_login)
        connect_row.addWidget(self.cloud_login_btn)

        # Rotating spinner icon shown directly on whichever button
        # triggered a connect/search, instead of a separate progress-bar
        # widget — reads as part of the button rather than bolted on.
        self._connect_btn_spinner = ButtonSpinner(self.connect_btn)
        self._change_server_btn_spinner = ButtonSpinner(self.change_server_btn)
        self._cloud_login_btn_spinner = ButtonSpinner(self.cloud_login_btn)

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

        # Advanced (hidden by default): manual server address entry, for
        # the rare case an admin needs to type a specific address instead
        # of using the guided Connect / Change Server flow.
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
        self.server_radio.toggled.connect(self._on_mode_radio_toggled)
        self.client_radio.toggled.connect(self._on_mode_radio_toggled)

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
        if s.network_mode == "client":
            self.client_radio.setChecked(True)
        else:
            self.server_radio.setChecked(True)

        self._update_network_ui()

    def _on_mode_radio_toggled(self, checked: bool):
        """Selecting a mode radio is a statement of intent — reflect it in
        the live runtime mode immediately, rather than waiting for a
        connect attempt to succeed. Without this, the rest of the app
        (main window layout included) keeps showing the *previous* mode's
        UI for as long as a connection is pending/slow/retrying, since
        get_network_mode() only used to flip on a successful connect.

        toggled() fires twice per switch (the button losing the check,
        then the one gaining it) — only act on the "gained" event.

        Switching away from an actively-in-use mode (sharing running, or
        connected as a client) would otherwise silently orphan that
        connection in the background while the UI moves on — confirm with
        the user and stop/disconnect it first, or revert the selection if
        they decline.
        """
        if not checked:
            return

        mode = "client" if self.client_radio.isChecked() else "server"

        if mode == "client":
            from gearledger.server import get_server, stop_server

            server = get_server()
            if server and server.is_running():
                reply = QMessageBox.question(
                    self,
                    tr("network_configuration"),
                    tr("switch_to_client_stop_sharing_confirm"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self.server_radio.setChecked(True)
                    return
                stop_server()
                self.settings.server_sharing_enabled = False
                save_settings(self.settings)
        else:
            from gearledger.api_client import get_client, disconnect_from_server

            client = get_client()
            if client and client.is_connected():
                reply = QMessageBox.question(
                    self,
                    tr("network_configuration"),
                    tr("switch_to_local_disconnect_confirm"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self.client_radio.setChecked(True)
                    return
                disconnect_from_server()
                self._client = None

        from gearledger.data_layer import set_runtime_mode

        set_runtime_mode(mode)
        self._update_network_ui()
        self.network_mode_changed.emit(mode, "")

    def _update_network_ui(self):
        """Update network UI based on selected mode."""
        is_server = self.server_radio.isChecked()
        is_client = self.client_radio.isChecked()

        # Show/hide server controls based on mode
        self.server_name_label.setVisible(is_server)
        self.server_name_edit.setVisible(is_server)
        self.server_port_label.setVisible(is_server)
        self.server_port_spin.setVisible(is_server)
        self.start_server_btn.setVisible(is_server)
        self.server_status_label.setVisible(is_server)

        # Show/hide client controls based on mode. The manual address
        # field stays hidden unless "Advanced" is also toggled on — the
        # default is just Connect + Change Server.
        is_advanced = self.advanced_toggle_btn.isChecked()
        self.advanced_toggle_btn.setVisible(is_client)
        self.server_address_label.setVisible(is_client and is_advanced)
        self.server_address_combo.setVisible(is_client and is_advanced)
        self.discovery_status_label.setVisible(is_client)
        self.connect_btn.setVisible(is_client)
        self.change_server_btn.setVisible(is_client)
        self.cloud_login_btn.setVisible(is_client)
        self.connection_status_label.setVisible(is_client)

        # Enable/disable based on mode
        self.server_port_spin.setEnabled(is_server)
        self.start_server_btn.setEnabled(is_server)

        self.server_address_combo.setEnabled(is_client)
        self.connect_btn.setEnabled(is_client)
        self.change_server_btn.setEnabled(is_client)
        self.cloud_login_btn.setEnabled(is_client)

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
            if not is_server:
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

        # Mid-session token expiry: a previously-successful cloud
        # connection whose most recent request came back 401. Caught here
        # (this method also runs on the 3s status timer while the dialog
        # is open) rather than only at initial connect time.
        if is_client and client and getattr(client, "needs_reauth", False):
            self._handle_reauth_needed()

        self._update_account_ui()

    def _update_account_ui(self):
        """Reflect current login state — independent of the Server/Client
        radio, since the account itself isn't tied to either mode."""
        from . import settings_manager

        settings = settings_manager.load_settings()
        if settings_manager.get_auth_token() and settings.auth_email:
            self.account_status_label.setText(
                tr("logged_in_as", email=settings.auth_email)
            )
            self.logout_btn.setEnabled(True)
        else:
            self.account_status_label.setText(tr("not_logged_in"))
            self.logout_btn.setEnabled(False)

    def _on_logout_clicked(self):
        """Log out: disconnect any active cloud session, drop the stored
        token, and hand off to MainWindow via logout_requested.

        This dialog doesn't decide what happens after logout — it used to
        (calling QApplication.closeAllWindows() directly), which worked
        but quit the whole app, forcing a manual relaunch to log back in.
        Emitting logout_requested and just closing this dialog instead
        lets MainWindow close itself (running its own closeEvent cleanup
        — camera/scale/threads — the same as any normal close) while
        app_desktop.py's main() loop notices and drops straight back to
        the login gate instead of exiting the process."""
        from . import settings_manager
        from gearledger.api_client import disconnect_from_server, get_client

        reply = QMessageBox.question(
            self,
            tr("logout"),
            tr("logout_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        client = get_client()
        if client:
            # Best-effort server-side revocation (client.logout() swallows
            # its own network errors — a server that happens to be
            # unreachable right now shouldn't block logging out locally).
            client.logout()
        if client and client.is_connected():
            disconnect_from_server()
            self._client = None
            self.client_disconnected.emit()

        settings_manager.clear_auth()
        self.logout_requested.emit()
        self.accept()

    def _on_advanced_toggled(self, checked: bool):
        """Show/hide the manual address field + discovery button."""
        self.advanced_toggle_btn.setText(
            tr("advanced_connection_options_hide")
            if checked
            else tr("advanced_connection_options")
        )
        self._update_network_ui()

    def _toggle_server(self):
        """Turn LAN sharing on/off. The local DB backend is always active
        regardless — this only controls whether the HTTP listener binds a
        port for other devices to connect to."""
        from gearledger.server import start_server, stop_server, get_server

        self._server = get_server()

        if self._server and self._server.is_running():
            # Stop sharing
            stop_server()
            self._server = None
            self.settings.server_sharing_enabled = False
            save_settings(self.settings)
            # Update UI to hide server controls
            self._update_network_ui()
            self.network_mode_changed.emit("server", "")
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
                    self.settings.server_sharing_enabled = True
                    save_settings(self.settings)
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

        self._client = get_client()

        if self._client and self._client.is_connected():
            # Disconnect stays in Client mode (just not connected) so the
            # dialog is ready to reconnect and doesn't reveal local
            # catalog/results editing that Client mode intentionally
            # hides. Emit client_disconnected (not network_mode_changed)
            # since the mode itself hasn't changed.
            disconnect_from_server()
            self._client = None
            self.connection_status_label.setText(tr("connection_status_disconnected"))
            self.connection_status_label.setStyleSheet(
                "color: #7f8c8d; font-style: italic;"
            )
            self.connect_btn.setText(tr("connect"))
            self.connect_btn.setStyleSheet(
                "background-color: #3498db; color: white; font-weight: bold; padding: 6px 12px;"
            )
            self.client_disconnected.emit()
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

    def _set_connecting_ui(self, active: bool, on_button: QPushButton = None):
        """Disable Connect/Change Server while a connect or search worker
        is running (so the two can't overlap), and spin a small rotating
        icon directly on whichever button triggered the action — defaults
        to Connect, since most call sites are part of the connect flow."""
        self.connect_btn.setEnabled(not active)
        self.change_server_btn.setEnabled(not active)
        target = on_button or self.connect_btn
        if active:
            self._active_spinner = (
                self._connect_btn_spinner
                if target is self.connect_btn
                else self._change_server_btn_spinner
            )
            self._active_spinner.start()
        else:
            self._connect_btn_spinner.stop()
            self._change_server_btn_spinner.stop()

    def _connect_to_address(self, address: str):
        """Connect directly to a specific address (the manual/advanced
        override path, or a server picked via discovery)."""
        from gearledger.api_client import connect_to_server, get_last_connect_error
        from gearledger.data_layer import set_runtime_mode

        if not address.startswith("http://") and not address.startswith("https://"):
            address = f"http://{address}"

        self._set_connecting_ui(True)
        self.connect_btn.setText(tr("connecting"))
        try:
            self._client = connect_to_server(address)
        except Exception as e:
            self._set_connecting_ui(False)
            self.connect_btn.setText(tr("connect"))
            QMessageBox.critical(
                self, tr("connection"), tr("connection_error", error=str(e))
            )
            return

        if self._client:
            set_runtime_mode("client")
            self._finish_successful_connect(address)
        else:
            self._set_connecting_ui(False)
            self.connect_btn.setText(tr("connect"))
            detail = get_last_connect_error()
            print(f"[NETWORK_SETTINGS] Connection to {address} failed: {detail}")
            from .translations import connection_error_detail

            if detail == "NO_NETWORK":
                msg = connection_error_detail(detail)
            else:
                msg = tr("connection_failed", address=address)
                if detail:
                    msg = f"{msg}\n\n{connection_error_detail(detail)}"
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
        self._set_connecting_ui(False)
        self.connect_btn.setText(tr("disconnect"))
        self.connect_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; font-weight: bold; padding: 6px 12px;"
        )
        self.network_mode_changed.emit("client", address)
        QMessageBox.information(
            self, tr("connection"), tr("connected_msg", address=display)
        )

    def _open_cloud_login(self):
        """Log In to Cloud: reuse a stored token if there is one, otherwise
        open LoginDialog to get one. Skips LAN discovery entirely — this
        always goes straight to a fixed cloud URL."""
        from . import settings_manager

        settings = settings_manager.load_settings()
        stored_token = settings_manager.get_auth_token()
        if stored_token and settings.cloud_server_url:
            self._connect_cloud(settings.cloud_server_url, stored_token)
            return

        from .login_dialog import LoginDialog

        dlg = LoginDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result:
            self._connect_cloud(
                dlg.result["cloud_server_url"],
                dlg.result["refresh_token"],
                access_token=dlg.result["access_token"],
            )

    def _connect_cloud(self, address: str, refresh_token: str, access_token: str = None):
        """Connect to the cloud backend with a refresh token in hand —
        either just obtained from LoginDialog (which also hands over the
        access token that came with it, saving one round trip) or reused
        from a prior session (access_token omitted; the first request
        401s and APIClient's silent-refresh path mints one). Mirrors
        _connect_to_address()'s shape but never touches LAN discovery, and
        an UNAUTHORIZED failure here means the refresh token itself is
        dead (not just "server unreachable"), so it clears it and
        re-prompts login instead of showing a generic connection error."""
        from gearledger.api_client import connect_to_server, get_last_connect_error
        from gearledger.data_layer import set_runtime_mode
        from . import settings_manager
        from .translations import connection_error_detail

        self.cloud_login_btn.setEnabled(False)
        self.connect_btn.setEnabled(False)
        self.change_server_btn.setEnabled(False)
        self.cloud_login_btn.setText(tr("connecting"))
        self._cloud_login_btn_spinner.start()

        try:
            self._client = connect_to_server(
                address, auth_token=access_token, refresh_token=refresh_token
            )
        except Exception as e:
            self._client = None
            error_detail = str(e)
        else:
            error_detail = None if self._client else get_last_connect_error()

        self._cloud_login_btn_spinner.stop()
        self.cloud_login_btn.setEnabled(True)
        self.connect_btn.setEnabled(True)
        self.change_server_btn.setEnabled(True)
        self.cloud_login_btn.setText(tr("log_in_to_cloud"))

        if self._client:
            set_runtime_mode("client")
            self._finish_successful_connect(address)
            return

        if error_detail == "UNAUTHORIZED":
            settings_manager.clear_auth()
            QMessageBox.information(
                self, tr("cloud_login_title"), tr("session_expired")
            )
            self._open_cloud_login()
            return

        if error_detail == "ACCOUNT_INACTIVE":
            # Deliberately not clear_auth()/re-prompt here: the token
            # itself is fine (login succeeded) -- re-authenticating
            # wouldn't change anything. Only an admin activating the
            # account fixes this.
            QMessageBox.information(
                self, tr("cloud_login_title"), tr("account_inactive_message")
            )
            return

        print(f"[NETWORK_SETTINGS] Cloud connect to {address} failed: {error_detail}")
        if error_detail == "NO_NETWORK":
            msg = connection_error_detail(error_detail)
        else:
            msg = tr("connection_failed", address=address)
            if error_detail:
                msg = f"{msg}\n\n{connection_error_detail(error_detail)}"
        QMessageBox.critical(self, tr("connection"), msg)

    def _start_one_touch_connect(self):
        """Kick off the shared background worker: try the saved address
        first, then fall back to LAN discovery — never blocks the UI."""
        from gearledger.desktop import settings_manager
        from gearledger.desktop.client_connect_worker import ClientConnectWorker

        if getattr(self, "_connect_worker", None) is not None:
            return  # already in progress

        settings = settings_manager.load_settings()
        saved_address = (settings.server_address or "").strip()

        self._set_connecting_ui(True)
        self.connect_btn.setText(tr("connecting"))

        self._connect_worker = ClientConnectWorker(
            saved_address, self, refresh_token=settings_manager.get_auth_token()
        )
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
        self._finish_successful_connect(address)

    def _on_one_touch_discovery_finished(self, servers: list):
        self._set_connecting_ui(False)
        self.connect_btn.setText(tr("connect"))

        if not servers:
            from gearledger.api_client import has_network_connection

            key = "no_server_found_simple" if has_network_connection() else "no_network_connection"
            QMessageBox.warning(self, tr("connection"), tr(key))
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

        self._set_connecting_ui(True, on_button=self.change_server_btn)
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
        self._set_connecting_ui(False)

        if not self.client_radio.isChecked():
            return  # user switched modes while the search was running

        if not servers:
            from gearledger.api_client import has_network_connection

            network_ok = has_network_connection()
            self.discovery_status_label.setText(
                tr("no_servers_found") if network_ok else tr("no_network_connection")
            )
            self.discovery_status_label.setStyleSheet(
                "color: #7f8c8d; font-size: 11px;"
            )
            key = "no_server_found_simple" if network_ok else "no_network_connection"
            QMessageBox.warning(self, tr("connection"), tr(key))
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
        self.settings.network_mode = (
            "client" if self.client_radio.isChecked() else "server"
        )

        save_settings(self.settings)
        super().accept()

    def closeEvent(self, event):
        """Handle dialog close event.

        If a background connect/search worker is still running, detach our
        signal handlers so it doesn't try to touch this dialog's widgets
        after it's gone, then wait for it to actually finish. The wait
        matters specifically because Logout can trigger
        QApplication.closeAllWindows() right after this dialog closes —
        letting the worker merely "finish later via its Qt parent" isn't
        enough once the whole app might be tearing down moments later;
        destroying a QThread object while its thread is still running
        aborts the process (each of these workers is internally bounded to
        a few seconds, so this wait is short, not indefinite).
        """
        for worker in (self._connect_worker, self._search_worker):
            if worker:
                try:
                    worker.disconnect()
                except Exception:
                    pass
                if worker.isRunning():
                    worker.requestInterruption()
                    worker.wait(10000)
        self._status_timer.stop()
        super().closeEvent(event)
