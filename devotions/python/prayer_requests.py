"""Functions for interacting with Firestore prayer requests."""

import datetime
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.query import Query


def get_db_client():
  """Initializes and returns a Firestore client."""
  # In a GCP environment (Cloud Run, GAE), the client automatically
  # authenticates using the service account or application default credentials.
  # For local development, ensure you have authenticated via gcloud:
  # `gcloud auth application-default login`
  return firestore.Client(
      project="lcms-prayer-app", database="prayer-app-datastore"
  )


def add_prayer_request(name, request, days_ttl=30):
  """Adds a prayer request to the Firestore database."""
  db = get_db_client()
  collection_ref = db.collection("prayer-requests")
  created_at = datetime.datetime.now(datetime.timezone.utc)
  expires_at = created_at + datetime.timedelta(days=days_ttl)
  collection_ref.add({
      "name": name,
      "request": request,
      "created_at": created_at,
      "expires_at": expires_at,
  })


def get_active_prayer_requests():
  """Returns a list of active prayer requests from Firestore."""
  db = get_db_client()
  now = datetime.datetime.now(datetime.timezone.utc)
  collection_ref = db.collection("prayer-requests")
  # Note: Firestore may require a composite index for this query.
  # If you see an error in logs asking to create an index, follow the link
  # provided in the error message to create it in the Cloud Console.
  query = collection_ref.where(
      filter=FieldFilter("expires_at", ">", now)
  ).order_by("created_at", direction=Query.DESCENDING)
  docs = query.stream()
  return [doc.to_dict() for doc in docs]


def remove_expired_requests():
  """Removes expired prayer requests from the Firestore database."""
  db = get_db_client()
  now = datetime.datetime.now(datetime.timezone.utc)
  collection_ref = db.collection("prayer-requests")
  # Queries for expired docs
  query = collection_ref.where(filter=FieldFilter("expires_at", "<=", now))
  docs_to_delete = list(query.stream())

  if not docs_to_delete:
    return

  batch = db.batch()
  deleted_count = 0
  for doc in docs_to_delete:
    batch.delete(doc.reference)
    deleted_count += 1
    # Firestore batches are limited to 500 operations.
    if deleted_count > 0 and deleted_count % 500 == 0:
      batch.commit()
      batch = db.batch()

  # Commit any remaining deletions in the last batch.
  if deleted_count % 500 > 0:
    batch.commit()

  print(f"Removed {deleted_count} expired prayer requests.")
