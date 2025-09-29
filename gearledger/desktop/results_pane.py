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
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableView, QLabel

COLUMNS = ["Артикул", "Клиент", "Количество", "Вес", "Последнее обновление"]


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

        self.label = QLabel("Results (Excel):")
        self.table = QTableView(self)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        df = self._read_df_safe(ledger_path)
        self.model = PandasModel(df, self)
        self.table.setModel(self.model)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.label)
        lay.addWidget(self.table)

        if self.ledger_path:
            self.label.setText(f"Results (Excel): {os.path.basename(self.ledger_path)}")

    def set_ledger_path(self, path: str):
        self.ledger_path = path or ""
        self.label.setText(
            f"Results (Excel): {os.path.basename(self.ledger_path) if self.ledger_path else ''}"
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
