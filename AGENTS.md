# Acelume — working notes for AI agents

Read this before touching the repo. It records decisions and traps that are expensive to
rediscover, not things you can learn by reading the code.

Companion docs: `README.md` (what the app is, how to run it), `SETUP.md` (fresh-machine
setup), `AUDIT.md` (full architecture audit + phase-by-phase progress log),
`MIGRATION-FOLLOWUPS.md` (outstanding domain-migration work).

---

## What this is

Exam-prep web app for Nigerian students (JAMB, WAEC, NECO, Post-UTME). Subject/topic MCQ
practice, full CBT mock exams, onboarding diagnostic, spaced repetition, AI tutor, lesson
notes, gamification, guardian/tutor progress sharing.

- **Backend**: FastAPI + SQLAlchemy 2.0, JWT in an httpOnly cookie, 17 routers under
  `backend/app/routers/`. SQLite locally, Neon Postgres in production.
- **Frontend**: React 19 + TypeScript + Vite + Tailwind + React Router + TanStack Query,
  27 pages, route-level `React.lazy()` splitting.
- **Native**: Capacitor (Android) and Electron (Windows) are thin shells that load the live
  site in a WebView — not bundled builds.
- **Deploy**: Render (`acelume-api`, `acelume-web`), Neon Postgres, live at
  **acelume.ng** (canonical) with naijaprep.com.ng still serving.
- **Naming**: Naija Prep → Burina (abandoned) → **Acelume**. Infrastructure identifiers
  still say `naijaprep` on purpose — see below.

## Naming: what is deliberately NOT renamed

Do not "fix" these. Each is load-bearing:

| Thing | Why it stays |
|---|---|
| `com.naijaprep.app` (Android package ID) | Permanently bound to the Play Console entry once uploaded. App is in closed testing. Changing = new listing, lose testers. |
| `naijaprep-web.onrender.com` / `naijaprep-api.onrender.com` | Render subdomains are immutable; renaming a service does not change them. They are live DNS CNAME targets. |
| `com.naijaprep.desktop`, `naijaprep-desktop` | Electron appId / npm name. Invisible to users. |
| `naijaprep.db`, `DATABASE_URL` SQLite default | Renaming orphans existing local dev databases. |
| `naijaprep.com.ng` domain | The shipped Android app loads it (`capacitor.config.json` → `server.url`). Must keep serving until testers migrate. |

## Active constraint (check before infrastructure changes)

As of 2026-07-30 the Android app is in Play Store closed testing, working toward the
**12 testers × 14 continuous days** requirement for production access (at 9 days). The
shipped app is a WebView pointed at `https://naijaprep.com.ng`, so **any change that stops
that domain serving normally can cost tester continuity and reset the counter**. No
redirects, no DNS migration on that domain, until production access is granted. Full
reasoning and correct sequencing in `MIGRATION-FOLLOWUPS.md`. Delete this section once
production access is through.

## Traps that have actually bitten

**Schema changes need `_PENDING_COLUMNS`.** `Base.metadata.create_all()` runs on startup but
only creates *new tables* — it never ALTERs an existing one. Adding a column to a model that
is already deployed with data requires an entry in `_PENDING_COLUMNS` in
`backend/app/database.py`, or production breaks on the first query touching that column
(e.g. any login, if it is on `User`). There is no Alembic. Migration is a hand-rolled
idempotent patcher with no down-migration path.

**`FRONTEND_ORIGINS` order is load-bearing.** `PUBLIC_APP_URL` is unset in production and
falls back to `FRONTEND_ORIGINS[0]`. That value builds password-reset links (`auth.py`) and
the Paystack callback URL (`payments.py`). Reordering silently redirects real user email.

