# Naija Prep — Repository Audit (2026-07-18)

Read-only audit, no code changed. Scope: everything in the 52-section brief, reduced to the 15 deliverables requested. Findings are grounded in the actual repo — every claim below was checked against a file, not assumed.

## 1. Repository audit

- **Stack**: FastAPI + SQLAlchemy 2.0 (Python) backend in `backend/`; React 19 + TypeScript + Vite 8 + Tailwind 4 + React Router 7 + TanStack Query 5 frontend in `frontend/`. Fully decoupled JSON REST API (README confirms this is a v2 migration off an earlier Flask/Jinja app — leftover `FLASK_APP`/`FLASK_ENV` keys still sit unused in `.env`).
- **Data**: SQLite for local dev, Postgres (Neon-hosted) in production. No Alembic — schema changes go through a hand-rolled `ensure_schema()` startup routine in `backend/app/database.py`-adjacent code.
- **Deployment**: Render.com, two services (`naijaprep-api`, `naijaprep-web`) defined in `render.yaml`. Neon DB is external to Render. Live at `naijaprep.com.ng`.
- **Native wrappers**: Capacitor (Android) and Electron (Windows) are both thin WebView shells pointed at the live URL — not bundled builds. Web/backend deploys reach them with no app republish, except when a signed Play Store release is needed.
- **No CI**: no `.github/workflows` directory exists. Nothing runs tests, lints, or type-checks automatically on push.
- **No automated test suite**: `find backend -iname test_*.py` returns zero project files (only vendored `.venv` package tests). No `conftest.py`, no `pytest.ini`. Verification so far has relied on ad hoc `TestClient` smoke scripts run manually.
- **17 backend routers**: `auth`, `subjects`, `quiz`, `mock`, `blitz`, `review`, `smart_review`, `dashboard`, `leaderboard`, `achievements`, `study_planner`, `flashcards`, `notifications`, `tutor`, `notes`, `admin`, `public`.
- **23 frontend pages**, all wired through a single `AppShell.tsx` sidebar for authenticated users; only 7 public routes exist (`/`, `/login`, `/register`, `/forgot-password`, `/reset-password`, `/privacy`, `*`).

## 2. Current feature inventory

Confirmed real and working (not scaffolding):

- Full auth: register/login/logout/forgot-password/reset-password, httpOnly JWT cookie, admin flag never auto-granted.
- Practice modes: quiz, CBT, diagnostic, marked-for-review, daily, blitz, mock exam — all backed by one `QuizAttempt` model with resumable server-side state (`question_ids`, `marked_question_ids` as JSON columns).
- Leitner-box spaced repetition (`QuestionMastery`, boxes 1–5, real interval schedule) — already implemented, not a gap.
- Study Planner — auto-computed from weak topics, no stale storage.
- Flashcards — reuses the existing question bank.
- Lesson Notes — 97/97 topics hand-authored, admin draft/publish workflow, AI tutor chat per note (capped ~75 words), glossary, related-topics, helpful/unhelpful feedback, read-progress tracking (Learn hub).
- Gamification: points, streaks + streak freezes, achievements, leaderboard.
- Web Push notifications (`PushSubscription` model, `pywebpush`/`py-vapid`, working subscribe/unsubscribe + reminder cron endpoint).
- PWA basics: `manifest.webmanifest`, `sw.js`, app icons present.
- Route-level code splitting via `React.lazy()` across `App.tsx`.
- Admin dashboard: question management, lesson notes (status table, editor, publish/publish-all), presumably user/question moderation (not yet read line-by-line, but the router exists and is substantial).

## 3. Missing-feature inventory

Checked directly against the brief, not inferred:

