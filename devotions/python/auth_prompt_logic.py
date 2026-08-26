"""Pure logic for the "you need an account" prompt.

Flask-Login's default `unauthorized` handler calls `abort(401)`, which serves
Werkzeug's bare "The server could not verify that you are authorized" page.
Every `@login_required` route showed that to signed-out visitors -- including
ones the nav menu links to, like "Prayer -> Submit Request".

Two decisions are needed to replace it with something friendly, and both are
pure string/header math, so they live here (no Flask import) and are unit
tested:

  * `wants_json_response` -- is this a page navigation (redirect the browser to
    the sign-in page) or a script's fetch/XHR (answer with JSON the caller can
    act on)?
  * `safe_next_url` -- where should sign-in send them afterwards, without
    becoming an open redirect?
"""

LOGIN_REQUIRED_CODE = "login_required"

LOGIN_REQUIRED_MESSAGE = (
    "You need a free account to use this feature. Sign in or create one to"
    " continue."
)

# Session key holding the page a signed-out visitor was trying to reach.
NEXT_URL_SESSION_KEY = "next_url"


def wants_json_response(
    path="",
    accept="",
    requested_with="",
    sec_fetch_mode="",
    sec_fetch_dest="",
    content_type="",
):
  """Returns True when the caller is a script rather than a page navigation.

  A redirect is right for a browser following a link, and wrong for `fetch()`
  -- the fetch would silently follow it and hand the caller a login *page*
  where it expected JSON. The signals, in order:

    * an `/api/` path -- this app's JSON namespace;
    * `X-Requested-With: XMLHttpRequest`, the classic XHR marker;
    * a JSON request body, which no browser navigation sends;
    * `Sec-Fetch-Mode: navigate` or an `Accept` that asks for HTML -- either
      one means a page, so the visitor gets the redirect;
    * an `Accept` naming JSON;
    * `Sec-Fetch-Dest`, as a last resort.

  Order matters because of the service worker. When sw.js re-issues a
  navigation through `fetch(event.request)`, the browser keeps `Accept:
  text/html` and `Sec-Fetch-Mode: navigate` but rewrites `Sec-Fetch-Dest` from
  `document` to `empty`. Trusting Dest first therefore answered navigations
  from returning visitors -- the ones who have the worker installed -- with
  raw JSON rendered as the page. Dest is only consulted when nothing better
  is available.
  """
  if (path or "").startswith("/api/"):
    return True

  if (requested_with or "").lower() == "xmlhttprequest":
    return True

  if "application/json" in (content_type or "").lower():
    return True

  if (sec_fetch_mode or "").strip().lower() == "navigate":
    return False

  accept = (accept or "").lower()
  if "text/html" in accept:
    return False
  if "application/json" in accept:
    return True

  dest = (sec_fetch_dest or "").strip().lower()
  return bool(dest) and dest != "document"


def safe_next_url(target, default="/"):
  """Returns `target` if it is a safe same-site path, else `default`.

  Only root-relative paths are allowed. `//evil.example` and
  `https://evil.example` are rejected (protocol-relative URLs are how an open
  redirect usually sneaks in), as are backslashes -- some browsers normalize
  `/\\evil.example` to a protocol-relative URL -- and any control characters,
  which can be used to split the eventual Location header.
  """
  if not target or not isinstance(target, str):
    return default

  target = target.strip()
  if not target.startswith("/"):
    return default
  if target.startswith("//") or target.startswith("/\\"):
    return default
  if any(ch in target for ch in "\r\n\t") or any(ord(ch) < 32 for ch in target):
    return default

  return target


def should_remember_next(path, method="GET"):
  """Returns True when `path` is worth returning the visitor to after sign-in.

  Only GET pages: re-running a POST after sign-in would replay an action the
  visitor never confirmed. Auth pages themselves are skipped so sign-in doesn't
  bounce back to sign-in.
  """
  if (method or "GET").upper() != "GET":
    return False

  path = path or ""
  # Exact match or a path segment below it, so "/login/google" is skipped but
  # a page merely starting with those letters is not.
  skipped = ("/login", "/register", "/logout", "/authorize", "/auth")
  return not any(path == s or path.startswith(s + "/") for s in skipped)
