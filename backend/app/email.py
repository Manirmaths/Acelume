"""
Minimal transactional email helper, currently used only for password reset
links. Sends via Resend's HTTP API (https://resend.com) if RESEND_API_KEY is
configured; otherwise logs the message so local dev / not-yet-configured
deployments still work end-to-end without a real email provider.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger("naijaprep.email")

RESEND_URL = "https://api.resend.com/emails"


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    if not settings.RESEND_API_KEY:
        logger.warning(
            "RESEND_API_KEY not set -- skipping real send. Would have emailed %s: %s\n%s",
            to, subject, text or html,
        )
        return False

    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        resp = httpx.post(
            RESEND_URL,
            json=payload,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Failed to send email to %s via Resend", to)
        return False


def send_password_reset_email(to: str, reset_url: str) -> bool:
    subject = "Reset your Acelume password"
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #111827;">Reset your password</h2>
      <p style="color: #374151;">
        Someone (hopefully you) asked to reset the password on your Acelume account.
        This link expires in 30 minutes and can only be used once.
      </p>
      <p style="margin: 24px 0;">
        <a href="{reset_url}" style="background: #16a34a; color: white; padding: 12px 20px;
           border-radius: 8px; text-decoration: none; font-weight: bold;">Reset password</a>
      </p>
      <p style="color: #6b7280; font-size: 13px;">
        If you didn't request this, you can safely ignore this email -- your password won't change.
      </p>
    </div>
    """
    text = f"Reset your Acelume password: {reset_url} (expires in 30 minutes, one-time use)"
    return send_email(to, subject, html, text)
