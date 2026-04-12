# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Environment

- **Language/Framework**: Python 3.14+, Flask web application.
- **Database**: Google Cloud Firestore (using `google-cloud-firestore` and `firebase-admin`).
- **Authentication**: Flask-Login with Google OAuth (using `authlib`).
- **Local Development**:
    - Ensure you have authenticated with GCP: `gcloud auth application-empty-credentials login`.
    - Use the virtual environment located at `devotions/.venv/`.
    - Activate the environment: `source devotions/.venv/bin/activate` (on Unix) or `devotions\.venv\Scripts\activate` (on Windows).

## Common Development Tasks

- **Run the application**:
    - Use `flask run` from the `devotions/python` directory.
    - For production-like testing, use `gunicorn` as specified in the `Procfile`.
- **Install dependencies**:
    - `pip install -r devotions/requirements.txt`
- **Environment Variables/Secrets**:
    - The app uses `devotions/python/secrets_fetcher.py` to fetch secrets from Google Cloud Secret Manager.
    - For local development, ensure necessary secrets are available or mocked.

## Architecture Overview

- **Core Logic (`devotions/python/`)**:
    - `main.py`: The primary Flask application entry point, containing routes and app configuration.
    - `models.py`: Data models (e.g., `User`).
    - `liturgy.py`: Contains logic for the liturgical year, church seasons, and calculating feast days.
    - `utils.py`: Shared utility functions (encryption, database access, scripture fetching, etc.).
    - `services/`: Business logic services (e.g., `users.py` for user management, `scripture.py` for ESV API interaction, `reminders.py` for notifications).
    - `devotional_content/`: Logic for generating various devotional types (e.ments, Bible in a Year, etc.).
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
    - Sensitive data like personal prayers are encrypted using `cryptography.fernet` (key managed via `secrets_fetch 
    - Email/Password and Google OAuth authentication are implemented.
- **PWA Support**: Includes a service worker (`sw.js`) for offline capabilities.