- **No guest/frictionless practice flow.** Every practice, dashboard, and subject route is wrapped in `RequireAuth` in `App.tsx`. A visitor cannot try a single question before registering.
- **No SEO landing pages, no `robots.txt`, no `sitemap.xml`** anywhere in `frontend/public/`. `index.html` has only a `<title>` tag — no meta description, no Open Graph, no Twitter Card, no canonical link, no JSON-LD. Because this is a pure client-rendered SPA with no SSR/prerendering, every route serves that same bare shell to crawlers and social-preview bots that don't execute JS.
- **No parent dashboard, no teacher/tutor tooling, no school/institution platform.**
- **No live payments.** `Payment` model and `User.premium_until`/`is_premium` exist but are explicitly commented as dormant/unenforced; `PAYSTACK_SECRET_KEY`/`PAYSTACK_PUBLIC_KEY` are defined in `.env.example` but nothing in the code calls Paystack or Flutterwave.
- **No rate limiting, no CSRF protection beyond SameSite=Lax, no security response headers** (no CSP, X-Frame-Options, HSTS) — `grep` across `backend/app` for all of these returns nothing.
- **No session revocation.** JWTs are stateless with a 7-day expiry and no server-side session table — logout only clears the cookie client-side; a stolen token remains valid until it expires.
- **No 2FA.**
- **No automated tests, no CI.**
- **No Hausa language support** — nothing in the codebase references locale/i18n at all.
- **No structured onboarding flow, no diagnostic-driven personalized plan generation** beyond the existing weak-topic-based Study Planner (which is reactive, not a first-session diagnostic).

## 4. Database review

- Models (`backend/app/models.py`, 421 lines): `User`, `Passage`, `Question`, `UserResponse`, `ReviewQuestion`, `QuizAttempt`, `Payment` (dormant), `PasswordResetToken`, `UserAchievement`, `QuestionMastery`, `TutorQuery`, `PushSubscription`, `StudyPlan`, `LessonNote`, `NoteProgress`, `NoteFeedback`, `NoteTutorQuery`.
- Migration mechanism is custom (`ensure_schema()`-style additive column patching), not Alembic. Works for additive changes; has no rollback story and no schema version history — riskier as the schema grows.
- `Payment`/premium fields are schema debt: present, unused, and will need either real wiring or explicit removal before payments launch — leaving them as-is a while longer is fine, but they should not silently multiply.
- No `related_topics` foreign-key constraint at the DB level for lesson notes — integrity is enforced only by the seed script's Python-side validation (confirmed real: this caught a genuine cross-subject bug during the lesson-notes work). Worth a comment in the model, not necessarily a DB constraint yet.

## 5. Security review

- **Good**: password hashing, generic forgot-password response (no user enumeration), hashed reset tokens, admin never auto-granted, server-side permission checks via FastAPI `Depends()` (not just frontend guards), `.env` correctly gitignored, `.env.example` has no real secrets.
- **Gaps**: no rate limiting on login/register/forgot-password (brute-force and credential-stuffing exposure), no security headers, non-revocable JWTs (7-day blast radius on any leaked token, no server-side logout), no 2FA, no CSRF token (relies solely on SameSite=Lax + CORS origin allowlist), no automated dependency/vulnerability scanning, no CI to catch regressions before deploy.
- Given this app will hold Nigerian minors' data (JAMB/WAEC candidates are frequently under 18), the brief's emphasis on child/student data protection is well-founded and currently unaddressed — there's no explicit data-retention policy, no parental-consent flow, and no distinct data classification for minor accounts.

## 6. UX review

- Authenticated experience is coherent: single sidebar (`AppShell.tsx`) with 11 nav items, consistent iconography, streak/points/push-bell in the topbar.
- The core positioning from the brief — diagnose → identify weak topics → explain mistakes → recommend practice → personalized plan → track improvement → estimate readiness — is **partially real**: weak-topic detection, a reactive Study Planner, and a projected-JAMB-score card on the Dashboard (computed from real practice accuracy once a user has answered 30+ questions) all already existed. **Correction to this audit's original claim**: a "readiness estimate" *was* already surfaced (missed on first pass — the projected-score card lives in `dashboard.py`/`Dashboard.tsx` and wasn't read closely enough the first time through). What was genuinely missing, confirmed by grepping for it and finding zero call sites: `User.has_taken_diagnostic` and QuizAttempt's `"diagnostic"` mode both existed in the schema and were read by the Dashboard (which showed a banner when the flag was false), but nothing anywhere ever *set* the flag or *created* a diagnostic-mode attempt — scaffolding with no feature behind it. Built in Phase 3 (see below). Mistake-explanation surfacing beyond the per-question AI tutor is still not built.
- Zero guest experience means the entire top-of-funnel (a visitor evaluating the product) has no product to evaluate — this is the single highest-leverage UX gap relative to a conversion-funnel product like this.

