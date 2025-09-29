# gearledger/desktop/results_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Dict, Any, List, Tuple, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QPushButton,
    QMessageBox,
)

from gearledger.config import DEFAULT_MIN_FUZZY


class ResultsWidget(QGroupBox):
    """Results display and fuzzy matching widget."""

    def __init__(self, parent=None):
        super().__init__("Result summary", parent)

        # Callbacks
        self.on_fuzzy_requested: Callable[[List[Tuple[str, str]]], None] | None = None
        self.on_manual_search_requested: Callable[[str], None] | None = None

        # State
        self._last_cand_order: List[Tuple[str, str]] = []

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Result display fields
        # Best visible
        best_vis_layout = QHBoxLayout()
        best_vis_layout.addWidget(QLabel("Best (visible):"))
        self.best_vis = QLineEdit()
        self.best_vis.setReadOnly(True)
        best_vis_layout.addWidget(self.best_vis, 1)
        layout.addLayout(best_vis_layout)

        # Best normalized
        best_norm_layout = QHBoxLayout()
        best_norm_layout.addWidget(QLabel("Best (normalized):"))
        self.best_norm = QLineEdit()
        self.best_norm.setReadOnly(True)
        best_norm_layout.addWidget(self.best_norm, 1)
        layout.addLayout(best_norm_layout)

        # Excel match
        match_layout = QHBoxLayout()
        match_layout.addWidget(QLabel("Excel match:"))
        self.match_line = QLineEdit()
        self.match_line.setReadOnly(True)
        match_layout.addWidget(self.match_line, 1)
        layout.addLayout(match_layout)

        # GPT cost
        cost_layout = QHBoxLayout()
        cost_layout.addWidget(QLabel("Est. GPT cost:"))
        self.cost_line = QLineEdit()
        self.cost_line.setReadOnly(True)
        cost_layout.addWidget(self.cost_line, 1)
        layout.addLayout(cost_layout)

        # Fuzzy matching section
        self.fuzzy_box = QGroupBox("No exact match — try fuzzy?")
        self.fuzzy_box.setVisible(False)

        fuzzy_layout = QVBoxLayout(self.fuzzy_box)
        fuzzy_layout.addWidget(QLabel("Likely candidates (from GPT/local ranking):"))

        self.cand_list = QListWidget()
        self.cand_list.setMinimumHeight(100)
        fuzzy_layout.addWidget(self.cand_list)

        self.chk_use_shown = QCheckBox("Limit fuzzy to shown candidates")
        fuzzy_layout.addWidget(self.chk_use_shown)

        self.btn_run_fuzzy = QPushButton("Run fuzzy match")
        fuzzy_layout.addWidget(
            self.btn_run_fuzzy, alignment=Qt.AlignmentFlag.AlignRight
        )

        layout.addWidget(self.fuzzy_box)

        # Manual code input section
        self.manual_box = QGroupBox("No match found — enter code manually?")
        self.manual_box.setVisible(False)

        manual_layout = QVBoxLayout(self.manual_box)
        manual_layout.addWidget(QLabel("Enter part code to search in invoice:"))

        # Manual input layout
        manual_input_layout = QHBoxLayout()
        self.manual_code_input = QLineEdit()
        self.manual_code_input.setPlaceholderText(
            "Enter part code (e.g., PK-5396, A 221 501 26 91)"
        )
        self.btn_search_manual = QPushButton("Search")
        manual_input_layout.addWidget(self.manual_code_input, 1)
        manual_input_layout.addWidget(self.btn_search_manual)
        manual_layout.addLayout(manual_input_layout)

        layout.addWidget(self.manual_box)

    def _setup_connections(self):
        """Set up signal connections."""
        self.btn_run_fuzzy.clicked.connect(self._on_run_fuzzy_clicked)
        self.btn_search_manual.clicked.connect(self._on_manual_search_clicked)
        self.manual_code_input.returnPressed.connect(self._on_manual_search_clicked)

    def set_fuzzy_requested_callback(
        self, callback: Callable[[List[Tuple[str, str]]], None]
    ):
        """Set callback for when fuzzy matching is requested."""
        self.on_fuzzy_requested = callback

    def set_manual_search_requested_callback(self, callback: Callable[[str], None]):
        """Set callback for when manual search is requested."""
        self.on_manual_search_requested = callback

    def clear_results(self):
        """Clear all result fields."""
        self.best_vis.clear()
        self.best_norm.clear()
        self.match_line.clear()
        self.cost_line.clear()
        self.fuzzy_box.setVisible(False)
        self.manual_box.setVisible(False)
        self.cand_list.clear()
        self.manual_code_input.clear()

    def set_best_visible(self, text: str):
        """Set the best visible result."""
        self.best_vis.setText(text or "")

    def set_best_normalized(self, text: str):
        """Set the best normalized result."""
        self.best_norm.setText(text or "")

    def set_match_result(self, text: str):
        """Set the match result."""
        self.match_line.setText(text or "")

    def set_cost(self, cost: float | None):
        """Set the GPT cost."""
        if isinstance(cost, (int, float)):
            self.cost_line.setText(f"${cost:.6f}")
        else:
            self.cost_line.setText("— (no API key)")

    def show_fuzzy_options(
        self, cand_order: List[Tuple[str, str]], prompt_fuzzy: bool = True
    ):
        """Show fuzzy matching options."""
        self._last_cand_order = cand_order or []

        if not prompt_fuzzy or not self._last_cand_order:
            return

        # Populate candidate list
        self.cand_list.clear()
        for vis, _norm in self._last_cand_order[:10]:
            QListWidgetItem(vis, self.cand_list)

        self.chk_use_shown.setChecked(True)
        self.fuzzy_box.setVisible(True)

        # Ask user if they want to start fuzzy matching
        preview = "\n".join(f"• {v}" for v, _ in self._last_cand_order[:5]) or "—"
        choice = QMessageBox.question(
            self,
            "Start fuzzy matching?",
            "No exact match found.\n\n"
            "Top candidates to try with fuzzy matching:\n"
            f"{preview}\n\n"
            "Start fuzzy matching now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if choice == QMessageBox.StandardButton.Yes:
            self._on_run_fuzzy_clicked()

    def hide_fuzzy_options(self):
        """Hide fuzzy matching options."""
        self.fuzzy_box.setVisible(False)

    def show_manual_input(self):
        """Show manual code input option."""
        self.manual_box.setVisible(True)

    def hide_manual_input(self):
        """Hide manual code input option."""
        self.manual_box.setVisible(False)

    def _on_run_fuzzy_clicked(self):
        """Handle fuzzy matching button click."""
        if not self.on_fuzzy_requested or not self._last_cand_order:
            return

        # Get candidates to use
        cand = self._last_cand_order
        if self.chk_use_shown.isChecked():
            shown_texts = set(
                self.cand_list.item(i).text() for i in range(self.cand_list.count())
            )
            cand = [
                (vis, norm)
                for (vis, norm) in self._last_cand_order
                if vis in shown_texts
            ]

        self.on_fuzzy_requested(cand)

    def _on_manual_search_clicked(self):
        """Handle manual search button click."""
        if not self.on_manual_search_requested:
            return

        code = self.manual_code_input.text().strip()
        if not code:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Manual Search",
                "Please enter a part code to search.",
            )
            return

        self.on_manual_search_requested(code)

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable controls."""
        self.cand_list.setEnabled(enabled)
        self.chk_use_shown.setEnabled(enabled)
        self.btn_run_fuzzy.setEnabled(enabled and self.fuzzy_box.isVisible())
        self.manual_code_input.setEnabled(enabled)
        self.btn_search_manual.setEnabled(enabled and self.manual_box.isVisible())

    def update_fuzzy_result(self, client: str, artikul: str):
        """Update result with fuzzy match."""
        if client and artikul:
            self.match_line.setText(f"{artikul} → {client}")
            self.hide_fuzzy_options()
            self.hide_manual_input()
        else:
            QMessageBox.information(self, "Fuzzy", "No fuzzy match found.")

    def update_manual_result(self, client: str, artikul: str):
        """Update result with manual search match."""
        if client and artikul:
            self.match_line.setText(f"{artikul} → {client}")
            self.hide_manual_input()
        else:
            QMessageBox.information(
                self, "Manual Search", "No match found for the entered code."
            )
