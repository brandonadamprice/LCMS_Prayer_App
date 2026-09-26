# A Simple Way to Pray

A web app for daily prayer, Scripture reading, and reflection on the Small
Catechism, following LCMS (Lutheran Church—Missouri Synod) tradition. Live at
[asimplewaytopray.com](https://asimplewaytopray.com). A part of Hallowed
Gains LLC.

## Features

- **Daily offices** — Morning, Midday, Evening, Close of Day, and Night Watch
  devotions, plus seasonal devotions (Advent, Lent, New Year, mid-week) and a
  children's devotion.
- **Liturgically dynamic** — menus, readings, and prayers change with the
  church year (calculated feast days, seasons, lectionary).
- **Bible in a Year** — reading plan with progress tracking.
- **Streaks & grace days** — daily prayer/reading streaks with achievements;
  a missed day can be bridged by grace (deliberately gospel, not law).
- **Prayer wall & requests** — submit requests, pray for others, mark praise
  reports.
- **Personal prayers** — private prayer lists, encrypted at rest.
- **Print mode** — devotion pages print as clean handouts for praying in a
  group; personal prayers stay off the printout unless explicitly included.
- **Bible family tree** — interactive D3 tree from Adam to Jesus with the
  Messianic line highlighted, the women of the family shown beside their
  husbands, and Mary's own descent from David traced through Nathan to her
  father Heli (Luke 3).
- **Memory work** — memory verses, catechism memorization, creed studies.
- **Reminders** — push (FCM), email, and SMS (Twilio) notifications.
- **PWA** — installable, offline-capable (service worker), with home-screen
  shortcuts.
- **Personalization** — timezones, dark mode, font size, favorites,
  background art (Full of Eyes), optional hiding of the catechism card in
  devotions (applies to web, print, and emailed versions).

## Tech stack

| Concern | Choice |
|---|---|
| Web framework | Flask (server-rendered Jinja2), gunicorn |
| Database | Google Cloud Firestore |
| Authentication | Firebase Authentication (migration in progress — see [docs/firebase-auth-migration.md](docs/firebase-auth-migration.md)) alongside legacy Google OAuth (authlib) and email/password; Flask-Login sessions |
| Push notifications | Firebase Cloud Messaging |
| Email / SMS | SMTP / Twilio |
| Secrets | Google Cloud Secret Manager (`secrets_fetcher.py`) |
| Encryption | `cryptography.fernet` for personal prayers (app-wide key) |
| Scripture text | ESV API |
| Analytics | Google Analytics 4 (+ admin traffic dashboard) |

## Repository layout

```
devotions/
  python/              # Flask app
    main.py            # Routes and app configuration (entry point)
    models.py          # User model (Flask-Login)
    liturgy.py         # Church-year math (pure, unit-tested)
    streak_logic.py    # Streak/grace-day math (pure, unit-tested)
    firebase_auth_logic.py  # Firebase sign-in mapping (pure, unit-tested)
    utils.py           # Shared helpers (db client, encryption, scripture)
    menu.py            # Seasonal navigation menus
    communication.py   # Email/SMS/push senders
    secrets_fetcher.py # Secret Manager access
    services/          # Business logic (users, reminders, prayer requests, ...)
    devotional_content/# Generators for each devotion type
    tests/             # Unit tests (stdlib-only; no Firestore imports)
  data/                # JSON content (lectionary, catechism, psalms, ...)
  templates/           # Jinja2 templates
  static/              # CSS, icons, manifest.json, sw.js (PWA)
  requirements.txt
  Procfile             # gunicorn entry (also see Dockerfile)
mobile/                # Capacitor native shell (android/ + ios/) wrapping the live site
docs/                  # Architecture, migration plans, native-app notes
CLAUDE.md              # Working notes for AI-assisted development
```

## Local development

```bash
# One-time: GCP credentials for Firestore/Secret Manager
gcloud auth application-default login

# Virtual environment lives at devotions/.venv
source devotions/.venv/bin/activate
pip install -r devotions/requirements.txt

# Run the app
cd devotions/python
flask run
```

## Tests

```bash
python -m unittest discover -s devotions/python/tests -t devotions/python
```

Tests are deliberately **stdlib-only** and cover the pure modules
(`liturgy.py`, `streak_logic.py`, `firebase_auth_logic.py`). Keep pure,
testable logic out of modules that import `firebase`/`google-cloud` — that
stack does not import under newer local Python versions (see the protobuf
pinning notes in `requirements.txt`), and the tests must run without it.

## Deployment

The app ships as a container (see `Dockerfile`: `python:3.11-slim`, gunicorn
on `:8080`) on two Cloud Run services, deployed by GitHub Actions. This is the
release pattern shared by every Hallowed Gains web app:

| Step | Workflow | Lands on |
|---|---|---|
| Merge / push to `main` | [`deploy.yml`](.github/workflows/deploy.yml) ("Deploy staging") | staging.asimplewaytopray.com |
| Actions → **Deploy production** → Branch `main` → type `DEPLOY` | [`deploy-prod.yml`](.github/workflows/deploy-prod.yml) | asimplewaytopray.com |

Flow: feature branch → PR (unit tests via [`ci.yml`](.github/workflows/ci.yml))
→ `main` → staging → manual production release. The `dev` branch is retired.

> **Note:** staging runs against the **production** environment and database —
> it is a separate instance for verifying deploys, not a data sandbox.

Both deploy workflows re-run the unit tests, then call
[`.github/actions/deploy-cloud-run`](.github/actions/deploy-cloud-run/action.yml):
`gcloud run deploy <service> --source .`, which builds the `Dockerfile` in
Cloud Build (upload context trimmed by `.gcloudignore`) and rolls the service
onto the new image. **Only the image changes** — env vars, secrets, the runtime
service account, scaling and domain mappings stay as configured on each
service, so manage those in the Cloud Run console (or `gcloud run services
update`), not in the workflows. Each deploy labels the service
`commit-sha=<sha>`.

Production guards: `workflow_dispatch` only, refuses any ref but `main`, typed
`DEPLOY` confirmation (read via `env:`), never cancelled mid-flight. Staging
deploys queue rather than cancel, because cancelling a job does not cancel the
Cloud Build it started.

### One-time setup

1. **Disable the old Cloud Build triggers** (GCP console → Cloud Build →
   Triggers: the `dev` → staging and `main` → prod ones). Until they are off,
   every merge to `main` still releases production automatically.
2. **Deployer service account** in the app's project with:
   `roles/run.developer`, `roles/iam.serviceAccountUser` (on the services'
   runtime service account), `roles/cloudbuild.builds.editor`,
   `roles/artifactregistry.writer` (the first source deploy creates the
   `cloud-run-source-deploy` repository — grant `artifactregistry.admin`
   instead if it doesn't exist yet), `roles/storage.admin` (source upload
   bucket) and `roles/serviceusage.serviceUsageConsumer`. Create a JSON key.
3. **Repo settings → Secrets and variables → Actions:**
   - Secret `GCP_DEPLOY_SA_JSON` — the key JSON.
   - Variables `GCP_PROJECT_ID`, `CLOUD_RUN_REGION`,
     `CLOUD_RUN_SERVICE_STAGING`, `CLOUD_RUN_SERVICE_PROD` — as shown on the
     Cloud Run services page.

   A deploy with any of these missing fails immediately and names what is
   missing.
4. Delete the `dev` branch once nothing depends on it.

## Documentation

- [Architecture overview](docs/architecture.md)
- [Firebase Auth migration plan](docs/firebase-auth-migration.md) (phases, status)
- [Native app (Android/iOS) plan](docs/native-apps.md)
- [Android build & ship checklist](docs/capacitor-android.md)
- [iOS build & ship checklist](docs/capacitor-ios.md) (shared build server: [ios-build-server.md](docs/ios-build-server.md); Apple process playbook: [apple-release-playbook.md](docs/apple-release-playbook.md))
