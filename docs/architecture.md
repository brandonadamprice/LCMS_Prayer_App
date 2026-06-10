# Architecture Overview

A server-rendered Flask application: routes render Jinja2 templates, sessions
are Flask-Login cookies, and all state lives in Google Cloud Firestore. There
is no separate frontend/API split — small `fetch` calls from inline template
JS hit JSON endpoints on the same app.

## Module map (`devotions/python/`)

| Module | Responsibility |
|---|---|
| `main.py` | All routes, app config, login manager, before/after-request hooks (request logging, domain redirect, last-seen tracking, static cache headers) |
| `models.py` | `User` (Flask-Login `UserMixin`), loaded from the `users` collection; computes active streaks on load |
| `liturgy.py` | Church-year math: seasons, movable feasts (pure; unit-tested) |
| `streak_logic.py` | Streak/grace-day date math (pure; unit-tested) |
| `firebase_auth_logic.py` | Maps Firebase sign-ins onto user docs (pure; unit-tested) — see [firebase-auth-migration.md](firebase-auth-migration.md) |
| `utils.py` | Firestore client, Fernet encryption helpers, scripture fetching, timezone helpers |
| `menu.py` | Seasonal navigation menus (Advent/Lent/New Year variants) |
| `communication.py` | Email (SMTP), SMS (Twilio), push (FCM via `firebase_admin`, initialized at import) |
| `secrets_fetcher.py` | All secrets via Google Cloud Secret Manager |
| `services/users.py` | User lifecycle: OAuth/Firebase login handling, registration helpers, streak/achievement transactions |
| `services/reminders.py` | Scheduled reminder delivery (collection-group query over user reminder subcollections) |
| `services/prayer_requests.py` | Prayer wall / request management |
| `services/scripture.py` | ESV API |
| `services/analytics_ga4.py` | GA4 stats for the admin traffic page |
| `services/fullofeyes_scraper.py` | Background art sourcing |
| `devotional_content/*` | One module per devotion type; reads JSON from `devotions/data/` |

## Authentication

Three coexisting paths, all ending in the same Flask-Login session
(`flask_login.login_user`). Full design, identity model, and phase status:
[firebase-auth-migration.md](firebase-auth-migration.md).

1. **Firebase Authentication** (target architecture): client signs in via the
   Firebase SDK, POSTs the ID token to `/auth/firebase`, which verifies it and
   logs the user in. Google sign-in buttons use this path with the legacy flow
   as automatic fallback. Auth helper pages are reverse-proxied under `/__/`
   so the OAuth chooser shows our domain.
2. **Legacy Google OAuth** (authlib): `/login/google` → `/authorize`. Kept as
   the no-JS/outage fallback until Phase 4.
3. **Legacy email/password** (werkzeug hashes on the user doc): `/login/email`,
   `/register` + verification, `/forgot_password`. Scheduled for replacement in
   Phase 3.

## Data model (Firestore)

- **`users/{id}`** — the central collection; everything keys off the doc ID.
  Legacy IDs are the Google OAuth `sub` (Google users) or a `uuid4` (email
  users); Firebase sign-ins link via a `firebase_uid` field rather than
  re-keying. Holds profile, preferences, streak state, achievements,
  `fcm_tokens`, favorites, completed devotions/readings.
- **`users/{id}/personal-prayers`** — private prayers, `text`/`for_whom`
  encrypted with an **app-wide** Fernet key (from Secret Manager, *not*
  identity-derived — auth changes never affect decryption).
- **Reminders** live in user subcollections and are queried across users with
  a collection-group query.
- Streak/achievement updates run in **Firestore transactions**
  (`services/users.py`) to keep counts consistent.

## Liturgical dynamicism

`inject_globals` (context processor) computes the current season (Advent,
Lent via church-year math, New Year) per-request in the user's timezone and
feeds `menu.get_menu_items`, so navigation and content shift with the church
calendar automatically.

## PWA / service worker (`static/sw.js`)

- **Navigations**: network-first, falling back to cache offline (users get
  fresh daily content when online).
- **Same-origin assets**: cache-first; refreshed by bumping `CACHE_NAME` on
  deploy (and `styles.css` via its `?v=` query string).
- **Never intercepted**: non-GET requests, cross-origin requests, `/login*`,
  `/authorize*`, and `/__/*` (proxied Firebase auth helper).
- **Push**: FCM messages → notifications; clicks focus/navigate an existing
  window when possible. `/sw.js` is served `no-cache` so worker updates ship
  promptly.

## Testing philosophy

Unit tests (`devotions/python/tests/`) are stdlib-only and target the pure
modules: `liturgy.py`, `streak_logic.py`, `firebase_auth_logic.py`. The
Firestore/protobuf stack fails to import under newer local Python versions
(see pinning notes in `requirements.txt`), so the rule is: **keep pure,
testable logic out of any module that imports `firebase`/`google-cloud`**, and
put orchestration (lookups/writes) in thin service-layer functions around it.

## Observability

- Every request is logged (`log_request_info`).
- Firebase sign-ins log their resolver action (`login`/`link`/`create`) with
  user id and provider; unverified-email rejections log warnings. A surprise
  `create` for a known email is the mis-linking canary.
- `/admin/traffic` (admin-only): GA4 stats, registered users (with Firebase
  migration status), active streaks.
- In production, Flask/root loggers are wired to gunicorn's handlers.
