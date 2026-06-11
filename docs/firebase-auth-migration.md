# Firebase Authentication Migration

Status tracker and plan for moving authentication from the app's own
session/credential handling onto Firebase Authentication. Originally motivated
by two goals:

1. **Native app shells (Android/iOS).** Google blocks its OAuth pages inside
   embedded webviews, so a native wrapper must sign in via the native Firebase
   SDK and hand the resulting ID token to the backend.
2. **Retiring self-managed password hashes.** The app currently hashes/verifies
   passwords itself (werkzeug) and owns the reset/verification machinery;
   Firebase can take that over.

## Architecture (how the bridge works)

The app stays a server-rendered Flask app with Flask-Login sessions. Firebase
Auth is layered in front as a **session bridge**, not a replacement:

- The client (web button or native shell) signs in through Firebase and gets a
  Firebase **ID token**.
- The client POSTs that token to `POST /auth/firebase`, which verifies it with
  `firebase_admin.auth.verify_id_token` and then calls
  `flask_login.login_user(...)` — the *same* session every legacy flow creates.
- Every existing `@login_required` route keeps working unchanged.

### Identity model (the crux)

Firestore user docs are keyed by document ID, and **all** user data hangs off
it (streaks, favorites, `fcm_tokens`, the encrypted `personal-prayers`
subcollection). Legacy doc IDs are the Google OAuth `sub` (Google users) or a
`uuid4` (email users). Firebase issues its **own `uid`**, which matches neither.

**Existing docs are never re-keyed.** Instead a user doc gains a `firebase_uid`
field the first time its owner signs in through Firebase, and lookups go
through that field. The personal-prayer Fernet key is **app-wide, not
identity-derived**, so changing the identity layer never affects encryption.

Matching precedence (`firebase_auth_logic.resolve_login`):
1. `firebase_uid` — has signed in through Firebase before → **login**.
2. `google_id` — legacy Google account (the Google `sub` is in the token's
   `firebase.identities["google.com"]`) → **link**, then login.
3. **verified** email — legacy email/password account → **link**, then login.
   An **unverified** email collision is **rejected**, never linked (account-
   takeover guard: otherwise anyone could claim an account by creating an
   unverified Firebase user with that email).
4. No match → **create** a new doc (Google-backed identities keep the legacy
   convention of using the Google `sub` as the doc ID).

### Key files

- `devotions/python/firebase_auth_logic.py` — pure, dependency-free decision
  logic (stdlib only, unit-tested like `streak_logic.py`).
- `devotions/python/services/users.py` — `handle_firebase_login()` does the
  Firestore lookups/writes; logs each sign-in action (login/link/create).
- `devotions/python/main.py` — `/auth/firebase` (bridge), `/auth/firebase_config`
  (public web-app config), `/__/auth/*` + `/__/firebase/*` (auth-helper reverse
  proxy for the custom auth domain).
- `devotions/templates/_firebase_signin.html` — progressive-enhancement script
  for the Google buttons (legacy `/login/google` is the fallback on any
  failure).
- `devotions/python/tests/test_firebase_auth_logic.py` — unit tests.

## Rollout strategy

Develop phases on `dev`; stage the **prod** cutover. The phased design exists so
each prod release is independently shippable and (for 1+2) cleanly reversible.

> **Note on environments:** staging uses the **prod env + database** (separate
> instance, shared data). There is **no data firewall** — testing on staging
> writes to real production user docs. For additive phases (1+2) this is safe
> and reversible; for the destructive parts of Phase 3 it means staging gives
> no data-isolation safety, so the deferred-delete + dry-run safeguards below
> are mandatory, not optional.

### Phase 1 — Session bridge — ✅ SHIPPED (PR #28)

Backward-compatible bridge. `/auth/firebase` + `firebase_auth_logic` +
`handle_firebase_login`. Nothing removed; legacy flows untouched. Dormant until
a client calls it.

### Phase 2 — Google sign-in via Firebase — ✅ on `dev` / prod (PRs #29, #30)

