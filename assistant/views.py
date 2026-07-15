"""
assistant/views.py
──────────────────────────────────────────────────────────────────────────────
Phase 4 — Django Webhook (Twilio WhatsApp + Voice Integration)
DeKUT CS & IT Smart FAQ Assistant

WEBHOOK FLOW
────────────
1. Twilio POSTs to /webhook/whatsapp/ whenever a student sends a message.
2. The view inspects the request:
     • If NumMedia > 0  →  audio voice note path:
         - Download the OGG file from Twilio's MediaUrl0.
         - Call transcribe_audio() (Whisper) to get the text.
     • Otherwise        →  plain text path:
         - Extract Body from the form data.
3. classify_query(text) runs the CFG parser + keyword fallback.
4. refine_response() calls GPT-4o (skipped gracefully if offline).
5. The response is sent back via TwilioMessagingResponse.
6. The interaction is logged to ConversationLog.

SECURITY
────────
validate_twilio_request() verifies the X-Twilio-Signature header against the
webhook URL and POST params using the Twilio Auth Token.  Requests that fail
validation are rejected with HTTP 403.

ENDPOINTS
──────────
  POST /webhook/whatsapp/   ← Twilio callback
  GET  /health/             ← Simple JSON health check
  POST /api/query/          ← Direct text query (for testing)
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import warnings
from pathlib import Path

import requests as http_requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .ai_services import OfflineModeError, transcribe_audio, refine_response, text_to_speech
from .models import ConversationLog
from .parser import classify_query

# Twilio imports are lazy — the package is optional at startup.
# If twilio is installed, full signature validation and TwiML responses are used.
# If not installed, the webhook falls back to plain XML construction.
try:
    from twilio.request_validator import RequestValidator  # type: ignore
    from twilio.twiml.messaging_response import MessagingResponse  # type: ignore
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    RequestValidator = None  # type: ignore


logger = logging.getLogger(__name__)

# ── Twilio credentials (from environment) ──────────────────────────────────────

TWILIO_AUTH_TOKEN       = os.getenv("TWILIO_AUTH_TOKEN", "")
# Treat placeholder values as unconfigured so we fall back to dev mode
_TOKEN_PLACEHOLDERS = ("replace", "your_", "example", "placeholder", "change")
if any(hint in TWILIO_AUTH_TOKEN.lower() for hint in _TOKEN_PLACEHOLDERS):
    TWILIO_AUTH_TOKEN = ""  # treat as not set
    warnings.warn(
        "TWILIO_AUTH_TOKEN appears to be a placeholder value — "
        "running in dev mode (Twilio signature validation is DISABLED). "
        "Set your real 32-char token in .env before going to production.",
        stacklevel=1,
    )
TWILIO_WHATSAPP_NUMBER  = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
PUBLIC_BASE_URL         = os.getenv("PUBLIC_BASE_URL", "")
TTS_OUTPUT_DIR          = Path(os.getenv("TTS_OUTPUT_DIR", "media/tts"))


# ── Helper: validate Twilio signature ─────────────────────────────────────────

def _validate_twilio(request) -> bool:
    """Return True if the request passes Twilio signature validation."""
    if not TWILIO_AVAILABLE or not TWILIO_AUTH_TOKEN:
        logger.warning(
            "Twilio not installed or TWILIO_AUTH_TOKEN not set — skipping validation (dev mode)."
        )
        return True

    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    url = request.build_absolute_uri()
    signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
    return validator.validate(url, request.POST, signature)


def _twiml_response(message: str) -> HttpResponse:
    """Build a TwiML MessagingResponse. Falls back to raw XML if twilio not installed."""
    if TWILIO_AVAILABLE:
        resp = MessagingResponse()
        resp.message(message)
        xml = str(resp)
    else:
        safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'
    return HttpResponse(xml, content_type="application/xml")


# ── Helper: download WhatsApp media ───────────────────────────────────────────

def _download_media(media_url: str, suffix: str = ".ogg") -> Path:
    """Download Twilio media to a temporary file and return its path."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = TWILIO_AUTH_TOKEN
    auth = (account_sid, auth_token) if account_sid and auth_token else None

    response = http_requests.get(media_url, auth=auth, timeout=30)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(response.content)
    tmp.flush()
    tmp.close()
    return Path(tmp.name)


# ── Core processing pipeline ───────────────────────────────────────────────────

