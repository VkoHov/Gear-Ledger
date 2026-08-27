# -*- coding: utf-8 -*-
"""
Transactional email via Resend — currently just password-reset codes.

Unlike GEARLEDGER_JWT_SECRET (fails the whole boot loudly if missing,
since a missing/weak signing key is a security hole), a missing
RESEND_API_KEY only means one feature is unavailable. The rest of the
server has no reason to be down because email isn't configured yet, so
this fails soft: callers get a clear RuntimeError only when they actually
try to send, and the route layer turns that into a 503.
"""
import os
from typing import Optional

import requests

_RESEND_API_URL = "https://api.resend.com/emails"


class EmailSender:
    def __init__(self, api_key: Optional[str] = None, from_address: Optional[str] = None):
        self.api_key = api_key or os.getenv("RESEND_API_KEY")
        # onboarding@resend.dev is Resend's shared test sender, usable
        # without a verified domain — fine for development, but Resend's
        # sandbox restricts it to delivering only to the account's own
        # verified address, not arbitrary real users. Swap in a verified
        # sending domain (via GEARLEDGER_RESET_EMAIL_FROM) once one exists.
        self.from_address = from_address or os.getenv(
            "GEARLEDGER_RESET_EMAIL_FROM", "Gear Ledger <onboarding@resend.dev>"
        )

    def send_password_reset_email(self, to_email: str, code: str) -> None:
        if not self.api_key:
            raise RuntimeError(
                "RESEND_API_KEY is not set — password reset email cannot be sent. "
                "Get a key at resend.com/api-keys (Sending access permission is "
                "enough) and export it before starting the server."
            )

        response = requests.post(
            _RESEND_API_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": self.from_address,
                "to": [to_email],
                "subject": "Your Gear Ledger password reset code",
                "html": (
                    f"<p>Your password reset code is:</p>"
                    f"<p style='font-size:24px;font-weight:bold;letter-spacing:2px;'>{code}</p>"
                    f"<p>This code expires in 15 minutes. If you didn't request this, "
                    f"you can ignore this email.</p>"
                ),
            },
            timeout=10,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Resend API returned {response.status_code}: {response.text[:300]}"
            )


_sender: Optional[EmailSender] = None


def get_email_sender() -> EmailSender:
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender
