# app_pyqt.py
from __future__ import annotations
import os, sys, tempfile
from typing import Dict, Any, List, Optional

# Make local package importable when running from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QImage
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

from gearledger.pipeline import process_image
from gearledger.config import (
    DEFAULT_LANGS,
    DEFAULT_MODEL,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
    DEFAULT_TARGET,
)
from gearledger import camera as cam
from gearledger.speech import speak, speak_match

MODELS = ["gpt-4o-mini", "gpt-4o"]

CAM_INDEX = int(os.getenv("CAM_INDEX", "0"))
CAM_W = int(os.getenv("CAM_WIDTH", "1280"))
CAM_H = int(os.getenv("CAM_HEIGHT", "720"))


# ---------------- Worker (runs pipeline off the UI thread) ----------------
class Worker(QObject):
    finished = pyqtSignal(dict)

    def __init__(self, image: str, excel: str, target: str, model: str):
        super().__init__()
        self.image = image
        self.excel = excel
        self.target = target
        self.model = model

    def run(self):
        try:
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
        self.finished.emit(res)


# ---------------- Main Window ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GearLedger — desktop")
        self.resize(1100, 760)
        try:
            self.setWindowIcon(QIcon.fromTheme("applications-graphics"))
        except Exception:
            pass

        self._thread: Optional[QThread] = None
        self._worker: Optional[Worker] = None

        # -------- Camera area --------
        cam_group = QGroupBox("Camera")
        self.preview = QLabel()
        self.preview.setFixedHeight(480)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "QLabel { background:#111; color:#bbb; border:1px solid #333; }"
        )
        self.preview.setText("Camera preview")

        self.btn_start = QPushButton("Start camera")
        self.btn_capture = QPushButton("Capture & Run")
        self.btn_stop = QPushButton("Stop camera")
        for b in (self.btn_capture, self.btn_stop):
            b.setEnabled(False)

        self.btn_start.clicked.connect(self.on_cam_start)
        self.btn_capture.clicked.connect(self.on_cam_capture_and_run)
        self.btn_stop.clicked.connect(self.on_cam_stop)

        row_btn = QHBoxLayout()
        row_btn.addWidget(self.btn_start)
        row_btn.addWidget(self.btn_capture)
        row_btn.addWidget(self.btn_stop)
        row_btn.addStretch(1)

        cam_layout = QVBoxLayout()
        cam_layout.addWidget(self.preview)
        cam_layout.addLayout(row_btn)
        cam_group.setLayout(cam_layout)

        # -------- Options (Excel / Target / Model) --------
        opt_group = QGroupBox("Options")

        # Excel
        xls_label = QLabel("Excel:")
        self.xls_edit = QLineEdit()
        self.btn_browse_xls = QPushButton("Browse…")
        self.btn_browse_xls.clicked.connect(self.pick_excel)

        # Target radios
        target_label = QLabel("Target:")
        self.rb_auto = QRadioButton("auto")
        self.rb_vendor = QRadioButton("vendor")
        self.rb_oem = QRadioButton("oem")
        self.tgroup = QButtonGroup(self)
        for rb in (self.rb_auto, self.rb_vendor, self.rb_oem):
            self.tgroup.addButton(rb)
        # set default
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

        opt_layout = QVBoxLayout()
        r1 = QHBoxLayout()
        r1.addWidget(xls_label)
        r1.addWidget(self.xls_edit, 1)
        r1.addWidget(self.btn_browse_xls)
        opt_layout.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(target_label)
        r2.addWidget(self.rb_auto)
        r2.addWidget(self.rb_vendor)
        r2.addWidget(self.rb_oem)
        r2.addStretch(1)
        opt_layout.addLayout(r2)

        r3 = QHBoxLayout()
        r3.addWidget(model_label)
        r3.addWidget(self.model_combo)
        r3.addStretch(1)
        opt_layout.addLayout(r3)

        opt_group.setLayout(opt_layout)

        # -------- Results --------
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
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Best (visible):"))
        r1.addWidget(self.best_vis, 1)
        rg.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Best (normalized):"))
        r2.addWidget(self.best_norm, 1)
        rg.addLayout(r2)
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Excel match:"))
        r3.addWidget(self.match_line, 1)
        rg.addLayout(r3)
        r4 = QHBoxLayout()
        r4.addWidget(QLabel("Est. GPT cost:"))
        r4.addWidget(self.cost_line, 1)
        rg.addLayout(r4)
        results.setLayout(rg)

        # -------- Logs --------
        logs = QGroupBox("Logs")
        self.log_txt = QTextEdit()
        self.log_txt.setReadOnly(True)
        self.log_txt.setStyleSheet(
            "QTextEdit { background:#0b1220; color:#e5e7eb; font-family: Menlo, Consolas, monospace; }"
        )
        lg = QVBoxLayout()
        lg.addWidget(self.log_txt)
        logs.setLayout(lg)

        # -------- Root layout --------
        root = QVBoxLayout()
        root.addWidget(cam_group)
        root.addWidget(opt_group)
        root.addWidget(results)
        root.addWidget(logs, 1)
        self.setLayout(root)

        self.append_logs(["Ready."])

        # camera state
        self.cap = None
        self.timer: Optional[QTimer] = None
        self._last_frame: Optional[np.ndarray] = None

    # ---------- Helpers ----------
    def append_logs(self, lines: List[str]):
        for ln in lines or []:
            self.log_txt.append(ln)

    def pick_excel(self):
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Excel file",
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            self.xls_edit.setText(fn)

    def _current_target(self) -> str:
        if self.rb_vendor.isChecked():
            return "vendor"
        if self.rb_oem.isChecked():
            return "oem"
        return "auto"

    def _current_model(self) -> str:
        return self.model_combo.currentText()

    def _start_threaded_run(
        self, image_path: str, excel_path: str, target: str, model: str
    ):
        # reset UI
        self.best_vis.clear()
        self.best_norm.clear()
        self.match_line.clear()
        self.cost_line.clear()
        self.log_txt.clear()
        self.append_logs(["Running…"])

        # avoid double clicks
        self.btn_capture.setEnabled(False)

        self._thread = QThread()
        self._worker = Worker(image_path, excel_path, target, model)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    # ---------- Camera flow ----------
    def on_cam_start(self):
        if self.cap:
            return
        self.cap = cam.open_camera(CAM_INDEX, CAM_W, CAM_H)
        if not self.cap:
            QMessageBox.critical(
                self,
                "Camera",
                "Failed to open camera. Try a different CAM_INDEX in .env",
            )
            return
        self.btn_start.setEnabled(False)
        self.btn_capture.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_and_show)
        self.timer.start(30)  # ~33fps

    def _grab_and_show(self):
        frame = cam.read_frame(self.cap)
        if frame is None:
            return
        self._last_frame = frame
        # BGR->RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview.width(),
            self.preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(pix)

    def on_cam_capture_and_run(self):
        if self._last_frame is None:
            QMessageBox.information(self, "Camera", "No frame yet. Try again.")
            return
        excel = self.xls_edit.text().strip()
        if not os.path.exists(excel):
            QMessageBox.critical(self, "Error", "Please choose a valid Excel file.")
            return

        # save to temp
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        try:
            # BGR -> write JPG
            cv2.imwrite(tmp.name, self._last_frame)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save capture: {e}")
            return

        # run pipeline with captured image
        self._start_threaded_run(
            tmp.name, excel, self._current_target(), self._current_model()
        )

    def on_cam_stop(self):
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.cap:
            cam.release_camera(self.cap)
            self.cap = None
        self.preview.setText("Camera preview")
        self.btn_start.setEnabled(True)
        self.btn_capture.setEnabled(False)
        self.btn_stop.setEnabled(False)

    # ---------- Results ----------
    def on_finished(self, res: Dict[str, Any]):
        # re-enable capture after run
        self.btn_capture.setEnabled(True)

        # logs
        self.append_logs(res.get("logs"))

        if not res.get("ok"):
            QMessageBox.critical(self, "Run failed", str(res.get("error")))
            return

        self.best_vis.setText(res.get("best_visible") or "")
        self.best_norm.setText(res.get("best_normalized") or "")

        client = res.get("match_client")
        artikul = res.get("match_artikul")

        if client and artikul:
            self.match_line.setText(f"{artikul} → {client}")
            speak_match(artikul, client)
        else:
            self.match_line.setText("not found")
            # Speak a best guess if we have one
            best = res.get("best_visible") or res.get("best_normalized")
            if best:
                from gearledger.speech import _spell_code

                speak(f"No match found. Best guess code: {_spell_code(best)}.")
            else:
                speak("No match found.")

        cost = res.get("gpt_cost")
        self.cost_line.setText(
            f"${cost:.6f}" if isinstance(cost, (int, float)) else "— (no API key)"
        )

    # ---------- Cleanup ----------
    def closeEvent(self, event):
        self.on_cam_stop()
        super().closeEvent(event)


def main():
    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
