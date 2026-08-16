# gearledger/desktop/button_spinner.py
# -*- coding: utf-8 -*-
"""Small rotating circular spinner shown as a QPushButton's icon while a
background operation is in progress — used instead of a separate
progress-bar widget, so the loading state reads as part of the button
itself rather than a generic gray bar bolted on next to it."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QRectF, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
from PyQt6.QtWidgets import QPushButton


class ButtonSpinner:
    """Drives a rotating arc icon on a QPushButton. Call start()/stop()
    around a long-running operation; the button's original icon (usually
    none) is restored automatically when stopped."""

    def __init__(self, button: QPushButton, size: int = 14, color: str = "#ffffff"):
        self._button = button
        self._size = size
        self._color = QColor(color)
        self._angle = 0
        self._original_icon = button.icon()
        self._timer = QTimer(button)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._angle = 0
        self._button.setIconSize(QSize(self._size, self._size))
        self._tick()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self._button.setIcon(self._original_icon)

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self._button.setIcon(QIcon(self._make_pixmap()))

    def _make_pixmap(self) -> QPixmap:
        pm = QPixmap(self._size, self._size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        margin = 1.5
        rect = QRectF(margin, margin, self._size - 2 * margin, self._size - 2 * margin)
        # A 270-degree arc (not a full circle) so it visibly reads as a
        # spinning "loading wheel" rather than a static ring.
        painter.drawArc(rect, int(-self._angle * 16), int(270 * 16))
        painter.end()
        return pm
