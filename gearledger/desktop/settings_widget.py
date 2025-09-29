# gearledger/desktop/settings_widget.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from typing import Callable

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QRadioButton,
    QButtonGroup,
)

from gearledger.config import DEFAULT_MODEL, DEFAULT_TARGET

MODELS = ["gpt-4o-mini", "gpt-4o"]
RESULT_SHEET = os.getenv("RESULT_SHEET", "result.xlsx")


class SettingsWidget(QGroupBox):
    """Settings and configuration widget."""

    def __init__(self, parent=None):
        super().__init__("Settings", parent)

        # Callbacks
        self.on_catalog_changed: Callable[[str], None] | None = None
        self.on_results_changed: Callable[[str], None] | None = None

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Catalog Excel file
        catalog_layout = QHBoxLayout()
        catalog_layout.addWidget(QLabel("Catalog Excel (lookup):"))
        self.catalog_edit = QLineEdit()
        self.btn_catalog = QPushButton("Browse…")
        catalog_layout.addWidget(self.catalog_edit, 1)
        catalog_layout.addWidget(self.btn_catalog)
        layout.addLayout(catalog_layout)

        # Results Excel file
        results_layout = QHBoxLayout()
        results_layout.addWidget(QLabel("Results Excel (ledger):"))
        self.results_edit = QLineEdit()
        self.results_edit.setText(RESULT_SHEET if RESULT_SHEET else "")
        self.btn_results = QPushButton("Browse…")
        self.btn_download = QPushButton("Download")
        results_layout.addWidget(self.results_edit, 1)
        results_layout.addWidget(self.btn_results)
        results_layout.addWidget(self.btn_download)
        layout.addLayout(results_layout)

        # Target selection
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("Target:"))
        self.rb_auto = QRadioButton("auto")
        self.rb_vendor = QRadioButton("vendor")
        self.rb_oem = QRadioButton("oem")
        self.tgroup = QButtonGroup(self)
        for rb in (self.rb_auto, self.rb_vendor, self.rb_oem):
            self.tgroup.addButton(rb)

        # Set default target
        if DEFAULT_TARGET == "vendor":
            self.rb_vendor.setChecked(True)
        elif DEFAULT_TARGET == "oem":
            self.rb_oem.setChecked(True)
        else:
            self.rb_auto.setChecked(True)

        target_layout.addWidget(self.rb_auto)
        target_layout.addWidget(self.rb_vendor)
        target_layout.addWidget(self.rb_oem)
        target_layout.addStretch(1)
        layout.addLayout(target_layout)

        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        self.model_combo.setCurrentText(
            DEFAULT_MODEL if DEFAULT_MODEL in MODELS else MODELS[0]
        )
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch(1)
        layout.addLayout(model_layout)

    def _setup_connections(self):
        """Set up signal connections."""
        self.btn_catalog.clicked.connect(self.pick_catalog_excel)
        self.btn_results.clicked.connect(self.pick_results_excel)
        self.btn_download.clicked.connect(self.download_results_excel)

    def set_catalog_changed_callback(self, callback: Callable[[str], None]):
        """Set callback for when catalog file changes."""
        self.on_catalog_changed = callback

    def set_results_changed_callback(self, callback: Callable[[str], None]):
        """Set callback for when results file changes."""
        self.on_results_changed = callback

    def pick_catalog_excel(self):
        """Open file dialog to select catalog Excel file."""
        from PyQt6.QtWidgets import QFileDialog

        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Catalog Excel (lookup)",
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            self.catalog_edit.setText(fn)
            if self.on_catalog_changed:
                self.on_catalog_changed(fn)

    def pick_results_excel(self):
        """Open file dialog to select results Excel file."""
        from PyQt6.QtWidgets import QFileDialog

        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Results Excel (ledger)",
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            self.results_edit.setText(fn)
            if self.on_results_changed:
                self.on_results_changed(fn)

    def download_results_excel(self):
        """Save results Excel file to a chosen location."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import shutil

        current_path = self.get_results_path()
        if not current_path or not os.path.exists(current_path):
            QMessageBox.warning(
                self,
                "Download Results",
                "No results file found. Please run some OCR operations first to generate results.",
            )
            return

        # Get save location
        fn, _ = QFileDialog.getSaveFileName(
            self,
            "Save Results Excel File",
            filter="Excel (*.xlsx);;All files (*)",
            initialFilter="Excel (*.xlsx)",
        )

        if fn:
            try:
                # Ensure .xlsx extension
                if not fn.endswith(".xlsx"):
                    fn += ".xlsx"

                # Copy the file
                shutil.copy2(current_path, fn)

                QMessageBox.information(
                    self,
                    "Download Complete",
                    f"Results file saved successfully to:\n{fn}",
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Download Failed",
                    f"Failed to save results file:\n{str(e)}",
                )

    def get_catalog_path(self) -> str:
        """Get the current catalog file path."""
        return self.catalog_edit.text().strip()

    def get_results_path(self) -> str:
        """Get the current results file path."""
        return self.results_edit.text().strip() or RESULT_SHEET

    def get_target(self) -> str:
        """Get the current target selection."""
        if self.rb_vendor.isChecked():
            return "vendor"
        if self.rb_oem.isChecked():
            return "oem"
        return "auto"

    def get_model(self) -> str:
        """Get the current model selection."""
        return self.model_combo.currentText()

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        for widget in (
            self.catalog_edit,
            self.results_edit,
            self.rb_auto,
            self.rb_vendor,
            self.rb_oem,
            self.model_combo,
            self.btn_catalog,
            self.btn_results,
            self.btn_download,
        ):
            widget.setEnabled(enabled)

    def validate_catalog(self) -> bool:
        """Validate that catalog file exists."""
        catalog = self.get_catalog_path()
        return bool(catalog and os.path.exists(catalog))
