Acelume (formerly Naija Prep) is a web app that helps students in Nigeria prepare for JAMB, WAEC, NECO, and Post-UTME. It provides subject/topic-based MCQ practice, a full JAMB CBT mock exam, a diagnostic placement test, progress tracking, and streak-based gamification.

## Tech stack (v2 — migrated from Flask/Jinja)

- **Backend**: FastAPI (Python), SQLAlchemy 2.0, JWT auth via httpOnly cookie, Pydantic schemas. SQLite for local dev, Postgres for production.
- **Frontend**: React + TypeScript, Vite, Tailwind CSS, React Router, TanStack Query.

The two are fully decoupled: the backend is a JSON REST API, the frontend is a single-page app that talks to it over HTTP.

## Project structure

```
Acelume/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + router registration + CORS
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schemas.py         # Pydantic request/response schemas
│   │   ├── auth.py            # password hashing, JWT, cookie auth dependency
│   │   ├── database.py        # engine/session setup + startup schema migration
│   │   ├── email.py           # transactional email (password reset) via Resend
│   │   ├── achievements.py    # badge registry + unlock criteria
│   │   ├── subjects.py        # canonical subject list
│   │   └── routers/           # auth, subjects, quiz, dashboard, review, admin, leaderboard, blitz, mock, achievements
│   ├── seed_questions.py      # imports data/*.csv into the DB (safe, re-runnable)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/              # Home, Login, Register, Subjects, Quiz, Results, Dashboard, Review, Admin, Blitz, Mock, Achievements...
│   │   ├── components/         # Layout (nav/footer), RequireAuth
│   │   ├── context/AuthContext.tsx
│   │   └── api/                # typed fetch client
│   ├── android/                 # Capacitor native Android project (generated, see below)
│   ├── capacitor.config.json
│   ├── package.json
│   └── .env.example
├── desktop/                     # Electron Windows desktop shell (see below)
└── data/                       # question bank CSVs (subject-agnostic of backend/frontend)
```

## Running it locally

### 1. Backend (FastAPI)

```
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

copy .env.example .env        # already done for you; edit SECRET_KEY etc. if you like
python seed_questions.py      # loads data/*.csv into backend/naijaprep.db (SQLite)

uvicorn app.main:app --reload --port 8000
```

API docs (auto-generated): http://localhost:8000/docs

The **first account you ever register becomes an admin automatically** (can manage questions at `/admin` in the frontend). Promote additional admins by editing `is_admin` directly in the DB, or add a small script later if you need it often.

### 2. Frontend (React + Vite)

```
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173 and proxies `/api/*` requests to the backend on port 8000 (see `vite.config.ts`) — no CORS setup needed in dev.

### 3. Try it

Register a free account, take a quiz, check the dashboard for streaks/points, mark a question for review, and (as the first/admin user) visit `/admin` to add or edit questions directly instead of touching CSVs.

## Notes on this migration

- **Subscriptions/premium are disabled** (all subjects are free) per a deliberate product decision — the `Payment` model and Paystack plumbing exist in `backend/app/models.py` but nothing calls it yet. Re-enabling paid tiers is a matter of wiring gating checks back into the relevant routers, not rebuilding payment infrastructure.
- **Quiz state moved from server sessions to a database table** (`QuizAttempt`). This is a deliberate upgrade for the new stateless-API architecture: attempts are resumable, auditable, and don't depend on a server-side session cookie (only the JWT auth cookie is needed).
- **Schema changes to an already-deployed table** (e.g. new columns on `User`) need an entry in `_PENDING_COLUMNS` in `backend/app/database.py` — `Base.metadata.create_all()` only creates brand-new tables, it never ALTERs existing ones, so this is the difference between a smooth deploy and a broken production login.
- **Known data quality issue**: a handful of legacy questions in `data/mathsQuestions.csv` (present before this migration) have `exam_year` values that look like they contain explanation text instead of a year, and at least one question's `correct_option` doesn't match its own explanation. Worth an audit pass — flagging here so it isn't missed.

## Deployment

- **Backend**: any ASGI host (Render, Railway, Fly.io, etc.) running `uvicorn app.main:app`. Set `DATABASE_URL` to a Postgres connection string in production, and `FRONTEND_ORIGINS` to your deployed frontend's URL (required for CORS + cookies to work). Set `RESEND_API_KEY` + `RESEND_FROM_EMAIL` for password-reset emails to actually send (without it, the reset link is just logged server-side, which still works for testing but not real users).
- **Frontend**: any static host (Vercel, Netlify, Render static site). Set `VITE_API_URL` to your deployed backend's URL at build time.

## Native apps (Android + Windows)

Both the Android app and the Windows desktop app are thin **wrappers around the live site** (`https://naijaprep.com.ng`) rather than separate bundled builds. They open a native window/WebView pointed straight at the real domain, so the existing login cookie, CORS setup, and every future site update all work exactly as they do in a browser — no separate mobile auth flow, no re-publishing the app just to ship a content change.

iOS was intentionally skipped for now (building/signing an iOS app requires Xcode on a Mac, which isn't available here) — revisit later if needed, e.g. via a cloud Mac build service like Codemagic or a GitHub Actions macOS runner.

### Android (via Capacitor)

Requires [Android Studio](https://developer.android.com/studio) installed (for the Android SDK + an emulator or a USB-connected device).

```
cd frontend
npm install
npm run cap:sync           # syncs capacitor.config.json into the native project
npm run cap:open:android   # opens the android/ project in Android Studio
```

From Android Studio: press Run to install on an emulator/device, or use **Build → Generate Signed Bundle / APK** to produce a release APK/AAB for the Play Store (you'll need to create a signing keystore the first time — Android Studio walks you through it).

The app's package ID is `com.naijaprep.app` — change it in `frontend/capacitor.config.json` before your first Play Store upload if you'd prefer something else (it can't be changed after publishing).

### Windows desktop (via Electron)

```
cd desktop
npm install
npm start        # launch the app locally to test
npm run dist      # build a Windows installer (.exe) into desktop/release/
```

The installer is unsigned (no code-signing certificate configured), so Windows SmartScreen may warn users the first time they run it — this is normal for an unsigned app and doesn't affect functionality. A code-signing certificate (from a CA like DigiCert/Sectigo) would remove that warning if you want a fully polished distribution later.

## License

MIT License. Built to help Nigerian students succeed in WAEC/JAMB/NECO.
