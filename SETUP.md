# New laptop setup (2026-07-29)

Run these in the VS Code terminal, opened at `C:\dev\Acelume`.
Use **PowerShell** (VS Code's default on Windows).

---

## 0. Prerequisites

Checked 2026-07-29 on this laptop: **Python 3.14.6 present; Git and Node.js missing.**

Install all three via winget:

```powershell
winget install --id Git.Git -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Python.Python.3.13 -e
```

**Then close VS Code entirely and reopen it** — PATH changes don't reach an
already-open terminal.

```powershell
git --version
node --version
npm --version
py -3.13 --version   # expect 3.13.x
```

### Why Python 3.13 and not the 3.14 already installed

`.python-version` pins 3.13, and `requirements.txt` pins exact dependency versions
from early 2025 — several have no Python 3.14 wheels. `psycopg2-binary==2.9.10` is
the certain failure: with no cp314 wheel, pip falls back to compiling from source and
dies without Postgres build tools on PATH.

Installing 3.13 *alongside* 3.14 is the cheap fix. Bumping ~18 pinned dependencies to
chase a Python version is a far larger change than it appears, and CI runs a fixed
version anyway — local and CI drifting apart is how "works on my machine" starts.

3.14 stays your system default; `py -3.13` reaches the other one explicitly, and only
for creating the venv. Once the venv is active, plain `python` inside it *is* 3.13.

---

## 1. Restore git history in place

This folder was downloaded as a ZIP from GitHub, so it has **no `.git` folder** — you
can't commit, pull, or push from it yet. Rather than cloning somewhere else (which would
move the folder out from under Cowork), re-attach the remote in place:

```powershell
cd C:\dev\Acelume
git init
git remote add origin https://github.com/<your-username>/<your-repo>.git
git fetch origin
git reset --mixed origin/main
git branch -M main
git branch --set-upstream-to=origin/main main
```

`git reset --mixed` attaches the history **without touching your files on disk**. After
it, run `git status` — anything listed as modified is a real difference between the ZIP
you downloaded and what's on GitHub. Expect it to be clean or near-clean.

> If GitHub asks for a password, use a **Personal Access Token**, not your account
> password (github.com → Settings → Developer settings → Personal access tokens).

---

## 2. Backend: virtualenv + dependencies

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the activate script ("running scripts is disabled"), run once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

`backend\.env` has already been created for you with a fresh local `SECRET_KEY` and
SQLite. All optional integrations (Paystack, Resend, OpenAI, Web Push) are left blank —
each degrades gracefully rather than erroring, so local dev works without any keys.

---

## 3. Seed the local database

With the venv still active, from `backend\`:

```powershell
python seed_questions.py
python -u sync_questions_db.py "sqlite:///./naijaprep.db"
python -u seed_lesson_notes.py "sqlite:///./naijaprep.db"
```

This creates `backend\naijaprep.db` (gitignored) and loads the question bank plus all
97 lesson notes.

---

## 4. Run the backend

```powershell
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs (dev only — disabled when `ENV=production`)
- Health check: http://localhost:8000/api/health

Leave this terminal running.

---

## 5. Frontend: dependencies + dev server

Open a **second** terminal:

```powershell
cd C:\dev\Acelume\frontend
npm install
npm run dev
```

App at http://localhost:5173. Vite proxies `/api/*` to port 8000, so no CORS setup and
no `frontend\.env` is needed in dev.

**The first account you register becomes admin automatically** — your old admin account
lives in the production Neon database, not this fresh local SQLite one, so register a
new local account to reach `/admin`.

---

## 6. Verify

```powershell
# backend (venv active, from backend\)
pytest                 # expect 46 passed

# frontend (from frontend\)
npx tsc -b             # expect no output
```

Then click through manually: quiz → results → dashboard → a lesson note → `/admin`.

---

## Security note — action needed

`.note` in the repo root contains the **live Neon production database password in
plaintext**, and `.note` is *not* in `.gitignore` — so that credential is committed to
GitHub and sits in the repo's history. The repo is private, which limits the blast
radius, but this is still worth fixing:

1. Rotate the Neon database password (Neon console → Roles → reset password).
2. Update `DATABASE_URL` in the Render dashboard for `naijaprep-api`.
3. Add `.note` to `.gitignore` and `git rm --cached .note`.

Rotating is the part that actually matters — removing the file from future commits
doesn't scrub it from history.
