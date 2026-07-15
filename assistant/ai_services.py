"""
assistant/ai_services.py
──────────────────────────────────────────────────────────────────────────────
Phase 4 — AI Services
DeKUT CS & IT Smart FAQ Assistant

This module wraps three OpenAI capabilities:

  1. transcribe_audio(file_path)
       Sends an audio file (OGG / MP3 / WAV) to OpenAI Whisper (whisper-1).
       Returns the transcribed text string.

  2. refine_response(intent, raw_response, student_query)
       Sends the deterministic CFG response to GPT-4o with a DeKUT-specific
       system prompt, asking the model to:
         • Personalise the tone for the specific student query.
         • Correct any awkward phrasing.
         • Keep the response under 300 words.

  3. text_to_speech(text, out_path)
       Converts text to speech using OpenAI's tts-1 model (alloy voice).
       Saves the audio file to out_path and returns the path.

OFFLINE FALLBACK
────────────────
All three functions check for the OPENAI_API_KEY environment variable at
call time.  If the key is missing (or blank), they raise OfflineModeError —
a custom exception that the caller (views.py, validate.py) catches and handles
gracefully by returning the raw CFG response as-is.

AUDIO FORMAT HANDLING
──────────────────────
WhatsApp voice notes arrive as OGG/Opus files.  Whisper accepts OGG directly
but pydub is used to convert to WAV when the file extension is not natively
supported by the OpenAI client.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Custom exception ───────────────────────────────────────────────────────────

class OfflineModeError(RuntimeError):
    """Raised when OPENAI_API_KEY is not set and an AI service is requested."""
    pass


# ── Helper: check API key ──────────────────────────────────────────────────────

def _require_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise OfflineModeError(
            "OPENAI_API_KEY is not set. The system is running in offline / "
            "CFG-only mode. Set the environment variable to enable AI services."
        )
    return key


# ── 1. Speech-to-Text (Whisper) ────────────────────────────────────────────────

def transcribe_audio(file_path: str | Path) -> str:
    """
    Transcribe an audio file using OpenAI Whisper.

    Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm, ogg.
    WhatsApp OGG/Opus voice notes are passed directly to Whisper.

    Args:
        file_path: Absolute or relative path to the audio file.

    Returns:
        Transcribed text string.

    Raises:
        OfflineModeError: If OPENAI_API_KEY is not configured.
        FileNotFoundError: If the audio file does not exist.
    """
    api_key = _require_api_key()
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    # Lazy import to avoid hard dependency when offline.
    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)

    # WhatsApp sends OGG/Opus.  Whisper accepts .ogg directly.
    # For other unusual formats, convert to WAV using pydub.
    suffix = file_path.suffix.lower()
    NATIVE_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}

    if suffix not in NATIVE_FORMATS:
        logger.info("Converting %s to WAV for Whisper...", file_path)
        try:
            from pydub import AudioSegment  # type: ignore
            audio = AudioSegment.from_file(str(file_path))
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio.export(tmp.name, format="wav")
                file_path = Path(tmp.name)
        except ImportError:
            raise RuntimeError(
                "pydub is required for non-standard audio formats.  "
                "Install it with: pip install pydub"
            )

    logger.info("Transcribing audio file: %s", file_path)
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
        )

    text = transcript.text.strip()
    logger.info("Transcription result: %s", text)
    return text


# ── 2. GPT-4o Response Refinement ─────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an official academic assistant representing the Dean and Chair of "
    "Department (COD) of the School of Computer Science & IT at Dedan Kimathi "
    "University of Technology (DeKUT), Kenya.  Your role is to respond to "
    "student inquiries in a professional, empathetic, and concise manner.\n\n"
    "When given a draft response, personalise it slightly for the student's "
    "specific question, fix any awkward phrasing, and ensure the response:\n"
    "  • Does not exceed 300 words.\n"
    "  • Maintains a formal academic tone.\n"
    "  • Addresses the student by 'Dear Student'.\n"
    "  • Is signed off with the appropriate office (COD or Dean).\n"
    "  • Does not invent new university policies not present in the draft."
)


def refine_response(
    intent: str,
    raw_response: str,
    student_query: str = "",
) -> str:
    """
    Use GPT-4o to personalise and polish the deterministic CFG response.

    Args:
        intent:         The classified intent label (e.g. 'missing_marks').
        raw_response:   The canned response from the response engine.
        student_query:  The original student question (for context).

    Returns:
        Refined response string from GPT-4o.

    Raises:
        OfflineModeError: If OPENAI_API_KEY is not configured.
    """
    api_key = _require_api_key()

    from openai import OpenAI  # type: ignore
    client = OpenAI(api_key=api_key)

    user_message = (
        f"Student's question ({intent}):\n{student_query}\n\n"
        f"Draft response:\n{raw_response}\n\n"
        "Please refine the draft response to be more personalised and natural "
        "while preserving all the factual content."
    )

    logger.info("Calling GPT-4o for response refinement (intent=%s).", intent)
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        max_tokens=600,
        temperature=0.4,
    )

    refined = completion.choices[0].message.content.strip()
    logger.info("GPT-4o refinement complete (%d chars).", len(refined))
    return refined


# ── 3. Text-to-Speech (TTS) ────────────────────────────────────────────────────

def text_to_speech(text: str, out_path: str | Path) -> Path:
    """
    Convert text to speech using OpenAI tts-1 and save to out_path.

    Args:
        text:     The text to synthesise.
        out_path: Destination file path (must end in .mp3 or .opus).

    Returns:
        Path object pointing to the saved audio file.

    Raises:
        OfflineModeError: If OPENAI_API_KEY is not configured.
    """
    api_key = _require_api_key()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    from openai import OpenAI  # type: ignore
    client = OpenAI(api_key=api_key)

    logger.info("Generating TTS audio → %s", out_path)
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",          # Clear, gender-neutral voice
        input=text,
        response_format="mp3",
    )
    response.stream_to_file(str(out_path))
    logger.info("TTS audio saved: %s (%d bytes)", out_path, out_path.stat().st_size)
    return out_path


# ── Self-test (offline) ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    print("\nDeKUT FAQ — AI Services Module")
    if os.getenv("OPENAI_API_KEY"):
        print("✓ OPENAI_API_KEY is set — AI services are available.")
    else:
        print("✗ OPENAI_API_KEY is NOT set — running in offline/CFG-only mode.")
        print("  Set the key in your .env file to enable STT, TTS, and refinement.")
    sys.exit(0)
