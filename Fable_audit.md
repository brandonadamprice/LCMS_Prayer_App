# Fable Audit — LCMS Prayer App

> **🗑️ DELETE THIS FILE when every checklist item below is either done or
> consciously declined.** It's a working scratchpad, not permanent docs. Once the
> work is complete (or triaged into issues/commits), remove `Fable_audit.md` from
> the repo.

_Audit date: 2026-06-12. Auditor: Claude (Fable 5). Scope: full codebase under
`devotions/` (excluding `.venv`)._

---

## TL;DR

The codebase is **in good shape** — solid fundamentals: per-user authorization
checks on owned resources, Fernet-encrypted personal prayers, secrets pulled from
Google Secret Manager (nothing hardcoded), Firebase ID-token verification,
`ProxyFix`, a smart service-worker caching strategy, and thorough dark mode. This
is not a rescue job.

The improvements worth making cluster into: a handful of **real security gaps**, a
few **cheap performance wins**, one **structural lever** (the 2,413-line
`main.py`), and some **accessibility polish**.

**Two findings from the initial sweep were verified to be FALSE/overstated and are
NOT in the checklist** — see [Corrections](#corrections-do-not-chase-these) so we
don't waste effort on them.

---

## Priority checklist

Recommended batching:
- **Batch A (one PR off `dev`)** — small, independent, low-risk: items 1, 5, 6, 7,
  8, 9, 10, 11, 12.
- **Separate focused changes** — behavioral risk: items 2, 3, 4.
- **Its own project** — item 13 (Blueprint split).

### Security

- [x] **1. Auth-gate the cron endpoint** — `/tasks/send_reminders` had **no
      authentication**; anyone hitting the URL triggered a full reminder send
      (spam, Twilio/email cost, DoS). _Effort: S._
      _Done & **verified live (staging + prod)**: the route now accepts
      either an `X-Appengine-Cron: true` header (honored automatically if you use
      App Engine cron) or an `X-Tasks-Secret` header matching a new `TASKS_SECRET`
      secret (`secrets_fetcher.get_tasks_secret`, constant-time compare). It is
      **fail-open until `TASKS_SECRET` is set** — deploying this does NOT break the
      reminder job; it just logs a warning each call until you enforce._
      _**To enforce (do in this order to avoid a self-lockout):**_
      _1. Add header `X-Tasks-Secret: <value>` to the Cloud Scheduler job (harmless
      while no secret is set — the app ignores it)._
      _2. Create the `TASKS_SECRET` secret (Secret Manager or env) = `<value>`._
      _Once the secret exists, unauthenticated calls get 403; the scheduler already
      sends the header, so no outage. (App Engine cron users can skip both steps.)_
      _**Verified:** `TASKS_SECRET` set in Secret Manager + the Cloud Scheduler job
      sends `X-Tasks-Secret`. Probed staging + prod — no-secret and wrong-secret both
      return 403; the scheduler's authorized run came back green. Enforced end-to-end._

- [ ] **2. CSRF on form routes + reconsider `SameSite=None`** — No `CSRFProtect`
      anywhere in the repo, and [main.py:74](devotions/python/main.py#L74) sets
      `SESSION_COOKIE_SAMESITE = "None"`, which disables the browser's built-in
      CSRF defense.
      - JSON endpoints reading `flask.request.json` are *implicitly* protected (a
        cross-site form can't send `Content-Type: application/json` without a CORS
        preflight, which is not granted).
      - **Form-based** POST routes (`request.form`) are genuinely CSRF-able:
        `/register`, `/login/email`, `/settings/update_profile`, add/edit/delete
        personal prayer, `/add_memory_verse`, etc.
      - **Cheapest fix:** if nothing depends on cross-site cookie delivery (a
        standalone PWA with OAuth redirect does **not** — `Lax` covers top-level
        OAuth navigations), change `SameSite` to `"Lax"`. That alone neutralizes
        most CSRF.
      - **Belt-and-suspenders:** add Flask-WTF CSRF tokens to the form routes.
      - ⚠️ **OPEN QUESTION:** confirm *why* `SameSite=None` was chosen. If the site
        is embedded cross-origin somewhere, keep `None` and use CSRF tokens
        instead of flipping to `Lax`. _Effort: S (Lax) / M (tokens)._

- [ ] **3. Rate-limit auth + constant-time code compare** — No throttling on
      `/login/email`, `/register`, `/forgot_password`, or email verification. The
      6-digit verification code is compared with `==` (timing-unsafe) and has no
      attempt cap → brute-forceable in minutes. **Fix:** add Flask-Limiter to auth
      routes; compare codes with `secrets.compare_digest`; cap verification
      attempts. _Effort: S–M._

- [x] **4. Validate the Twilio webhook signature** — `/twilio/sms_reply` was
      unauthenticated; a spoofed POST could fake a "STOP" and disable a user's
      SMS. _Effort: S._
      _Done: validates `X-Twilio-Signature` via Twilio's `RequestValidator` over
      `request.url` + form params, returns 403 on mismatch. Backward-compatible
      (Twilio signs every request); if the auth token isn't configured it skips
      with a warning rather than hard-failing. Round-trip verified (valid sig
      accepted, forged sig rejected). If STOP handling ever 403s in prod, check the
      logged `url=` — it must match Twilio's configured webhook URL exactly
      (ProxyFix should make `request.url` the public https URL)._

- [x] **5. Add security headers** — The only `@app.after_request`
      ([main.py:163](devotions/python/main.py#L163)) sets cache headers. Missing:
      `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options`,
      `X-Content-Type-Options: nosniff`, `Referrer-Policy`. _Effort: S._
      _Done: new `set_security_headers` after_request adds `X-Content-Type-Options:
      nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy:
      strict-origin-when-cross-origin`, and HSTS (`max-age=31536000`, HTTPS-only via
      `request.is_secure`). CSP is shipped **Report-Only** (per user choice) on HTML
      responses, with a minimal `/csp-report` log sink — it observes violations
      without blocking, so we can tune a real policy before enforcing._
      _**Follow-ups before enforcing CSP:** (a) watch `/csp-report` logs for missed
      origins; (b) decide whether to keep `'unsafe-inline'` or refactor inline
      scripts/styles to nonces; (c) consider `includeSubDomains`/`preload` on HSTS
      once subdomains are confirmed HTTPS-only._

### Performance (cheap wins)

- [x] ~~**6. Remove duplicate startup data load**~~ — **DROPPED: false positive.**
      Verified that [main.py:77](devotions/python/main.py#L77)
      (`app.config["OTHER_PRAYERS"] = utils.get_other_prayers()`) is **not** a
      redundant disk load: `utils.get_other_prayers()` returns an
      already-in-memory module-level dict, and ~10 devotion templates read it via
      `config['OTHER_PRAYERS'][...]` (morning, evening, close_of_day, lent, etc.).
      Deleting the line would break those pages. No change made.

- [x] **7. Drop the redundant Firestore read in Bible-in-a-Year route** — the route
      re-fetches the user doc that's already loaded on `current_user`
      (`bia_progress`, `completed_bible_days`, `bible_streak_count` are all
      attributes). Use `flask_login.current_user.*` instead. Saves one read per
      page view. _Effort: S._
      _Done: reads `current_user.{bia_progress,completed_bible_days,bible_streak_count}`;
      also aligns the page's streak with the (lapse-adjusted) nav streak._

- [x] **8. Bound the prayer-wall query** —
      `get_active_prayer_requests()`
      ([prayer_requests.py](devotions/python/services/prayer_requests.py)) streams
      the entire non-expired collection to then randomly sample 10. Add
      `.limit(50)` to the query. _Effort: S._
      _Done: added optional `limit` to `get_active_prayer_requests` (default
      `None` = unchanged); wall + random-picker now pass a 100-row cap, answered
      praise-report path stays unbounded. Behavior identical until >100 active
      requests exist._

- [ ] **9. Don't block page render on the fullofeyes scraper** —
      `_get_soup()` ([fullofeyes_scraper.py:66](devotions/python/services/fullofeyes_scraper.py#L66))
      does `time.sleep(random.uniform(1.0, 3.0))` synchronously on every fetch.
      Cache results with a long TTL (24h) or move the fetch off the request path.
      _Effort: S–M._

- [x] **10. Memoize menu generation** — the context processor recomputes the menu
      every request though it only changes a few times a year. `@lru_cache` keyed
      on the seasonal flags (`is_advent`, `is_new_year`, `is_lent`). _Effort: S._
      _Done: `@functools.lru_cache` on `menu.get_menu_items`. Note: the church-year
      calc in the same context processor was already cached (`liturgy.get_church_year`,
      lru_cache), so this is the smaller remaining win._

### Structure & hygiene

- [x] **11. Fix the bare `except:`** —
      [main.py:1808](devotions/python/main.py#L1808) swallowed everything (incl.
      `KeyboardInterrupt`/`SystemExit`) with no logging, around a
      `utils.fetch_passages` validation call. Change to `except Exception as e:`
      and log it. _Effort: S._
      _Done: now `except Exception as e:` with `app.logger.warning(...)`._

- [x] **12. Cleanup: relocate orphaned test + pin deps** —
      - **CORRECTION:** the two `test_liturgy.py` files were **not** duplicates —
        different sizes, different suites. The root one
        (`MidWeekLectionaryKeyTest` + `DailyLectionaryCoverageTest`) was
        **orphaned**: the documented discover command (`-s devotions/python/tests`)
        never ran it, so ~5 valuable tests sat dead. Instead of deleting, **moved**
        it to `devotions/python/tests/test_lectionary_keys.py` (fixed the relative
        data path, added the sys.path shim its sibling uses). Suite now runs
        **89 tests** (was 84).
      - In [requirements.txt](devotions/requirements.txt), pinned `cryptography`,
        `requests`, `pandas`, `twilio`, `beautifulsoup4` to the versions currently
        resolved in the venv (cryptography==48.0.0, requests==2.34.2, pandas==3.0.3,
        twilio==9.10.9, beautifulsoup4==4.14.3) — no behavior change, just
        reproducible builds. _Effort: S._

- [ ] **13. (Larger) Split `main.py` into Blueprints** — 2,413 lines / 97 routes in
      one file. Extract by feature: auth, devotions, prayers, reminders, admin,
      webhooks, static. Biggest long-term maintainability/testability lever, but
      purely internal so lowest urgency. _Effort: M–L._

- [ ] **14. (Optional) Add tests for `menu.py`** — it's pure logic with no
      Firestore imports, so it fits the existing "testable-logic-stays-importable"
      pattern (works around the Python 3.14 protobuf blocker), but currently has no
      tests. _Effort: S–M._

### Frontend / accessibility

- [x] **15. Make collapsible card headers keyboard-operable** —
      [_macros.html:15](devotions/templates/_macros.html#L15) used
      `<div class="card-header" onclick="toggleCard(this)">`, which keyboard users
      couldn't activate. This card appears on **every devotion page**. _Effort: S._
      _Done: kept the `<div>` (so **zero CSS/visual change** across all cards) but made
      it operable — `role="button"`, `tabindex="0"`, `aria-expanded` synced in
      `toggleCard`, and a `handleCardKeydown` handler for Enter/Space. Decorative ▼
      marked `aria-hidden`. (Chose role+tabindex over a real `<button>` to avoid
      inheriting browser button styling on every card.)_

- [ ] **16. (PARTIAL) Skip-to-content link + menu `aria-expanded`** — _Effort: S._
      _**Done:** menu button now has `aria-haspopup`, `aria-controls="app-menu"`, and
      `aria-expanded` synced on open / close / outside-click._
      _**Deferred to its own batch:** the skip link needs new CSS (`.skip-link` +
      `:focus`) and therefore a `styles.css` `?v=` bump **and** a service-worker
      cache-version bump (forces all clients to re-fetch cached assets) — split out so
      that version bump gets isolated review._

- [x] **17. Add `autocomplete` to auth forms** — sign-in/register email + password
      fields lacked `autocomplete`, hurting password-manager UX. _Effort: S._
      _Done: sign-in → `username` / `current-password`; register → `name`,
      `username`, `new-password` (×2). Also added `role="dialog"` / `aria-modal` /
      `aria-labelledby="milestone-title"` to the milestone modal (the confirm modal
      already had them)._

---

## Corrections (do NOT chase these)

The initial automated sweep flagged two issues that **direct code inspection
disproved**. Listed here so nobody re-opens them:

1. **"Missing `SESSION_COOKIE_HTTPONLY` / `REMEMBER_COOKIE_HTTPONLY`" — FALSE
   POSITIVE.** Flask defaults `SESSION_COOKIE_HTTPONLY=True` and Flask-Login
   defaults `REMEMBER_COOKIE_HTTPONLY=True`. The cookies are already HttpOnly; no
   code change needed.

2. **"Stored XSS via `|safe`" — OVERSTATED.** Verified that all user-generated
   content (`prayer.text`, `prayer.for_whom`) is rendered **escaped**
   (e.g. [_macros.html:99](devotions/templates/_macros.html#L99),
   [my_prayers.html:58](devotions/templates/my_prayers.html#L58)). The 54 `|safe`
   uses are all on **trusted server-side** content (ESV scripture HTML, catechism
   JSON, liturgical prayer objects). There is **no stored-XSS-via-user-input**. The
   only residual risk is "if the ESV API or fullofeyes scraper were compromised,"
   which is defense-in-depth — covered by the CSP in item 5, not template surgery.

---

## What's already done well (don't re-invest here)

- **Authorization:** routes that modify owned resources verify
  `current_user.id` against the doc's `user_id` (prayers, prayer requests,
  reminders, memory verses).
- **Secrets:** all fetched from Secret Manager / env via `secrets_fetcher.py`;
  nothing hardcoded.
- **Encryption:** personal prayer text + "for whom" encrypted with Fernet before
  Firestore storage.
- **Auth:** `werkzeug` password hashing; Firebase ID-token verification;
  `admin_required` decorator gates admin routes.
- **Infra:** `ProxyFix` for correct client IP / scheme behind the load balancer;
  Flask-Compress on text responses.
- **Caching that's already right:** Firestore client (`lru_cache`), ESV scripture
  responses (LRU + Firestore persistence), most JSON data files, `last_seen`
  writes throttled to 1/10min, prayer-expiry sweep throttled to 1/15min.
- **Service worker:** network-first for HTML (fresh devotions), cache-first for
  assets, auth routes excluded, cross-origin passthrough, versioned cache name.
- **Frontend:** comprehensive dark mode, visible focus rings, aria-labels on the
  icon-only buttons, ARIA live regions on toasts, documented print mode.

---

## Verification notes

Claims in the Security/Performance sections above were spot-checked directly
against the source (not just the automated sweep):
- Confirmed no `CSRFProtect`/`flask_wtf` import anywhere in `devotions/`.
- Confirmed `SESSION_COOKIE_SAMESITE = "None"` at main.py:74.
- Confirmed `/tasks/send_reminders` has no auth decorator (main.py:2101).
- Confirmed the only `after_request` is the cache-header one (no Talisman /
  security-header middleware; no Flask-Limiter).
- Confirmed the single bare `except:` at main.py:1808.
- Confirmed user prayer fields render without `|safe` (escaped); `|safe` is on
  trusted content only.
- Confirmed `cryptography`/`requests`/`pandas`/`twilio`/`beautifulsoup4` unpinned
  in requirements.txt.
