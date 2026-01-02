"""Fetches secrets from environment variables or Google Cloud Secret Manager."""

import os
from google.cloud import secretmanager

PROJECT_ID = "978583660884"
_SECRET_VERSION = "1"


def _get_secret(secret_name, environment_variable, version=_SECRET_VERSION):
  """Fetches a secret from environment variables or Google Cloud Secret Manager."""
  if os.getenv(environment_variable) is not None:
    return os.getenv(environment_variable)
  try:
    secret_id = (
        f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/{version}"
    )
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(name=secret_id)
    return response.payload.data.decode("UTF-8")
  except Exception as e:
    print(f"Failed to fetch secret: {secret_name} - Error: {e}")
    raise RuntimeError(f"Could not fetch secret {secret_name}") from e


def get_esv_api_key():
  """Fetches the ESV API key."""
  return _get_secret("ESV_API_KEY", "ESV_API_KEY")


def get_google_client_id():
  """Fetches the Google OAuth Client ID."""
  return _get_secret("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID")


def get_google_client_secret():
  """Fetches the Google OAuth Client Secret."""
  return _get_secret("GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET")


def get_flask_secret_key():
  """Fetches the Flask SECRET_KEY for session signing."""
  return _get_secret("FLASK_SECRET_KEY", "FLASK_SECRET_KEY")


def get_fernet_key():
  """Fetches the Fernet encryption key."""
  return _get_secret("FERNET_KEY", "FERNET_KEY")


def get_brandon_user_id():
  """Fetches BRANDON_USER_ID."""
  return _get_secret("BRANDON_USER_ID", "BRANDON_USER_ID")


def get_firebase_api_key():
  """Fetches the Firebase API Key."""
  return _get_secret("FIREBASE_API_KEY", "FIREBASE_API_KEY")


def get_firebase_messaging_sender_id():
  """Fetches the Firebase Messaging Sender ID."""
  return _get_secret("FIREBASE_MESSAGING_SENDER_ID", "FIREBASE_MESSAGING_SENDER_ID")


def get_firebase_app_id():
  """Fetches the Firebase App ID."""
  return _get_secret("FIREBASE_APP_ID", "FIREBASE_APP_ID")


def get_firebase_vapid_key():
  """Fetches the Firebase VAPID Key."""
  return _get_secret("FIREBASE_VAPID_KEY", "FIREBASE_VAPID_KEY")


def get_facebook_client_id():
  """Fetches the Facebook App ID."""
  return _get_secret("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_ID")


def get_facebook_client_secret():
  """Fetches the Facebook App Secret."""
  return _get_secret("FACEBOOK_CLIENT_SECRET", "FACEBOOK_CLIENT_SECRET")



