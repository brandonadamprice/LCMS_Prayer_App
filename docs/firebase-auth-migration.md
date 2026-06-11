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

**Bake before Phase 3:** watch the "N of M migrated" count climb and the logs
show `link`/`login` (not surprise `create`s, which would indicate mis-linking).

### Phase 3 — Email/password via Firebase + migration — ⏳ IN PROGRESS

**Done so far:**
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

Two prod releases.

**Release 3a — migrate + switch (non-destructive):**
- Sign-in/register forms call Firebase (`signInWithEmailAndPassword`,
  `createUserWithEmailAndPassword`) and post the token to the bridge; legacy
  form-POST stays as fallback during transition.
- **Migrate existing password users into Firebase Auth.** First a *read-only*
  check of the hash format in real docs (werkzeug = `pbkdf2:sha256` or
  `scrypt`, both accepted by Firebase `importUsers`). Then a **dry-run-first
  backfill script** that imports password users, **setting the Firebase `uid`
  to the existing Firestore doc ID** so `firebase_uid` matching is exact for
  everyone (no email-matching needed). Users keep their passwords; no resets.
  Prefer this auditable batch over implicit lazy migration, since staging
  shares the prod DB.
- Password reset + email verification become Firebase's job
  (`sendPasswordResetEmail`, verification emails). Preserve current behavior:
  an unverified password-provider sign-in gets **no** session/doc until
  verified (mirrors today's `/register/verify` gate). Reset/verification emails
  will come from Firebase templates (customizable in console).
- **Deferred delete:** stop *reading* `password_hash` but **leave the field in
  Firestore** as an escape hatch. Keep linking idempotent/guarded (only write
  `firebase_uid` if absent; never touch an unmatched doc).

**Release 3b — delete (after 3a proven in prod):**
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

- **Hash format confirmation** for Phase 3 (read-only) decides batch-import vs.
  lazy migration parameters.
- **Email deliverability** for Firebase auth emails (sender domain / DNS) if we
  want them to match the current SMTP sender.
- **Native shell wiring** (Capacitor `@capacitor-firebase/authentication`) is
  downstream of these phases and out of scope here.
