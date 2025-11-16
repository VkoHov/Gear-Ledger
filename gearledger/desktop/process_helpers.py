# gearledger/desktop/process_helpers.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import multiprocessing as mp
import queue
from typing import Dict, Any, List, Tuple

from gearledger.pipeline import process_image, run_fuzzy_match
from gearledger.config import (
    DEFAULT_LANGS,
    DEFAULT_MIN_FUZZY,
    DEFAULT_MAX_ITEMS,
    DEFAULT_MAX_SIDE,
)


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


class ProcessManager:
    """Manages multiprocessing jobs for the desktop application."""

    def __init__(self):
        self.proc_main: mp.Process | None = None
        self.q_main: mp.Queue | None = None
        self.proc_fuzzy: mp.Process | None = None
        self.q_fuzzy: mp.Queue | None = None
        self._job_running = False
        self._fuzzy_running = False

    def start_main_job(self, image: str, excel_catalog: str, target: str, model: str):
        """Start the main OCR processing job."""
        if self._job_running:
            return False

        self._job_running = True
        self.q_main = mp.Queue()
        self.proc_main = mp.Process(
            target=_main_job,
            args=(image, excel_catalog, target, model, self.q_main),
            daemon=True,
        )
        self.proc_main.start()
        return True

    def start_fuzzy_job(
        self, excel_catalog: str, cand_order: List[Tuple[str, str]], min_fuzzy: int
    ):
        """Start the fuzzy matching job."""
        if self._fuzzy_running:
            return False

        self._fuzzy_running = True
        self.q_fuzzy = mp.Queue()
        self.proc_fuzzy = mp.Process(
            target=_fuzzy_job,
            args=(excel_catalog, cand_order, min_fuzzy, self.q_fuzzy),
            daemon=True,
        )
        self.proc_fuzzy.start()
        return True

    def poll_main_queue(self) -> Dict[str, Any] | None:
        """Poll the main job queue for results."""
        if not self.q_main:
            return None

        try:
            return self.q_main.get_nowait()
        except queue.Empty:
            if self.proc_main and not self.proc_main.is_alive():
                self._finish_main_process(None)
            return None

    def poll_fuzzy_queue(self) -> Dict[str, Any] | None:
        """Poll the fuzzy job queue for results."""
        if not self.q_fuzzy:
            return None

        try:
            return self.q_fuzzy.get_nowait()
        except queue.Empty:
            if self.proc_fuzzy and not self.proc_fuzzy.is_alive():
                self._finish_fuzzy_process(None)
            return None

    def _finish_main_process(self, res: Dict[str, Any] | None):
        """Clean up main process."""
        if self.proc_main:
            try:
                if self.proc_main.is_alive():
                    # Try to join with timeout (wait for process to finish naturally)
                    self.proc_main.join(timeout=1.0)
                    # If still alive after join, terminate it
                    if self.proc_main.is_alive():
                        self.proc_main.terminate()
                        self.proc_main.join(timeout=0.5)
                # Only close if process is not alive
                if not self.proc_main.is_alive():
                    self.proc_main.close()
            except Exception:
                # Process may already be gone or in invalid state
                pass
        self.proc_main = None
        self.q_main = None
        self._job_running = False

    def _finish_fuzzy_process(self, res: Dict[str, Any] | None):
        """Clean up fuzzy process."""
        if self.proc_fuzzy:
            try:
                if self.proc_fuzzy.is_alive():
                    # Try to join with timeout (wait for process to finish naturally)
                    self.proc_fuzzy.join(timeout=1.0)
                    # If still alive after join, terminate it
                    if self.proc_fuzzy.is_alive():
                        self.proc_fuzzy.terminate()
                        self.proc_fuzzy.join(timeout=0.5)
                # Only close if process is not alive
                if not self.proc_fuzzy.is_alive():
                    self.proc_fuzzy.close()
            except Exception:
                # Process may already be gone or in invalid state
                pass
        self.proc_fuzzy = None
        self.q_fuzzy = None
        self._fuzzy_running = False

    def cancel_all(self):
        """Cancel all running processes."""
        # Cancel main process
        if self.proc_main and self.proc_main.is_alive():
            self.proc_main.terminate()
            self.proc_main.join(timeout=0.5)
            self.proc_main.close()
            self.proc_main = None
            self.q_main = None
            self._job_running = False

        # Cancel fuzzy process
        if self.proc_fuzzy and self.proc_fuzzy.is_alive():
            self.proc_fuzzy.terminate()
            self.proc_fuzzy.join(timeout=0.5)
            self.proc_fuzzy.close()
            self.proc_fuzzy = None
            self.q_fuzzy = None
            self._fuzzy_running = False

    @property
    def job_running(self) -> bool:
        return self._job_running

    @property
    def fuzzy_running(self) -> bool:
        return self._fuzzy_running

    @property
    def any_running(self) -> bool:
        return self._job_running or self._fuzzy_running
