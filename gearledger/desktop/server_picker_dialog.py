# gearledger/desktop/server_picker_dialog.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)

from gearledger.network_discovery import DiscoveredServer
from .translations import tr


class ServerPickerDialog(QDialog):
    """Simple picker shown when discovery finds more than one server.

    Shows each server's friendly display name only (never raw IP:port) —
    warehouse workers shouldn't need to recognize or type a network
    address, just pick the machine by name.
    """

    def __init__(self, servers: List[DiscoveredServer], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("select_server_title"))
        self.resize(360, 320)
        self.selected_server: Optional[DiscoveredServer] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        label = QLabel(tr("select_server_prompt"))
        label.setWordWrap(True)
        layout.addWidget(label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                font-size: 13px;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
            }
            QListWidget::item {
                padding: 10px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """
        )
        for server in servers:
            display_name = (server.name or "").strip() or tr("server")
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, server)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self._on_accept)
        layout.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QPushButton(tr("cancel"))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        select_btn = QPushButton(tr("select"))
        select_btn.setStyleSheet(
            "background-color: #3498db; color: white; font-weight: bold; padding: 8px 20px;"
        )
        select_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(select_btn)

        layout.addLayout(btn_row)

    def _on_accept(self):
        item = self.list_widget.currentItem()
        if item is not None:
            self.selected_server = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
