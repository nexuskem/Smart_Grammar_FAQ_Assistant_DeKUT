"""
assistant/models.py
──────────────────────────────────────────────────────────────────────────────
Django model — ConversationLog
Persists every student interaction for audit and analytics.
──────────────────────────────────────────────────────────────────────────────
"""

from django.db import models


class ConversationLog(models.Model):
    """
    Records every student query processed by the FAQ assistant.

    Fields:
        created_at     – Timestamp of the interaction.
        channel        – Source channel: 'whatsapp' | 'voice' | 'api'.
        sender         – WhatsApp number or identifier (hashed for privacy).
        raw_input      – Original student message or transcribed audio.
        detected_intent – Classified intent label.
        matched_rule   – The CFG rule (or 'keyword-vote') that fired.
        confidence     – Parser confidence score (0.0–1.0).
        ai_refined     – Whether GPT-4o refinement was applied.
        response_sent  – The final response text returned to the student.
    """

    CHANNEL_CHOICES = [
        ("whatsapp", "WhatsApp"),
        ("voice",    "Voice Note"),
        ("api",      "API / Validation"),
    ]

    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    channel         = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="whatsapp")
    sender          = models.CharField(max_length=50, blank=True)
    raw_input       = models.TextField()
    detected_intent = models.CharField(max_length=50, blank=True)
    matched_rule    = models.CharField(max_length=200, blank=True)
    confidence      = models.FloatField(default=0.0)
    ai_refined      = models.BooleanField(default=False)
    response_sent   = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Conversation Log"
        verbose_name_plural = "Conversation Logs"

    def __str__(self) -> str:
        return (
            f"[{self.created_at:%Y-%m-%d %H:%M}] "
            f"{self.channel} | {self.detected_intent} | "
            f"conf={self.confidence:.2f}"
        )