- Google buttons sign in through Firebase (popup) and post the token to the
  bridge; legacy `/login/google` is the automatic fallback on any failure.
- `/auth/firebase_config` (public, pre-auth config).
- **Custom auth domain**: `authDomain = asimplewaytopray.com` + `/__/auth`,
  `/__/firebase` reverse proxy, so Google's chooser shows our domain. SW
  excludes `/__/` paths.
- **Observability**: sign-in action logging; admin traffic page shows a
  Firebase column + "N of M migrated" count (the Phase 3 readiness meter).
- Discreet "Trouble signing in? Let us know" link → feedback form (no mention
  of the migration, to avoid alarming users).

**Console prerequisites (one-time, done):** enable Google provider; authorized
domains include staging + prod; OAuth client has
`https://asimplewaytopray.com/__/auth/handler` as a redirect URI and the domain
as a JS origin.

**Bake outcome (✅):** Google sign-ins flowed through the bridge in prod with
no mis-linking — confirmed independently by the Phase 3 audit (zero duplicate
emails across all 87 docs).

### Phase 3 — Email/password via Firebase + migration — ⏳ IN PROGRESS

**Audit tooling:**
- `password_hash_logic.py` (pure, unit-tested) — classifies stored werkzeug
  hashes and accounts; encodes the batch-import rules.
- `scripts/audit_password_hashes.py` — **read-only** audit to run with prod
  credentials: account categories, hash-format buckets, importable-vs-lazy
  split, anomalies (unknown formats, credential-less docs, duplicate emails).
  Run from `devotions/python`: `python scripts/audit_password_hashes.py`.

**Key constraint discovered:** Firebase `importUsers` caps PBKDF2 rounds at
**120,000**. werkzeug's scrypt hashes (3.x default, `scrypt:32768:8:1`) map
cleanly onto STANDARD_SCRYPT, but werkzeug's historical pbkdf2 defaults
(150k/260k/600k/1M rounds) all exceed the cap — those accounts **cannot** be
batch-imported and must use the lazy-migration fallback (verify against the
legacy hash on next login, then create their Firebase user). The audit
quantifies the split; expect newer accounts (scrypt era) to batch-import and
older pbkdf2 accounts to lazy-migrate.

**Audit results (prod, 2026-06):** 87 docs — 45 google-only, 33 password-only,
6 password+google, 3 firebase-linked. **All 41 password hashes are
`scrypt:32768:8:1` → 100% batch-importable; no lazy-migration machinery
needed** (the retained legacy form fallback covers gap accounts). Zero
anomalies, zero duplicate emails. 2 of the 3 firebase-linked docs also hold
passwords — the import skips them (their Firebase accounts already exist;
their passwords stay usable via the legacy form until 3b).

**Import tooling:** `scripts/import_password_users.py` — dry-run by default;
`--uid <doc-id> --execute` for the mandatory canary (import one test account,
verify Firebase sign-in with its known password, THEN bulk `--execute`).
Sets Firebase `uid` = Firestore doc ID, marks emails verified (both legacy
paths guaranteed verification), backfills `firebase_uid` on success, never
touches `password_hash`. werkzeug's scrypt digest was verified to be exactly
standard `scrypt(password, ascii salt, N, r, p, dkLen=64)` by recomputation;
the canary's job is confirming Firebase's STANDARD_SCRYPT parameter
interpretation (memory_cost passed as raw N). Prerequisite: Email/Password
provider enabled, "one account per email" (default) — that setting is also
what makes a later Google sign-in by the same email link onto the imported
account.

Two prod releases.

