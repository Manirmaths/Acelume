"""
Regression test for app/push.py.

Context: the daily-reminders cron (.github/workflows/daily-reminders.yml)
calls POST /api/notifications/send-reminders, which loops over every
subscription and calls send_push() one at a time, synchronously. pywebpush's
webpush() delegates the actual HTTP call to `requests`, which has NO default
timeout -- a single unresponsive push endpoint (dead browser, stalled
gateway) could hang that call forever, stalling the whole batch behind it.

That's what happened in GitHub Actions run #8 on 2026-08-06: a run that
normally takes ~10 seconds ran for 15 minutes before being cancelled. The
fix has two parts, both covered here:

1. Pass timeout=10 to webpush() so a slow endpoint fails fast instead of
   hanging indefinitely.
2. Catch requests.exceptions.RequestException (which a timeout raises) in
   send_push -- without this, a timeout would propagate uncaught out of
   send_push and crash the reminder job for every remaining user behind the
   slow one, rather than just marking that one subscription "failed".
"""
from unittest.mock import patch

import pytest
import requests
from pywebpush import WebPushException

from app.push import send_push


class FakeSubscription:
    def __init__(self):
        self.endpoint = "https://push.example.com/fake"
        self.p256dh = "fake-p256dh"
        self.auth = "fake-auth"


@pytest.fixture(autouse=True)
def vapid_configured(monkeypatch):
    monkeypatch.setattr("app.push.settings.VAPID_PRIVATE_KEY", "fake-private-key")
    monkeypatch.setattr("app.push.settings.VAPID_CLAIM_EMAIL", "mailto:test@example.com")


def test_webpush_is_called_with_a_timeout_so_a_dead_endpoint_cannot_hang_forever():
    """`requests` has no default timeout; without an explicit one, a single
    unresponsive subscription can block the whole sequential reminder loop
    indefinitely, as happened in the incident this test documents."""
    with patch("app.push.webpush") as mock_webpush:
        send_push(FakeSubscription(), title="t", body="b")
    _, kwargs = mock_webpush.call_args
    assert kwargs.get("timeout") is not None
    assert kwargs["timeout"] > 0


def test_a_timed_out_subscription_is_marked_failed_not_raised():
    """A timeout raises requests.exceptions.Timeout, which is not a
    WebPushException. Before this fix that would propagate out of
    send_push and crash the reminder job for every user still queued
    behind the slow subscription, instead of just skipping this one."""
    with patch("app.push.webpush", side_effect=requests.exceptions.Timeout("timed out")):
        result = send_push(FakeSubscription(), title="t", body="b")
    assert result == "failed"


def test_a_connection_error_is_also_marked_failed_not_raised():
    with patch("app.push.webpush", side_effect=requests.exceptions.ConnectionError("refused")):
        result = send_push(FakeSubscription(), title="t", body="b")
    assert result == "failed"


def test_expired_subscription_status_still_reported_as_expired():
    """Pre-existing behavior must survive the new exception handler:
    404/410 from the push service still means 'delete this subscription',
    not 'failed'."""
    response = type("Resp", (), {"status_code": 410})()
    with patch("app.push.webpush", side_effect=WebPushException("gone", response=response)):
        result = send_push(FakeSubscription(), title="t", body="b")
    assert result == "expired"


def test_other_webpush_exceptions_still_reported_as_failed():
    response = type("Resp", (), {"status_code": 500})()
    with patch("app.push.webpush", side_effect=WebPushException("boom", response=response)):
        result = send_push(FakeSubscription(), title="t", body="b")
    assert result == "failed"


def test_not_configured_short_circuits_before_any_network_call(monkeypatch):
    monkeypatch.setattr("app.push.settings.VAPID_PRIVATE_KEY", None)
    with patch("app.push.webpush") as mock_webpush:
        result = send_push(FakeSubscription(), title="t", body="b")
    assert result == "not_configured"
    mock_webpush.assert_not_called()
