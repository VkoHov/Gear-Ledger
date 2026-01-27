# gearledger/speech.py
# -*- coding: utf-8 -*-
import sys
import subprocess
import os
import tempfile
import threading

# Don't initialize engine at module level - create it on demand
_ENGINE_AVAILABLE = None

# Current speech language (synced with app language)
_SPEECH_LANGUAGE = "en"

# Preferred macOS voices (in order of preference)
_MACOS_VOICE_PREFERENCES = {
    "en": ["Samantha", "Alex", "Victoria", "Karen", "Daniel"],
    "ru": ["Milena", "Yuri", "Katya", "Anna"],
}

# Cache for available voices (detected at runtime)
_AVAILABLE_MACOS_VOICES = None


def set_speech_language(lang: str):
    """Set the speech language."""
    global _SPEECH_LANGUAGE
    _SPEECH_LANGUAGE = lang


def get_speech_language() -> str:
    """Get current speech language."""
    return _SPEECH_LANGUAGE


def _list_macos_voices() -> list[str]:
    """List all available macOS voices by querying the system."""
    global _AVAILABLE_MACOS_VOICES
    if _AVAILABLE_MACOS_VOICES is not None:
        return _AVAILABLE_MACOS_VOICES

    if sys.platform != "darwin":
        _AVAILABLE_MACOS_VOICES = []
        return []

    try:
        result = subprocess.run(
            ["say", "-v", "?"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            voices = []
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # Format: "Voice Name    Language    # Comment"
                    # Extract first word (voice name)
                    parts = line.split()
                    if parts:
                        voice_name = parts[0]
                        voices.append(voice_name)
            _AVAILABLE_MACOS_VOICES = voices
            return voices
    except Exception as e:
        print(f"[SPEECH] Failed to list macOS voices: {e}")

    _AVAILABLE_MACOS_VOICES = []
    return []


def _pick_macos_voice(lang: str) -> str:
    """
    Pick the best available macOS voice for the given language.
    Returns the first available voice from preferences, or default if none found.
    """
    available = _list_macos_voices()
    if not available:
        return "Samantha"  # Default fallback

    preferences = _MACOS_VOICE_PREFERENCES.get(lang, _MACOS_VOICE_PREFERENCES["en"])

    # Find first preferred voice that exists
    for preferred in preferences:
        if preferred in available:
            return preferred

    # If no preferred voice found, try to find any voice with language hint
    lang_hints = {"en": ["en", "english", "us"], "ru": ["ru", "russian"]}
    hints = lang_hints.get(lang, lang_hints["en"])

    for voice in available:
        voice_lower = voice.lower()
        if any(hint in voice_lower for hint in hints):
            return voice

    # Final fallback: return first available or default
    return available[0] if available else "Samantha"


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

                # Prefer premium/neural voices for better quality
                voice_found = False
                for voice in voices:
                    voice_id = voice.id.lower()
                    voice_name = voice.name.lower() if voice.name else ""

                    # Check for Russian voice
                    if target_lang == "ru":
                        if ("premium" in voice_name or "neural" in voice_name) and (
                            "ru" in voice_id
                            or "russian" in voice_id
                            or "milena" in voice_name
                            or "yuri" in voice_name
                        ):
                            engine.setProperty("voice", voice.id)
                            voice_found = True
                            break

                # If premium not found, try regular voices
                if not voice_found:
                    for voice in voices:
                        voice_id = voice.id.lower()
                        voice_name = voice.name.lower() if voice.name else ""

                        if target_lang == "ru":
                            if (
                                "ru" in voice_id
                                or "russian" in voice_id
                                or "milena" in voice_name
                                or "yuri" in voice_name
                            ):
                                engine.setProperty("voice", voice.id)
                                break
                        elif target_lang == "en":
                            if "en" in voice_id or "english" in voice_id:
                                engine.setProperty("voice", voice.id)
                                break

                # Adjust rate and pitch for more natural sound
                try:
                    # Slower rate = more natural (default is usually 200, try 150-170)
                    engine.setProperty("rate", 160)
                    # Slightly lower pitch = more natural (default is usually 50, try 45-48)
                    engine.setProperty("pitch", 47)
                except Exception:
                    pass  # Some engines don't support these properties
            except Exception:
                pass  # Use default voice if setting fails

            return engine
    except Exception:
        _ENGINE_AVAILABLE = False
    return None


def _detect_name_language(name: str) -> str:
    """
    Detect if a name is mostly Cyrillic (RU) or Latin (EN).
    Returns "ru" if Cyrillic characters > Latin, else "en".
    """
    if not name:
        return "en"

    cyrillic_count = 0
    latin_count = 0

    for char in name:
        # Cyrillic range: U+0400-U+04FF
        if "\u0400" <= char <= "\u04ff":
            cyrillic_count += 1
        # Latin letters (A-Z, a-z)
        elif char.isalpha() and ord(char) < 128:
            latin_count += 1

    # If more Cyrillic than Latin, treat as Russian
    return "ru" if cyrillic_count > latin_count else "en"


def _clean_text_for_speech(text: str) -> str:
    """
    Clean and format text for better TTS pronunciation.
    - Replace → and other arrows with language-appropriate word
    - Improve number formatting
    - Remove problematic symbols
    """
    if not text:
        return ""

    # Replace various arrow types (language-aware)
    arrows = ["→", "→", "->", "⇒", "➜", "→"]
    replacement = " to " if _SPEECH_LANGUAGE == "en" else " клиент "
    for arrow in arrows:
        text = text.replace(arrow, replacement)

    # Clean up extra spaces
    text = " ".join(text.split())

    return text.strip()


def speak(text: str):
    if not text:
        return

    # Clean text for better speech
    text = _clean_text_for_speech(text)

    # Determine speech engine
    try:
        from gearledger.desktop.settings_manager import get_speech_engine

        engine = get_speech_engine()
    except Exception:
        engine = "os"

    # Piper engine (local, offline)
    if engine == "piper":
        try:
            from gearledger.piper_tts import speak_with_piper

            if speak_with_piper(text):
                return
        except Exception as e:
            print(f"[SPEECH] Piper TTS failed, falling back to OS TTS: {e}")

    # Default: Use OS TTS (free, offline)
    # Windows: prefer pyttsx3 (SAPI5)
    # macOS: prefer native 'say' command

    if sys.platform == "win32":
        # Windows: Use pyttsx3 (SAPI5) as primary OS TTS
        engine = _get_engine()
        if engine:
            try:
                engine.say(text)
                engine.runAndWait()
                engine.stop()  # Clean up after use
                return
            except Exception as e:
                print(f"[SPEECH] pyttsx3 failed: {e}")
                # Fall through to final fallback

    elif sys.platform == "darwin":
        # macOS: Use native 'say' command as primary OS TTS
        try:
            # Pick best available voice for current language
            voice = _pick_macos_voice(_SPEECH_LANGUAGE)

            # Language-specific rate (RU needs slower for clarity)
            rate = 170 if _SPEECH_LANGUAGE == "ru" else 185

            result = subprocess.run(
                ["say", "-v", voice, "-r", str(rate), text],
                check=False,
                capture_output=True,
            )
            if result.returncode == 0:
                return

            # Fallback: try default voice
            subprocess.run(["say", "-r", str(rate), text], check=False)
            return
        except Exception as e:
            print(f"[SPEECH] macOS say failed: {e}")
            # Fall through to final fallback

    else:
        # Linux: Try pyttsx3
        engine = _get_engine()
        if engine:
            try:
                engine.say(text)
                engine.runAndWait()
                engine.stop()
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
        elif ch == ".":
            parts.append(punct.get(".", "dot"))
        elif ch == "_":
            parts.append(punct.get("_", "underscore"))
        else:
            parts.append(" ")  # pause for spaces/others
    # collapse extra spaces
    spoken = " ".join(p for p in parts if p is not None)
    spoken = " ".join(spoken.split())
    return spoken.strip()


def _format_weight_for_speech(weight: float) -> str:
    """
    Format weight for natural speech.
    EN: 2.0 -> "2", 2.5 -> "2 point 5"
    RU: 2.0 -> "2", 2.5 -> "2 запятая 5" (RU uses comma for decimals)
    """
    if weight == int(weight):
        return str(int(weight))

    # For decimals, format naturally
    weight_str = f"{weight:.2f}".rstrip("0").rstrip(".")
    parts = weight_str.split(".")

    if len(parts) == 2:
        if _SPEECH_LANGUAGE == "ru":
            # RU uses comma, say "запятая" (comma)
            return f"{parts[0]} запятая {parts[1]}"
        else:
            return f"{parts[0]} point {parts[1]}"

    return weight_str


def _speak_macos(text: str, lang: str = None, wait: bool = True):
    """
    Speak text using macOS 'say' command with language-specific voice and rate.
    Used for split-speaking mixed content.

    Args:
        text: Text to speak
        lang: Language code ("en" or "ru"), defaults to current language
        wait: If True, wait for speech to complete (blocking)
    """
    if not text or sys.platform != "darwin":
        return False

    target_lang = lang or _SPEECH_LANGUAGE
    voice = _pick_macos_voice(target_lang)
    rate = 170 if target_lang == "ru" else 185

    try:
        if wait:
            # Blocking call - wait for completion
            result = subprocess.run(
                ["say", "-v", voice, "-r", str(rate), text],
                check=False,
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        else:
            # Non-blocking call
            subprocess.Popen(
                ["say", "-v", voice, "-r", str(rate), text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    except Exception:
        return False


def speak_match(artikul: str, client: str, weight: float = None):
    """
    Say match announcement with improved quality.
    For macOS: Uses split-speaking (RU parts with RU voice, EN code/name with EN voice).
    For others: Single voice with cleaned text.

    Args:
        artikul: Part code to spell out
        client: Client name (will be cleaned of → symbols)
        weight: Optional weight to announce naturally
    """
    msgs = _MATCH_MESSAGES.get(_SPEECH_LANGUAGE, _MATCH_MESSAGES["en"])
    code_spelled = _spell_code(artikul)
    client_clean = _clean_text_for_speech(client) if client else None

    # If Piper engine is selected, speak a simple Armenian sentence with the client name.
    try:
        from gearledger.desktop.settings_manager import get_speech_engine

        engine = get_speech_engine()
    except Exception:
        engine = "os"

    # Debug log for engine used in speak_match
    try:
        print(
            f"[SPEECH] speak_match() engine='{engine}', lang='{_SPEECH_LANGUAGE}', "
            f"artikul='{artikul}', client='{client_clean}'"
        )
    except Exception:
        pass

    if engine == "piper":
        try:
            from gearledger.piper_tts import speak_with_piper
        except Exception:
            speak_with_piper = None

        if speak_with_piper is not None and client_clean:
            # Keep it short and name-focused; artikul/weight are not spoken here.
            text = f"Արմատիկ. {client_clean}"
            if not speak_with_piper(text):
                # If Piper fails, fall back to normal path below
                pass
            else:
                return

    # macOS: Use split-speaking for better quality (RU + EN parts) for OS/OpenAI engines
    if sys.platform == "darwin":
        # Check if we should use OpenAI (if enabled)
        try:
            from gearledger.desktop.settings_manager import get_use_openai_tts

            use_openai = get_use_openai_tts() and os.environ.get("OPENAI_API_KEY")
        except Exception:
            use_openai = False

        if not use_openai:
            # Split-speaking: RU parts with RU voice, EN code/name with EN voice
            if _SPEECH_LANGUAGE == "ru":
                # Part 1: RU intro
                ru_intro = f"{msgs['match_found']}. {msgs['code']}:"
                _speak_macos(ru_intro, "ru", wait=True)

                # Part 2: Code (spell with EN voice for clarity)
                _speak_macos(code_spelled, "en", wait=True)

                # Part 3: Weight (if provided)
                if weight is not None and weight > 0:
                    weight_formatted = _format_weight_for_speech(weight)
                    ru_weight = f". Вес: {weight_formatted} килограмм"
                    _speak_macos(ru_weight, "ru", wait=True)

                # Part 4: Client (with EN voice for names)
                if client_clean:
                    ru_client_label = f". {msgs['client']}:"
                    _speak_macos(ru_client_label, "ru", wait=True)
                    _speak_macos(client_clean, "en", wait=True)
                    _speak_macos(".", "ru", wait=True)  # Final period
                else:
                    _speak_macos(".", "ru", wait=True)

                return
            # EN: Single voice is fine, continue to default path

    # Default: Single voice (Windows, Linux, or EN on macOS)
    parts = [f"{msgs['match_found']}", f"{msgs['code']}: {code_spelled}"]

    if weight is not None and weight > 0:
        weight_formatted = _format_weight_for_speech(weight)
        if _SPEECH_LANGUAGE == "ru":
            parts.append(f"Вес: {weight_formatted} килограмм")
        else:
            parts.append(f"Weight: {weight_formatted} kilograms")

    if client_clean:
        parts.append(f"{msgs['client']}: {client_clean}")

    message = ". ".join(parts) + "."
    speak(message)


def _get_engine_for_language(lang: str):
    """
    Get pyttsx3 engine configured for a specific language.
    Used for speak_name() to select voice based on name language.
    """
    engine = _get_engine()
    if not engine:
        return None

    try:
        voices = engine.getProperty("voices")

        # Try to find voice matching the target language
        for voice in voices:
            voice_id = voice.id.lower()
            voice_name = voice.name.lower() if voice.name else ""

            if lang == "ru" and (
                "ru" in voice_id
                or "russian" in voice_id
                or "milena" in voice_name
                or "yuri" in voice_name
            ):
                engine.setProperty("voice", voice.id)
                break
            elif lang == "en" and ("en" in voice_id or "english" in voice_id):
                engine.setProperty("voice", voice.id)
                break

        # Adjust rate and pitch
        try:
            engine.setProperty("rate", 160)
            engine.setProperty("pitch", 47)
        except Exception:
            pass
    except Exception:
        pass  # Use default voice if setting fails

    return engine


def speak_name(name: str) -> None:
    """
    Speak ONLY the user/client name (no code, no weight, no "match found" text).

    Args:
        name: The name to speak. Will be cleaned of arrows and symbols.
    """
    if not name or not name.strip():
        return

    # Clean the name
    cleaned_name = _clean_text_for_speech(name)
    if not cleaned_name:
        return

    print(f"[SPEECH] speak_name called with '{cleaned_name}'")

    # Detect language (Cyrillic vs Latin)
    detected_lang = _detect_name_language(cleaned_name)

    # Determine preferred speech engine (os / openai / piper)
    try:
        from gearledger.desktop.settings_manager import get_speech_engine

        engine = get_speech_engine()
    except Exception:
        engine = "os"

    # 1) Piper (offline, local) – preferred when explicitly selected
    if engine == "piper":
        try:
            from gearledger.piper_tts import speak_with_piper

            if speak_with_piper(cleaned_name):
                return
        except Exception as e:
            print(f"[SPEECH] Piper TTS failed for name, falling back: {e}")

        # If Piper fails, fall through to OS/OpenAI below

    # 2) OpenAI TTS (premium) when engine=openai and API key present
    api_key = os.environ.get("OPENAI_API_KEY")
    if engine == "openai" and api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            voice = _OPENAI_VOICES.get(detected_lang, "alloy")
            audio_format = "wav"

            # Try models in order
            models_to_try = [_OPENAI_TTS_MODEL, "tts-1-hd", "tts-1"]
            response = None

            for model in models_to_try:
                try:
                    kwargs = {
                        "model": model,
                        "voice": voice,
                        "input": cleaned_name,  # ONLY the name, nothing else
                        "response_format": audio_format,
                    }

                    # Add instructions and speed for gpt-4o-mini-tts
                    if model == "gpt-4o-mini-tts":
                        kwargs["instructions"] = (
                            "Pronounce the name clearly and naturally."
                        )
                        kwargs["speed"] = 0.95

                    response = client.audio.speech.create(**kwargs)
                    break
                except Exception as model_error:
                    error_str = str(model_error).lower()
                    if "model" in error_str or "invalid" in error_str:
                        continue
                    else:
                        raise

            if response:
                # Save to temporary file
                suffix = ".wav" if audio_format == "wav" else ".mp3"
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=suffix
                ) as tmp_file:
                    tmp_path = tmp_file.name
                    response.stream_to_file(tmp_path)

                # Play audio file
                playback_done = False
                if sys.platform == "darwin":
                    result = subprocess.run(
                        ["afplay", tmp_path],
                        check=False,
                        timeout=30,
                        capture_output=True,
                    )
                    playback_done = result.returncode == 0
                elif sys.platform == "win32":
                    try:
                        import playsound

                        playsound.playsound(tmp_path, block=True)
                        playback_done = True
                    except ImportError:
                        os.startfile(tmp_path)
                        import time

                        time.sleep(2)
                        playback_done = False
                else:
                    for player in ["ffplay", "mpv", "aplay", "mpg123", "mpg321"]:
                        try:
                            subprocess.run([player, tmp_path], check=False, timeout=30)
                            playback_done = True
                            break
                        except FileNotFoundError:
                            continue

                # Clean up temp file in background
                def cleanup():
                    try:
                        import time

                        wait_time = 5 if playback_done else 90
                        time.sleep(wait_time)
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:
                        pass

                threading.Thread(target=cleanup, daemon=True).start()
                return
        except Exception as e:
            print(f"[SPEECH] OpenAI TTS failed for name: {e}")
            # Fall through to OS TTS

    # 3) Default / fallback: Use OS TTS
    if sys.platform == "darwin":
        # macOS: Use 'say' with detected language voice
        try:
            voice = _pick_macos_voice(detected_lang)
            rate = 170 if detected_lang == "ru" else 185
            subprocess.run(
                ["say", "-v", voice, "-r", str(rate), cleaned_name],
                check=False,
                capture_output=True,
                timeout=10,
            )
            return
        except Exception as e:
            print(f"[SPEECH] macOS say failed for name: {e}")
    elif sys.platform == "win32":
        # Windows: Use pyttsx3 with detected language voice
        engine_obj = _get_engine_for_language(detected_lang)
        if engine_obj:
            try:
                engine_obj.say(cleaned_name)
                engine_obj.runAndWait()
                engine_obj.stop()
                return
            except Exception as e:
                print(f"[SPEECH] pyttsx3 failed for name: {e}")
    else:
        # Linux: Use pyttsx3
        engine_obj = _get_engine_for_language(detected_lang)
        if engine_obj:
            try:
                engine_obj.say(cleaned_name)
                engine_obj.runAndWait()
                engine_obj.stop()
                return
            except Exception:
                pass

    # Final fallback: print to console
    print(f"[SPEAK NAME] {cleaned_name}")


def demo_speak_name():
    """Demo function to test speak_name() with different name types."""
    print("Testing speak_name() with Latin name...")
    speak_name("Armen Mkrtchyan")

    import time

    time.sleep(2)

    print("Testing speak_name() with Cyrillic name...")
    speak_name("Армен Мкртчян")


if __name__ == "__main__":
    demo_speak_name()
