# gearledger/speech.py
# -*- coding: utf-8 -*-
import sys
import subprocess

# Don't initialize engine at module level - create it on demand
_ENGINE_AVAILABLE = None


def _get_engine():
    """Get or create a pyttsx3 engine instance."""
    global _ENGINE_AVAILABLE
    try:
        import pyttsx3

        if _ENGINE_AVAILABLE is None:
            # Check if pyttsx3 is available
            try:
                test_engine = pyttsx3.init()
                test_engine.stop()  # Clean up test engine
                _ENGINE_AVAILABLE = True
            except Exception:
                _ENGINE_AVAILABLE = False
                return None

        if _ENGINE_AVAILABLE:
            # Create a new engine instance each time to avoid issues
            engine = pyttsx3.init()
            return engine
    except Exception:
        _ENGINE_AVAILABLE = False
    return None


def speak(text: str):
    if not text:
        return

    # Try pyttsx3 first
    engine = _get_engine()
    if engine:
        try:
            engine.say(text)
            engine.runAndWait()
            engine.stop()  # Clean up after use
            return
        except Exception:
            # If engine fails, try fallback
            pass

    # Fallback to system speech (macOS say command)
    if sys.platform == "darwin":
        try:
            subprocess.run(["say", text], check=False)
            return
        except Exception:
            pass

    # Final fallback: print to console
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
