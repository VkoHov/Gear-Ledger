# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

# Cross-platform app data directory
if os.name == "nt":  # Windows
    APP_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")),
        "GearLedger",
    )
else:  # macOS/Linux
    APP_DIR = os.path.join(os.path.expanduser("~"), ".gearledger")

CFG_PATH = os.path.join(APP_DIR, "settings.json")


@dataclass
class Settings:
    """Application settings stored in user's app data directory."""

    openai_api_key: str = ""
    vision_backend: str = "openai"  # "openai" or "paddle"
    openai_model: str = "gpt-4o-mini"
    cam_index: int = 0
    cam_width: int = 1280
    cam_height: int = 720
    scale_port: str = ""  # Empty means not set
    scale_baudrate: int = 9600
    weight_threshold: float = 0.1  # kg
    stable_time: float = 2.0  # seconds
    price_per_kg: float = 1200.0
    default_target: str = "auto"  # "auto", "vendor", "oem"
    default_min_fuzzy: int = 70
    default_result_file: str = ""  # Default result file path (empty = auto-generate)
    show_logs: bool = True  # Show/hide logs widget in both tabs


def ensure_dirs():
    """Ensure app directories exist."""
    os.makedirs(APP_DIR, exist_ok=True)
    data_dir = os.path.join(APP_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_default_result_file() -> str:
    """Get the default result file path. Creates it in app data directory if not set."""
    ensure_dirs()
    data_dir = os.path.join(APP_DIR, "data")
    default_path = os.path.join(data_dir, "results.xlsx")
    return default_path


def load_settings() -> Settings:
    """Load settings from disk, or create defaults if not found."""
    ensure_dirs()

    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults to handle new fields
            defaults = asdict(Settings())
            defaults.update(data)
            return Settings(**defaults)
        except Exception as e:
            print(f"[WARNING] Failed to load settings: {e}, using defaults")

    # Create default settings
    s = Settings()
    save_settings(s)
    return s


def save_settings(s: Settings):
    """Save settings to disk."""
    ensure_dirs()
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(s), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save settings: {e}")


def get_settings_path() -> str:
    """Get the path to the settings file (for display purposes)."""
    return CFG_PATH
