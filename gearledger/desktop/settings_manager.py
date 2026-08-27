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
    language: str = "en"  # UI language: "en" or "ru"
    # Remember the user's last-chosen input mode for each widget, instead
    # of always resetting to scale/camera mode on every launch.
    scale_manual_mode: bool = False
    camera_manual_mode: bool = False
    # Deprecated: OpenAI TTS is no longer used (kept for backwards compatibility only)
    use_openai_tts: bool = False
    # Speech / voice settings (only OS and Piper are supported)
    speech_engine: str = "os"  # "os" or "piper"
    piper_voice: str = "hy_AM-gor-medium"  # Default Armenian Piper voice
    piper_binary_path: str = ""  # Custom Piper executable path (optional)
    # Network mode settings
    network_mode: str = "server"  # "server" (local, solo or hosting) or "client"
    # Independently controls whether the local HTTP listener binds a port
    # for LAN clients when network_mode == "server". Decoupled from
    # storage (server mode's DB backend is always used regardless of this
    # flag) — off by default so solo users get zero network exposure
    # (matching the old "standalone" behavior) while still using the DB
    # instead of an Excel file.
    server_sharing_enabled: bool = False
    # Port for server mode. Default deliberately avoids 8080 — Windows'
    # Hyper-V/WSL2 virtual switch commonly reserves it as part of an
    # "excluded port range" for its own NAT, which silently drops inbound
    # connections to that port even though the app is genuinely listening
    # on it (confirmed on a real deployment: netsh interface ipv4 show
    # excludedportrange protocol=tcp showed 8080 reserved).
    server_port: int = 8081
    server_address: str = (
        ""  # Address to connect to in client mode (e.g., "192.168.1.100:8081")
    )
    # Friendly name shown to clients in the server picker instead of raw
    # IP:port (e.g. "Warehouse Server") — empty means fall back to this
    # machine's hostname, set at server-start time.
    server_name: str = ""
    # Cloud auth: identity/tenant metadata only, not secret — safe to keep
    # in plain settings.json. The JWT itself is not a Settings field; it
    # lives in the OS credential store (see get_auth_token() below) rather
    # than plaintext on disk.
    auth_email: str = ""
    auth_tenant_id: str = ""
    cloud_server_url: str = ""
    # Last Reset/Restore breadcrumb — informational only, not true version
    # tracking (the app has no notion of "is the live data still exactly
    # version X" once anything changes after a restore).
    last_results_action: str = ""  # "reset" or "restore", empty = never happened
    last_results_action_at: str = ""  # ISO timestamp
    last_results_action_detail: str = ""  # e.g. archived version filename


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


def is_path_for_this_platform(path: str) -> bool:
    """Check whether *path* looks like it was saved on this OS.

    settings.json can end up on a different machine/OS than it was written
    on (e.g. a copied config, or a synced app-data folder). A path saved on
    macOS/Linux (e.g. "/Users/name/...") is syntactically "absolute" on
    Windows too (rooted, just driveless) — os.path.isabs() alone won't catch
    the mismatch — so check for a drive letter/UNC prefix on Windows instead.
    """
    if not path:
        return False
    if os.name == "nt":
        drive, _ = os.path.splitdrive(path)
        return bool(drive)
    return path.startswith("/") or path.startswith(os.path.expanduser("~"))


def get_versions_dir() -> str:
    """Get (and ensure) the directory where retired result-file versions are archived."""
    ensure_dirs()
    versions_dir = os.path.join(APP_DIR, "data", "versions")
    os.makedirs(versions_dir, exist_ok=True)
    return versions_dir


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


def record_last_results_action(action: str, detail: str = ""):
    """Record a Reset/Restore breadcrumb — informational provenance only,
    not true version tracking (once anything changes after a restore, the
    live data is no longer verifiably "exactly" that version)."""
    import datetime

    settings = load_settings()
    settings.last_results_action = action
    settings.last_results_action_at = datetime.datetime.now().isoformat()
    settings.last_results_action_detail = detail
    save_settings(settings)


