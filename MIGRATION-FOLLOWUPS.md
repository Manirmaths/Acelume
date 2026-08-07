# Domain migration follow-ups (acelume.ng)

Written 2026-07-30, after Step 2 of the phased migration (canonical is now acelume.ng).

**Do these in order.** Task 2 must ship before Task 3, or you break the Android app for
your closed-testing group. Task 1 is independent — do it whenever.

---

## ⚠️ RESOLVED 2026-08-07 — "Couldn't load your dashboard" on the Android app

**Symptom reported:** the app installed from Play Store testing showed
*"Couldn't load your dashboard"*, and the launcher icon still read **Naija Prep**.

**Both symptoms have the same cause: the phone is running the OLD build.**
`strings.xml` already says `Acelume`, so a "Naija Prep" launcher label can only come from
a build made before the rename. Capacitor writes `app_name` at `cap add` time and does
**not** rewrite it on `cap sync`, so this is worth remembering: if the label is ever wrong
in a *new* build, edit `android/app/src/main/res/values/strings.xml` directly.

**Why the dashboard specifically failed — the part worth understanding:**

1. The old build's `server.url` is `https://naijaprep.com.ng`.
2. That domain serves the same static bundle as acelume.ng, and `VITE_API_URL` is baked in
   at build time as `https://api.acelume.ng` (see `render.yaml`).
3. `naijaprep.com.ng` → `api.acelume.ng` crosses **registrable domains**, so it is a
   **cross-site** request — unlike `acelume.ng` → `api.acelume.ng`, which is same-site.
4. The auth cookie was `SameSite=Lax`. On a cross-site response the browser **refuses to
   store it at all**.
5. `POST /api/auth/login` still returned **200 with a user body**. The frontend set that
   user, `RequireAuth` let them through, and then every authenticated call 401'd.

So the student saw a signed-in app with a dead session, and no way to recover — the
worst possible failure shape, because nothing on screen suggested they were not logged in.

**Fixes shipped:**

- `frontend/src/context/AuthContext.tsx` — login and register now **verify the session**
  with `GET /api/auth/me` before setting a user, and surface a real message if the cookie
  did not persist. This is the durable fix: it also covers private browsing, blocked
  third-party cookies and Safari ITP, none of which were handled before.
- `frontend/src/pages/Dashboard.tsx` — a 401 now reads *"Your session has ended"* with a
  Sign in button, instead of *"Couldn't load your dashboard"* with nothing to do.
- `backend/app/config.py` — new `COOKIE_SAMESITE` env var, **default `lax`, unchanged**.

**Decision left for you (deliberately not taken automatically):**

Setting `COOKIE_SAMESITE=none` in the Render dashboard would un-break every existing
tester **immediately, without shipping a new APK**, because it makes the cookie survive
the cross-site request from naijaprep.com.ng.

The cost is a weaker CSRF posture — cookies would ride along on cross-site requests. It is
substantially mitigated here (every endpoint takes JSON, so every request is preflighted,
and `allow_origins` is an explicit allowlist with no wildcard), but it is a real change to
auth behaviour and was not worth making unilaterally.

- **If testers are stuck on the old build for a while** → set `COOKIE_SAMESITE=none`.
- **If the versionCode 6 build reaches them soon** → change nothing. That build points at
  acelume.ng, which is same-site, and Lax works correctly.

Either way, `SameSite=None` is only ever needed for the legacy domain. Once
naijaprep.com.ng is retired, remove the env var.

---

## 🚦 BLOCKING CONSTRAINT — read before touching naijaprep.com.ng

**As of 2026-07-30, Play Console shows: _"12 testers have currently been opted in for 9 days
continuously"_ — 14 continuous days are required to unlock production access.**

The counter measures **continuous opt-in**, so it resets if testers leave the closed test.
The shipped Android app is a WebView pointed at `https://naijaprep.com.ng`
(`capacitor.config.json` → `server.url`). Anything that makes that domain stop serving the
app normally — a 301 redirect, or a botched DNS migration — shows testers a broken app,
and frustrated testers opt out.

