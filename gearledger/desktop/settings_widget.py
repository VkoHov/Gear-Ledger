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
)

from gearledger.desktop.translations import tr


class SettingsWidget(QGroupBox):
    """Settings and configuration widget."""

    def __init__(self, parent=None):
        super().__init__(tr("settings_group"), parent)

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
        catalog_layout.addWidget(QLabel(tr("catalog_excel_lookup")))
        self.catalog_edit = QLineEdit()
        self.btn_catalog = QPushButton(tr("browse"))
        catalog_layout.addWidget(self.catalog_edit, 1)
        catalog_layout.addWidget(self.btn_catalog)
        layout.addLayout(catalog_layout)

        # Catalog info (client mode only - shows server catalog status)
        catalog_info_layout = QHBoxLayout()
        self.catalog_info_label = QLabel("")
        self.catalog_info_label.setWordWrap(True)
        self.catalog_info_label.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; padding: 4px;"
        )
        self.catalog_info_label.setVisible(False)  # Only visible in client mode
        catalog_info_layout.addWidget(self.catalog_info_label, 1)
        layout.addLayout(catalog_info_layout)

        # Results Excel file
        results_layout = QHBoxLayout()
        results_layout.addWidget(QLabel(tr("results_excel_ledger")))
        self.results_edit = QLineEdit()
        # Leave empty initially - will auto-generate on first use
        self.btn_results = QPushButton(tr("browse"))
        self.btn_reset_results = QPushButton(tr("reset"))
        self.btn_reset_results.setToolTip(tr("reset_tooltip"))
        self.btn_download = QPushButton(tr("download"))
        self.btn_generate_invoice = QPushButton(tr("generate_invoice"))
        self.btn_generate_invoice.setStyleSheet("background-color: #27ae60;")
        results_layout.addWidget(self.results_edit, 1)
        results_layout.addWidget(self.btn_results)
        results_layout.addWidget(self.btn_reset_results)
        results_layout.addWidget(self.btn_download)
        results_layout.addWidget(self.btn_generate_invoice)
        layout.addLayout(results_layout)

        # Manual entry section (hidden by default, shown only in Manual tab)
        self.manual_entry_box = QGroupBox(tr("manual_entry_without_scanning"))
        self.manual_entry_box.setVisible(False)  # Hide in Automated tab
        manual_entry_layout = QVBoxLayout(self.manual_entry_box)

        # Part code input
        code_layout = QHBoxLayout()
        code_layout.addWidget(QLabel(tr("part_code_label")))
        self.manual_part_code = QLineEdit()
        self.manual_part_code.setPlaceholderText(tr("part_code_placeholder_short"))
        code_layout.addWidget(self.manual_part_code, 1)
        manual_entry_layout.addLayout(code_layout)

        # Weight input
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel(tr("weight_kg_label")))
        self.manual_weight = QLineEdit()
        self.manual_weight.setPlaceholderText(tr("enter_weight"))
        weight_layout.addWidget(self.manual_weight, 1)
        manual_entry_layout.addLayout(weight_layout)

        # Add button
        self.btn_add_manual = QPushButton(tr("add_to_results"))
        manual_entry_layout.addWidget(self.btn_add_manual)

        layout.addWidget(self.manual_entry_box)

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

    def set_results_refresh_callback(self, callback: Callable[[], None]):
        """Set callback to force refresh of results pane."""
        self.on_results_refresh = callback

    def pick_catalog_excel(self):
        """Open file dialog to select catalog Excel file."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd

        fn, _ = QFileDialog.getOpenFileName(
            self,
            tr("choose_catalog_excel"),
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            # Validate that the file can be read
            try:
                # Try to read the file to check if it's corrupted
                df = pd.read_excel(
                    fn, nrows=10
                )  # Read first 10 rows to validate structure
            except Exception as e:
                error_msg = str(e)
                # Show user-friendly error popup
                file_name = os.path.basename(fn)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle(tr("excel_file_problem"))
                msg.setText(tr("catalog_cannot_open"))
                msg.setInformativeText(tr("catalog_corrupted_msg", file=file_name))
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()
                return  # Don't set the file path if it's corrupted

            # Validate that the file is not empty (has data rows)
            if len(df) == 0:
                file_name = os.path.basename(fn)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle(tr("empty_catalog_file"))
                msg.setText(tr("catalog_empty"))
                msg.setInformativeText(tr("catalog_empty_msg", file=file_name))
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()
                return  # Don't set the file path if it's empty

            # Validate that the file has required columns
            artikul_col = None
            client_col = None

            # Check for artikul/part-code column (required)
            for c in df.columns:
                lc = str(c).strip().lower()
                if artikul_col is None and any(
                    k in lc
                    for k in [
                        "номер",
                        "арт",
                        "artikul",
                        "article",
                        "part",
                        "sku",
                        "code",
                        "number",
                    ]
                ):
                    artikul_col = c
                if client_col is None and any(
                    k in lc
                    for k in ["клиент", "client", "name", "buyer", "vendor", "customer"]
                ):
                    client_col = c

            # Check exact names (prioritize Номер over Артикул)
            if "Номер" in df.columns:
                artikul_col = "Номер"
            elif "Артикул" in df.columns:
                artikul_col = "Артикул"
            if "Клиент" in df.columns:
                client_col = "Клиент"

            # Validate required column exists
            if not artikul_col:
                file_name = os.path.basename(fn)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle(tr("invalid_catalog_file"))
                msg.setText(tr("catalog_missing_columns"))
                msg.setInformativeText(
                    tr("catalog_missing_columns_msg", file=file_name)
                )
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()
                return  # Don't set the file path if it's missing required columns

            # File is valid, set it
            self.catalog_edit.setText(fn)
            if self.on_catalog_changed:
                self.on_catalog_changed(fn)

            # Automatically upload to server if in server mode
            from gearledger.data_layer import get_network_mode

            mode = get_network_mode()
            if mode == "server":
                # Upload catalog to server automatically
                self._upload_catalog_to_server_auto(fn)

    def pick_results_excel(self):
        """Open file dialog to select results Excel file."""
        from PyQt6.QtWidgets import QFileDialog

        fn, _ = QFileDialog.getOpenFileName(
            self,
            tr("choose_results_excel"),
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            self.results_edit.setText(fn)
            if self.on_results_changed:
                self.on_results_changed(fn)

    def reset_results_excel(self):
        """Reset results file to a new empty file (or clear database in network mode)."""
        from PyQt6.QtWidgets import QMessageBox
        import datetime
        import pandas as pd
        from gearledger.config import ROOT_DIR
        from gearledger.result_ledger import COLUMNS

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            tr("reset_results_file"),
            tr("reset_results_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Check if in network mode - clear database instead
            from gearledger.data_layer import get_network_mode

            mode = get_network_mode()

            if mode == "server":
                # Clear the database
                from gearledger.database import get_database

                db = get_database()
                count = db.clear_all_results()
                print(f"[RESET] Cleared {count} results from database")

                # Force refresh results pane
                if hasattr(self, "on_results_refresh") and self.on_results_refresh:
                    self.on_results_refresh()

                QMessageBox.information(
                    self,
                    tr("reset_complete"),
                    tr("reset_complete_msg", path=f"Database ({count} items cleared)"),
                )
                return
            elif mode == "client":
                # Clear results on server via API
                from gearledger.api_client import get_client

                client = get_client()
                if client and client.is_connected():
                    count = client.clear_all_results()
                    print(f"[RESET] Cleared {count} results from server")

                    # Force refresh results pane
                    if hasattr(self, "on_results_refresh") and self.on_results_refresh:
                        self.on_results_refresh()

                    QMessageBox.information(
                        self,
                        tr("reset_complete"),
                        tr(
                            "reset_complete_msg", path=f"Server ({count} items cleared)"
                        ),
                    )
                    return
                else:
                    QMessageBox.warning(
                        self,
                        tr("reset_failed"),
                        "Not connected to server",
                    )
                    return

            # Standalone mode - create new Excel file
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
                tr("reset_complete"),
                tr("reset_complete_msg", path=new_path),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("reset_failed"),
                tr("reset_failed_msg", error=str(e)),
            )

    def download_results_excel(self):
        """Save results Excel file to a chosen location."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import shutil

        current_path = self.get_results_path()
        if not current_path or not os.path.exists(current_path):
            QMessageBox.warning(
                self,
                tr("download_results"),
                tr("no_results_file"),
            )
            return

        # Get save location
        fn, _ = QFileDialog.getSaveFileName(
            self,
            tr("save_results_excel"),
            filter=tr("excel_filter"),
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
                    tr("download_complete"),
                    tr("download_complete_msg", path=fn),
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    tr("download_failed"),
                    tr("download_failed_msg", error=str(e)),
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
                tr("manual_entry"),
                tr("enter_part_code"),
            )
            return

        if not weight_text:
            QMessageBox.warning(
                self,
                tr("manual_entry"),
                tr("enter_the_weight"),
            )
            return

        try:
            weight = float(weight_text)
            if weight <= 0:
                QMessageBox.warning(
                    self,
                    tr("manual_entry"),
                    tr("weight_greater_than_zero"),
                )
                return
        except ValueError:
            QMessageBox.warning(
                self,
                tr("manual_entry"),
                tr("enter_valid_weight"),
            )
            return

        if self.on_manual_entry_requested:
            self.on_manual_entry_requested(part_code, weight)

    def get_catalog_path(self) -> str:
        """Get the current catalog file path."""
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client
        from gearledger.desktop.settings_manager import APP_DIR

        mode = get_network_mode()

        # In client mode, use server catalog if available
        if mode == "client":
            client = get_client()
            if client and client.is_connected():
                # Check if we have a cached server catalog
                catalog_cache_dir = os.path.join(APP_DIR, "catalog_cache")
                os.makedirs(catalog_cache_dir, exist_ok=True)
                cached_catalog = os.path.join(catalog_cache_dir, "server_catalog.xlsx")

                # If cached catalog exists, use it
                if os.path.exists(cached_catalog):
                    return cached_catalog

            # Fallback to local catalog if server catalog not available
            return self.catalog_edit.text().strip()

        # In server/standalone mode, use local catalog
        return self.catalog_edit.text().strip()

    def _upload_catalog_to_server_auto(self, catalog_path: str):
        """Automatically upload catalog file to server (called when catalog is selected in server mode)."""
        from gearledger.server import get_server

        if not catalog_path or not os.path.exists(catalog_path):
            return

        server = get_server()
        if not server or not server.is_running():
            print(
                "[SETTINGS] Server is not running, cannot upload catalog automatically"
            )
            return

        import requests

        try:
            with open(catalog_path, "rb") as f:
                files = {
                    "file": (
                        os.path.basename(catalog_path),
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                }
                response = requests.post(
                    f"{server.get_server_url()}/api/catalog",
                    files=files,
                    timeout=30,
                )
                result = response.json()

                if result.get("ok"):
                    print(
                        f"[SETTINGS] ✓ Catalog uploaded to server automatically: {result.get('filename')}"
                    )
                else:
                    print(
                        f"[SETTINGS] ✗ Failed to upload catalog: {result.get('error', 'Unknown error')}"
                    )
        except Exception as e:
            print(f"[SETTINGS] Error uploading catalog automatically: {e}")

    def update_catalog_ui_for_mode(self):
        """Update catalog UI based on network mode."""
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client

        mode = get_network_mode()

        if mode == "client":
            # In client mode: hide catalog selection, show server catalog status
            if hasattr(self, "catalog_label"):
                self.catalog_label.setVisible(False)
            self.catalog_edit.setVisible(False)
            self.btn_catalog.setVisible(False)
            self.catalog_info_label.setVisible(True)

            # Update catalog status from server
            client = get_client()
            if client and client.is_connected():
                info = client.get_catalog_info()
                if info.get("ok") and info.get("exists"):
                    filename = info.get("filename", "catalog.xlsx")
                    size = info.get("size", 0)
                    size_mb = size / (1024 * 1024) if size > 0 else 0
                    self.catalog_info_label.setText(
                        f"📋 Catalog from server: {filename} ({size_mb:.2f} MB)"
                    )
                    self.catalog_info_label.setStyleSheet(
                        "color: #27ae60; font-size: 11px; padding: 4px;"
                    )
                else:
                    self.catalog_info_label.setText(
                        "📋 No catalog on server. Please upload on server."
                    )
                    self.catalog_info_label.setStyleSheet(
                        "color: #7f8c8d; font-size: 11px; padding: 4px;"
                    )
            else:
                self.catalog_info_label.setText("📋 Not connected to server")
                self.catalog_info_label.setStyleSheet(
                    "color: #e74c3c; font-size: 11px; padding: 4px;"
                )
        else:
            # In server/standalone mode: show catalog selection, hide status
            if hasattr(self, "catalog_label"):
                self.catalog_label.setVisible(True)
            self.catalog_edit.setVisible(True)
            self.btn_catalog.setVisible(True)
            self.catalog_info_label.setVisible(False)

    def get_results_path(self) -> str:
        """Get the current results file path. Uses default from settings if not set."""
        path = self.results_edit.text().strip()

        # If no path is set, use default from settings or create one
        if not path:
            try:
                from gearledger.desktop.settings_manager import (
                    load_settings,
                    get_default_result_file,
                )
                import os

                settings = load_settings()
                # Use configured default, or fall back to app data directory
                if settings.default_result_file:
                    path = settings.default_result_file
                else:
                    path = get_default_result_file()

                # Ensure the file exists (create empty if it doesn't) - do this lazily
                if not os.path.exists(path):
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    # Create empty file asynchronously to avoid blocking startup
                    # Import pandas only when needed
                    try:
                        import pandas as pd
                        from gearledger.result_ledger import COLUMNS

                        df = pd.DataFrame(columns=COLUMNS)
                        df.to_excel(path, index=False)
                    except Exception:
                        # If pandas fails, just create empty file - will be created on first write
                        pass

                # Update the UI with the new path (so it persists for this session)
                self.results_edit.setText(path)

                # Notify that the results path has changed
                if self.on_results_changed:
                    self.on_results_changed(path)

            except Exception as e:
                # Fallback to old behavior if settings manager fails
                import datetime
                from gearledger.config import ROOT_DIR

                default_filename = (
                    f"results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                path = str(ROOT_DIR / default_filename)
                self.results_edit.setText(path)
                if self.on_results_changed:
                    self.on_results_changed(path)

        return path

    def get_target(self) -> str:
        """Get the current target selection from settings manager."""
        try:
            from gearledger.desktop.settings_manager import load_settings

            settings = load_settings()
            return settings.default_target
        except Exception:
            from gearledger.config import DEFAULT_TARGET

            return DEFAULT_TARGET

    def get_model(self) -> str:
        """Get the current model selection from settings manager."""
        try:
            from gearledger.desktop.settings_manager import load_settings

            settings = load_settings()
            return settings.openai_model
        except Exception:
            from gearledger.config import DEFAULT_MODEL

            return DEFAULT_MODEL

    def get_weight_price(self) -> float:
        """Get the current weight price per kg from settings manager."""
        try:
            from gearledger.desktop.settings_manager import load_settings

            settings = load_settings()
            return settings.price_per_kg
        except Exception:
            return 1200.0

    def is_weight_price_valid(self) -> bool:
        """Check if weight price is valid (not empty and > 0)."""
        price = self.get_weight_price()
        return price > 0

    def get_weight_price_error_message(self) -> str:
        """Get error message for invalid weight price."""
        price = self.get_weight_price()
        if price <= 0:
            return tr("weight_price_error")
        return ""

    def set_controls_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        for widget in (
            self.catalog_edit,
            self.results_edit,
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