def get_settings_path() -> str:
    """Get the path to the settings file (for display purposes)."""
    return CFG_PATH


def get_use_openai_tts() -> bool:
    """OpenAI TTS is no longer used; always return False (for backwards compatibility)."""
    return False


def set_use_openai_tts(value: bool):
    """OpenAI TTS is no longer used; keep the stored flag False for backwards compatibility."""
    settings = load_settings()
    if settings.use_openai_tts:
        settings.use_openai_tts = False
        save_settings(settings)


def get_speech_engine() -> str:
    """Get current speech engine ('os' or 'piper')."""
    settings = load_settings()
    # Clamp to supported values; map any legacy 'openai' value back to 'os'
    if settings.speech_engine not in ("os", "piper"):
        return "os"
    return settings.speech_engine


def set_speech_engine(engine: str):
    """Set current speech engine ('os' or 'piper')."""
    if engine not in ("os", "piper"):
        engine = "os"
    settings = load_settings()
    settings.speech_engine = engine
    # Ensure legacy OpenAI flag is always off
    settings.use_openai_tts = False
    save_settings(settings)


def get_piper_voice() -> str:
    """Get configured Piper voice model id."""
    settings = load_settings()
    return settings.piper_voice or "hy_AM-gor-medium"


def set_piper_voice(voice: str):
    """Set Piper voice model id."""
    settings = load_settings()
    settings.piper_voice = voice or "hy_AM-gor-medium"
    save_settings(settings)


def get_piper_binary_path() -> str:
    """Get custom Piper binary path (may be empty)."""
    settings = load_settings()
    return settings.piper_binary_path or ""


def set_piper_binary_path(path: str):
    """Set custom Piper binary path."""
    settings = load_settings()
    settings.piper_binary_path = path or ""
    save_settings(settings)


# Cloud auth token storage — deliberately not a Settings/settings.json
# field. What's stored here is the refresh token (30 days) — a JWT is a
# bearer credential, so it goes in the OS credential store (Windows
# Credential Manager / macOS Keychain via `keyring`) instead of plaintext
# JSON on disk. The short-lived (30 min) access token that pairs with it
# is never persisted at all — api_client.APIClient keeps it in memory
# only and re-derives it from this refresh token on demand (see
# APIClient._try_refresh). Everything *about* the login (email, tenant
# id, which cloud URL) is non-secret and still lives in Settings as usual.
_KEYRING_SERVICE = "GearLedger"
_KEYRING_USERNAME = "cloud_auth_token"


def get_auth_token() -> str:
    """Return the stored refresh token, or "" if there isn't one (never
    logged in, logged out, or the OS keyring is unavailable/inaccessible)."""
    try:
        import keyring

        return keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME) or ""
    except Exception as e:
        print(f"[WARNING] Failed to read auth token from keyring: {e}")
        return ""


def save_auth(token: str, tenant_id: str, email: str, cloud_server_url: str):
    """Persist a successful login (or a token refresh's rotation): the
    refresh token goes to the OS keyring, everything else to settings.json."""
    try:
        import keyring

        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, token)
    except Exception as e:
        print(f"[ERROR] Failed to save auth token to keyring: {e}")

    settings = load_settings()
    settings.auth_tenant_id = tenant_id
    settings.auth_email = email
    settings.cloud_server_url = cloud_server_url
    save_settings(settings)


def clear_auth():
    """Log out: drop the token from the keyring and forget the tenant/email
    so the login dialog doesn't pre-fill a session that no longer works."""
    try:
        import keyring

        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except Exception:
        pass  # nothing stored, or keyring unavailable — either way, nothing to clean up

    settings = load_settings()
    settings.auth_tenant_id = ""
    settings.auth_email = ""
    save_settings(settings)
