# app_pyqt.py
from __future__ import annotations
import os, sys, tempfile
from typing import Dict, Any, List, Tuple

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
    QListWidget,
    QListWidgetItem,
    QCheckBox,
)

from gearledger.pipeline import process_image, run_fuzzy_match
from gearledger.config import (
    DEFAULT_LANGS,
    DEFAULT_MODEL,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
    DEFAULT_TARGET,
)

# Optional speech helpers (guarded import)
try:
    from gearledger.speech import speak, speak_match, _spell_code
except Exception:  # safe fallbacks if speech isn't available

    def speak(*a, **k):
        pass

    def speak_match(*a, **k):
        pass

    def _spell_code(x):
        return x


MODELS = ["gpt-4o-mini", "gpt-4o"]

# Camera defaults via env
CAM_INDEX = int(os.getenv("CAM_INDEX", "0"))
CAM_W = int(os.getenv("CAM_WIDTH", "1280"))
CAM_H = int(os.getenv("CAM_HEIGHT", "720"))


# ---------------- Camera helpers (tiny wrapper over OpenCV) ----------------
def open_camera(index: int, w: int, h: int):
    cap = cv2.VideoCapture(index)
    if not cap or not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    return cap


def read_frame(cap) -> np.ndarray | None:
    ok, frame = cap.read()
    return frame if ok else None


def release_camera(cap):
    try:
        cap.release()
    except Exception:
        pass


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


class FuzzyWorker(QObject):
    finished = pyqtSignal(dict)

    def __init__(self, excel: str, cand_order: List[Tuple[str, str]], min_fuzzy: int):
        super().__init__()
        self.excel = excel
        self.cand_order = cand_order
        self.min_fuzzy = min_fuzzy

    def run(self):
        try:
            res = run_fuzzy_match(self.excel, self.cand_order, self.min_fuzzy)
        except Exception as e:
            res = {"ok": False, "error": str(e), "logs": [f"[ERROR] {e}"]}
        self.finished.emit(res)


