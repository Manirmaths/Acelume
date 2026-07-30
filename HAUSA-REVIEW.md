# Hausa translation review — `frontend/src/i18n/translations.ts`

Reviewed 2026-07-30. Covers all 27 Hausa strings in the Phase 6 first increment.

## ✅ RESOLVED (2026-07-30)

**All findings in this document have been addressed.** The triage pass below was reviewed by
a native Hausa speaker (the project owner), who supplied revised strings. Those are now live
in `frontend/src/i18n/translations.ts`, and the conventions they establish are documented in
that file's header comment so they survive future edits.

What the native revision settled:

- **Gender** → plural/polite `ku` form throughout (`Burin ku`, `muku`, `ci gabanku`,
  `ɗinku`), with impersonal constructions where person can be dropped entirely
  (`An manta da password?`, `An sa wa alamar bita`).
- **Hooked letters** → applied (`ɗaliban`, `buƙatar`, `kaɗan`, `ɗinku`).
- **`nav.mock`** → `Cikakkiyar jarrabawar gwaji (Mock)`, correcting the feminine agreement.
- **"Subject"** → standardised on `darussa`.
- **Hero tagline** → now tracks the English: `Burin ku.` / `Ya kusa cika.` ("Your ambition. /
  It is nearly fulfilled."), replacing the earlier reinterpretation.
- **`na baka`** → `yana samar muku da`.
- **Word choices** → `Jerin Matsayi` for Leaderboard; `Flashcards` and `Password` kept in
  English as established loanwords; `bita mai tazarar lokaci` replaced with the clearer
  `bitar da ake maimaitawa a kan tazara`.

The document below is retained as a record of what was wrong and why, and as a checklist for
reviewing any future additions to the Hausa strings.

---

**Original status note.** This is a triage pass, not a native-speaker sign-off. The
orthographic and grammatical-agreement findings below are high confidence and mechanical.
The idiom and word-choice notes are lower confidence — flag them for a native speaker
rather than acting on them blind. The goal is to make a native review faster and cheaper by
pre-identifying what to look at.

---

## High confidence — should be fixed

### 1. Hooked letters are missing throughout (affects ~8 strings)

Standard Hausa Boko orthography uses the hooked consonants **ɓ, ɗ, ƙ, ƴ**. These are
distinct letters, not decorative accents — substituting `b`/`d`/`k` changes or breaks the
word. Every affected string currently uses the plain ASCII form:

| Current | Should be | Word |
|---|---|---|
| `Bude asusu` | `Buɗe asusu` | buɗe = open |
| `bude asusu` (home.noCard) | `buɗe asusu` | " |
| `Ba a bukatar` | `Ba a buƙatar` | buƙata = need |
| `daliban Najeriya` | `ɗaliban Najeriya` | ɗalibai = students |

This is the most visible issue to a Hausa reader — comparable to writing English without
the letter "h". It is also purely mechanical to fix.

Check rendering after fixing: the app's font stack must support these glyphs. Plus Jakarta
Sans and Inter both cover Latin Extended-B, so this should be fine, but verify in-browser
rather than assuming.

### 2. Gender agreement — the entire Hausa UI addresses users as male

Hausa second-person singular is gendered: **ka** (masculine) vs **ki** (feminine). The
current strings consistently use masculine forms:

| String | Masculine form used |
|---|---|
| `home.heroSubtitle` | `na baka` (to you, m.), `ci gabanka` (your progress, m.) |
| `home.ctaDashboard` | `dashboard naka` (your dashboard, m.) |
| `auth.forgotPassword` | `Ka manta` (you forgot, m.) |

Roughly half of JAMB/WAEC candidates are female, so this reads as excluding them. The
English source is genderless, so this is introduced entirely by the translation.

Two standard ways out — a native speaker should pick:

- **Plural/polite `ku`/`naku`/`kun`** — addresses everyone, slightly formal. e.g.
  `Kun manta da kalmar sirri?`
- **Impersonal construction** — e.g. `An manta da kalmar sirri?` ("has the password been
  forgotten?"), sidestepping person entirely. Common in Hausa UI and signage.

### 3. Adjective agreement error — `nav.mock`

`jarrabawa` (exam) is a **feminine** noun. The codebase itself gets this right in one place
and wrong in another:

- `home.heroSubtitle`: `cikakkiyar jarrabawar JAMB` ✅ feminine agreement
- `nav.mock`: `Cikakken Jarrabawa` ❌ masculine agreement

`nav.mock` should be **`Cikakkiyar Jarrabawa`**.

### 4. Terminology inconsistency — "subject"

Two different words are used for the same concept:

- `nav.subjects`: **`Darussa`** (lessons)
- `home.heroSubtitle`: **`fanni`** (field/discipline)

Both are defensible for school subjects; using both is not. Pick one and apply it
consistently. Worth deciding deliberately, since it will propagate as coverage expands.

---

## Lower confidence — worth a native speaker's opinion

### 5. The hero tagline is a reinterpretation, not a translation

| | |
|---|---|
| **EN** | "Your ambition. / Within reach." |
| **HA** | `Yi karatu da hikima.` / `Shiga jarrabawa a shirye.` |
| **Back-translates to** | "Study with wisdom. / Enter the exam prepared." |

This is a different message — instructional rather than aspirational. It may well be a
deliberate localisation choice (a literal rendering of "within reach" often falls flat), but
it is your brand tagline, and it currently says something else in Hausa. Confirm this was
intentional.

### 6. `na baka` — likely grammatically loose

`Acelume na baka atisaye` compresses what would more standardly be `Acelume yana ba ka
atisaye`. The current form reads as informal/spoken. Fine if that register is intended;
worth confirming for marketing copy.

### 7. Word choices to sanity-check

| Key | Hausa | Note |
|---|---|---|
| `nav.flashcards` | `Katunan Tunani` | lit. "cards of thought". `Katunan karatu` may be more natural. |
| `nav.review` | `Alamun Bita` | lit. "marks of review". Understandable but possibly opaque as a nav label. |
| `nav.leaderboard` | `Jerin Gasa` | lit. "competition list". Reads fine. |
| `home.noCard` | `samfur` | `samfuri` is the more standard form for "sample". |
| `home.noCard` | `koda yaushe` | for "ever". `kullum` may read more naturally. |
| `home.heroSubtitle` | `bita mai tazarar lokaci` | a coinage for "spaced repetition". No standard Hausa term exists; verify it is comprehensible to students. |

### 8. Untranslated strings — probably correct, worth confirming

`Dashboard`, `Blitz`, `Admin`, and the `JAMB · WAEC · NECO · Post-UTME` badge are left in
English. For a Nigerian student audience these are likely recognised as-is, and `nav.admin`
is staff-only. Flagging only so the decision is explicit rather than accidental.

---

## Suggested process

1. Apply findings 1–4 (mechanical, low risk) — these need no linguistic judgement beyond
   picking the gender-neutral strategy in #2.
2. Send the file to a native Hausa speaker, ideally one familiar with Nigerian secondary
   education, with items 5–7 as specific questions. Reviewing 27 strings against a
   pre-flagged list is maybe 30 minutes of their time.
3. Only expand Hausa coverage beyond these 27 strings after that review — otherwise the
   same systematic errors (hooked letters, gendered address) propagate across the app and
   get much more expensive to unwind.

Until step 2 is done, the warning at the top of `translations.ts` should stay exactly where
it is.
