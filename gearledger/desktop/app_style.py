# gearledger/desktop/app_style.py
# -*- coding: utf-8 -*-
"""Shared Qt stylesheet for the desktop app.

Extracted out of MainWindow._apply_styling() so any dialog can use the
same light theme regardless of whether it has a parent widget to inherit
a stylesheet from. This matters for LoginDialog specifically: the
app-launch gate shows it with no parent (MainWindow doesn't exist yet),
so without its own copy of this stylesheet it falls back to raw OS
theming (unreadable in dark mode, inconsistent everywhere else)."""
from __future__ import annotations


def get_app_stylesheet() -> str:
    return """
            QWidget {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-family: Arial, sans-serif;
                font-size: 11px;
            }

            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                color: #2c3e50;
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #34495e;
                background-color: #ffffff;
            }

            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                min-height: 20px;
            }

            QPushButton:hover {
                background-color: #2980b9;
            }

            QPushButton:pressed {
                background-color: #21618c;
            }

            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }

            QLineEdit {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                background-color: #ffffff;
                font-size: 11px;
                selection-background-color: #3498db;
            }

            QLineEdit:focus {
                border-color: #3498db;
            }

            QLineEdit:read-only {
                background-color: #ecf0f1;
                color: #7f8c8d;
            }

            QComboBox {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 6px;
                background-color: #ffffff;
                font-size: 11px;
                min-width: 100px;
            }

            QComboBox:focus {
                border-color: #3498db;
            }

            QComboBox::drop-down {
                border: none;
                width: 20px;
            }

            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #7f8c8d;
                margin-right: 5px;
            }

            QComboBox QAbstractItemView {
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
                selection-background-color: #3498db;
                selection-color: white;
            }

            QRadioButton {
                font-size: 11px;
                color: #2c3e50;
                spacing: 8px;
            }

            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
            }

            QRadioButton::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
            }

            QRadioButton::indicator:hover {
                border-color: #3498db;
            }

            QCheckBox {
                font-size: 11px;
                color: #2c3e50;
                spacing: 8px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
            }

            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }

            QCheckBox::indicator:hover {
                border-color: #3498db;
            }

            QListWidget {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ffffff;
                selection-background-color: #3498db;
                selection-color: white;
                font-size: 11px;
            }

            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #ecf0f1;
            }

            QListWidget::item:hover {
                background-color: #e8f4fd;
            }

            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }

            QTextEdit {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #0b1220;
                color: #e5e7eb;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
                padding: 8px;
            }

            QScrollArea {
                border: none;
                background-color: transparent;
            }

            QScrollBar:vertical {
                background-color: #ecf0f1;
                width: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background-color: #bdc3c7;
                border-radius: 6px;
                min-height: 20px;
            }

            QScrollBar::handle:vertical:hover {
                background-color: #95a5a6;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QSplitter::handle {
                background-color: #bdc3c7;
                height: 3px;
            }

            QSplitter::handle:hover {
                background-color: #3498db;
            }
        """
