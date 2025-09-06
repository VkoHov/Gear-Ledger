# app_pyqt.py
from __future__ import annotations
import os, sys
from typing import Dict, Any, List

# Make local package importable when running from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QFileDialog,
    QLineEdit,
    QComboBox,
    QRadioButton,
    QHBoxLayout,
    QVBoxLayout,
    QGroupBox,
    QTextEdit,
    QMessageBox,
    QButtonGroup,
)

# ---- pipeline & config
from gearledger.pipeline import process_image
from gearledger.config import (
    DEFAULT_LANGS,
    DEFAULT_MODEL,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
    DEFAULT_TARGET,
)

# We will patch these logging helpers to stream lines to the UI
import gearledger.logging_utils as glog

MODELS = ["gpt-4o-mini", "gpt-4o"]


# ---------------- Worker (runs pipeline off the UI thread) ----------------
class Worker(QObject):
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str)

    def __init__(self, image: str, excel: str, target: str, model: str):
        super().__init__()
        self.image = image
        self.excel = excel
        self.target = target
        self.model = model

        # keep originals so we can restore after run
        self._orig_step = glog.step
        self._orig_info = glog.info
        self._orig_warn = glog.warn
        self._orig_err = glog.err

    def _patch_loggers(self):
        # wrap each logger to also emit a UI line
        def _wrap(fn):
            def _inner(msg):
                try:
                    self.progress.emit(msg)
                except Exception:
                    pass
                try:
                    fn(msg)
                except Exception:
                    pass

            return _inner

        glog.step = _wrap(self._orig_step)
        glog.info = _wrap(self._orig_info)
        glog.warn = _wrap(self._orig_warn)
        glog.err = _wrap(self._orig_err)

    def _restore_loggers(self):
        glog.step = self._orig_step
        glog.info = self._orig_info
        glog.warn = self._orig_warn
        glog.err = self._orig_err

    def run(self):
        # patch -> run -> restore (always restore!)
        self._patch_loggers()
        try:
            self.progress.emit("Running…")
            res = process_image(
                self.image,
                self.excel,
                langs=DEFAULT_LANGS,
                model=self.model,
                min_fuzzy=DEFAULT_MIN_FUZZY,
                max_items=DEFAULT_MAX_ITEMS,
                max_side=DEFAULT_MAX_SIDE,
                target=self.target,
            )
        except Exception as e:
            res = {"ok": False, "error": str(e), "logs": [f"[ERROR] {e}"]}
            self.progress.emit(f"[ERROR] {e}")
        finally:
            self._restore_loggers()
        self.finished.emit(res)


