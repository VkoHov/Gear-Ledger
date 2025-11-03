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


class SettingsWidget(QGroupBox):
    """Settings and configuration widget."""

    def __init__(self, parent=None):
        super().__init__("Settings", parent)

        # Callbacks
        self.on_catalog_changed: Callable[[str], None] | None = None
        self.on_results_changed: Callable[[str], None] | None = None
        self.on_manual_entry_requested: Callable[[str, float], None] | None = None
        self.on_generate_invoice_requested: Callable[[], None] | None = None

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
        # Leave empty initially - will auto-generate on first use
        self.btn_results = QPushButton("Browse…")
        self.btn_reset_results = QPushButton("Reset")
        self.btn_reset_results.setToolTip(
            "Clear selection and start with new empty results file"
        )
        self.btn_download = QPushButton("Download")
        self.btn_generate_invoice = QPushButton("Generate Invoice")
        self.btn_generate_invoice.setStyleSheet("background-color: #27ae60;")
        results_layout.addWidget(self.results_edit, 1)
        results_layout.addWidget(self.btn_results)
        results_layout.addWidget(self.btn_reset_results)
        results_layout.addWidget(self.btn_download)
        results_layout.addWidget(self.btn_generate_invoice)
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

        # Weight price setting
        weight_price_layout = QHBoxLayout()
        weight_price_label = QLabel("Weight Price (per kg):")
        weight_price_layout.addWidget(weight_price_label)
        self.weight_price_edit = QLineEdit()
        self.weight_price_edit.setPlaceholderText(
            "Enter price per kg (e.g., 1200) - REQUIRED"
        )
        self.weight_price_edit.setText("1200")  # Default value
        weight_price_layout.addWidget(self.weight_price_edit, 1)
        layout.addLayout(weight_price_layout)

        # Manual entry section
        manual_entry_box = QGroupBox("Manual Entry (without scanning)")
        manual_entry_layout = QVBoxLayout(manual_entry_box)

        # Part code input
        code_layout = QHBoxLayout()
        code_layout.addWidget(QLabel("Part Code:"))
        self.manual_part_code = QLineEdit()
        self.manual_part_code.setPlaceholderText("Enter part code (e.g., PK-5396)")
        code_layout.addWidget(self.manual_part_code, 1)
        manual_entry_layout.addLayout(code_layout)

        # Weight input
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("Weight (kg):"))
        self.manual_weight = QLineEdit()
        self.manual_weight.setPlaceholderText("Enter weight")
        weight_layout.addWidget(self.manual_weight, 1)
        manual_entry_layout.addLayout(weight_layout)

        # Add button
        self.btn_add_manual = QPushButton("Add to Results")
        manual_entry_layout.addWidget(self.btn_add_manual)

        layout.addWidget(manual_entry_box)

    def _setup_connections(self):
        """Set up signal connections."""
        self.btn_catalog.clicked.connect(self.pick_catalog_excel)
        self.btn_results.clicked.connect(self.pick_results_excel)
        self.btn_reset_results.clicked.connect(self.reset_results_excel)
        self.btn_download.clicked.connect(self.download_results_excel)
        self.btn_generate_invoice.clicked.connect(self.generate_invoice)
        self.btn_add_manual.clicked.connect(self.add_manual_entry)

    def set_catalog_changed_callback(self, callback: Callable[[str], None]):
        """Set callback for when catalog file changes."""
        self.on_catalog_changed = callback

    def set_results_changed_callback(self, callback: Callable[[str], None]):
        """Set callback for when results file changes."""
        self.on_results_changed = callback

    def set_manual_entry_requested_callback(
        self, callback: Callable[[str, float], None]
    ):
        """Set callback for when manual entry is requested."""
        self.on_manual_entry_requested = callback

    def set_generate_invoice_requested_callback(self, callback: Callable[[], None]):
        """Set callback for when invoice generation is requested."""
        self.on_generate_invoice_requested = callback

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

    def reset_results_excel(self):
        """Reset results file to a new empty file."""
        from PyQt6.QtWidgets import QMessageBox
        import datetime
        import pandas as pd
        from gearledger.config import ROOT_DIR
        from gearledger.result_ledger import COLUMNS

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Reset Results File",
            "This will clear the current results file selection and create a new empty file.\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Generate new filename with timestamp
            default_filename = (
                f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            new_path = str(ROOT_DIR / default_filename)

            # Create empty DataFrame with column headers
            df = pd.DataFrame(columns=COLUMNS)

            # Save empty file
            df.to_excel(new_path, index=False)

            # Update UI
            self.results_edit.setText(new_path)

            # Notify that the results path has changed
            if self.on_results_changed:
                self.on_results_changed(new_path)

            QMessageBox.information(
                self,
                "Reset Complete",
                f"New empty results file created:\n{new_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Reset Failed",
                f"Failed to create new results file:\n{str(e)}",
            )

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

    def generate_invoice(self):
        """Generate invoice from results file."""
        if self.on_generate_invoice_requested:
            self.on_generate_invoice_requested()

    def add_manual_entry(self):
        """Handle manual entry request."""
        from PyQt6.QtWidgets import QMessageBox

        part_code = self.manual_part_code.text().strip()
        weight_text = self.manual_weight.text().strip()

        if not part_code:
            QMessageBox.warning(
                self,
                "Manual Entry",
                "Please enter a part code.",
            )
            return

        if not weight_text:
            QMessageBox.warning(
                self,
                "Manual Entry",
                "Please enter the weight.",
            )
            return

        try:
            weight = float(weight_text)
            if weight <= 0:
                QMessageBox.warning(
                    self,
                    "Manual Entry",
                    "Weight must be greater than 0.",
                )
                return
        except ValueError:
            QMessageBox.warning(
                self,
                "Manual Entry",
                "Please enter a valid weight number.",
            )
            return

        if self.on_manual_entry_requested:
            self.on_manual_entry_requested(part_code, weight)

    def get_catalog_path(self) -> str:
        """Get the current catalog file path."""
        return self.catalog_edit.text().strip()

    def get_results_path(self) -> str:
        """Get the current results file path. Creates default if not set."""
        path = self.results_edit.text().strip()

        # If no path is set, create a default one with timestamp
        if not path:
            import datetime
            from gearledger.config import ROOT_DIR

            default_filename = (
                f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            path = str(ROOT_DIR / default_filename)

            # Update the UI with the new path (so it persists for this session)
            self.results_edit.setText(path)

            # Notify that the results path has changed
            if self.on_results_changed:
                self.on_results_changed(path)

        return path

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

    def get_weight_price(self) -> float:
        """Get the current weight price per kg."""
        try:
            return float(self.weight_price_edit.text().strip() or "0")
        except ValueError:
            return 0.0

    def is_weight_price_valid(self) -> bool:
        """Check if weight price is valid (not empty and > 0)."""
        try:
            price = float(self.weight_price_edit.text().strip() or "0")
            return price > 0
        except ValueError:
            return False

    def get_weight_price_error_message(self) -> str:
        """Get error message for invalid weight price."""
        text = self.weight_price_edit.text().strip()
        if not text:
            return "Weight Price is required. Please enter a price per kg."
        try:
            price = float(text)
            if price <= 0:
                return "Weight Price must be greater than 0."
        except ValueError:
            return "Weight Price must be a valid number."
        return ""

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        for widget in (
            self.catalog_edit,
            self.results_edit,
            self.rb_auto,
            self.rb_vendor,
            self.rb_oem,
            self.model_combo,
            self.weight_price_edit,
            self.btn_catalog,
            self.btn_results,
            self.btn_reset_results,
            self.btn_download,
            self.btn_generate_invoice,
            self.manual_part_code,
            self.manual_weight,
            self.btn_add_manual,
        ):
            widget.setEnabled(enabled)

    def validate_catalog(self) -> bool:
        """Validate that catalog file exists."""
        catalog = self.get_catalog_path()
        return bool(catalog and os.path.exists(catalog))

    def clear_manual_entry(self):
        """Clear manual entry fields."""
        self.manual_part_code.clear()
        self.manual_weight.clear()