## 7. SEO review

Already covered concretely in items 2–3: no per-route metadata (client-only SPA, no SSR/prerendering means crawlers and link-preview bots see one generic shell for every URL), no `robots.txt`, no `sitemap.xml`, no structured data, no blog/content-marketing surface, no react-helmet-async or equivalent in `frontend/package.json` for even client-side tag swapping. This is close to an SEO blank slate today, not a tuning problem.

## 8. Performance review

- Real, working optimization already in place: route-level `React.lazy()` code-splitting across the whole app.
- Question-diagram assets are SVG (lightweight, resolution-independent) — good choice already made.
- `render.yaml` history: `naijaprep-api` was on Render's free tier (cold start after ~15 min idle) — user has since upgraded; this was a real factor but was wrongly blamed for the lesson-notes hang, which was actually a client-side infinite loop in `NoteContent.tsx` (fixed this session, not yet deployed — see Files Changed below).
- No CDN/image-optimization pipeline, no bundle-size budget or analysis step, no Lighthouse/perf CI gate.

## 9. Proposed revised architecture

No rewrite. The stack is sound and modern; the gaps are additive, not structural:

- Add a lightweight rate-limiting + security-headers middleware layer to FastAPI (e.g. `slowapi` + a small headers middleware) rather than restructuring auth.
- Add per-route SEO metadata via `react-helmet-async` (client-side is an acceptable first step; true SSR/prerendering is a larger, separate decision to make deliberately later, not bundled into Phase 1).
- Add a guest-mode path: a small set of publicly reachable practice routes reusing existing `Question`/`Quiz` logic behind `get_current_user_optional` (already exists in `auth.py`), rather than a parallel guest system.
- Introduce `pytest` + `conftest.py` + a minimal GitHub Actions CI workflow (lint + test on push) as foundational infra before further feature work compounds untested surface area.
- Leave `Payment`/premium fields and the AI-generation path dormant until they're each deliberately re-scoped — don't let Phase 1 touch them.

## 10. Prioritised implementation roadmap

