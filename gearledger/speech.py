# gearledger/speech.py
# -*- coding: utf-8 -*-
import sys
import subprocess

# Don't initialize engine at module level - create it on demand
_ENGINE_AVAILABLE = None

# Current speech language (synced with app language)
_SPEECH_LANGUAGE = "en"

# macOS voice names for different languages
_MACOS_VOICES = {
    "en": "Samantha",  # English voice
    "ru": "Milena",  # Russian voice (if installed)
}


def set_speech_language(lang: str):
    """Set the speech language."""
    global _SPEECH_LANGUAGE
    _SPEECH_LANGUAGE = lang


def get_speech_language() -> str:
    """Get current speech language."""
    return _SPEECH_LANGUAGE


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

            # Try to set voice based on language
            try:
                voices = engine.getProperty("voices")
                target_lang = _SPEECH_LANGUAGE

                for voice in voices:
                    voice_id = voice.id.lower()
                    voice_name = voice.name.lower() if voice.name else ""

                    # Check for Russian voice
                    if target_lang == "ru":
                        if (
                            "ru" in voice_id
                            or "russian" in voice_id
                            or "milena" in voice_name
                            or "yuri" in voice_name
                        ):
                            engine.setProperty("voice", voice.id)
                            break
                    # Check for English voice
                    elif target_lang == "en":
                        if "en" in voice_id or "english" in voice_id:
                            engine.setProperty("voice", voice.id)
                            break
            except Exception:
                pass  # Use default voice if setting fails

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
            voice = _MACOS_VOICES.get(_SPEECH_LANGUAGE, "Samantha")
            # Try with specified voice first
            result = subprocess.run(
                ["say", "-v", voice, text], check=False, capture_output=True
            )
            if result.returncode != 0:
                # If voice not available, try default
                subprocess.run(["say", text], check=False)
            return
        except Exception:
            pass

    # Final fallback: print to console
    print(f"[SPEAK] {text}")


# --- NEW: spell-out helpers for part codes ---

# Punctuation words in different languages
_PUNCT_WORDS = {
    "en": {
        "-": "dash",
        "/": "slash",
        ".": "dot",
        "_": "underscore",
    },
    "ru": {
        "-": "дефис",
        "/": "слэш",
        ".": "точка",
        "_": "подчёркивание",
    },
}

# Match messages in different languages
_MATCH_MESSAGES = {
    "en": {
        "match_found": "Match found",
        "code": "Code",
        "client": "Client",
        "no_match": "No match found",
    },
    "ru": {
        "match_found": "Найдено совпадение",
        "code": "Код",
        "client": "Клиент",
        "no_match": "Совпадение не найдено",
    },
}


def _spell_code(code: str) -> str:
    """
    Read codes clearly: letters individually, digits individually,
    '-' as 'dash/дефис', '/' as 'slash/слэш'. Spaces become pauses.
    """
    if not code:
        return ""

    punct = _PUNCT_WORDS.get(_SPEECH_LANGUAGE, _PUNCT_WORDS["en"])

    parts = []
    for ch in code:
        if ch.isalpha():
            parts.append(ch.upper())  # e.g., "A"
        elif ch.isdigit():
            parts.append(ch)  # e.g., "2"
        elif ch == "-":
            parts.append(punct.get("-", "dash"))
        elif ch == "/":
            parts.append(punct.get("/", "slash"))
        elif ch in (".", "_"):
            parts.append(punct.get(".", "dot"))
        else:
            parts.append(" ")  # pause for spaces/others
    # collapse extra spaces
    spoken = " ".join(p for p in parts if p is not None)
    spoken = " ".join(spoken.split())
    return spoken.strip()


def speak_match(artikul: str, client: str):
    """
    Say: 'Match found. Code: A 2 1 0 dash 1 0 5. Client: ACME.'
    In Russian: 'Найдено совпадение. Код: A 2 1 0 дефис 1 0 5. Клиент: ACME.'
    """
    msgs = _MATCH_MESSAGES.get(_SPEECH_LANGUAGE, _MATCH_MESSAGES["en"])
    code_spelled = _spell_code(artikul)

    if client:
        speak(
            f"{msgs['match_found']}. {msgs['code']}: {code_spelled}. {msgs['client']}: {client}."
        )
    else:
        speak(f"{msgs['match_found']}. {msgs['code']}: {code_spelled}.")
