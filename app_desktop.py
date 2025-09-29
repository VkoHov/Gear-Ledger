# app_desktop.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, tempfile, multiprocessing as mp, queue
from typing import Dict, Any, List, Tuple

# Make local package importable when running from repo root
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QImage, QTextCursor
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
    QSplitter,
    QScrollArea,
)

# --- project imports ---
from gearledger.pipeline import process_image, run_fuzzy_match
from gearledger.result_ledger import record_match
from gearledger.desktop.results_pane import ResultsPane
from gearledger.config import (
    DEFAULT_LANGS,
    DEFAULT_MODEL,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
    DEFAULT_TARGET,
)

# Optional speech helpers (guarded)
try:
    from gearledger.speech import speak, speak_match, _spell_code
except Exception:

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

# Results ledger default path (env or repo root file name)
RESULT_SHEET = os.getenv("RESULT_SHEET", "result.xlsx")


# ---------------- Camera helpers ----------------
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


# ---------------- Process job functions (must be top-level!) ----------------
def _main_job(image: str, excel_catalog: str, target: str, model: str, out_q: mp.Queue):
    """Runs the main pipeline in a separate process and puts result dict on out_q."""
    try:
        res = process_image(
            image,
            excel_catalog,  # lookup file
            langs=DEFAULT_LANGS,
            model=model,
            min_fuzzy=DEFAULT_MIN_FUZZY,
            max_items=DEFAULT_MAX_ITEMS,
            max_side=DEFAULT_MAX_SIDE,
            target=target,
        )
    except Exception as e:
        res = {"ok": False, "error": str(e), "logs": [f"[ERROR] {e}"]}
    out_q.put(res)


def _fuzzy_job(
    excel_catalog: str,
    cand_order: List[Tuple[str, str]],
    min_fuzzy: int,
    out_q: mp.Queue,
):
    """Runs fuzzy-matching in a separate process and puts result dict on out_q."""
    try:
        res = run_fuzzy_match(excel_catalog, cand_order, min_fuzzy)
    except Exception as e:
        res = {"ok": False, "error": str(e), "logs": [f"[ERROR] {e}"]}
    out_q.put(res)


