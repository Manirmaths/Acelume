"""
Minimal Web Push helper (used only by routers/notifications.py). Falls back
to a no-op if VAPID keys aren't configured -- same pattern as
app/email.py (Resend) and app/ai.py (OpenAI).
"""
import json
import logging

import requests
from pywebpush import webpush, WebPushException

from app.config import settings
from app.models import PushSubscription

logger = logging.getLogger("naijaprep.push")


def send_push(subscription: PushSubscription, title: str, body: str, url: str = "/dashboard") -> str:
    """Returns 'sent', 'expired' (caller should delete the subscription),
    'not_configured', or 'failed'."""
    if not settings.VAPID_PRIVATE_KEY:
        return "not_configured"

    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIM_EMAIL},
            # pywebpush passes this straight to requests.post(), which has NO
            # default timeout of its own -- one unresponsive push endpoint
            # (dead browser, stalled gateway) would otherwise hang forever.
            # The daily-reminders cron calls this once per subscription in a
            # sequential loop, so a single bad subscription stalls the whole
            # job: exactly what turned a normally ~10s run into a 15-minute
            # one that had to be cancelled (GitHub Actions run #8, 2026-08-06).
            timeout=10,
        )
        return "sent"
    except WebPushException as e:
        status = e.response.status_code if e.response is not None else None
        if status in (404, 410):
            # Browser/OS says this subscription no longer exists -- normal
            # churn (uninstall, browser data cleared, etc.), not an error.
            return "expired"
        logger.warning("Push send failed (status=%s): %s", status, e)
        return "failed"
    except requests.exceptions.RequestException as e:
        # Covers the new `timeout` above (requests.exceptions.Timeout) and
        # connection failures -- neither is a WebPushException, so without
        # this they'd propagate uncaught and crash the whole reminder batch
        # over one flaky endpoint instead of just marking it failed.
        logger.warning("Push send failed (network error): %s", e)
        return "failed"