def _process_query(text: str, channel: str, sender: str) -> str:
    """
    Run the full pipeline on a text query and return the final response string.
    Logs the interaction to the database.
    """
    # Stage 1: Parse
    result = classify_query(text)
    logger.info(
        "Classified: intent=%s rule=%s conf=%.2f",
        result.category, result.matched_rule, result.confidence,
    )

    # Stage 2: AI refinement (optional)
    ai_refined = False
    final_response = result.raw_response
    try:
        final_response = refine_response(
            intent=result.category,
            raw_response=result.raw_response,
            student_query=text,
        )
        ai_refined = True
    except OfflineModeError:
        logger.info("Offline mode — using raw CFG response.")
    except Exception as exc:
        logger.error("GPT-4o refinement failed: %s", exc)

    # Stage 3: Persist
    try:
        ConversationLog.objects.create(
            channel=channel,
            sender=sender,
            raw_input=text,
            detected_intent=result.category,
            matched_rule=result.matched_rule,
            confidence=result.confidence,
            ai_refined=ai_refined,
            response_sent=final_response,
        )
    except Exception as exc:
        logger.error("Failed to persist ConversationLog: %s", exc)

    return final_response


# ── 1. WhatsApp Webhook ────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """
    POST /webhook/whatsapp/

    Twilio posts form-encoded data here when a WhatsApp message arrives.
    Relevant POST fields:
        Body       – plain text message (may be empty for voice notes)
        NumMedia   – number of media files attached
        MediaUrl0  – URL of the first media file (voice note)
        MediaContentType0 – MIME type (e.g. audio/ogg)
        From       – sender's WhatsApp number
    """
    # ── Security: validate Twilio signature ──────────────────────────────
    if not _validate_twilio(request):
        logger.warning("Invalid Twilio signature — rejecting request.")
        return HttpResponse("Forbidden", status=403)

    sender     = request.POST.get("From", "unknown")
    body       = request.POST.get("Body", "").strip()
    num_media  = int(request.POST.get("NumMedia", "0"))
    media_url  = request.POST.get("MediaUrl0", "")
    media_type = request.POST.get("MediaContentType0", "")

    query_text = ""
    channel    = "whatsapp"

    # ── Branch: voice note ────────────────────────────────────────────────
    if num_media > 0 and "audio" in media_type:
        channel = "voice"
        suffix  = ".ogg" if "ogg" in media_type else ".mp3"
        try:
            audio_path = _download_media(media_url, suffix=suffix)
            query_text = transcribe_audio(audio_path)
            logger.info("STT result: %s", query_text)
            # Clean up temp file
            audio_path.unlink(missing_ok=True)
        except OfflineModeError:
            # Offline mode — cannot transcribe audio, ask for text.
            return _twiml_response(
                "📵 Voice processing requires AI services (offline mode is active). "
                "Please resend your question as a text message."
            )
        except Exception as exc:
            logger.error("Audio transcription failed: %s", exc)
            return _twiml_response(
                "⚠️ We were unable to process your voice note. "
                "Please resend your question as a text message."
            )

    # ── Branch: plain text ────────────────────────────────────────────────
    elif body:
        query_text = body
    else:
        return _twiml_response("Hello! Please type your question and we will assist you.")

    # ── Process & respond ─────────────────────────────────────────────────
    final_response = _process_query(query_text, channel=channel, sender=sender)

    # WhatsApp messages are limited to 1600 characters; truncate if needed.
    if len(final_response) > 1600:
        final_response = final_response[:1597] + "..."

    return _twiml_response(final_response)


# ── 2. Health Check ────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def health_check(request):
    """GET /health/ — returns JSON status for monitoring."""
    ai_available = bool(os.getenv("OPENAI_API_KEY", "").strip())
    twilio_configured = bool(TWILIO_AUTH_TOKEN)
    return JsonResponse({
        "status": "ok",
        "service": "DeKUT CS & IT FAQ Assistant",
        "ai_mode": "online" if ai_available else "offline (CFG only)",
        "twilio_configured": twilio_configured,
    })


# ── 3. Direct API Query (text) ────────────────────────────────────────────────

@csrf_exempt
@require_POST
def api_query(request):
    """
    POST /api/query/
    Body (JSON): {"query": "...", "sender": "..."}

    Returns JSON with matched_rule, category, confidence, and response.
    Useful for testing without WhatsApp.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    query_text = data.get("query", "").strip()
    sender     = data.get("sender", "api-test")

    if not query_text:
        return JsonResponse({"error": "Query field is required."}, status=400)

    result = classify_query(query_text)
    ai_refined = False
    final_response = result.raw_response

    try:
        final_response = refine_response(
            intent=result.category,
            raw_response=result.raw_response,
            student_query=query_text,
        )
        ai_refined = True
    except OfflineModeError:
        pass
    except Exception as exc:
        logger.error("GPT-4o refinement failed: %s", exc)

    try:
        ConversationLog.objects.create(
            channel="api",
            sender=sender,
            raw_input=query_text,
            detected_intent=result.category,
            matched_rule=result.matched_rule,
            confidence=result.confidence,
            ai_refined=ai_refined,
            response_sent=final_response,
        )
    except Exception as exc:
        logger.error("ConversationLog persist error: %s", exc)

    return JsonResponse({
        "query":        query_text,
        "matched_rule": result.matched_rule,
        "category":     result.category,
        "confidence":   result.confidence,
        "tokens_used":  result.tokens_used,
        "ai_refined":   ai_refined,
        "response":     final_response,
    })