**The trade is bad in both directions**: the upside of moving early is a few days of faster
SEO consolidation; the downside is losing 9+ days of tester continuity and delaying
production launch by two weeks or more.

**So until the 14-day requirement is met and production access is granted:**

- ❌ Do **not** add the Cloudflare 301 (Task 3 below).
- ❌ Do **not** migrate naijaprep.com.ng nameservers to Cloudflare — not even as
  "preparation". DNS import silently dropping a record takes the site, and therefore the
  app, down. There is no safe partial step here.
- ❌ Do **not** change `capacitor.config.json` → `server.url` in a shipped build.
- ✅ Uploading new releases is fine — the counter tracks opt-in continuity, not builds.
  Shipping the acelume.ng rebuild once the upload key reset lands does **not** reset it.
- ✅ Everything on acelume.ng is fine — it is additive and nothing points at it yet.

### Correct sequence

1. **Now → day 14**: change nothing on naijaprep.com.ng. The upload key reset (see Task 2)
   should be approved during this window anyway.
2. **Day 14**: apply for production access.
3. **After that**: rebuild against acelume.ng, ship to closed testing, and confirm in Play
   Console that testers have actually received the update.
4. **Only then**: Task 3 (Cloudflare 301 + Change of Address).

Safe to do at any time, with no effect on the tester count: publish the 97 lesson notes,
back up the upload keystore, Resend/Render config, and anything touching acelume.ng only.

---

## 1. Verify acelume.ng in Resend, then move the sender address — ✅ DOMAIN VERIFIED

**Status 2026-07-30**: `acelume.ng` verified in Resend on the **apex** (region Ireland,
eu-west-1), so `noreply@acelume.ng` is a valid sender and the subdomain caveat below does
not apply. The code defaults in `backend/app/config.py` and `backend/.env.example` have been
moved onto acelume.ng. Remaining: set `RESEND_FROM_EMAIL` in the Render dashboard and test
a real password reset.


Right now password-reset emails send from `noreply@naijaprep.com.ng`. That works, but it's
off-brand, and it will look like a phishing attempt once users associate you with acelume.ng.

### Steps

1. **Resend dashboard → Domains → Add Domain**, enter `acelume.ng` and pick the region
   closest to your users (EU or US — this determines the MX value, so pick once and don't
   change it later).
2. Resend shows a **Records** table with three kinds of entry:
   - a **DKIM** `TXT` record (a public key — this is what proves you own the domain),
   - an **SPF** `TXT` record (lists who may send as you),
   - an **MX** record (routes bounce and complaint feedback back to you).
3. Add all of them at your `.ng` registrar exactly as shown. Copy-paste the values — a
   single truncated DKIM key is the most common cause of failure, and the keys are long
   enough that manual retyping reliably breaks them.
4. Wait. Verification usually completes **within 15 minutes**, but DNS can take up to
   **72 hours**. Resend rechecks for 72 hours and then marks the domain `Failure`, at which
   point you re-trigger rather than wait longer.
5. Once it shows **Verified**, set in **Render → `acelume-api` → Environment**:

   ```
   RESEND_FROM_EMAIL=Acelume <noreply@acelume.ng>
   ```

6. Save (this redeploys), then test end-to-end: use **Forgot password** on acelume.ng with
   a real address and confirm the email arrives, the From line reads Acelume, and the reset
   link actually works.

### Gotchas

- **If Resend has you verify a subdomain** (e.g. `send.acelume.ng`) rather than the apex,
  then `RESEND_FROM_EMAIL` must use that exact subdomain — `noreply@send.acelume.ng`.
  Sending from the apex while only the subdomain is verified is rejected.
- **`RESEND_FROM_EMAIL` is not declared in `render.yaml`** — it lives only in the Render
  dashboard. Editing the repo does nothing for production here.