# ---------------- Main Window (Camera UI + Bottom Excel table) ----------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GearLedger — desktop (camera)")
        self.resize(1100, 820)
        try:
            self.setWindowIcon(QIcon.fromTheme("applications-graphics"))
        except Exception:
            pass

        # State: processes & queues
        self.proc_main: mp.Process | None = None
        self.q_main: mp.Queue | None = None
        self.proc_fuzzy: mp.Process | None = None
        self.q_fuzzy: mp.Queue | None = None

        self._job_running = False
        self._fuzzy_running = False

        # --- Controls: Catalog Excel + Results Excel + Target + Model ---
        inputs = QGroupBox("Settings")

        lbl_catalog = QLabel("Catalog Excel (lookup):")
        self.catalog_edit = QLineEdit()
        btn_catalog = QPushButton("Browse…")
        btn_catalog.clicked.connect(self.pick_catalog_excel)

        lbl_results = QLabel("Results Excel (ledger):")
        self.results_edit = QLineEdit()
        self.results_edit.setText(RESULT_SHEET if RESULT_SHEET else "")
        btn_results = QPushButton("Browse…")
        btn_results.clicked.connect(self.pick_results_excel)

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
        r1.addWidget(lbl_catalog)
        r1.addWidget(self.catalog_edit, 1)
        r1.addWidget(btn_catalog)
        g.addLayout(r1)
        r1b = QHBoxLayout()
        r1b.addWidget(lbl_results)
        r1b.addWidget(self.results_edit, 1)
        r1b.addWidget(btn_results)
        g.addLayout(r1b)
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
        self.preview.setFixedHeight(430)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet(
            "QLabel { background:#111; color:#bbb; border:1px solid #333; }"
        )

        self.btn_start = QPushButton("Start camera")
        self.btn_capture = QPushButton("Capture & Run")
        self.btn_stop_cancel = QPushButton("Stop / Cancel")
        self.btn_capture.setEnabled(False)
        self.btn_stop_cancel.setEnabled(False)

        self.btn_start.clicked.connect(self.on_cam_start)
        self.btn_capture.clicked.connect(self.on_cam_capture_and_run)
        self.btn_stop_cancel.clicked.connect(self.on_stop_or_cancel)

        c = QVBoxLayout()
        c.addWidget(self.preview)
        cr = QHBoxLayout()
        cr.addWidget(self.btn_start)
        cr.addWidget(self.btn_capture)
        cr.addWidget(self.btn_stop_cancel)
        cr.addStretch(1)
        c.addLayout(cr)
        cam_box.setLayout(c)

        # --- Result summary (top) ---
        results = QGroupBox("Result summary")
        self.best_vis = QLineEdit()
        self.best_vis.setReadOnly(True)
        self.best_norm = QLineEdit()
        self.best_norm.setReadOnly(True)
        self.match_line = QLineEdit()
        self.match_line.setReadOnly(True)
        self.cost_line = QLineEdit()
        self.cost_line.setReadOnly(True)

        rg = QVBoxLayout()
        rr1 = QHBoxLayout()
        rr1.addWidget(QLabel("Best (visible):"))
        rr1.addWidget(self.best_vis, 1)
        rg.addLayout(rr1)
        rr2 = QHBoxLayout()
        rr2.addWidget(QLabel("Best (normalized):"))
        rr2.addWidget(self.best_norm, 1)
        rg.addLayout(rr2)
        rr3 = QHBoxLayout()
        rr3.addWidget(QLabel("Excel match:"))
        rr3.addWidget(self.match_line, 1)
        rg.addLayout(rr3)
        rr4 = QHBoxLayout()
        rr4.addWidget(QLabel("Est. GPT cost:"))
        rr4.addWidget(self.cost_line, 1)
        rg.addLayout(rr4)

        # Fuzzy UI
        self.fuzzy_box = QGroupBox("No exact match — try fuzzy?")
        self.fuzzy_box.setVisible(False)
        self.cand_list = QListWidget()
        self.cand_list.setMinimumHeight(100)
        self.chk_use_shown = QCheckBox("Limit fuzzy to shown candidates")
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

        # --- Logs (top) ---
        logs = QGroupBox("Logs")
        self.log_txt = QTextEdit()
        self.log_txt.setReadOnly(True)
        self.log_txt.setStyleSheet(
            "QTextEdit { background:#0b1220; color:#e5e7eb; font-family: Menlo, Consolas, monospace; }"
        )
        lg = QVBoxLayout()
        lg.addWidget(self.log_txt)
        logs.setLayout(lg)

        # --- TOP container holding original UI ---
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.addWidget(inputs)
        top_layout.addWidget(cam_box)
        top_layout.addWidget(results)
        top_layout.addWidget(logs, 1)

        # make the entire top part scrollable
        top_scroll = QScrollArea()
        top_scroll.setWidgetResizable(True)
        top_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        top_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        top_scroll.setWidget(top_container)

        # --- BOTTOM: Excel results table (shows ledger) ---
        self.results_pane = ResultsPane(
            self.results_edit.text().strip() or RESULT_SHEET
        )

        # --- Splitter so the bottom table is resizable ---
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_scroll)  # use the scroll area
        splitter.addWidget(self.results_pane)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # Root layout
        outer = QVBoxLayout()
        outer.addWidget(splitter)
        self.setLayout(outer)

        self.append_logs(["Ready."])

        # camera state
        self.cap = None
        self.timer: QTimer | None = None
        self._last_frame: np.ndarray | None = None

        # poll timers for process queues
        self.poll_main_timer = QTimer(self)
        self.poll_main_timer.timeout.connect(self._poll_main_queue)
        self.poll_fuzzy_timer = QTimer(self)
        self.poll_fuzzy_timer.timeout.connect(self._poll_fuzzy_queue)

        # store last cand_order for fuzzy
        self._last_cand_order: List[Tuple[str, str]] = []

        self._update_controls()

    # ---------- Busy-aware helpers ----------
    def _update_controls(self):
        busy = self._job_running or self._fuzzy_running
        cam_open = self.cap is not None

        # settings area
        for w in (
            self.catalog_edit,
            self.results_edit,
            self.rb_auto,
            self.rb_vendor,
            self.rb_oem,
            self.model_combo,
        ):
            w.setEnabled(not busy)

        # camera buttons
        self.btn_start.setEnabled((not busy) and (not cam_open))
        self.btn_capture.setEnabled((not busy) and cam_open)
        self.btn_stop_cancel.setEnabled(cam_open or busy)

        # fuzzy controls
        self.cand_list.setEnabled(not busy)
        self.chk_use_shown.setEnabled(not busy)
        self.btn_run_fuzzy.setEnabled((not busy) and self.fuzzy_box.isVisible())

    def _set_job_running(self, running: bool):
        self._job_running = running
        self._update_controls()

    def _set_fuzzy_running(self, running: bool):
        self._fuzzy_running = running
        self._update_controls()

    # ---------- Helpers ----------
    def append_logs(self, lines: List[str]):
        for ln in lines or []:
            self.log_txt.append(ln)
        # auto-scroll to bottom
        self.log_txt.moveCursor(QTextCursor.MoveOperation.End)

    def pick_catalog_excel(self):
        if self._job_running or self._fuzzy_running:
            return
        fn, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Catalog Excel (lookup)",
            filter="Excel (*.xlsx *.xlsm *.xls);;All files (*)",
        )
        if fn:
            self.catalog_edit.setText(fn)

    def pick_results_excel(self):
        if self._job_running or self._fuzzy_running:
            return
        fn, _ = QFileDialog.getSaveFileName(
            self,
            "Choose Results Excel (ledger)",
            filter="Excel (*.xlsx);;All files (*)",
            selectedFilter="Excel (*.xlsx)",
        )
        if fn:
            if not os.path.splitext(fn)[1]:
                fn = fn + ".xlsx"
            self.results_edit.setText(fn)
            self.results_pane.set_ledger_path(fn)  # bottom table now watches this file

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
        if self._job_running or self._fuzzy_running:
            return
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
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._grab_and_show)
        self.timer.start(30)
        self._update_controls()

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

    # ---------- Start main job (process) ----------
    def on_cam_capture_and_run(self):
        if self._job_running or self._fuzzy_running:
            return
        if self._last_frame is None:
            QMessageBox.information(self, "Camera", "No frame yet. Try again.")
            return

        catalog = self.catalog_edit.text().strip()
        if not os.path.exists(catalog):
            QMessageBox.critical(
                self, "Error", "Please choose a valid Catalog Excel file."
            )
            return

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        try:
            cv2.imwrite(tmp.name, self._last_frame)
        except Exception as e:
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

        # start process
        self._set_job_running(True)
        self.q_main = mp.Queue()
        self.proc_main = mp.Process(
            target=_main_job,
            args=(
                tmp.name,
                catalog,
                self._current_target(),
                self._current_model(),
                self.q_main,
            ),
            daemon=True,
        )
        self.proc_main.start()
        self.poll_main_timer.start(100)  # poll every 100ms

    def _poll_main_queue(self):
        if not self.q_main:
            return
        try:
            res = self.q_main.get_nowait()
        except queue.Empty:
            if self.proc_main and (not self.proc_main.is_alive()):
                self._finish_main_process(None)
            return
        self._finish_main_process(res)

    def _finish_main_process(self, res: Dict[str, Any] | None):
        self.poll_main_timer.stop()
        if self.proc_main:
            if self.proc_main.is_alive():
                self.proc_main.join(timeout=0.2)
            self.proc_main.close()
        self.proc_main = None
        self.q_main = None
        self._set_job_running(False)

        if res is None:
            self.append_logs(["[INFO] Job was canceled."])
            self.match_line.setText("canceled")
            return

        # -------- Handle main result --------
        self.append_logs(res.get("logs"))
        if not res.get("ok"):
            QMessageBox.critical(self, "Run failed", str(res.get("error")))
            return

        self.best_vis.setText(res.get("best_visible") or "")
        self.best_norm.setText(res.get("best_normalized") or "")

        client = res.get("match_client")
        artikul = res.get("match_artikul")
        ledger_path = self.results_edit.text().strip() or RESULT_SHEET

        if client and artikul:
            self.match_line.setText(f"{artikul} → {client}")
            speak_match(artikul, client)
            rec = record_match(ledger_path, artikul, client, qty_inc=1, weight_inc=1)
            if rec["ok"]:
                self.append_logs(
                    [f"[INFO] Logged to results: {rec['action']} → {rec['path']}"]
                )
                self.results_pane.refresh()  # update bottom table
            else:
                self.append_logs([f"[WARN] Results log failed: {rec['error']}"])
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

        # If no match, suggest fuzzy and ask
        self._last_cand_order = res.get("cand_order") or []
        if not client and res.get("prompt_fuzzy") and self._last_cand_order:
            self.cand_list.clear()
            for vis, _norm in self._last_cand_order[:10]:
                QListWidgetItem(vis, self.cand_list)
            self.chk_use_shown.setChecked(True)
            self.fuzzy_box.setVisible(True)

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

        self._update_controls()

    # ---------- Stop / Cancel ----------
    def on_stop_or_cancel(self):
        # Cancel main process
        if self.proc_main and self.proc_main.is_alive():
            self.proc_main.terminate()
            self.proc_main.join(timeout=0.5)
            self.proc_main.close()
            self.proc_main = None
            self.q_main = None
            self.poll_main_timer.stop()
            self._set_job_running(False)
            self.append_logs(["[INFO] Main job canceled."])

        # Cancel fuzzy process
        if self.proc_fuzzy and self.proc_fuzzy.is_alive():
            self.proc_fuzzy.terminate()
            self.proc_fuzzy.join(timeout=0.5)
            self.proc_fuzzy.close()
            self.proc_fuzzy = None
            self.q_fuzzy = None
            self.poll_fuzzy_timer.stop()
            self._set_fuzzy_running(False)
            self.append_logs(["[INFO] Fuzzy job canceled."])

        # Stop camera
        if self.cap:
            self._really_stop_camera()

        self._update_controls()

    def _really_stop_camera(self):
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.cap:
            release_camera(self.cap)
            self.cap = None
        self.preview.setText("Camera preview")

    # ---------- Fuzzy pass (process) ----------
    def on_run_fuzzy_clicked(self):
        if self._job_running or self._fuzzy_running:
            return

        catalog = self.catalog_edit.text().strip()
        if not os.path.exists(catalog):
            QMessageBox.critical(
                self, "Error", "Please choose a valid Catalog Excel file."
            )
            return
        if not self._last_cand_order:
            QMessageBox.information(self, "Fuzzy", "No candidates available.")
            return

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

        self._set_fuzzy_running(True)
        self.q_fuzzy = mp.Queue()
        self.proc_fuzzy = mp.Process(
            target=_fuzzy_job,
            args=(catalog, cand, DEFAULT_MIN_FUZZY, self.q_fuzzy),
            daemon=True,
        )
        self.proc_fuzzy.start()
        self.poll_fuzzy_timer.start(100)

    def _poll_fuzzy_queue(self):
        if not self.q_fuzzy:
            return
        try:
            res = self.q_fuzzy.get_nowait()
        except queue.Empty:
            if self.proc_fuzzy and (not self.proc_fuzzy.is_alive()):
                self._finish_fuzzy_process(None)
            return
        self._finish_fuzzy_process(res)

    def _finish_fuzzy_process(self, res: Dict[str, Any] | None):
        self.poll_fuzzy_timer.stop()
        if self.proc_fuzzy:
            if self.proc_fuzzy.is_alive():
                self.proc_fuzzy.join(timeout=0.2)
            self.proc_fuzzy.close()
        self.proc_fuzzy = None
        self.q_fuzzy = None
        self._set_fuzzy_running(False)

        if res is None:
            self.append_logs(["[INFO] Fuzzy job was canceled."])
            return

        self.append_logs(res.get("logs"))
        if not res.get("ok"):
            QMessageBox.critical(self, "Fuzzy failed", str(res.get("error")))
            return

        c = res.get("match_client")
        a = res.get("match_artikul")
        ledger_path = self.results_edit.text().strip() or RESULT_SHEET

        if c and a:
            self.match_line.setText(f"{a} → {c}")
            speak_match(a, c)
            self.fuzzy_box.setVisible(False)
            rec = record_match(ledger_path, a, c, qty_inc=1, weight_inc=1)
            if rec["ok"]:
                self.append_logs(
                    [f"[INFO] Logged to results: {rec['action']} → {rec['path']}"]
                )
                self.results_pane.refresh()
            else:
                self.append_logs([f"[WARN] Results log failed: {rec['error']}"])
        else:
            QMessageBox.information(self, "Fuzzy", "No fuzzy match found.")

        self._update_controls()

    # ---------- Cleanup ----------
    def closeEvent(self, event):
        # kill any running processes
        if self.proc_main and self.proc_main.is_alive():
            self.proc_main.terminate()
            self.proc_main.join(timeout=0.5)
        if self.proc_fuzzy and self.proc_fuzzy.is_alive():
            self.proc_fuzzy.terminate()
            self.proc_fuzzy.join(timeout=0.5)
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.cap:
            release_camera(self.cap)
            self.cap = None
        super().closeEvent(event)


def main():
    # macOS-safe multiprocessing start method
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass

    os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
