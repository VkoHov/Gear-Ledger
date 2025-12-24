# gearledger/desktop/results_pane.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, datetime
import pandas as pd

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QAbstractTableModel,
    QModelIndex,
    pyqtSignal,
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel, QHeaderView
from PyQt6.QtGui import QFont, QPalette

from gearledger.result_ledger import COLUMNS
from gearledger.desktop.translations import tr


class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid():
            return None

        if role in (int(Qt.ItemDataRole.DisplayRole), int(Qt.ItemDataRole.EditRole)):
            v = self._df.iat[index.row(), index.column()]

            # 1) handle missing values (NaN/NaT/None) first
            try:
                if pd.isna(v):
                    return ""
            except Exception:
                if v is None:
                    return ""

            # 2) pretty-print datetimes that are real (not NaT)
            try:
                if isinstance(v, (datetime.datetime, pd.Timestamp)):
                    return v.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            return str(v)

        if role == int(Qt.ItemDataRole.TextAlignmentRole):
            col = self._df.columns[index.column()]
            if col in ("Количество", "Вес"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ):
        if role != int(Qt.ItemDataRole.DisplayRole):
            return None
        if orientation == Qt.Orientation.Horizontal:
            return (
                str(self._df.columns[section])
                if 0 <= section < len(self._df.columns)
                else ""
            )
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder):
        if not (0 <= column < len(self._df.columns)):
            return
        col = self._df.columns[column]
        self.layoutAboutToBeChanged.emit()
        asc = order == Qt.SortOrder.AscendingOrder
        try:
            self._df.sort_values(by=col, ascending=asc, inplace=True, kind="mergesort")
            self._df.reset_index(drop=True, inplace=True)
        finally:
            self.layoutChanged.emit()

    def set_dataframe(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df
        self.endResetModel()


class ResultsPane(QWidget):
    ledger_path_changed = pyqtSignal(str)

    def __init__(self, ledger_path: str = "", parent=None):
        super().__init__(parent)
        self.ledger_path = ledger_path

        # Create styled label
        self.label = QLabel(tr("results_excel"))
        self.label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
                padding: 8px 0px;
                border-bottom: 2px solid #3498db;
                margin-bottom: 8px;
            }
        """
        )

        # Create styled table
        self.table = QTableView(self)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        # Apply table styling
        self.table.setStyleSheet(
            """
            QTableView {
                gridline-color: #bdc3c7;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                selection-background-color: #3498db;
                selection-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                font-size: 12px;
            }
            
            QTableView::item {
                padding: 8px;
                border-bottom: 1px solid #ecf0f1;
            }
            
            QTableView::item:selected {
                background-color: #3498db;
                color: white;
            }
            
            QTableView::item:hover {
                background-color: #e8f4fd;
            }
            
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 10px;
                border: none;
                border-right: 1px solid #2c3e50;
                font-weight: bold;
                font-size: 12px;
            }
            
            QHeaderView::section:first {
                border-top-left-radius: 6px;
            }
            
            QHeaderView::section:last {
                border-top-right-radius: 6px;
                border-right: none;
            }
            
            QHeaderView::section:hover {
                background-color: #2c3e50;
            }
        """
        )

        # Set header properties
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setDefaultSectionSize(120)
        header.setMinimumSectionSize(80)

        # Set row height
        self.table.verticalHeader().setDefaultSectionSize(35)

        # Start with empty DataFrame to avoid blocking startup
        # Load actual data asynchronously after UI is ready
        df = pd.DataFrame(columns=COLUMNS)
        self.model = PandasModel(df, self)
        self.table.setModel(self.model)

        # Load actual data after a short delay (non-blocking)
        if ledger_path:
            QTimer.singleShot(200, self.refresh)

        # Create main layout with styling
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        lay.addWidget(self.label)
        lay.addWidget(self.table)

        if self.ledger_path:
            self.label.setText(
                f"{tr('results_excel')} {os.path.basename(self.ledger_path)}"
            )

    def set_ledger_path(self, path: str):
        self.ledger_path = path or ""
        self.label.setText(
            f"{tr('results_excel')} {os.path.basename(self.ledger_path) if self.ledger_path else ''}"
        )
        self.ledger_path_changed.emit(self.ledger_path)
        self.refresh()

    def refresh(self):
        try:
            df = self._read_df_safe(self.ledger_path)
            self.model.set_dataframe(df)
        except Exception:
            # file might be locked/being replaced atomically — retry soon
            QTimer.singleShot(300, self._refresh_retry)

    def _refresh_retry(self):
        try:
            df = self._read_df_safe(self.ledger_path)
            self.model.set_dataframe(df)
        except Exception:
            pass

    @staticmethod
    def _read_df_safe(path: str) -> pd.DataFrame:
        # Check network mode first
        try:
            from gearledger.data_layer import get_network_mode, is_network_mode

            mode = get_network_mode()
            print(f"[RESULTS_PANE] Reading data, mode={mode}")
            if mode in ("server", "client"):
                print(f"[RESULTS_PANE] Using network mode: {mode}")
                return ResultsPane._read_from_network(mode)
        except Exception as e:
            print(f"[RESULTS_PANE] Network mode check failed: {e}")

        # Fall back to Excel file
        if not path or not os.path.exists(path):
            return pd.DataFrame(columns=COLUMNS)
        try:
            df = pd.read_excel(path, engine="openpyxl")
        except Exception:
            df = pd.DataFrame(columns=COLUMNS)
        # ensure columns
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = pd.Series(dtype="object")
        # coerce datetime column for safe rendering (NaT handled in model)
        try:
            df["Последнее обновление"] = pd.to_datetime(
                df["Последнее обновление"], errors="coerce"
            )
        except Exception:
            pass
        return df

    @staticmethod
    def _read_from_network(mode: str) -> pd.DataFrame:
        """Read results from database (server) or API (client)."""
        print(f"[RESULTS_PANE] _read_from_network called with mode={mode}")
        results = []

        if mode == "server":
            # Read from local database
            try:
                from gearledger.database import get_database

                db = get_database()
                print(f"[RESULTS_PANE] Reading from database: {db.db_path}")
                results = db.get_all_results()
                print(f"[RESULTS_PANE] Got {len(results)} results from database")
            except Exception as e:
                print(f"[RESULTS_PANE] ERROR: Failed to read from database: {e}")
                return pd.DataFrame(columns=COLUMNS)
        elif mode == "client":
            # Read from remote server via API
            try:
                from gearledger.api_client import get_client

                client = get_client()
                print(f"[RESULTS_PANE] API client: {client}")
                if client and client.is_connected():
                    results = client.get_all_results()
                    print(f"[RESULTS_PANE] Got {len(results)} results from API")
                else:
                    print("[RESULTS_PANE] WARN: Client not connected")
                    return pd.DataFrame(columns=COLUMNS)
            except Exception as e:
                print(f"[RESULTS_PANE] ERROR: Failed to read from API: {e}")
                return pd.DataFrame(columns=COLUMNS)

        if not results:
            return pd.DataFrame(columns=COLUMNS)

        # Convert database results to DataFrame with correct column names
        rows = []
        for r in results:
            rows.append(
                {
                    "Артикул": r.get("artikul", ""),
                    "Клиент": r.get("client", ""),
                    "Количество": r.get("quantity", 0),
                    "Вес": r.get("weight", 0),
                    "Последнее обновление": r.get("last_updated", ""),
                    "Брэнд": r.get("brand", ""),
                    "Описание": r.get("description", ""),
                    "Цена продажи": r.get("sale_price", 0),
                    "Сумма продажи": r.get("total_price", 0),
                }
            )

        df = pd.DataFrame(rows, columns=COLUMNS)

        # Coerce datetime column
        try:
            df["Последнее обновление"] = pd.to_datetime(
                df["Последнее обновление"], errors="coerce"
            )
        except Exception:
            pass

        return df
