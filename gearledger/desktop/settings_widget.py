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
        self.on_check_completeness_requested: Callable[[], None] | None = None

        self._setup_ui()
        self._setup_connections()
        self._update_last_action_label()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)

        # Catalog Excel file
        catalog_layout = QHBoxLayout()
        self.catalog_label = QLabel(tr("catalog_excel_lookup"))
        catalog_layout.addWidget(self.catalog_label)
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
        self.results_label = QLabel(tr("results_excel_ledger"))
        results_layout.addWidget(self.results_label)
        self.results_edit = QLineEdit()
        # Leave empty initially - will auto-generate on first use
        self.btn_results = QPushButton(tr("browse"))
        self.btn_import_results = QPushButton(tr("import_results"))
        self.btn_import_results.setToolTip(tr("import_results_tooltip"))
        self.btn_reset_results = QPushButton(tr("reset"))
        self.btn_reset_results.setToolTip(tr("reset_tooltip"))
        self.btn_versions = QPushButton(tr("versions"))
        self.btn_versions.setToolTip(tr("versions_tooltip"))
        self.btn_download = QPushButton(tr("download"))
        self.btn_generate_invoice = QPushButton(tr("generate_invoice"))
        self.btn_generate_invoice.setStyleSheet("background-color: #27ae60;")
        self.btn_check_completeness = QPushButton(tr("check_completeness"))
        self.btn_check_completeness.setToolTip(tr("check_completeness_tooltip"))
        results_layout.addWidget(self.results_edit, 1)
        results_layout.addWidget(self.btn_results)
        results_layout.addWidget(self.btn_import_results)
        results_layout.addWidget(self.btn_reset_results)
        results_layout.addWidget(self.btn_versions)
        results_layout.addWidget(self.btn_download)
        results_layout.addWidget(self.btn_generate_invoice)
        results_layout.addWidget(self.btn_check_completeness)
        layout.addLayout(results_layout)

        # Results info (client mode only - shows server results status)
        results_info_layout = QHBoxLayout()
        self.results_info_label = QLabel("")
        self.results_info_label.setWordWrap(True)
        self.results_info_label.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; padding: 4px;"
        )
        self.results_info_label.setVisible(False)  # Only visible in client mode
        results_info_layout.addWidget(self.results_info_label, 1)
        layout.addLayout(results_info_layout)

        # Last Reset/Restore breadcrumb (standalone/server only, not client —
        # informational provenance, not true version tracking)
        last_action_layout = QHBoxLayout()
        self.last_action_label = QLabel("")
        self.last_action_label.setWordWrap(True)
        self.last_action_label.setStyleSheet(
            "color: #7f8c8d; font-size: 11px; padding: 0 4px 4px 4px;"
        )
        last_action_layout.addWidget(self.last_action_label, 1)
        layout.addLayout(last_action_layout)

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
        self.btn_import_results.clicked.connect(self.import_results_excel)
        self.btn_reset_results.clicked.connect(self.reset_results_excel)
        self.btn_versions.clicked.connect(self.show_versions_dialog)
        self.btn_download.clicked.connect(self.download_results_excel)
        self.btn_generate_invoice.clicked.connect(self.generate_invoice)
        self.btn_check_completeness.clicked.connect(self.check_completeness)
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

    def set_check_completeness_requested_callback(self, callback: Callable[[], None]):
        """Set callback for when the completeness check is requested."""
        self.on_check_completeness_requested = callback

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

    def import_results_excel(self):
        """Import an external Excel file's rows into the database (server
        mode only — standalone just uses Browse directly).

        Validates the file has our expected column structure first, then
        archives whatever's currently in the database (same safety net
        Restore uses, including skipping a redundant duplicate archive)
        before loading the imported rows in.
        """
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import pandas as pd

        fn, _ = QFileDialog.getOpenFileName(
            self,
            tr("import_results_title"),
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if not fn:
            return

        try:
            header_df = pd.read_excel(fn, nrows=0)
        except Exception as e:
            QMessageBox.critical(
                self, tr("import_failed"), tr("import_failed_msg", error=str(e))
            )
            return

        required_cols = ["Артикул", "Клиент", "Количество"]
        missing = [c for c in required_cols if c not in header_df.columns]
        if missing:
            QMessageBox.critical(
                self,
                tr("import_invalid_title"),
                tr("import_invalid_msg", columns=", ".join(missing)),
            )
            return

        reply = QMessageBox.question(
            self,
            tr("import_confirm_title"),
            tr("import_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from gearledger.database import get_database
        from gearledger.desktop.settings_manager import (
            get_versions_dir,
            record_last_results_action,
        )

        db = get_database()
        result = db.restore_from_version(fn, get_versions_dir())
        if not result.get("ok"):
            QMessageBox.critical(
                self,
                tr("import_failed"),
                tr("import_failed_msg", error=result.get("error", "")),
            )
            return

        self._notify_server_clients_data_changed()
        # Store the full path (not just a basename like restore does) since
        # an imported file can live anywhere on disk, not just our own
        # versions folder.
        record_last_results_action("import", fn)
        self._update_last_action_label()
        if hasattr(self, "on_results_refresh") and self.on_results_refresh:
            self.on_results_refresh()

        QMessageBox.information(
            self,
            tr("import_complete_title"),
            tr("import_complete_msg", count=result.get("restored", 0)),
        )

    def _archive_active_file_if_needed(self, path: str):
        """Move *path* into the versions folder if it exists and has data.

        Uses a collision-safe timestamp suffix so two archives created within
        the same second don't silently overwrite one another. Skips
        archiving if the data is unchanged since the last Restore —
        otherwise restoring back and forth with nothing recorded in
        between piles up duplicate versions.
        """
        import shutil
        import pandas as pd
        from gearledger.desktop.settings_manager import get_versions_dir
        from gearledger.result_ledger import unique_version_path

        if not os.path.exists(path):
            return
        try:
            had_rows = len(pd.read_excel(path)) > 0
        except Exception:
            had_rows = True  # unreadable — archive rather than silently drop
        if not had_rows:
            return

        if self._is_redundant_of_last_restore(path):
            return

        shutil.move(path, unique_version_path(get_versions_dir()))

    def _is_redundant_of_last_restore(self, current_path: str) -> bool:
        """True if current_path's data is unchanged since the last Restore —
        i.e. archiving it now would just duplicate the version already
        restored from.

        Deliberately restore-only, not import: an imported file can live
        anywhere on disk (outside our control), so import always creates
        its own internal version copy rather than relying on the external
        source file staying put.
        """
        try:
            from gearledger.desktop.settings_manager import (
                load_settings,
                get_versions_dir,
            )
            from gearledger.result_ledger import get_all_results_excel, rows_equal

            settings = load_settings()
            if settings.last_results_action != "restore":
                return False
            source_path = os.path.join(
                get_versions_dir(), settings.last_results_action_detail
            )
            if not os.path.exists(source_path):
                return False
            return rows_equal(
                get_all_results_excel(current_path),
                get_all_results_excel(source_path),
            )
        except Exception:
            return False

    def _set_active_results_path(self, path: str):
        """Point the app at *path* as the active results file and remember it."""
        from gearledger.desktop.settings_manager import load_settings, save_settings

        self.results_edit.setText(path)
        if self.on_results_changed:
            self.on_results_changed(path)

        # Persist so relaunching the app keeps using this file instead of
        # reverting to whatever default_result_file was last saved
        settings = load_settings()
        settings.default_result_file = path
        save_settings(settings)

    def _notify_server_clients_data_changed(self):
        """Broadcast a results_changed SSE event to any connected clients.

        Server-mode actions triggered locally by the operator (Reset,
        Restore) call the database directly in the same process, bypassing
        the HTTP API routes that already broadcast this event on remote
        writes — so without this, connected clients would keep looking at
        stale data until they happened to reconnect.
        """
        try:
            from gearledger.server import get_server

            server = get_server()
            if server and server.is_running():
                server._data_version += 1
                server._broadcast_sse_event(
                    {"type": "results_changed", "version": server._data_version}
                )
        except Exception:
            pass

    def _update_last_action_label(self):
        """Refresh the "last Reset/Restore" breadcrumb from settings.

        Purely informational provenance (when + what) — not true version
        tracking, since the live data can diverge from that version the
        moment anything new is recorded afterward.
        """
        try:
            from gearledger.desktop.settings_manager import load_settings
            import datetime

            settings = load_settings()
            action = settings.last_results_action
            if not action:
                self.last_action_label.setText("")
                return

            try:
                dt = datetime.datetime.fromisoformat(settings.last_results_action_at)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = settings.last_results_action_at

            key_map = {
                "restore": "last_action_restore",
                "import": "last_action_import",
            }
            key = key_map.get(action, "last_action_reset")
            detail = settings.last_results_action_detail
            if action == "import":
                detail = os.path.basename(detail)  # stored as full path
            self.last_action_label.setText(tr(key, detail=detail, time=time_str))
        except Exception:
            self.last_action_label.setText("")

    def reset_results_excel(self):
        """Reset results file to a new empty file (or clear database in network mode)."""
        from PyQt6.QtWidgets import QMessageBox
        import pandas as pd
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
                # Archive current results to a version file, then clear the database
                from gearledger.database import get_database
                from gearledger.desktop.settings_manager import (
                    get_versions_dir,
                    record_last_results_action,
                )

                db = get_database()
                count = db.archive_results_before_clear(get_versions_dir())
                print(f"[RESET] Archived and cleared {count} results from database")
                self._notify_server_clients_data_changed()
                record_last_results_action("reset", f"{count} items cleared")
                self._update_last_action_label()

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

            # Standalone mode - archive the current file (if it has data) as a
            # version, then recreate a fresh empty file at the same path.
            from gearledger.desktop.settings_manager import (
                get_default_result_file,
                record_last_results_action,
            )

            target_path = self.get_results_path() or get_default_result_file()
            self._archive_active_file_if_needed(target_path)

            # Create empty DataFrame with column headers, saved at the same
            # path so it keeps being the one relaunch picks up
            df = pd.DataFrame(columns=COLUMNS)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            df.to_excel(target_path, index=False)

            self._set_active_results_path(target_path)
            record_last_results_action("reset", os.path.basename(target_path))
            self._update_last_action_label()

            QMessageBox.information(
                self,
                tr("reset_complete"),
                tr("reset_complete_msg", path=target_path),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("reset_failed"),
                tr("reset_failed_msg", error=str(e)),
            )

    def show_versions_dialog(self):
        """List archived result-file versions (created by Reset) with Open/Export actions."""
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QWidget,
        )
        from gearledger.desktop.settings_manager import get_versions_dir
        from gearledger.data_layer import get_network_mode
        import datetime
        import pandas as pd

        can_restore = get_network_mode() in ("standalone", "server")
        versions_dir = get_versions_dir()
        try:
            filenames = sorted(
                (f for f in os.listdir(versions_dir) if f.lower().endswith(".xlsx")),
                reverse=True,
            )
        except OSError:
            filenames = []

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("previous_versions_title"))
        dlg.setModal(True)
        dlg.setMinimumWidth(480)
        layout = QVBoxLayout(dlg)

        no_versions_label = QLabel(tr("no_previous_versions"))
        no_versions_label.setVisible(not filenames)
        layout.addWidget(no_versions_label)

        def _make_delete_handler(fpath, row_widget, label):
            def _delete():
                from PyQt6.QtWidgets import QMessageBox

                reply = QMessageBox.question(
                    dlg,
                    tr("delete_version_confirm_title"),
                    tr("delete_version_confirm_msg", version=label),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                try:
                    os.remove(fpath)
                    row_widget.setParent(None)
                    no_versions_label.setVisible(
                        not any(f.lower().endswith(".xlsx") for f in os.listdir(versions_dir))
                    )
                except OSError as e:
                    QMessageBox.critical(
                        dlg, tr("delete_version_confirm_title"), str(e)
                    )

            return _delete

        for fname in filenames:
            fpath = os.path.join(versions_dir, fname)
            try:
                count = len(pd.read_excel(fpath))
            except Exception:
                count = 0
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
            date_str = mtime.strftime("%Y-%m-%d %H:%M")

            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 4, 0, 4)
            row.addWidget(
                QLabel(tr("version_row_label", date=date_str, count=count)),
                1,
            )
            open_btn = QPushButton(tr("open_version"))
            export_btn = QPushButton(tr("export_version"))
            open_btn.clicked.connect(self._make_open_version_handler(fpath))
            export_btn.clicked.connect(self._make_export_version_handler(fpath))
            row.addWidget(open_btn)
            row.addWidget(export_btn)
            if can_restore:
                restore_btn = QPushButton(tr("restore_version"))
                restore_btn.clicked.connect(
                    self._make_restore_version_handler(fpath, dlg)
                )
                row.addWidget(restore_btn)
            delete_btn = QPushButton(tr("delete_version"))
            delete_btn.setStyleSheet("background-color: #e74c3c; color: white;")
            delete_btn.clicked.connect(
                _make_delete_handler(fpath, row_widget, f"{date_str} ({count})")
            )
            row.addWidget(delete_btn)
            layout.addWidget(row_widget)

        close_btn = QPushButton(tr("close"))
        close_btn.clicked.connect(dlg.reject)
        layout.addWidget(close_btn)

        dlg.exec()

    def _make_open_version_handler(self, path: str):
        def _open():
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices

            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

        return _open

    def _make_export_version_handler(self, path: str):
        def _export():
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            import shutil

            fn, _ = QFileDialog.getSaveFileName(
                self,
                tr("save_results_excel"),
                filter=tr("excel_filter"),
                initialFilter="Excel (*.xlsx)",
            )
            if not fn:
                return
            try:
                if not fn.endswith(".xlsx"):
                    fn += ".xlsx"
                shutil.copy2(path, fn)
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

        return _export

    def _make_restore_version_handler(self, path: str, dlg):
        def _restore():
            from PyQt6.QtWidgets import QMessageBox
            from gearledger.data_layer import get_network_mode

            is_server = get_network_mode() == "server"
            confirm_msg = (
                tr("restore_version_confirm_server")
                if is_server
                else tr("restore_version_confirm")
            )
            reply = QMessageBox.question(
                self,
                tr("restore_version_title"),
                confirm_msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ok = (
                self._restore_version_server(path)
                if is_server
                else self._restore_version(path)
            )
            if ok:
                dlg.accept()

        return _restore

    def _restore_version_server(self, version_path: str) -> bool:
        """Replace the database's current results with an archived version
        (server mode). Whatever's currently active gets archived first, and
        connected clients are notified so they don't keep showing stale
        data. Returns True on success."""
        from PyQt6.QtWidgets import QMessageBox
        from gearledger.database import get_database
        from gearledger.desktop.settings_manager import (
            get_versions_dir,
            record_last_results_action,
        )

        db = get_database()
        result = db.restore_from_version(version_path, get_versions_dir())
        if not result.get("ok"):
            QMessageBox.critical(
                self,
                tr("restore_failed"),
                tr("restore_failed_msg", error=result.get("error", "")),
            )
            return False

        self._notify_server_clients_data_changed()
        record_last_results_action("restore", os.path.basename(version_path))
        self._update_last_action_label()
        if hasattr(self, "on_results_refresh") and self.on_results_refresh:
            self.on_results_refresh()

        QMessageBox.information(
            self,
            tr("restore_complete"),
            tr("restore_complete_msg", path=f"Database ({result.get('restored', 0)} items)"),
        )
        return True

    def _restore_version(self, version_path: str) -> bool:
        """Make an archived version the active results file again
        (standalone mode).

        Whatever is currently active gets archived first (same rule as
        Reset: only if it has data), so switching back never loses work.
        Returns True on success.
        """
        import shutil
        from PyQt6.QtWidgets import QMessageBox
        from gearledger.desktop.settings_manager import (
            get_default_result_file,
            record_last_results_action,
        )

        try:
            target_path = self.get_results_path() or get_default_result_file()
            self._archive_active_file_if_needed(target_path)

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(version_path, target_path)  # keep the archived copy intact

            self._set_active_results_path(target_path)
            record_last_results_action("restore", os.path.basename(version_path))
            self._update_last_action_label()

            if hasattr(self, "on_results_refresh") and self.on_results_refresh:
                self.on_results_refresh()

            QMessageBox.information(
                self,
                tr("restore_complete"),
                tr("restore_complete_msg", path=target_path),
            )
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("restore_failed"),
                tr("restore_failed_msg", error=str(e)),
            )
            return False

    def download_results_excel(self):
        """Save results Excel file to a chosen location.

        In server mode, results live in the database, not the local Excel
        file (which nothing writes to anymore) — so this exports the live
        database contents instead of copying that unused local file.
        """
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import shutil
        from gearledger.data_layer import get_network_mode

        is_server = get_network_mode() == "server"

        if is_server:
            from gearledger.database import get_database
            from gearledger.result_ledger import rows_to_dataframe

            rows = get_database().get_all_results()
            if not rows:
                QMessageBox.warning(self, tr("download_results"), tr("no_results_file"))
                return
        else:
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

                if is_server:
                    rows_to_dataframe(rows).to_excel(fn, index=False)
                else:
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

    def check_completeness(self):
        """Compare recorded results against catalog demand."""
        if self.on_check_completeness_requested:
            self.on_check_completeness_requested()

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
        """
        Get the current catalog file path.

        In server mode with uploaded catalog, returns empty string (catalog is in memory).
        In client mode, returns cached catalog path if available.
        Otherwise returns local catalog path from settings.
        """
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client
        from gearledger.server import get_server
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

        # In server mode, prioritize in-memory uploaded catalog, but fall back to file from settings
        if mode == "server":
            server = get_server()
            if server and server.is_running():
                catalog_bytes = server.get_uploaded_catalog_data()
                if catalog_bytes is not None:
                    # Catalog is in memory, save it to a temporary cache file for search functions
                    # Search functions (run_fuzzy_match, process_image) need a file path, not bytes
                    from gearledger.desktop.settings_manager import APP_DIR

                    catalog_cache_dir = os.path.join(APP_DIR, "catalog_cache")
                    os.makedirs(catalog_cache_dir, exist_ok=True)
                    cached_catalog = os.path.join(
                        catalog_cache_dir, "server_catalog.xlsx"
                    )

                    # Save in-memory catalog to cache file if it doesn't exist or is outdated
                    # Check modification time to avoid unnecessary writes
                    needs_write = True
                    if os.path.exists(cached_catalog):
                        # Compare with server's upload time
                        upload_time = server._catalog_upload_time or 0
                        local_modified = os.path.getmtime(cached_catalog)
                        if upload_time <= local_modified:
                            needs_write = False

                    if needs_write:
                        try:
                            with open(cached_catalog, "wb") as f:
                                f.write(catalog_bytes)
                            print(
                                f"[SETTINGS] Saved in-memory catalog to cache: {cached_catalog}"
                            )
                        except Exception as e:
                            print(f"[SETTINGS] Failed to save catalog cache: {e}")
                            # Fall back to file from settings if cache write fails
                            local_catalog = self.catalog_edit.text().strip()
                            if local_catalog and os.path.exists(local_catalog):
                                return local_catalog
                            return ""

                    # Return cached file path for search functions
                    return cached_catalog
                else:
                    # No uploaded catalog, use the catalog file from settings
                    local_catalog = self.catalog_edit.text().strip()
                    if local_catalog and os.path.exists(local_catalog):
                        return local_catalog
                    # No catalog file selected either
                    return ""

        # In standalone mode, use local catalog
        return self.catalog_edit.text().strip()

    def _upload_catalog_to_server_auto(self, catalog_path: str):
        """Automatically upload catalog file to server (called when catalog is selected in server mode)."""
        from gearledger.server import get_server

        print(f"[SETTINGS] Auto-upload catalog called with path: {catalog_path}")
        if not catalog_path or not os.path.exists(catalog_path):
            print(f"[SETTINGS] Catalog path invalid or doesn't exist: {catalog_path}")
            return

        server = get_server()
        if not server or not server.is_running():
            print(
                "[SETTINGS] Server is not running, cannot upload catalog automatically"
            )
            return

        import requests

        try:
            # Use localhost when uploading from server to itself
            server_url = f"http://127.0.0.1:{server.port}"
            print(f"[SETTINGS] Uploading catalog to {server_url}/api/catalog")
            with open(catalog_path, "rb") as f:
                files = {
                    "file": (
                        os.path.basename(catalog_path),
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                }
                response = requests.post(
                    f"{server_url}/api/catalog",
                    files=files,
                    timeout=30,
                )
                result = response.json()
                print(f"[SETTINGS] Upload response: {result}")

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
            import traceback

            traceback.print_exc()

    def update_catalog_ui_for_mode(self, catalog_info: dict = None):
        """Update catalog UI based on network mode.

        Args:
            catalog_info: Optional catalog info dict with 'filename', 'size', 'exists' keys.
                         If provided, uses this instead of making API call.
        """
        from gearledger.data_layer import get_network_mode
        from gearledger.api_client import get_client

        mode = get_network_mode()

        if mode == "client":
            # In client mode: hide catalog and results selection, show status only
            client = get_client()
            connected = client and client.is_connected()

            self.catalog_label.setVisible(False)
            self.catalog_edit.setVisible(False)
            self.btn_catalog.setVisible(False)
            self.catalog_info_label.setVisible(True)

            # Use provided catalog info or fetch from server
            if catalog_info and catalog_info.get("exists"):
                # Use provided catalog info (from SSE event)
                filename = catalog_info.get("filename", "catalog.xlsx")
                size = catalog_info.get("size", 0)
                size_mb = size / (1024 * 1024) if size > 0 else 0
                self.catalog_info_label.setText(
                    f"📋 {tr('catalog_status_from_server')}: {filename} ({size_mb:.2f} MB)"
                )
                self.catalog_info_label.setStyleSheet(
                    "color: #27ae60; font-size: 11px; padding: 4px;"
                )
            else:
                # Fetch catalog status from server (fallback if no info provided)
                if connected:
                    if not catalog_info:  # Only make API call if we don't have info
                        info = client.get_catalog_info()
                    else:
                        info = catalog_info

                    if info.get("ok") and info.get("exists"):
                        filename = info.get("filename", "catalog.xlsx")
                        size = info.get("size", 0)
                        size_mb = size / (1024 * 1024) if size > 0 else 0
                        self.catalog_info_label.setText(
                            f"📋 {tr('catalog_status_from_server')}: {filename} ({size_mb:.2f} MB)"
                        )
                        self.catalog_info_label.setStyleSheet(
                            "color: #27ae60; font-size: 11px; padding: 4px;"
                        )
                    else:
                        self.catalog_info_label.setText(
                            f"📋 {tr('catalog_status_not_on_server')}"
                        )
                        self.catalog_info_label.setStyleSheet(
                            "color: #7f8c8d; font-size: 11px; padding: 4px;"
                        )
                else:
                    self.catalog_info_label.setText(
                        f"📋 {tr('catalog_status_not_connected')}"
                    )
                    self.catalog_info_label.setStyleSheet(
                        "color: #e74c3c; font-size: 11px; padding: 4px;"
                    )

            # In client mode: hide results selection, download, invoice; show status only
            self.results_label.setVisible(False)
            self.results_edit.setVisible(False)
            self.btn_results.setVisible(False)
            self.btn_import_results.setVisible(False)
            self.btn_reset_results.setVisible(False)
            self.btn_versions.setVisible(False)
            self.btn_download.setVisible(False)
            self.btn_generate_invoice.setVisible(False)
            self.btn_check_completeness.setVisible(False)
            self.last_action_label.setVisible(False)
            self.results_info_label.setVisible(True)
            if connected:
                self.results_info_label.setText(
                    f"📄 {tr('results_status_available')}"
                )
                self.results_info_label.setStyleSheet(
                    "color: #27ae60; font-size: 11px; padding: 4px;"
                )
            else:
                self.results_info_label.setText(
                    f"📄 {tr('results_status_not_connected')}"
                )
                self.results_info_label.setStyleSheet(
                    "color: #e74c3c; font-size: 11px; padding: 4px;"
                )
        else:
            # In server/standalone mode: show catalog selection, hide status
            is_server = mode == "server"
            self.catalog_label.setVisible(True)
            self.catalog_edit.setVisible(True)
            self.btn_catalog.setVisible(True)
            self.catalog_info_label.setVisible(False)

            # Results Excel path/Browse only apply in standalone mode — in
            # server mode nothing reads or writes that local file anymore,
            # everything goes through the database instead.
            self.results_label.setVisible(not is_server)
            self.results_edit.setVisible(not is_server)
            self.btn_results.setVisible(not is_server)
            self.btn_import_results.setVisible(is_server)
            self.btn_reset_results.setVisible(True)
            self.btn_versions.setVisible(True)
            self.btn_download.setVisible(True)
            self.btn_generate_invoice.setVisible(True)
            self.btn_check_completeness.setVisible(True)
            self.last_action_label.setVisible(True)
            self.results_info_label.setVisible(is_server)
            if is_server:
                self.results_info_label.setText(f"📄 {tr('results_status_database')}")
                self.results_info_label.setStyleSheet(
                    "color: #7f8c8d; font-size: 11px; padding: 4px;"
                )
            self._update_last_action_label()

    def get_results_path(self) -> str:
        """Get the current results file path. Uses default from settings if not set."""
        path = self.results_edit.text().strip()

        # If no path is set, use default from settings or create one
        if not path:
            try:
                from gearledger.desktop.settings_manager import (
                    load_settings,
                    get_default_result_file,
                    is_path_for_this_platform,
                )
                import os

                settings = load_settings()
                # Use configured default, or fall back to app data directory.
                # Ignore a stored path that doesn't belong to this OS (e.g.
                # settings.json copied over from a different machine) instead
                # of trying to use/create a foreign, nonsensical path.
                if settings.default_result_file and is_path_for_this_platform(
                    settings.default_result_file
                ):
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
            self.btn_import_results,
            self.btn_reset_results,
            self.btn_download,
            self.btn_generate_invoice,
            self.btn_check_completeness,
            self.manual_part_code,
            self.manual_weight,
            self.btn_add_manual,
        ):
            widget.setEnabled(enabled)

    def validate_catalog(self) -> bool:
        """Validate that catalog file exists or in-memory catalog is available."""
        from gearledger.data_layer import get_network_mode
        from gearledger.server import get_server

        mode = get_network_mode()

        # In server mode, check for in-memory catalog first
        if mode == "server":
            server = get_server()
            if server and server.is_running():
                if server.get_uploaded_catalog_data() is not None:
                    # In-memory catalog is available
                    return True

        # Check for file-based catalog
        catalog = self.get_catalog_path()
        return bool(catalog and os.path.exists(catalog))

    def clear_manual_entry(self):
        """Clear manual entry fields."""
        self.manual_part_code.clear()
        self.manual_weight.clear()
