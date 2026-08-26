# gearledger/desktop/login_dialog.py
# -*- coding: utf-8 -*-
"""Email/password sign up or log in against the cloud backend (server/'s
/api/auth/signup and /api/auth/login). On success, persists the token via
settings_manager.save_auth() (JWT to the OS keyring, everything else to
settings.json) and exposes the result so the caller can connect
immediately without a second round trip."""
from __future__ import annotations

from typing import Optional, TypedDict

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from . import settings_manager
from .button_spinner import ButtonSpinner
from .translations import tr, connection_error_detail


class AuthResult(TypedDict):
    access_token: str
    tenant_id: str
    email: str
    cloud_server_url: str


class _AuthWorker(QThread):
    """Runs the signup/login POST off the UI thread."""

    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url: str, email: str, password: str, parent=None):
        super().__init__(parent)
        self.url = url
        self.email = email
        self.password = password

    def run(self):
        try:
            response = requests.post(
                self.url,
                json={"email": self.email, "password": self.password},
                timeout=15,
            )
        except requests.exceptions.ConnectionError:
            from gearledger.api_client import has_network_connection

            self.failed.emit(
                "NO_NETWORK" if not has_network_connection() else "SERVER_UNREACHABLE"
            )
            return
        except requests.exceptions.RequestException as e:
            self.failed.emit(str(e))
            return

        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code not in (200, 201):
            self.failed.emit(data.get("error") or f"HTTP {response.status_code}")
            return

        access_token = data.get("access_token")
        tenant_id = data.get("tenant_id")
        if not access_token or not tenant_id:
            self.failed.emit("Server response was missing access_token/tenant_id")
            return

        self.succeeded.emit({"access_token": access_token, "tenant_id": tenant_id})


class LoginDialog(QDialog):
    def __init__(self, parent=None, required: bool = False):
        """required=True is the app-launch gate (app_desktop.py): closing
        without a successful login exits the app instead of just closing a
        dialog, so this shows an explanatory banner making that clear up
        front rather than surprising the user."""
        super().__init__(parent)
        # Applied directly rather than relying on inheriting it from a
        # parent: the app-launch gate shows this dialog with parent=None
        # (MainWindow doesn't exist yet), so without its own copy it falls
        # back to raw OS theming — unreadable in dark mode, and
        # inconsistent with every other dialog in the app either way.
        from .app_style import get_app_stylesheet

        self.setStyleSheet(get_app_stylesheet())
        self.setWindowTitle(tr("cloud_login_title"))
        self.setMinimumWidth(380)
        self.result: Optional[AuthResult] = None
        self._worker: Optional[_AuthWorker] = None
        self._signup_mode = False

        settings = settings_manager.load_settings()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        if required:
            required_label = QLabel(tr("account_required_message"))
            required_label.setWordWrap(True)
            required_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
            layout.addWidget(required_label)

        form = QFormLayout()
        self.server_edit = QLineEdit(settings.cloud_server_url)
        self.server_edit.setPlaceholderText("http://localhost:8081")
        form.addRow(tr("cloud_server_label"), self.server_edit)

        self.email_edit = QLineEdit(settings.auth_email)
        form.addRow(tr("email_label"), self.email_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("password_label"), self.password_edit)

        layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #e74c3c;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        self.toggle_btn = QPushButton()
        self.toggle_btn.setStyleSheet(
            "background-color: transparent; color: #3498db; border: none; "
            "text-decoration: underline;"
        )
        self.toggle_btn.clicked.connect(self._toggle_mode)
        # Without this, Qt's default "Enter triggers the first autoDefault
        # button" behavior picks toggle_btn (created first) over the
        # actual submit button — Enter would switch Login/Signup instead
        # of submitting the form.
        self.toggle_btn.setAutoDefault(False)
        button_row.addWidget(self.toggle_btn)
        button_row.addStretch(1)

        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setAutoDefault(False)
        button_row.addWidget(cancel_btn)

        self.submit_btn = QPushButton()
        self.submit_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 6px 16px;"
        )
        self.submit_btn.clicked.connect(self._submit)
        self.submit_btn.setDefault(True)
        self.submit_btn.setAutoDefault(True)
        button_row.addWidget(self.submit_btn)
        self._submit_spinner = ButtonSpinner(self.submit_btn)

        layout.addLayout(button_row)

        self._update_mode_ui()

    def _toggle_mode(self):
        self._signup_mode = not self._signup_mode
        self._update_mode_ui()

    def _update_mode_ui(self):
        self._reset_submit_button_text()
        if self._signup_mode:
            self.toggle_btn.setText(tr("log_in"))
        else:
            self.toggle_btn.setText(tr("sign_up"))
        self.status_label.setText("")

    def _reset_submit_button_text(self):
        self.submit_btn.setText(tr("sign_up") if self._signup_mode else tr("log_in"))

    def _submit(self):
        server_url = self.server_edit.text().strip().rstrip("/")
        email = self.email_edit.text().strip()
        password = self.password_edit.text()

        if not server_url:
            self.status_label.setText(tr("cloud_server_required"))
            return
        if not email or not password:
            self.status_label.setText(tr("email_password_required"))
            return
        if not server_url.startswith("http://") and not server_url.startswith("https://"):
            server_url = f"http://{server_url}"

        self.status_label.setText("")
        self.submit_btn.setEnabled(False)
        self.toggle_btn.setEnabled(False)
        self.submit_btn.setText(
            tr("signing_up") if self._signup_mode else tr("logging_in")
        )
        self._submit_spinner.start()

        endpoint = "signup" if self._signup_mode else "login"
        self._worker = _AuthWorker(
            f"{server_url}/api/auth/{endpoint}", email, password, self
        )
        self._worker.succeeded.connect(
            lambda data: self._on_success(data, server_url, email)
        )
        self._worker.failed.connect(self._on_failure)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self):
        self._submit_spinner.stop()
        self.submit_btn.setEnabled(True)
        self.toggle_btn.setEnabled(True)
        self._reset_submit_button_text()
        worker = self._worker
        self._worker = None
        if worker:
            worker.deleteLater()

    def _on_success(self, data: dict, server_url: str, email: str):
        settings_manager.save_auth(
            token=data["access_token"],
            tenant_id=data["tenant_id"],
            email=email,
            cloud_server_url=server_url,
        )
        self.result = {
            "access_token": data["access_token"],
            "tenant_id": data["tenant_id"],
            "email": email,
            "cloud_server_url": server_url,
        }
        self.accept()

    def _on_failure(self, error: str):
        title = tr("signup_failed") if self._signup_mode else tr("login_failed")
        if error == "NO_NETWORK":
            self.status_label.setText(connection_error_detail("NO_NETWORK"))
        elif error == "SERVER_UNREACHABLE":
            self.status_label.setText(
                tr("connection_failed", address=self.server_edit.text().strip())
            )
        else:
            self.status_label.setText(f"{title}: {error}")

    def closeEvent(self, event):
        if self._worker:
            try:
                self._worker.disconnect()
            except Exception:
                pass
        super().closeEvent(event)
