# -*- coding: utf-8 -*-
"""
Logging setup for Gear Ledger.

Writes to ~/.gear-ledger/logs/app.log with rotation (1 MB × 3 files).
Console prints are kept unchanged throughout the codebase.

Usage:
    # Once at startup (app_desktop.py):
    from gearledger.logging_utils import setup_logging
    setup_logging()

    # In any module that needs file logging:
    from gearledger.logging_utils import get_logger
    _log = get_logger(__name__)
    _log.info("something happened")
    _log.error("something failed", exc_info=True)  # includes traceback
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

_LOG_DIR = Path.home() / ".gear-ledger" / "logs"
_LOG_FILE = _LOG_DIR / "app.log"

# Root logger for the whole package
_logger = logging.getLogger("gearledger")
_initialized = False


def setup_logging(level: int = logging.DEBUG) -> None:
    """
    Initialize file logging. Call once at app startup.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler: 1 MB per file, keep last 3
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    fh.setLevel(level)

    _logger.setLevel(level)
    _logger.addHandler(fh)

    # Do NOT add a StreamHandler — existing print() calls stay as-is
    _logger.info("=" * 60)
    _logger.info("Gear Ledger started")
    _logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'gearledger' namespace.
    Pass __name__ from the calling module — it is already namespaced
    correctly when the module lives inside the gearledger package.

    Example:
        _log = get_logger(__name__)
        _log.info("catalog loaded")
        _log.error("write failed", exc_info=True)
    """
    # Ensure the logger is always a child of 'gearledger' so it inherits
    # the file handler regardless of what name is passed.
    if name == "gearledger" or name.startswith("gearledger."):
        return logging.getLogger(name)
    return logging.getLogger(f"gearledger.{name}")


def get_log_path() -> str:
    """Return the absolute path to the current log file."""
    return str(_LOG_FILE)


# ---------------------------------------------------------------------------
# Convenience wrappers (keep existing call sites working, now also log to file)
# ---------------------------------------------------------------------------

def step(msg: str) -> None:
    print(f"[STEP] {msg}")
    _logger.info("[STEP] %s", msg)


def info(msg: str) -> None:
    print(f"[INFO] {msg}")
    _logger.info("%s", msg)


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")
    _logger.warning("%s", msg)


def err(msg: str) -> None:
    print(f"[ERROR] {msg}")
    _logger.error("%s", msg)