**Render env vars can drift from `render.yaml`.** Several production vars
(`RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `VAPID_*`, `NOTIFICATIONS_CRON_SECRET`) exist only
in the dashboard and are absent from `render.yaml`. Editing the repo does nothing for them.
Always check the dashboard before concluding a var is unset.

**Integrations fail silently by design.** `RESEND_API_KEY`, `OPENAI_API_KEY`, `VAPID_*`,
`PAYSTACK_*` all degrade to a no-op or friendly fallback when blank rather than erroring.
Good for local dev; means a missing production key looks identical to working code. Two
real outages were found this way — password-reset email and web push were both unconfigured
in production for an unknown length of time while appearing fine.

**Math only renders inside `\( ... \)`.** `MathText` (used by Quiz, Mock, Results, Review,
Flashcards, Home and Try) treats everything outside those delimiters as plain text, so
`Find \int cos4 x dx` shows students raw LaTeX source. Two consequences:

- **Any new component that displays `question_text`, `option_*` or `explanation` must route
  it through `<MathText>`.** Five components were rendering options as bare `{text}`, which
  is why the guest `/try` page showed `\(\frac{-2}{7}\)` as literal source.
- **Never put `\,` (LaTeX thin space) in `data/questions.csv`.** It contains a literal comma
  and silently splits unquoted CSV fields, shifting every column after it. Use `\;`.
  `python tools/fix_question_latex.py --check` guards both of these and runs in CI.

**`$` in question text is currency, not math.** Economics and English questions contain
`$36`, `$10,000`. `MathText`'s docstring once claimed `$$...$$` support; the regex
deliberately does not implement it, and must not — that would turn prices into math.

**Fixing `data/questions.csv` does not fix production.** The CSV is the source of truth, but
the live Neon database is only updated by running
`python sync_questions_db.py "<DATABASE_URL>"` from `backend/`. A content fix that is
committed but not synced changes nothing for students.

**Verify in a browser, not just via API.** A lesson-notes bug once passed every API check
while being completely broken in the UI (infinite loop in `NoteContent.tsx`). Load the
actual page.

**Lesson notes seed as `draft`.** After running `seed_lesson_notes.py` they are invisible
until published via Admin → Lesson notes → Publish all. A fresh database looks empty, not
broken.

**Keep the repo out of OneDrive.** It previously lived in
`C:\Users\Admin\OneDrive\Documents\Acelume`, where OneDrive held file handles on `.git/` —
causing the recurring `.git/index.lock` failures referenced throughout `AUDIT.md`, and at
least one push that printed "Writing objects: 100%" while never updating the remote ref.
Relocated to **`C:\dev\Acelume`** on 2026-07-30 and the problem stopped. Do not move it back.

Relocating was done by fresh `git clone`, not by moving the directory: `.venv` and
`node_modules` are not relocatable on Windows (`pyvenv.cfg`, `Scripts\activate` and npm
`.bin` shims all hardcode absolute paths). Only `backend/.env` and `backend/naijaprep.db`
needed copying across, both being gitignored.

**Agents: do not run `git` against this repo from a Linux container or sandbox mount.**
Even read-only commands like `git status` create `.git/index.lock`, and a mount that lacks
delete permission leaves it behind — the next `git` command on Windows then fails with
`Unable to create '.git/index.lock': File exists`. Recovery is
`Remove-Item .git\index.lock -Force`. Read files directly instead, and let the human run git.
This produced a false `index.lock` on 2026-07-30 that looked exactly like the historical
OneDrive problem but had a completely different cause.

**Line endings differ between the old and new checkouts.** The OneDrive copy came from a
GitHub ZIP (LF); the current clone was checked out by Git for Windows with
`core.autocrlf=true` (CRLF in the working tree, LF in the blobs). Windows git normalises
this and reports a clean tree. Any tool reading the working tree with a *different* autocrlf
setting — notably a Linux container or sandbox — will see every line of every file as
modified. That is an artifact, not a real diff: the giveaway is insertions exactly equalling
deletions. Trust `git status` run on Windows.

## Local development

Full instructions in `SETUP.md`. The essentials:

- **Python 3.13 specifically** (`.python-version`). Pinned deps have no cp314 wheels —
  `psycopg2-binary==2.9.10` will try to build from source and fail.
- PowerShell needs `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` before `npm` or
  the venv activate script will run.
- Backend on :8000 (`uvicorn app.main:app --reload --port 8000`), frontend on :5173
  (`npm run dev`). Vite proxies `/api/*`, so no CORS setup and no `frontend/.env` in dev.
- **First registered account becomes admin automatically.** Local SQLite is separate from
  production, so register a fresh local account to reach `/admin`.

## Before you call something done

- `pytest` from `backend/` — **52 tests**, all must pass.
- `npx tsc -b` from `frontend/` — must produce no output.
- CI (`.github/workflows/ci.yml`) runs both on every push to `main`.
- Expect ~417 `datetime.utcnow()` deprecation warnings. Known, harmless today, not a
  regression you introduced.

## Product decisions to respect

- **AI-generated lesson notes are intentionally dormant.** The endpoint exists; the user
  deliberately chose not to use it. All 97 notes are hand-authored. Do not wire it up.
- **Payments are live but barely scoped.** Paystack checkout + signature-verified webhook
  exist. The only premium gate is the full JAMB mock after `FREE_MOCK_EXAMS` (default 1),
  flagged in-code as a first guess, not a final business decision.
- **Hausa i18n is a first increment only** — navigation, homepage hero, auth labels. Strings
  have **never been reviewed by a native speaker**. Do not treat as production-complete or
  expand without review.
- **No SSR/prerendering.** A deliberate open decision, not an oversight. The SPA serves one
  shell to crawlers; SEO rests on the canonical tag and client-side meta swapping.
- Rate limits must stay generous — shared school and cybercafé IPs are common in Nigeria.

## Style

Match what is already there. The codebase comments *why*, not *what* — particularly around
non-obvious decisions (see `database.py`'s `_PENDING_COLUMNS` block or `render.yaml`).
Preserve that when editing: if you make a non-obvious choice, leave the reasoning behind.
