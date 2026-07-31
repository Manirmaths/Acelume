from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import Base, engine, ensure_schema, normalize_emails
from app.rate_limit import limiter
from app import models  # noqa: F401 -- ensure models are registered before create_all
from app.routers import (
    auth, subjects, quiz, dashboard, review, admin, leaderboard, blitz, mock, achievements,
    smart_review, tutor, notifications, study_planner, flashcards, public, notes, payments, family,
    quest, missions, leagues, battles,
)

# Interactive API docs (Swagger/ReDoc) pull scripts from a CDN and expose the
# full schema -- fine for local dev, unnecessary attack-surface/information
# disclosure on the public production API. Disabled in production only.
app = FastAPI(
    title="Acelume API",
    version="2.0.0",
    docs_url=None if settings.IS_PRODUCTION else "/docs",
    redoc_url=None if settings.IS_PRODUCTION else "/redoc",
    openapi_url=None if settings.IS_PRODUCTION else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Docs paths only exist at all when not in production (see docs_url= above),
# but the strict CSP below would break Swagger/ReDoc's own CDN-loaded assets
# in dev if applied unconditionally -- skip CSP specifically for those paths.
_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Baseline hardening headers. This is a JSON-only API (the frontend is a
    # separately hosted static SPA), so a strict CSP with no script/style
    # allowances is safe here and doesn't risk breaking any real page render.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.url.path not in _DOCS_PATHS:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if settings.IS_PRODUCTION:
        # Only meaningful over HTTPS, which is what production always is.
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    normalize_emails()


app.include_router(auth.router)
app.include_router(subjects.router)
app.include_router(quiz.router)
app.include_router(dashboard.router)
app.include_router(review.router)
app.include_router(admin.router)
app.include_router(leaderboard.router)
app.include_router(blitz.router)
app.include_router(mock.router)
app.include_router(achievements.router)
app.include_router(smart_review.router)
app.include_router(tutor.router)
app.include_router(notifications.router)
app.include_router(study_planner.router)
app.include_router(flashcards.router)
app.include_router(public.router)
app.include_router(notes.router)
app.include_router(payments.router)
app.include_router(family.router)
app.include_router(quest.router)
app.include_router(missions.router)
app.include_router(leagues.router)
app.include_router(battles.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
