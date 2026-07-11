# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

- **Language/Framework**: Python 3.14+, Flask web application.
- **Database**: Google Cloud Firestore (using `google-cloud-firestore` and `firebase-admin`).
- **Authentication**: Flask-Login with Google OAuth (using `authlib`).
- **Local Development**:
    - Ensure you have authenticated with GCP: `gcloud auth application-default login`.
    - Use the virtual environment located at `devotions/.venv/`.
    - Activate the environment: `source devotions/.venv/bin/activate` (on Unix) or `devotions\.venv\Scripts\activate` (on Windows).

## Common Development Tasks

- **Run the application**:
    - Use `flask run` from the `devotions/python` directory.
    - For production-like testing, use `gunicorn` as specified in the `Procfile`.
- **Install dependencies**:
    - `pip install -r devotions/requirements.txt`
- **Run tests**:
    - `python -m unittest discover -s devotions/python/tests -t devotions/python`
    - Tests cover the pure, import-light modules (`streak_logic.py`,
      `liturgy.py`, `firebase_auth_logic.py`, `password_hash_logic.py`,
      `reminder_logic.py`, `menu.py`) and run without
      touching Firestore. Keep pure, testable logic out of modules that
      import `firebase`/`google-cloud`.
    - The whole app imports cleanly under Python 3.14 (protobuf is pinned to
      6.x for this — see the comment in `requirements.txt`). For a local
      smoke test without Secret Manager, set dummy env vars for the secrets
      (`secrets_fetcher` reads env first; `FERNET_KEY` must be a valid
      Fernet key) and `import main`.
- **Environment Variables/Secrets**:
    - The app uses `devotions/python/secrets_fetcher.py` to fetch secrets from Google Cloud Secret Manager.
    - For local development, ensure necessary secrets are available or mocked.

## Versioning — increment on every release

- **Android shell**: any PR that touches `mobile/` (native resources,
  manifest, plugins, config) MUST bump `versionCode` in
  `mobile/android/app/build.gradle` in the same PR — assume the previous
  code is already consumed (Play rejects a reused code, and the bump is
  harmless if it wasn't). Bump the human-facing `versionName` alongside it,
  and keep `mobile/package.json`'s `version` in step with `versionName`.
- **Web static assets**: any change to `static/app.js` or `static/styles.css`
  requires bumping its `?v=` query in `base.html` AND the matching entry in
  the offline-download list in `settings.html` — the two must stay in sync or
  offline caching serves stale files. Bump `CACHE_NAME` in `static/sw.js` on
  deploys that change the cached static assets.

## Architecture Overview

- **Core Logic (`devotions/python/`)**:
    - `main.py`: App setup only — config, request hooks, security headers, error handlers. Route handlers live in `routes/` (`auth`, `settings`, `devotions`, `prayers`, `api`, `misc`), each exposing `register(app, **deps)` with plain `@app.route`. Deliberately NOT Flask Blueprints: Blueprints would prefix endpoint names and break the bare `url_for()` calls used throughout the templates.
    - `reminder_logic.py`: Pure, DST-safe "next reminder run" math (Firestore side: `services/reminders.py`).
    - `models.py`: Data models (e.g., `User`).
    - `liturgy.py`: Contains logic for the liturgical year, church seasons, and calculating feast days.
    - `streak_logic.py`: Pure, dependency-free streak/grace-day math (no Firestore imports) so it stays unit-testable.
    - `firebase_auth_logic.py`: Pure, dependency-free logic mapping Firebase Authentication sign-ins onto existing user docs (matching precedence, account-linking rules). Firestore side: `services/users.py` (`handle_firebase_login`); session bridge: `/auth/firebase` in `main.py`. Migration plan and phase status: `docs/firebase-auth-migration.md`.
    - `utils.py`: Shared utility functions (encryption, database access, scripture fetching, etc.).
    - `services/`: Business logic services (e.g., `users.py` for user management, `scripture.py` for ESV API interaction, `reminders.py` for notifications).
    - `devotional_content/`: Logic for generating various devotional types (daily offices, seasonal devotions, Bible in a Year, etc.).
    - `menu.py`: Logic for generating dynamic navigation menus based on the liturgical season.
- **Data (`devotions/data/`)**:
    - Contains JSON files providing the underlying data for devotions (catechism, lectionary, psalms, etc.).
- **Templates (`devotions/templates/`)**:
    - Jinja2 HTML templates for rendering the web interface.
- **Static Assets (`devotions/static/`)**:
    - CSS, JavaScript (including Service Worker for PWA support), and images.

## Key Features & Implementation Details

- **Liturgical Dynamicism**: The application's content (menus, readings, prayers) changes dynamically based on the current date and the liturgical calendar (Advent, Lent, etc.).
- **Personalization**: Users can manage profiles, set timezones, and track "Bible in a Year" progress. Personal prayers are stored in Firestore subcollections.
- **Security**: 
    - Sensitive data like personal prayers are encrypted using `cryptography.fernet` (key managed via `secrets_fetcher.py` / Secret Manager).
    - Email/Password and Google OAuth authentication are implemented; Firebase Authentication is being phased in (see `docs/firebase-auth-migration.md`).
- **PWA Support**: Includes a service worker (`sw.js`) for offline capabilities.
- **Print Mode**: An `@media print` block in `static/styles.css` turns devotion pages into clean handouts (chrome/buttons hidden, ink-friendly colors). The Print button injected in `base.html` asks before including personal prayers; they only print when `body.print-include-personal` is set. Any template markup that renders personal prayers MUST be wrapped in a `personal-prayers-block` element (that class drives both the print hiding and the Print button's prompt). Mark interactive-only template blocks with the `no-print` class.