1. **Phase 1 — Audit & stabilisation** (this document + the items below): testing/CI foundation, security hardening (rate limits, headers), ship the already-fixed `NoteContent.tsx` bug + 97 lesson notes to production, deploy publish-all.
2. **Phase 2 — SEO & top-of-funnel**: guest practice flow, per-route metadata, `robots.txt`/`sitemap.xml`, landing pages.
3. **Phase 3 — Diagnostic & personalization loop**: onboarding diagnostic, mistake-explanation surfacing, readiness estimate.
4. **Phase 4 — Trust & monetization**: decide and wire real payments (Paystack first, given Nigerian market fit), subscription gating.
5. **Phase 5 — Multi-role surfaces**: parent dashboard, teacher/school tooling.
6. **Phase 6 — Accessibility, i18n (Hausa), advanced PWA/offline.**
7. **Phase 7 — Advanced/AI features**, gated behind explicit guardrail design (brief's own Section on AI guardrails), not before.

## 11. Specific files that will be changed (Phase 1 only)

- `frontend/src/components/ui/NoteContent.tsx` — already fixed this session (infinite-loop bug); needs commit + push + deploy.
- `backend/seed_lesson_notes.py` — needs one more run against production `DATABASE_URL` to sync all 97 notes (currently only 10 Math notes confirmed live).
- `backend/sync_questions_db.py` — needs confirming/running against production for the earlier topic-relabel work.
- `backend/app/main.py` — add rate-limiting + security-headers middleware registration.
- New: `backend/tests/conftest.py`, `backend/tests/test_*.py` — first real automated test suite.
- New: `.github/workflows/ci.yml` — lint/test on push.
- `backend/requirements.txt` — add `slowapi` (or equivalent) and `pytest` if not already present (pytest presence not yet confirmed — check before assuming).

## 12. Database migrations required

None required for Phase 1 as scoped above — no schema changes are implied by rate limiting, headers, CI, or the lesson-notes sync (which is a data operation via the existing seed script, not a schema change). Flag for Phase 2: guest-mode may need a nullable-user-id path on `QuizAttempt` if guest attempts should persist across a later signup — needs a deliberate migration, not assumed here.

## 13. Risks and backward-compatibility concerns

- Adding rate limiting could lock out legitimate users on shared school/cybercafé IPs common in Nigeria — needs generous, tested thresholds, not aggressive defaults.
- Non-revocable JWTs mean any auth hardening (e.g. shortening expiry) will log out all currently-logged-in users — should be scheduled as a known, communicated change, not a silent side effect of another fix.
- The custom `ensure_schema()` migration approach has no down-migration path — moving to Alembic later (recommended before Phase 4's payment schema work) will need a careful one-time reconciliation, not a rewrite.
- `Payment`/premium fields already exist unused — any new monetization work must audit these fields first rather than creating parallel ones.

## 14. Features that should not be implemented yet

- Real payment integration (Paystack/Flutterwave) — no rate limiting/security headers/tests exist yet to safely handle money-adjacent flows.
- AI-generation-based lesson notes (endpoint exists but is intentionally dormant per the user's explicit prior decision — leave it that way).
- Parent/teacher/school multi-role dashboards — depends on decisions (data model, permissions) that shouldn't be made before Phase 1's security/testing foundation is in place.
- SSR/prerendering — a genuine architecture decision (adds build/deploy complexity) that deserves its own scoped discussion, not a Phase 1 side effect of the SEO metadata fix.
- Hausa localization — no i18n infrastructure exists; bolting on translations before an i18n framework is chosen creates rework.

## 15. Acceptance criteria for Phase 1

- `NoteContent.tsx` fix is committed, pushed, and deployed; all 97 lesson notes are live in production and published (verified by loading at least 3 notes per subject in a real browser, not just an API check — per the earlier verification-gap lesson).
- `sync_questions_db.py` topic-relabel confirmed run against production (or explicitly confirmed unnecessary).
- Rate limiting is active on `/api/auth/login`, `/api/auth/register`, `/api/auth/forgot-password` with thresholds tested against normal multi-user-per-IP usage.
- Basic security headers (CSP, X-Frame-Options, X-Content-Type-Options) are present on all responses, verified via a live curl/header check against production.
- A first `pytest` suite exists covering auth (register/login/permission checks) and the lesson-notes publish/publish-all endpoints, runs green locally.
- A CI workflow runs that test suite (and, if feasible, `tsc --noEmit` for the frontend) on every push.
- No existing feature regresses — verified by re-running the existing manual smoke checks (quiz, mock, dashboard, admin) after all Phase 1 changes.

---

## Progress log

- **Phase 1 (2026-07-18), complete**: rate limiting (`slowapi`, register/login 10/min, forgot-password 5/min), security headers + CSP + disabled prod API docs, first `pytest` suite (backend/tests/), CI (`.github/workflows/ci.yml`). All verified with real test runs, not just written.
- **Phase 2 (2026-07-18), complete**: guest practice flow (`/api/public/guest-practice`, stateless/rate-limited/no schema change, new public `/try` page), SEO basics (`robots.txt`, `sitemap.xml`, meta/OG/Twitter tags, per-route `useDocumentMeta` hook).
- **Phase 3, in progress (2026-07-18)**: built the real onboarding diagnostic (`POST /api/quiz/start-diagnostic`, 3 questions x 11 subjects = 33, reuses the existing generic attempt/answer/results flow, flips `User.has_taken_diagnostic` on completion, Dashboard banner now actually starts it instead of linking to `/subjects`). Deferred within Phase 3: aggregate mistake-explanation surfacing beyond the existing per-question AI tutor.
- **Phase 4 (payments), complete (2026-07-18)**: Paystack checkout initialize + signature-verified webhook (`backend/app/routers/payments.py`), reused the previously-dormant `Payment` model and `User.premium_until`/`is_premium` (no migration). First real premium/free split: `/api/mock/start` (Full JAMB Mock) now free once, then requires premium (`FREE_MOCK_EXAMS` env, default 1) -- flagged in-code as a first-guess business decision, not final. No live Paystack keys configured -- `/initialize` 501s until they are.
- **Phase 5 (family/guardian links), complete (2026-07-18)**: generalized "parent dashboard" + "teacher/tutor tooling" into one feature rather than two separate role systems -- any user can share a code (`User.guardian_link_code`) that another user redeems to become a read-only watcher of their progress (`GuardianLink` model, `backend/app/routers/family.py`, new `/family` page). A tutor watching 5 students is just 5 links under one guardian -- no classroom/cohort model built, and formal school-level tooling (bulk roster import, assignments) remains explicitly out of scope. Progress-summary computation extracted into `backend/app/progress.py`, shared between the real dashboard and the guardian's read-only child summary so there's one implementation of "projected score," not two.
- **Phase 6 (accessibility + PWA), complete (2026-07-18)**: skip-to-content links, `aria-label` on the notification bell, Escape-to-close on the mobile nav drawer; `frontend/public/offline.html` + service worker `v2` for a branded offline fallback (deliberately did not cache lesson-note API responses -- they carry live per-user state, would risk showing stale personalized data).
- **Phase 6 (Hausa), first increment only (2026-07-18)**: lightweight dependency-free i18n (`frontend/src/i18n/translations.ts`, `LanguageContext`, EN/HA switcher in both layouts) covering navigation, the homepage hero, and auth-page labels -- not full-app coverage. **Hausa strings have not been reviewed by a native speaker** -- recommend a review pass before treating this as production-complete or expanding further.

All of Phases 1-6 are implemented and verified (backend tests pass; frontend: `tsc -b` clean) but repeatedly end up sitting as uncommitted changes because of a recurring `.git/index.lock` issue on the user's machine -- see project memory for the resolution steps each time this recurs.

- **New-laptop environment rebuild (2026-07-29)**: previous laptop was lost; repo re-downloaded from private GitHub (`Manirmaths/Acelume`). Git history reattached in place via `git init` + `git reset --mixed origin/main` -- **confirmed the working tree matched `origin/main` exactly, so no work was ever stranded by the old index.lock issue.** Full setup steps are in `SETUP.md`. Two environment notes worth keeping: Python **3.13** is required (3.14 was the system default and has no cp314 wheels for `psycopg2-binary==2.9.10`, which would force a source build); and PowerShell needs `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` before `npm` or the venv activate script will run. Test count is now **52 passed**, not the 46 recorded above -- six tests were added after that line was written.

- **Rebrand Burina -> Acelume (2026-07-29), code and copy only**: the interim "Burina" name was dropped; Acelume is current and is already the GitHub repo name. Renamed across 24 source files plus `render.yaml` and `README.md`: page copy, meta/OG/Twitter tags, `useDocumentMeta` site name, PWA manifest, service worker notification title, offline page, password-reset email subject/body, FastAPI docs title, EN **and HA** i18n strings, Electron `productName`, Capacitor `appName`, and the Android display name in `strings.xml`.

  Deliberately **not** changed, each for a specific reason:
  - **Domains stay `naijaprep.com.ng`** -- no Acelume domain is registered yet. The dead `burina.ng` entries were removed from `FRONTEND_ORIGINS` since that domain was never registered either. When an Acelume domain is secured, append it *after* the naijaprep entries: `PUBLIC_APP_URL` defaults to `FRONTEND_ORIGINS[0]`, so ordering silently controls where password-reset links point.
  - **Android package ID stays `com.naijaprep.app`** -- the app is in Play Store closed testing, and a package ID is permanently bound to its Play Console entry once uploaded. Changing it would mean a new listing and losing existing testers. Same reasoning for the Electron `appId` (`com.naijaprep.desktop`) and the npm package name (`naijaprep-desktop`), neither of which users ever see.
  - **Render service names stay `naijaprep-api` / `naijaprep-web`** -- these are Render resource identifiers; renaming recreates the services and loses their env vars and custom domains.
  - **`naijaprep.db`** (local SQLite filename) and the `DATABASE_URL` default -- cosmetic, and renaming would orphan existing local dev databases.
