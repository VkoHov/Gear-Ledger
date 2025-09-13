# gearledger/speech.py
# -*- coding: utf-8 -*-
import sys
import subprocess

try:
    import pyttsx3

    _ENGINE = pyttsx3.init()
except Exception:
    _ENGINE = None


def speak(text: str):
    if not text:
        return
    if _ENGINE:
        try:
            _ENGINE.say(text)
            _ENGINE.runAndWait()
            return
        except Exception:
            pass
    if sys.platform == "darwin":
        try:
            subprocess.run(["say", text], check=False)
            return
        except Exception:
            pass
    print(f"[SPEAK] {text}")


# --- NEW: spell-out helpers for part codes ---
def _spell_code(code: str) -> str:
    """
    Read codes clearly: letters individually, digits individually,
    '-' as 'dash', '/' as 'slash'. Spaces become pauses.
    """
    if not code:
        return ""
    parts = []
    for ch in code:
        if ch.isalpha():
            parts.append(ch.upper())  # e.g., "A"
        elif ch.isdigit():
            parts.append(ch)  # e.g., "2"
        elif ch == "-":
            parts.append("dash")
        elif ch == "/":
            parts.append("slash")
        elif ch in (".", "_"):
            parts.append("dot")
        else:
            parts.append(" ")  # pause for spaces/others
    # collapse extra spaces
    spoken = " ".join(p for p in parts if p is not None)
    spoken = " ".join(spoken.split())
    return spoken.strip()


def speak_match(artikul: str, client: str):
    """
    Say: 'Match found. Code: A 2 1 0 dash 1 0 5. Client: ACME.'
    """
    code_spelled = _spell_code(artikul)
    if client:
        speak(f"Match found. Code: {code_spelled}. Client: {client}.")
    else:
        speak(f"Match found. Code: {code_spelled}.")