**Release 3a — migrate + switch (non-destructive) — ✅ code complete, merged
to `dev` (PRs #33, #34); migration executed:**
- **Bulk import executed against prod**: 39/39 imported (Firebase `uid` =
  Firestore doc ID, emails marked verified, `firebase_uid` backfilled); the 2
  firebase-linked password holders correctly skipped.
- **Canary verified end-to-end**: a known-password test account was imported
  with `--uid` and signed in through Firebase's REST API
  (`accounts:signInWithPassword` returned an `idToken`) — proving the
  werkzeug→STANDARD_SCRYPT mapping (memory_cost = raw N) for the whole
  population. The canary account has been deleted.
- Sign-in/register forms call Firebase (`signInWithEmailAndPassword`,
  `createUserWithEmailAndPassword`) and post the token to the bridge
  (`_firebase_email_auth.html`); the legacy form-POST remains the fallback
  and the authority during 3a — wrong password, missing Firebase account
  (gap registrations), or any infrastructure failure falls through to it.
- Password reset + email verification are Firebase's job
  (`sendPasswordResetEmail`, verification links). The legacy behavior is
  preserved: an unverified password-provider sign-in gets **no** session/doc
  (bridge returns `403 email_unverified`; client resends the link) — the
  pure rule is `firebase_auth_logic.needs_email_verification`.
- User-facing messages include spam-folder hints (deliverability is rough
  until the custom sending domain lands — see below).
- **Deferred delete honored:** nothing reads less of `password_hash` yet and
  the field is untouched; linking stays idempotent.

**Release 3a — remaining rollout steps:**
1. Staging smoke test: register (verification email arrives, link works,
   first verified sign-in creates the doc), sign in, forgot-password, and a
   wrong-password attempt (exercises the legacy fallback path).
2. **Email deliverability (in progress):** custom sending domain for Firebase
   auth emails + SPF/DKIM; customize sender name/templates (Firebase console
   → Authentication → Templates) before wide exposure.
3. Deploy `dev` → prod.
4. **Immediately after prod deploy:** re-run
   `python scripts/import_password_users.py --execute` once to sweep
   accounts registered via the legacy form since the bulk import
   (idempotent; already-linked docs are skipped). Until swept, gap accounts
   sign in fine via the fallback, but Firebase-side password reset silently
   no-ops for them.
5. Bake: admin "migrated" count (~42/87 post-import) climbing; logs show
   `login`/`link`, no surprise `create`s; no feedback-form reports.

**Release 3b — delete (after 3a proven in prod) — ⏳ NOT STARTED:**
- Remove the now-dead code:
  - `main.py`: `/login/email`, `/register` POST, `/register/verify`,
    `/forgot_password`, `/reset_password/<token>`, `/settings/update_password`;
    `werkzeug.security` imports.
  - `services/users.py`: `validate_password`, reset-token make/verify,
    reset/verification email senders.
  - Templates: `forgot_password.html`, `reset_password.html`,
    `verify_email.html`, and the password forms in signin/register/settings.
- Optionally drop the `password_hash` field from docs (small migration).

### Phase 4 — Retire legacy Google OAuth — ⏳ PLANNED (later)

Once prod shows the Firebase path handling essentially all sign-ins, remove the
legacy Google OAuth path that Phase 2 keeps as a fallback:
- `main.py`: `/login/google`, `/authorize`, authlib setup, the merge-account
  flow (`/login/merge`, `/login/merge/confirm`).
- `templates/merge_account.html`; the progressive-enhancement fallback in
  `_firebase_signin.html` becomes the only path.

**Permanent (never removed):** Flask-Login, the `/auth/firebase` bridge, and
`firebase_auth_logic` — this is the architecture now, not legacy.

## Open considerations

- **Email deliverability (in progress):** Firebase auth emails currently tend
  to land in spam. Custom sending domain + SPF/DKIM being set up; UI shows
  spam-folder hints in the meantime.
- **Sign in with Apple** will be required when the iOS app ships with Google
  sign-in (see `docs/native-apps.md`). The bridge handles any Firebase
  provider, but review `firebase_auth_logic` matching first: Apple's
  email-relay addresses won't match existing doc emails.
- **Native shell wiring** (Capacitor `@capacitor-firebase/authentication`) is
  downstream of these phases and out of scope here.

*(Resolved: hash-format question — audit showed 100% `scrypt:32768:8:1`, all
batch-importable; mapping proven by canary.)*