- Don't delete the naijaprep.com.ng domain from Resend yet. If a queued reset email is
  in flight, you want the old sender still valid.

---

## 2. Rebuild the Android app against acelume.ng

**Do this before Task 3.** The shipped app loads `server.url` from
`frontend/capacitor.config.json`, currently `https://naijaprep.com.ng`. Capacitor
restricts in-app navigation to the configured host by default, so if you put a redirect on
naijaprep.com.ng *first*, the app may follow it to acelume.ng and be blocked — a blank
screen for every existing tester.

### Keystore status (resolved 2026-07-30)

The original upload keystore **was lost with the previous laptop** — a filesystem-wide
search for `*.jks` / `*.keystore` found nothing. Recovered as follows:

- **Play App Signing is enrolled**, so Google holds the real app signing key
  (SHA-1 `46:92:27:90:A2:BD:09:70:7D:14:F8:0E:45:24:8C:5B:C2:81:BC:1B`). That key is
  unchanged and unaffected — existing installs and closed-testing releases were never at
  risk. Only the *upload* key was lost, and only publishing was blocked.
- A new upload keystore was generated at `C:\Users\Admin\keys\acelume-upload.jks`
  (alias `acelume-upload`, RSA 2048, valid to 2051), and an **upload key reset was
  requested** on 2026-07-30 with reason "I lost my upload key".
- New upload key SHA-1: `E6:6C:A8:0A:D7:A2:D5:21:0F:A0:67:41:FC:2A:14:C6:81:4D:77:9D`.
  **Play Console showing this fingerprint under "Upload key certificate" is the signal that
  the reset has been approved** — until then it still displays the old `07:76:01:...`.

**The new keystore and its password must be backed up off-machine.** It is deliberately
outside the repo (so `git add -A` can never sweep it up) and outside OneDrive, which means
without a deliberate backup it exists in exactly one place — the same single-point-of-failure
that caused this whole exercise.

Note the app signing key fingerprint above is what Firebase, Google Maps, and Google OAuth
register against, should any of those ever be added. The upload key is irrelevant to them.

### Original guidance: do you still have the signing keystore?

Your previous laptop is gone. An Android app **cannot be updated** without the key it was
signed with.

- **If you enrolled in Play App Signing** (the default for new apps for years now), Google
  holds the app signing key and you only need your *upload* key. If that's lost, request an
  **upload key reset** in Play Console — Google support can issue one. Recoverable.
- **If you opted out of Play App Signing** and the keystore only existed on the lost laptop
  with no backup, you cannot update this app at all. The only path is a new listing under a
  new package ID, losing your testers and any install base.

Find out which before you spend time on a build. Play Console → your app → **Test and
release → Setup → App signing** shows whether Play App Signing is enabled.

Whatever you find: back the keystore up somewhere off-machine today.

### Steps

1. Edit `frontend/capacitor.config.json`:

   ```json
   "server": { "url": "https://acelume.ng", "cleartext": false }
   ```

2. From `frontend/`:

   ```powershell
   npm run build
   npx cap sync
   ```

3. Bump the version in `frontend/android/app/build.gradle` — **increment `versionCode`**
   (an integer) and update `versionName` (the human-readable string). Play rejects any
   upload whose `versionCode` is not higher than the last one.
4. `npx cap open android` to open Android Studio.
5. **Build → Generate Signed Bundle / APK → Android App Bundle**, signing with your
   existing keystore (see the warning above).
6. Play Console → **Testing → Closed testing** → your track → **Create new release**,
   upload the `.aab`, add release notes, roll out.
7. Verify on a real tester device that the app opens acelume.ng and login works.

### Note

Testers do not update instantly. Leave `naijaprep.com.ng` fully serving (not redirecting)
until you can see in Play Console that the new version has actually reached your testers.

---

