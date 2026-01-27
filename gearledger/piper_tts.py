"""Piper TTS integration for GearLedger.

Provides helpers to download and run local Piper TTS models (e.g., Armenian hy_AM-gor-medium).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Tuple

from huggingface_hub import hf_hub_download
from platformdirs import user_data_dir

from gearledger.desktop.settings_manager import (
    APP_DIR,
    get_piper_voice,
    get_piper_binary_path,
)


# Known Piper voices and their Hugging Face locations (Armenian)
_PIPER_VOICES = {
    "hy_AM-gor-medium": {
        "repo_id": "davit312/piper-TTS-Armenian",
        "filenames": [
            "v1/hy_AM-gor-medium.onnx",
            "v1/hy_AM-gor-medium.onnx.json",
        ],
    },
}


def _get_platform_voices_root() -> str:
    """Root directory for voices using platformdirs (preferred)."""
    base = user_data_dir("GearLedger", "GearLedger")
    voices_root = os.path.join(base, "voices", "piper")
    os.makedirs(voices_root, exist_ok=True)
    return voices_root


def _get_legacy_voices_root() -> str:
    """Legacy voices root (~/.gearledger/voices/piper)."""
    legacy_root = os.path.join(APP_DIR, "voices", "piper")
    # Do not create here; only used for lookups
    return legacy_root


def get_piper_voices_root() -> str:
    """Return preferred voices root (platformdirs-based)."""
    return _get_platform_voices_root()


def get_voice_dir(voice_id: str) -> str:
    """Get directory for a specific Piper voice (platformdirs-based)."""
    root = get_piper_voices_root()
    path = os.path.join(root, voice_id)
    os.makedirs(path, exist_ok=True)
    return path


def get_voice_files(voice_id: str) -> Tuple[str, str]:
    """Return (model_path, config_path) for given voice id.

    Supports both:
      .../hy_AM-gor-medium/v1/hy_AM-gor-medium.onnx
      .../hy_AM-gor-medium/hy_AM-gor-medium.onnx
    and legacy ~/.gearledger layout.
    """
    base = get_voice_dir(voice_id)
    legacy_root = _get_legacy_voices_root()

    candidates = []

    # Preferred platformdirs paths
    candidates.append(
        (
            os.path.join(base, "v1", f"{voice_id}.onnx"),
            os.path.join(base, "v1", f"{voice_id}.onnx.json"),
        )
    )
    candidates.append(
        (
            os.path.join(base, f"{voice_id}.onnx"),
            os.path.join(base, f"{voice_id}.onnx.json"),
        )
    )

    # Legacy ~/.gearledger paths
    legacy_base = os.path.join(legacy_root, voice_id)
    candidates.append(
        (
            os.path.join(legacy_base, "v1", f"{voice_id}.onnx"),
            os.path.join(legacy_base, "v1", f"{voice_id}.onnx.json"),
        )
    )
    candidates.append(
        (
            os.path.join(legacy_base, f"{voice_id}.onnx"),
            os.path.join(legacy_base, f"{voice_id}.onnx.json"),
        )
    )

    for model_path, config_path in candidates:
        if os.path.isfile(model_path) and os.path.isfile(config_path):
            return model_path, config_path

    # Fallback to preferred v1 layout
    model_path = os.path.join(base, "v1", f"{voice_id}.onnx")
    config_path = os.path.join(base, "v1", f"{voice_id}.onnx.json")
    return model_path, config_path


def download_piper_voice_model(voice_id: str | None = None) -> Tuple[str, str]:
    """Download Piper voice model + config into app data (platformdirs-based).

    Returns:
        (model_path, config_path)
    """
    vid = voice_id or get_piper_voice()
    info = _PIPER_VOICES.get(vid)
    if not info:
        raise ValueError(f"Unknown Piper voice id: {vid}")

    dest_base = get_voice_dir(vid)
    dest_v1 = os.path.join(dest_base, "v1")
    os.makedirs(dest_v1, exist_ok=True)

    repo_id = info["repo_id"]
    filenames = info["filenames"]

    for filename in filenames:
        # filename already includes "v1/..."
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=dest_base,
            local_dir_use_symlinks=False,
        )

    # After download, resolve final paths
    return get_voice_files(vid)


def resolve_piper_binary() -> str | None:
    """Resolve Piper binary path from settings or system PATH."""
    custom = get_piper_binary_path()
    if custom and os.path.isfile(custom):
        return custom

    # Check app-local bin
    candidates = []
    if os.name == "nt":
        candidates.append(os.path.join(APP_DIR, "bin", "piper.exe"))
    else:
        candidates.append(os.path.join(APP_DIR, "bin", "piper"))

    for cand in candidates:
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand

    # Fallback to system PATH
    from shutil import which

    return which("piper")


def speak_with_piper(text: str) -> bool:
    """Speak text using Piper if possible. Returns True if Piper was used."""
    if not text:
        return False

    voice_id = get_piper_voice()
    model_path, config_path = get_voice_files(voice_id)

    if not (os.path.isfile(model_path) and os.path.isfile(config_path)):
        print(
            f"[PIPER] Voice model not found for '{voice_id}', falling back to OS TTS."
        )
        return False

    binary = resolve_piper_binary()
    if not binary:
        print("[PIPER] Piper binary not found, falling back to OS TTS.")
        return False

    print(
        f"[PIPER] Using binary='{binary}', model='{model_path}', config='{config_path}'"
    )

    # Create temporary WAV file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        wav_path = tmp.name

    # Run Piper to generate audio
    try:
        result = subprocess.run(
            [
                binary,
                "-m",
                model_path,
                "-c",
                config_path,
                "-f",
                wav_path,
            ],
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore")
            print(f"[PIPER] Piper failed: {stderr}")
            try:
                os.unlink(wav_path)
            except OSError:
                pass
            return False
    except Exception as e:
        print(f"[PIPER] Piper invocation failed: {e}")
        try:
            os.unlink(wav_path)
        except OSError:
            pass
        return False

    # Play WAV file (blocking)
    playback_done = False
    try:
        if sys.platform == "darwin":
            r = subprocess.run(["afplay", wav_path], check=False)
            playback_done = r.returncode == 0
        elif sys.platform == "win32":
            try:
                import playsound

                playsound.playsound(wav_path, block=True)
                playback_done = True
            except ImportError:
                os.startfile(wav_path)
        else:
            for player in ["ffplay", "mpv", "aplay", "mpg123", "mpg321"]:
                try:
                    subprocess.run([player, wav_path], check=False, timeout=30)
                    playback_done = True
                    break
                except FileNotFoundError:
                    continue
    finally:
        # Cleanup in background
        def cleanup():
            try:
                import time

                time.sleep(5 if playback_done else 90)
                if os.path.exists(wav_path):
                    os.unlink(wav_path)
            except Exception:
                pass

        threading.Thread(target=cleanup, daemon=True).start()

    return True
