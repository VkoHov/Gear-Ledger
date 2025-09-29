# gearledger/desktop/logs_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QTextEdit


class LogsWidget(QGroupBox):
    """Logs display widget."""

    def __init__(self, parent=None):
        super().__init__("Logs", parent)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        self.log_txt = QTextEdit()
        self.log_txt.setReadOnly(True)
        # Styling is handled by the global stylesheet

        layout.addWidget(self.log_txt)

    def append_logs(self, lines: List[str]):
        """Append log lines to the display."""
        for ln in lines or []:
            self.log_txt.append(ln)
        # Auto-scroll to bottom
        self.log_txt.moveCursor(QTextCursor.MoveOperation.End)

    def clear_logs(self):
        """Clear all logs."""
        self.log_txt.clear()

    def add_log(self, message: str):
        """Add a single log message."""
        self.log_txt.append(message)
        self.log_txt.moveCursor(QTextCursor.MoveOperation.End)
