import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-me")
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./naijaprep.db")
    FRONTEND_ORIGINS: list[str] = [
        o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
    ALGORITHM: str = "HS256"
    PAYSTACK_SECRET_KEY: str = os.environ.get("PAYSTACK_SECRET_KEY", "")
    PAYSTACK_PUBLIC_KEY: str = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
    # Placeholder pricing -- a real business decision the user should set,
    # not something to guess permanently. ₦1500/mo default just keeps the
    # integration runnable end-to-end with sane-looking numbers; override via
    # env before actually taking real payments.
    PREMIUM_PRICE_KOBO: int = int(os.environ.get("PREMIUM_PRICE_KOBO", "150000"))  # kobo (₦1,500.00)
    PREMIUM_DURATION_DAYS: int = int(os.environ.get("PREMIUM_DURATION_DAYS", "30"))
    FREE_MOCK_EXAMS: int = int(os.environ.get("FREE_MOCK_EXAMS", "1"))
    IS_PRODUCTION: bool = os.environ.get("ENV", "development") == "production"

    # Transactional email (password reset) via Resend's HTTP API. Left unset
    # in dev/until configured -- app/email.py falls back to logging the
    # reset link instead of failing, so forgot-password still works locally.
    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.environ.get("RESEND_FROM_EMAIL", "Acelume <noreply@acelume.ng>")
    # Base URL used to build the reset-password link sent by email.
    PUBLIC_APP_URL: str = os.environ.get(
        "PUBLIC_APP_URL",
        FRONTEND_ORIGINS[0] if FRONTEND_ORIGINS else "http://localhost:5173",
    )

    # AI tutor ("explain this differently") + admin auto-tagging, via
    # OpenAI's API. Left unset in dev/until configured -- app/ai.py falls
    # back to a friendly "not set up yet" response instead of failing, same
    # pattern as RESEND_API_KEY above.
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    # Per-user, per-day cap on AI tutor requests -- bounds OpenAI cost.
    TUTOR_DAILY_LIMIT: int = int(os.environ.get("TUTOR_DAILY_LIMIT", "30"))

    # Web Push (PWA notifications). Generate a pair with:
    #   python -c "from py_vapid import Vapid; from cryptography.hazmat.primitives.asymmetric import ec; from cryptography.hazmat.primitives import serialization; import base64; v=Vapid(); v.generate_keys(); b64=lambda d: base64.urlsafe_b64encode(d).rstrip(b'=').decode(); print(b64(v.private_key.private_numbers().private_value.to_bytes(32,'big'))); print(b64(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))"
    # Left unset in dev/until configured -- app/push.py no-ops instead of
    # failing, same fallback pattern as RESEND_API_KEY/OPENAI_API_KEY above.
    VAPID_PRIVATE_KEY: str = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY: str = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIM_EMAIL: str = os.environ.get("VAPID_CLAIM_EMAIL", "mailto:arewatutorials@gmail.com")
    # Shared secret an external cron (e.g. cron-job.org) must pass to trigger
    # /api/notifications/send-reminders -- this endpoint isn't behind normal
    # user auth since it's meant to be hit by a scheduler, not a browser.
    NOTIFICATIONS_CRON_SECRET: str = os.environ.get("NOTIFICATIONS_CRON_SECRET", "")


settings = Settings()
