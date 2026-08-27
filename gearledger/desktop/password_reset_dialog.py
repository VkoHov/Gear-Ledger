# gearledger/desktop/password_reset_dialog.py
# -*- coding: utf-8 -*-
"""Two-step "forgot password" flow against the cloud backend's
/api/auth/password-reset/request and /api/auth/password-reset/confirm.
Code-based rather than link-based: this is a desktop app, not a website,
so there's no page for a "click this link" email to open — the user
copies an 8-character code out of the email and types it back in here."""
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

from .button_spinner import ButtonSpinner
from .translations import tr, connection_error_detail


class ResetResult(TypedDict):
    email: str
    new_password: str


class _PostWorker(QThread):
    """Posts JSON to one endpoint and reports back — shared shape for both
    steps of this dialog (request a code, confirm a code); unlike
    login_dialog.py's _AuthWorker this doesn't need any endpoint-specific
    field validation, so one small generic worker covers both instead of
    two near-identical ones."""

    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, url: str, payload: dict, parent=None):
        super().__init__(parent)
        self.url = url
        self.payload = payload

    def run(self):
        try:
            response = requests.post(self.url, json=self.payload, timeout=15)
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

        if response.status_code >= 400:
            self.failed.emit(data.get("error") or f"HTTP {response.status_code}")
            return

        self.succeeded.emit(data)


class PasswordResetDialog(QDialog):
    def __init__(self, parent=None, server_url: str = "", email: str = ""):
        super().__init__(parent)
        from .app_style import get_app_stylesheet

        self.setStyleSheet(get_app_stylesheet())
        self.setWindowTitle(tr("password_reset_title"))
        self.setMinimumWidth(380)
        self.result: Optional[ResetResult] = None
        self._worker: Optional[_PostWorker] = None
        self._server_url = server_url.rstrip("/")
        # Set once step 1 succeeds — confirm's request body needs the code
        # the user types plus this remembered new password field pairing,
        # but the *email* itself is only needed for step 1's request.
        self._code_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        intro = QLabel(tr("password_reset_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.email_edit = QLineEdit(email)
        form.addRow(tr("email_label"), self.email_edit)
        layout.addLayout(form)

        # Step 2 fields — hidden until a code has been requested.
        self.step2_form = QFormLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(tr("password_reset_code_placeholder"))
        self.step2_form.addRow(tr("password_reset_code_label"), self.code_edit)

        self.new_password_edit = QLineEdit()
        self.new_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.step2_form.addRow(tr("password_reset_new_password_label"), self.new_password_edit)
        layout.addLayout(self.step2_form)
        self._set_step2_visible(False)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #e74c3c;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setAutoDefault(False)
        button_row.addWidget(cancel_btn)

        self.submit_btn = QPushButton(tr("password_reset_send_code"))
        self.submit_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 6px 16px;"
        )
        self.submit_btn.clicked.connect(self._submit)
        self.submit_btn.setDefault(True)
        self.submit_btn.setAutoDefault(True)
        button_row.addWidget(self.submit_btn)
        self._submit_spinner = ButtonSpinner(self.submit_btn)

        layout.addLayout(button_row)

    def _set_step2_visible(self, visible: bool):
        self.code_edit.setVisible(visible)
        self.new_password_edit.setVisible(visible)
        for i in range(self.step2_form.rowCount()):
            label_item = self.step2_form.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setVisible(visible)

    def _submit(self):
        if not self._code_requested:
            self._submit_request_code()
        else:
            self._submit_confirm()

    def _submit_request_code(self):
        email = self.email_edit.text().strip()
        if not email:
            self.status_label.setStyleSheet("color: #e74c3c;")
            self.status_label.setText(tr("email_password_required"))
            return
        if not self._server_url:
            self.status_label.setStyleSheet("color: #e74c3c;")
            self.status_label.setText(tr("cloud_server_required"))
            return

        self._run_worker(
            f"{self._server_url}/api/auth/password-reset/request",
            {"email": email},
            on_success=self._on_code_requested,
            busy_text=tr("password_reset_sending"),
        )

    def _on_code_requested(self, data: dict):
        self._code_requested = True
        self.email_edit.setEnabled(False)
        self._set_step2_visible(True)
        self.submit_btn.setText(tr("password_reset_submit"))
        self.status_label.setStyleSheet("color: #27ae60;")
        self.status_label.setText(tr("password_reset_code_sent"))

    def _submit_confirm(self):
        code = self.code_edit.text().strip()
        new_password = self.new_password_edit.text()
        if not code or not new_password:
            self.status_label.setStyleSheet("color: #e74c3c;")
            self.status_label.setText(tr("password_reset_code_and_password_required"))
            return
        if len(new_password) < 8:
            self.status_label.setStyleSheet("color: #e74c3c;")
            self.status_label.setText(tr("password_too_short"))
            return

        self._run_worker(
            f"{self._server_url}/api/auth/password-reset/confirm",
            {"code": code, "new_password": new_password},
            on_success=lambda data: self._on_confirmed(new_password),
            busy_text=tr("password_reset_resetting"),
        )

    def _on_confirmed(self, new_password: str):
        self.result = {"email": self.email_edit.text().strip(), "new_password": new_password}
        self.accept()

    def _run_worker(self, url: str, payload: dict, on_success, busy_text: str):
        self.status_label.setText("")
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText(busy_text)
        self._submit_spinner.start()

        self._worker = _PostWorker(url, payload, self)
        self._worker.succeeded.connect(on_success)
        self._worker.failed.connect(self._on_failure)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self):
        self._submit_spinner.stop()
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText(
            tr("password_reset_submit") if self._code_requested else tr("password_reset_send_code")
        )
        worker = self._worker
        self._worker = None
        if worker:
            worker.deleteLater()

    def _on_failure(self, error: str):
        self.status_label.setStyleSheet("color: #e74c3c;")
        if error == "NO_NETWORK":
            self.status_label.setText(connection_error_detail("NO_NETWORK"))
        elif error == "SERVER_UNREACHABLE":
            self.status_label.setText(tr("connection_failed", address=self._server_url))
        else:
            self.status_label.setText(error)

    def closeEvent(self, event):
        if self._worker:
            try:
                self._worker.disconnect()
            except Exception:
                pass
        super().closeEvent(event)
