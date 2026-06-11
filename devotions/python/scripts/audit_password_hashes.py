"""READ-ONLY audit of user credentials for Firebase Auth migration Phase 3a.

Reports, without writing anything:
  - account categories (firebase-linked / password-only / google-only / both /
    no credentials at all)
  - password hash formats and whether each is batch-importable into Firebase
    Auth via importUsers (see password_hash_logic.py for the rules)
  - anomalies worth eyeballing before the migration: unknown hash formats,
    docs with no credentials, duplicate emails (the mis-linking canary)

Run from devotions/python with GCP application-default credentials available
(the same setup `flask run` uses):

    python scripts/audit_password_hashes.py [--limit N] [--show-emails]

This script performs Firestore READS ONLY -- it never writes. It uses a
field-projection query, so document data beyond the audited fields (including
encrypted personal prayers, which live in subcollections anyway) is never
even transferred.
"""

import argparse
import collections
import os
import sys

# Allow running as `python scripts/audit_password_hashes.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import password_hash_logic  # pylint: disable=wrong-import-position
import utils  # pylint: disable=wrong-import-position

_AUDITED_FIELDS = ["password_hash", "google_id", "firebase_uid", "email"]


def run_audit(limit=None, show_emails=False):
  """Streams the users collection (projected fields only) and prints a report."""
  db = utils.get_db_client()
  query = db.collection("users").select(_AUDITED_FIELDS)
  if limit:
    query = query.limit(limit)

  total = 0
  categories = collections.Counter()
  hash_buckets = collections.Counter()
  email_to_doc_ids = collections.defaultdict(list)
  unknown_hash_docs = []
  no_credential_docs = []

  for doc in query.stream():
    total += 1
    fields = doc.to_dict() or {}

    category = password_hash_logic.classify_account(fields)
    categories[category] += 1
    if category == password_hash_logic.ACCOUNT_NO_CREDENTIALS:
      no_credential_docs.append(doc.id)

    if fields.get("password_hash"):
      info = password_hash_logic.classify_hash(fields["password_hash"])
      hash_buckets[info.bucket] += 1
      if info.scheme == password_hash_logic.SCHEME_UNKNOWN:
        unknown_hash_docs.append(doc.id)

    email = (fields.get("email") or "").strip().lower()
    if email:
      email_to_doc_ids[email].append(doc.id)

  duplicate_emails = {
      email: ids for email, ids in email_to_doc_ids.items() if len(ids) > 1
  }

  print(f"\n=== User credential audit ({total} docs) ===\n")

  print("Account categories:")
  for category, count in categories.most_common():
    print(f"  {category:25s} {count}")

  print("\nPassword hash formats (password holders only):")
  if not hash_buckets:
    print("  (none)")
  for bucket, count in hash_buckets.most_common():
    print(f"  {count:5d}  {bucket}")

  importable = sum(
      c for b, c in hash_buckets.items() if "[importable]" in b
  )
  total_hashes = sum(hash_buckets.values())
  print(
      f"\nBatch-importable into Firebase Auth: {importable}/{total_hashes}"
      " password hashes"
  )
  if total_hashes - importable:
    print(
        f"  -> {total_hashes - importable} will need the lazy-migration"
        " fallback (legacy verify on next login)."
    )

  print("\nAnomalies:")
  print(f"  docs with unknown hash format: {len(unknown_hash_docs)}")
  for doc_id in unknown_hash_docs:
    print(f"    {doc_id}")
  print(f"  docs with no credentials at all: {len(no_credential_docs)}")
  for doc_id in no_credential_docs:
    print(f"    {doc_id}")
  print(f"  duplicate emails: {len(duplicate_emails)}")
  for email, ids in sorted(duplicate_emails.items()):
    shown = email if show_emails else "(hidden; rerun with --show-emails)"
    print(f"    {shown}: {ids}")


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "--limit", type=int, default=None,
      help="audit only the first N docs (quick sample run)",
  )
  parser.add_argument(
      "--show-emails", action="store_true",
      help="print the actual addresses for duplicate emails",
  )
  args = parser.parse_args()
  run_audit(limit=args.limit, show_emails=args.show_emails)


if __name__ == "__main__":
  main()