# ---------------- Main Window ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GearLedger — desktop")
        self.resize(980, 680)
        try:
            self.setWindowIcon(QIcon.fromTheme("applications-graphics"))
        except Exception:
            pass

        # Inputs group
        inputs = QGroupBox("Input")
        img_label = QLabel("Image:")
        self.img_edit = QLineEdit()
        self.img_browse = QPushButton("Browse…")
        self.img_browse.clicked.connect(self.pick_image)

        xls_label = QLabel("Excel:")
        self.xls_edit = QLineEdit()
        self.xls_browse = QPushButton("Browse…")
        self.xls_browse.clicked.connect(self.pick_excel)

        # Target radios
        target_label = QLabel("Target:")
        self.rb_auto = QRadioButton("auto")
        self.rb_vendor = QRadioButton("vendor")
        self.rb_oem = QRadioButton("oem")
        self.tgroup = QButtonGroup(self)
        for rb in (self.rb_auto, self.rb_vendor, self.rb_oem):
            self.tgroup.addButton(rb)
        if DEFAULT_TARGET == "vendor":
            self.rb_vendor.setChecked(True)
        elif DEFAULT_TARGET == "oem":
            self.rb_oem.setChecked(True)
        else:
            self.rb_auto.setChecked(True)

        # Model
        model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        if DEFAULT_MODEL in MODELS:
            self.model_combo.setCurrentText(DEFAULT_MODEL)

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.on_run)

        # Layout: inputs
        g = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(img_label)
        row1.addWidget(self.img_edit, 1)
        row1.addWidget(self.img_browse)
        g.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(xls_label)
        row2.addWidget(self.xls_edit, 1)
        row2.addWidget(self.xls_browse)
        g.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(target_label)
        row3.addWidget(self.rb_auto)
        row3.addWidget(self.rb_vendor)
        row3.addWidget(self.rb_oem)
        row3.addStretch(1)
        g.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(model_label)
        row4.addWidget(self.model_combo)
        row4.addStretch(1)
        row4.addWidget(self.run_btn)
        g.addLayout(row4)

        inputs.setLayout(g)

        # Results group
        results = QGroupBox("Result")
        self.best_vis = QLineEdit()
        self.best_vis.setReadOnly(True)
        self.best_norm = QLineEdit()
        self.best_norm.setReadOnly(True)
        self.match_line = QLineEdit()
        self.match_line.setReadOnly(True)
        self.cost_line = QLineEdit()
        self.cost_line.setReadOnly(True)

        rg = QVBoxLayout()
        row_r1 = QHBoxLayout()
        row_r1.addWidget(QLabel("Best (visible):"))
        row_r1.addWidget(self.best_vis, 1)
        rg.addLayout(row_r1)
        row_r2 = QHBoxLayout()
        row_r2.addWidget(QLabel("Best (normalized):"))
        row_r2.addWidget(self.best_norm, 1)
        rg.addLayout(row_r2)
        row_r3 = QHBoxLayout()
        row_r3.addWidget(QLabel("Excel match:"))
        row_r3.addWidget(self.match_line, 1)
        rg.addLayout(row_r3)
        row_r4 = QHBoxLayout()
        row_r4.addWidget(QLabel("Est. GPT cost:"))
        row_r4.addWidget(self.cost_line, 1)
        rg.addLayout(row_r4)
        results.setLayout(rg)

        # Logs
        logs = QGroupBox("Logs")
        self.log_txt = QTextEdit()
        self.log_txt.setReadOnly(True)
        self.log_txt.setStyleSheet(
            "QTextEdit { background:#0b1220; color:#e5e7eb; font-family: Menlo, Consolas, monospace; }"
        )
        lg = QVBoxLayout()
        lg.addWidget(self.log_txt)
        logs.setLayout(lg)

        # Root layout
        root = QVBoxLayout()
        root.addWidget(inputs)
        root.addWidget(results)
        root.addWidget(logs, 1)
        self.setLayout(root)

        self.append_logs(["Ready."])

        # Thread holder
        self._thread: QThread | None = None
        self._worker: Worker | None = None

    # ---- UI helpers
    def append_logs(self, lines: List[str]):
        for ln in lines or []:
            self.log_txt.append(ln)

    def pick_image(self):
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Choose image",
            filter="Images (*.jpg *.jpeg *.png *.heic *.heif *.webp *.bmp);;All files (*)",
        )
        if fn:
            self.img_edit.setText(fn)

    def pick_excel(self):
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Excel file",
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            self.xls_edit.setText(fn)

    # ---- Run pipeline
    def on_run(self):
        image = self.img_edit.text().strip()
        excel = self.xls_edit.text().strip()
        if not os.path.exists(image):
            QMessageBox.critical(self, "Error", "Please choose a valid image file.")
            return
        if not os.path.exists(excel):
            QMessageBox.critical(self, "Error", "Please choose a valid Excel file.")
            return

        target = "auto"
        if self.rb_vendor.isChecked():
            target = "vendor"
        elif self.rb_oem.isChecked():
            target = "oem"

        model = self.model_combo.currentText()

        # reset UI
        self.best_vis.clear()
        self.best_norm.clear()
        self.match_line.clear()
        self.cost_line.clear()
        self.log_txt.clear()
        self.append_logs(["Running…"])
        self.run_btn.setEnabled(False)

        # thread
        self._thread = QThread()
        self._worker = Worker(image, excel, target, model)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.on_progress)  # <<< live logs
        self._worker.finished.connect(self.on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def on_progress(self, line: str):
        self.append_logs([line])

    def on_finished(self, res: Dict[str, Any]):
        self.run_btn.setEnabled(True)
        # also append whatever the pipeline collected
        self.append_logs(res.get("logs"))

        if not res.get("ok"):
            QMessageBox.critical(self, "Run failed", str(res.get("error")))
            return

        self.best_vis.setText(res.get("best_visible") or "")
        self.best_norm.setText(res.get("best_normalized") or "")

        client, artikul = res.get("match_client"), res.get("match_artikul")
        self.match_line.setText(
            f"{artikul} → {client}" if client and artikul else "not found"
        )

        cost = res.get("gpt_cost")
        self.cost_line.setText(
            f"${cost:.6f}" if isinstance(cost, (int, float)) else "— (no API key)"
        )


def main():
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
