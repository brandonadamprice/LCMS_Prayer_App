"""Fetches secrets from environment variables or Google Cloud Secret Manager."""

import os
from google.cloud import secretmanager

PROJECT_ID = "978583660884"
SECRET_NAME = "ESV_API_KEY"
SECRET_VERSION = "1"


def get_esv_api_key():
  """Fetches the ESV API key from the secrets manager."""
  if os.getenv("ESV_API_KEY") is not None:
    return os.getenv("ESV_API_KEY")
  secret_id = f"projects/{PROJECT_ID}/secrets/{SECRET_NAME}/versions/{SECRET_VERSION}"
  secret_manager = secretmanager.SecretManagerServiceClient()
  response = secret_manager.access_secret_version(name=secret_id)
  return response.payload.data.decode("UTF-8")