# ---------------- Main Window (Camera-only UI) ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GearLedger — desktop (camera)")
        self.resize(1100, 760)
        try:
            self.setWindowIcon(QIcon.fromTheme("applications-graphics"))
        except Exception:
            pass

        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._fthread: QThread | None = None
        self._fworker: FuzzyWorker | None = None
        self._main_running: bool = False

        # --- Controls: Excel + Target + Model ---
        inputs = QGroupBox("Settings")
        lbl_x = QLabel("Excel:")
        self.xls_edit = QLineEdit()
        btn_x = QPushButton("Browse…")
        btn_x.clicked.connect(self.pick_excel)

        lbl_t = QLabel("Target:")
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

        lbl_m = QLabel("Model:")
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        self.model_combo.setCurrentText(
            DEFAULT_MODEL if DEFAULT_MODEL in MODELS else MODELS[0]
        )

        g = QVBoxLayout()
        r1 = QHBoxLayout()
        r1.addWidget(lbl_x)
        r1.addWidget(self.xls_edit, 1)
        r1.addWidget(btn_x)
        g.addLayout(r1)
        r2 = QHBoxLayout()
        r2.addWidget(lbl_t)
        r2.addWidget(self.rb_auto)
        r2.addWidget(self.rb_vendor)
        r2.addWidget(self.rb_oem)
        r2.addStretch(1)
        g.addLayout(r2)
        r3 = QHBoxLayout()
        r3.addWidget(lbl_m)
        r3.addWidget(self.model_combo)
        r3.addStretch(1)
        g.addLayout(r3)
        inputs.setLayout(g)

        # --- Camera preview + buttons ---
        cam_box = QGroupBox("Camera")
        self.preview = QLabel("Camera preview")
        self.preview.setFixedHeight(420)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "QLabel { background:#111; color:#bbb; border:1px solid #333; }"
        )

        self.btn_start = QPushButton("Start camera")
        self.btn_capture = QPushButton("Capture & Run")
        self.btn_stop = QPushButton("Stop")
        self.btn_capture.setEnabled(False)
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self.on_cam_start)
        self.btn_capture.clicked.connect(self.on_cam_capture_and_run)
        self.btn_stop.clicked.connect(self.on_cam_stop)

        c = QVBoxLayout()
        c.addWidget(self.preview)
        cr = QHBoxLayout()
        cr.addWidget(self.btn_start)
        cr.addWidget(self.btn_capture)
        cr.addWidget(self.btn_stop)
        cr.addStretch(1)
        c.addLayout(cr)
        cam_box.setLayout(c)

        # --- Results ---
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

        # --- Fuzzy UI (appears when no exact/variant match) ---
        self.fuzzy_box = QGroupBox("No exact match — try fuzzy?")
        self.fuzzy_box.setVisible(False)
        self.cand_list = QListWidget()
        self.cand_list.setMinimumHeight(100)
        self.chk_use_shown = QCheckBox("Limit fuzzy to shown candidates")
        self.chk_use_shown.setChecked(True)
        self.btn_run_fuzzy = QPushButton("Run fuzzy match")
        self.btn_run_fuzzy.clicked.connect(self.on_run_fuzzy_clicked)

        fg = QVBoxLayout()
        fg.addWidget(QLabel("Likely candidates (from GPT/local ranking):"))
        fg.addWidget(self.cand_list)
        fg.addWidget(self.chk_use_shown)
        fg.addWidget(self.btn_run_fuzzy, alignment=Qt.AlignmentFlag.AlignRight)
        self.fuzzy_box.setLayout(fg)

        rg.addWidget(self.fuzzy_box)
        results.setLayout(rg)

        # --- Logs ---
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
        root.addWidget(cam_box)
        root.addWidget(results)
        root.addWidget(logs, 1)
        self.setLayout(root)

        self.append_logs(["Ready."])

        # camera state
        self.cap = None
        self.timer: QTimer | None = None
        self._last_frame: np.ndarray | None = None

        # store last cand_order for fuzzy
        self._last_cand_order: List[Tuple[str, str]] = []

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

    # ---------- Camera flow ----------
    def on_cam_start(self):
        if self.cap:
            return
        self.cap = open_camera(CAM_INDEX, CAM_W, CAM_H)
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
        frame = read_frame(self.cap)
        if frame is None:
            return
        self._last_frame = frame
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
        # prevent double start
        if self._main_running:
            return

        if self._last_frame is None:
            QMessageBox.information(self, "Camera", "No frame yet. Try again.")
            return
        excel = self.xls_edit.text().strip()
        if not os.path.exists(excel):
            QMessageBox.critical(self, "Error", "Please choose a valid Excel file.")
            return

        # disable capture immediately to block double-clicks
        self.btn_capture.setEnabled(False)

        # save frame to temp jpg
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        try:
            cv2.imwrite(tmp.name, self._last_frame)
        except Exception as e:
            # re-enable since we failed
            self.btn_capture.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Failed to save capture: {e}")
            return

        # reset UI
        self.best_vis.clear()
        self.best_norm.clear()
        self.match_line.clear()
        self.cost_line.clear()
        self.log_txt.clear()
        self.fuzzy_box.setVisible(False)
        self.cand_list.clear()
        self.append_logs(["Running…"])

        # mark running + (optionally) lock settings while running
        self._main_running = True
        self.model_combo.setEnabled(False)
        self.rb_auto.setEnabled(False)
        self.rb_vendor.setEnabled(False)
        self.rb_oem.setEnabled(False)

        # start worker
        self._thread = QThread()
        self._worker = Worker(
            tmp.name, excel, self._current_target(), self._current_model()
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self.on_finished_main)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def on_cam_stop(self):
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.cap:
            release_camera(self.cap)
            self.cap = None
        self.preview.setText("Camera preview")
        self.btn_start.setEnabled(True)
        self.btn_capture.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_capture.setEnabled(False)

    # ---------- Results (main pass) ----------
    def on_finished_main(self, res: Dict[str, Any]):
        self.append_logs(res.get("logs"))

        if not res.get("ok"):
            QMessageBox.critical(self, "Run failed", str(res.get("error")))
            return

        self.best_vis.setText(res.get("best_visible") or "")
        self.best_norm.setText(res.get("best_normalized") or "")

        client = res.get("match_client")
        artikul = res.get("match_artikul")

        # Speak + show match
        if client and artikul:
            self.match_line.setText(f"{artikul} → {client}")
            speak_match(artikul, client)
        else:
            self.match_line.setText("not found")
            best = res.get("best_visible") or res.get("best_normalized")
            if best:
                speak(f"No match found. Best guess code: {_spell_code(best)}.")
            else:
                speak("No match found.")

        cost = res.get("gpt_cost")
        self.cost_line.setText(
            f"${cost:.6f}" if isinstance(cost, (int, float)) else "— (no API key)"
        )

        # If no match and pipeline suggests fuzzy, populate candidates and ASK
        self._last_cand_order = res.get("cand_order") or []
        if not client and res.get("prompt_fuzzy") and self._last_cand_order:
            # Fill the embedded list
            self.cand_list.clear()
            for vis, _norm in self._last_cand_order[:10]:
                QListWidgetItem(vis, self.cand_list)
            self.chk_use_shown.setChecked(True)
            self.fuzzy_box.setVisible(True)

            # Build a short preview and ask to start fuzzy now
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
                self.on_run_fuzzy_clicked()
            else:
                # Keep the group visible so you can run it later if you change your mind
                pass

        # re-enable after run finishes
        self._main_running = False
        # Only allow capture if camera is open
        self.btn_capture.setEnabled(self.cap is not None)
        # Let user tweak settings again
        self.model_combo.setEnabled(True)
        self.rb_auto.setEnabled(True)
        self.rb_vendor.setEnabled(True)
        self.rb_oem.setEnabled(True)

    # ---------- Fuzzy pass ----------
    def on_run_fuzzy_clicked(self):
        excel = self.xls_edit.text().strip()
        if not os.path.exists(excel):
            QMessageBox.critical(self, "Error", "Please choose a valid Excel file.")
            return
        if not self._last_cand_order:
            QMessageBox.information(self, "Fuzzy", "No candidates available.")
            return

        # Avoid starting a second fuzzy run while one is running
        if getattr(self, "_fthread", None) and self._fthread.isRunning():
            self.append_logs(["Fuzzy already running…"])
            return

        # Optionally limit to shown candidates
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

        self.append_logs(["Starting fuzzy…"])
        self.btn_run_fuzzy.setEnabled(False)

        # Create a new thread owned by the window (ties lifetime to self)
        self._fthread = QThread(self)
        self._fworker = FuzzyWorker(excel, cand, DEFAULT_MIN_FUZZY)
        self._fworker.moveToThread(self._fthread)

        self._fthread.started.connect(self._fworker.run)
        self._fworker.finished.connect(self.on_finished_fuzzy)
        self._fworker.finished.connect(self._fthread.quit)
        self._fworker.finished.connect(self._fworker.deleteLater)
        # When the thread finishes, clean up our refs and re-enable the button
        self._fthread.finished.connect(lambda: setattr(self, "_fthread", None))
        self._fthread.finished.connect(lambda: setattr(self, "_fworker", None))
        self._fthread.finished.connect(lambda: self.btn_run_fuzzy.setEnabled(True))
        self._fthread.finished.connect(self._fthread.deleteLater)

        self._fthread.start()

    def on_finished_fuzzy(self, res: Dict[str, Any]):
        self.append_logs(res.get("logs"))

        if not res.get("ok"):
            QMessageBox.critical(self, "Fuzzy failed", str(res.get("error")))
            return

        c = res.get("match_client")
        a = res.get("match_artikul")
        if c and a:
            self.match_line.setText(f"{a} → {c}")
            try:
                speak_match(a, c)
            except Exception:
                pass
            self.fuzzy_box.setVisible(False)
        else:
            QMessageBox.information(self, "Fuzzy", "No fuzzy match found.")

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