## 3. Add 301 redirects, then run Change of Address — ⛔ BLOCKED until production access

**Do not start this before the 14-day tester requirement is met and the acelume.ng rebuild
has reached testers.** See the blocking constraint at the top of this file. Everything below
is correct, just not yet.

### Why this needs extra infrastructure

Google's **Change of Address** tool validates real 301 redirects on your top 5 URLs,
page-by-page — a canonical tag alone is not accepted, and neither is a blanket redirect of
everything to the homepage.

Render static sites apply route rules to **every** attached domain, so there is no way to
redirect naijaprep.com.ng while continuing to serve acelume.ng from the same service. You
need a layer in front of the old domain. Cloudflare's free tier does this well.

**You can skip this entirely.** Doing nothing still works: Google honours the canonical tag
and will consolidate on acelume.ng eventually, just more slowly and less completely than a
redirect plus Change of Address. If that trade is acceptable, stop here — this is the most
involved item on the list for the least certain payoff.

### Steps (Cloudflare route)

1. Cloudflare → **Add a site** → `naijaprep.com.ng` (Free plan). Only this domain moves to
   Cloudflare; acelume.ng stays on your current DNS.
2. Cloudflare imports existing DNS. **Check the import carefully** and make sure these
   survive:
   - apex `A` → `216.24.57.1`
   - `www` `CNAME` → `naijaprep-web.onrender.com`
   - `api` `CNAME` → `naijaprep-api.onrender.com` ← **critical**
3. Change the nameservers at your `.ng` registrar to the two Cloudflare gives you. Wait for
   Cloudflare to report the zone **Active** (usually under an hour; can be much longer on
   `.ng`).
4. **Rules → Redirect Rules → Create rule**:
   - **When**: `hostname` equals `naijaprep.com.ng` **or** `www.naijaprep.com.ng`
   - **Then**: Dynamic redirect, status **301**, preserve query string
   - **Expression**: `concat("https://acelume.ng", http.request.uri.path)`

   The `concat` is what makes it page-by-page: `/try` lands on `/try`, not the homepage.
   That is exactly what Change of Address validates.
5. **Do not match `api.naijaprep.com.ng`** in that rule. Redirecting the API would break
   CORS and every older app build still calling it. Scope the rule to the two web
   hostnames only.
6. Test before touching Search Console:

   ```powershell
   curl -I https://naijaprep.com.ng/try
   # expect: HTTP/2 301  +  location: https://acelume.ng/try
   curl -I https://api.naijaprep.com.ng/api/health
   # expect: HTTP/2 200  (NOT a redirect)
   ```

7. **Search Console** → add `acelume.ng` as a property (Domain property, verified by TXT
   record) and let it collect data for a few days.
8. Open the **naijaprep.com.ng** property → **Settings → Change of address** → select
   acelume.ng → Google validates the redirects → **Confirm**.

### Gotchas

- Once the redirect is live, `naijaprep.com.ng` no longer serves the site. Confirm Task 2
  has reached your testers first.
- Keep the redirect in place for **at least a year**. Removing it early throws away the
  link equity you just transferred.
- Update the Play Store listing, social profiles, and any printed material to acelume.ng.
  Change of Address handles Google; it does nothing for humans following old links.

---

## Still outstanding from earlier (unrelated to the domain)

- **Rotate the Neon database password.** `.note` in this repo contains the live production
  credential in plaintext and is committed to git history. Rotate in Neon, update
  `DATABASE_URL` in Render, then `git rm --cached .note` and add it to `.gitignore`.
  Rotating is the part that matters — history keeps the old value forever.
- **`AGENTS.md` is an empty stub.** Rebuilding it restores project context for future
  sessions.
- **Hausa strings have never been reviewed by a native speaker** (flagged in AUDIT.md
  Phase 6).
- **~417 `datetime.utcnow()` deprecation warnings** across the backend. Harmless today,
  but it is removed in a future Python and will eventually force the change.
