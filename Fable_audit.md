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

## Progress snapshot

Worked in small per-theme batches on `dev` (= staging — see deploy topology).
Commits `53a31d6 → 8…` on `dev`; verified each via the unit suite (now **95 tests**)
and `py_compile`/`jinja` parse (the app can't fully boot under Python 3.14).

- **✅ Implemented & on `dev`/staging:** 1, 4, 5, 7, 8, 10, 11, 12, 14, 15, 16, 17,
  and 18 (offline-cache bug found mid-work).
  - **Item 1 (cron auth) also verified live in prod.**
- **✅ Closed with no code change (verified false/non-issue):** 6 (would have broken
  ~10 templates), 9 (art is async, never render-blocking). See
  [Corrections](#corrections-do-not-chase-these).
- **⏳ In progress — needs YOU:** **2 (CSRF)** — `SameSite=Lax` shipped to staging;
  **test Google sign-in on `staging.asimplewaytopray.com`** before promoting to prod.
- **⬜ Not started (need a decision):** **3** (rate-limit — adds a `Flask-Limiter`
  dependency; per-worker vs shared-storage question), **13** (Blueprint split of
  `main.py` — large internal refactor).

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

- [ ] **2. CSRF on form routes** _(SameSite=Lax ruled out on staging — CSRF tokens pending)_ — No `CSRFProtect`
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
      - ❌ **`SameSite=Lax` tried on staging → broke Google sign-in** (despite the
        first-party flow analysis). `signInWithPopup` hung after account selection;
        the console COOP/`window.frames` message is Google's own, not ours. `None`
        is empirically load-bearing for the Firebase popup, so **reverted both
        cookies to `None`** ([main.py](devotions/python/main.py)).
      - ➡️ **Path forward: keep `SameSite=None`, add Flask-WTF CSRF tokens** to the
        form-based POST routes (`/register`, `/login/email`, `/settings/update_profile`,
        add/edit/delete personal prayer, `/add_memory_verse`). JSON/`request.json`
        endpoints stay implicitly protected. _Effort: M (form templates + the AJAX
        `fetch` calls; new `Flask-WTF` dep)._ **Awaiting your go.**
      - ⚠️ If sign-in is **still** broken after this revert, the Batch 3 security
        headers become the next suspect (try exempting `/__/`, `/login`, `/authorize`).

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

- [x] ~~**9. Don't block page render on the fullofeyes scraper**~~ — **CLOSED:
      premise wrong, no change made.** `_get_soup()` does sleep 1–3s, but
      `get_art_for_reading` is called **only** from `/api/lectionary/art`, which
      every devotion template hits via **async `fetch()` after the page loads**
      (e.g. [morning_devotion.html:177](devotions/templates/morning_devotion.html#L177)).
      So it never blocks render — only the decorative background art arrives a
      couple seconds late, and only on a cache miss (`search_images_cached` /
      `fetch_recent_images_cached` already memoize results). The sleep is also
      *deliberate* anti-block politeness toward fullofeyes.com (the code handles 403
      blocks), so removing it would risk losing art entirely. Left as-is. _(A
      persistent cross-restart cache like `scripture.py` uses is a possible future
      nicety, but marginal for an async decorative element.)_

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

- [x] **14. Add tests for `menu.py`** — it's pure logic with no Firestore imports,
      so it fits the existing "testable-logic-stays-importable" pattern. _Effort: S–M._
      _Done: `tests/test_menu.py` covers seasonal enable/disable (Advent / New Year /
      Lent), flag independence, evergreen items, and structure shape. Suite now runs
      **95 tests** (was 89)._

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

- [x] **16. Skip-to-content link + menu `aria-expanded`** — _Effort: S._
      _**Done (Batch 5):** menu button has `aria-haspopup`, `aria-controls="app-menu"`,
      and `aria-expanded` synced on open / close / outside-click._
      _**Done (Batch 7):** skip link added as the first focusable element in
      `base.html` targeting `#main-content` (`<main>` given `tabindex="-1"` so focus
      actually moves there; its focus outline suppressed). New `.skip-link` CSS;
      bumped `styles.css?v=24→25` and SW `CACHE_NAME` `prayer-app-v24→v25` together._

- [x] **17. Add `autocomplete` to auth forms** — sign-in/register email + password
      fields lacked `autocomplete`, hurting password-manager UX. _Effort: S._
      _Done: sign-in → `username` / `current-password`; register → `name`,
      `username`, `new-password` (×2). Also added `role="dialog"` / `aria-modal` /
      `aria-labelledby="milestone-title"` to the milestone modal (the confirm modal
      already had them)._

### Discovered during cleanup

- [x] **18. Offline-download cache wiped on every deploy** — the Settings
      "Download Next 3 Days" feature wrote to a version-style cache name
      `prayer-app-v8` ([settings.html](devotions/templates/settings.html)), but the
      service worker's `activate` handler deletes every cache ≠ `CACHE_NAME`, so the
      saved offline devotions were wiped on the next deploy (and the stale `v8` never
      matched the bumped asset cache anyway). _Effort: S._
      _Done: added a stable, version-independent `OFFLINE_CACHE_NAME =
      'prayer-app-offline'` in `sw.js`; `activate` now preserves it across deploys;
      `settings.html` writes to that name. The SW fetch handler already uses global
      `caches.match()` (all caches), so offline serving needed no change. Verified by
      JS syntax + reasoning; full end-to-end check needs a download-then-deploy cycle.
      (Pre-existing bug, unrelated to the audit.)_

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
