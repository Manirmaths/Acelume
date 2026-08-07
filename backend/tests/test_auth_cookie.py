"""
Auth cookie attributes.

These guard the fix for the 2026-08-07 "Couldn't load your dashboard" report.

Root cause: the Android build in Play Store testing points at
naijaprep.com.ng while the API is on api.acelume.ng. Those are different
registrable domains, so every API call from the app is CROSS-site, so the
browser silently refused to store a SameSite=Lax cookie. Login returned 200
with a user body, the frontend believed it, and every authenticated request
afterwards 401'd.

Two things are asserted here:
  1. the cookie's SameSite is configurable, so the legacy domain can be
     un-broken from Render env without shipping a new APK; and
  2. SameSite=None never ships without Secure, which browsers reject outright
     and which would silently log everyone out.
"""

import importlib

import pytest


def _reload_settings(monkeypatch, **env):
    """Re-import config + auth router so class-level settings pick up env."""
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import app.config
    importlib.reload(app.config)
    import app.routers.auth
    importlib.reload(app.routers.auth)
    return app.routers.auth


@pytest.fixture(autouse=True)
def _restore_modules():
    """Leave the imported modules exactly as the rest of the suite expects."""
    yield
    import app.config
    importlib.reload(app.config)
    import app.routers.auth
    importlib.reload(app.routers.auth)


def _register(client, username="cookieuser"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "sup3rsecret"},
    )


def _set_cookie_header(response) -> str:
    raw = response.headers.get("set-cookie", "")
    assert raw, "expected a Set-Cookie header on a successful auth response"
    return raw.lower()


def test_default_samesite_is_lax(client):
    """Unchanged default -- same-site deployments keep the safer policy."""
    header = _set_cookie_header(_register(client))
    assert "samesite=lax" in header


def test_cookie_is_httponly_by_default(client):
    header = _set_cookie_header(_register(client))
    assert "httponly" in header


def test_samesite_none_is_honoured_when_configured(client, monkeypatch):
    """The escape hatch that un-breaks a cross-site legacy domain."""
    auth = _reload_settings(monkeypatch, COOKIE_SAMESITE="none")
    assert auth.settings.COOKIE_SAMESITE == "none"

    from fastapi import Response
    response = Response()
    auth._set_auth_cookie(response, 1)
    header = response.headers["set-cookie"].lower()

    assert "samesite=none" in header


def test_samesite_none_always_forces_secure(client, monkeypatch):
    """
    SameSite=None without Secure is rejected by every modern browser. If that
    combination ever shipped, the cookie would be dropped and every user would
    be silently logged out -- the exact failure this file exists to prevent,
    reintroduced from the other direction.
    """
    auth = _reload_settings(monkeypatch, COOKIE_SAMESITE="none", ENV="development")
    assert auth.settings.IS_PRODUCTION is False

    from fastapi import Response
    response = Response()
    auth._set_auth_cookie(response, 1)
    header = response.headers["set-cookie"].lower()

    assert "samesite=none" in header
    assert "secure" in header


def test_unknown_samesite_value_falls_back_to_lax(client, monkeypatch):
    """A typo in the env var must not produce an invalid cookie attribute."""
    auth = _reload_settings(monkeypatch, COOKIE_SAMESITE="banana")

    from fastapi import Response
    response = Response()
    auth._set_auth_cookie(response, 1)
    header = response.headers["set-cookie"].lower()

    assert "samesite=lax" in header


def test_login_actually_sets_a_usable_session(client):
    """
    End-to-end guard on the real bug shape: a 200 from /login must come with a
    session that /me accepts. If these ever disagree, the frontend's
    verifySession() is the only thing standing between a student and a
    signed-in shell with no session behind it.
    """
    _register(client, "sessionuser")
    client.cookies.clear()

    login = client.post(
        "/api/auth/login",
        json={"email": "sessionuser@example.com", "password": "sup3rsecret"},
    )
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "sessionuser"
