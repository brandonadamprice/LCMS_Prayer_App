# Feature Ideas / Backlog

Living list of candidate features, mostly from the 2026-07-07 site audit.
Not commitments — grab one when there's appetite. Each entry notes why it
fits this site and roughly what it builds on. (Bug/debt items live in
`Fable_audit.md`; auth work lives in `firebase-auth-migration.md`.)

## High fit, moderate effort

- **Audio devotions / "pray along" mode.** A play button on each office.
  Cheapest version is the Web Speech API (client-side TTS, works offline,
  zero hosting cost); the premium version is recorded audio for the fixed
  ordinary (Invocation, Creed, Lord's Prayer) with TTS for the variable
  parts. Fits commutes, walks, and older users. Most-requested category in
  prayer apps generally.

- **Psalter reading plan.** The classic 30-day full-psalter cycle (morning/
  evening portions) alongside Bible-in-a-Year. Reuses the existing
  completion/streak machinery (`streak_logic`, completed-days arrays) and
  the ESV fetch/cache. Data file is a simple 30x2 mapping.

- **Hymn of the day.** `liturgy.py` already knows season/feast; TLH hymn
  texts are public domain. A hymn card per office (text + LSB/TLH number)
  deepens the Lutheran identity. Currently there is no hymn data at all —
  needs a `hymns.json` keyed by liturgical season/key.

- **Congregation "bulletin mode".** Print mode is already excellent; add a
  "pick a date → print Sunday's devotion as a handout" flow aimed at
  pastors/elders. Could be the feature that spreads the app church-to-
  church. Mostly a date-picker wrapper around existing print CSS.

- **Prayer circles.** Personal prayers are fully private; the prayer wall is
  fully public; nothing in between. A "share my prayer list with spouse /
  family / small group" tier. The encrypted-subcollection model extends
  (app-wide Fernet key, so sharing is an authorization question, not a
  crypto one).

## Engagement / reach

- **Weekly email digest.** Sunday-evening email: this week in the church
  year, your streak, a featured (public) prayer request. SMTP, reminders
  infra, and per-type notification preferences already exist — mostly
  assembly work plus an unsubscribe type.

- **Shareable verse/prayer images.** OG images per devotion/day (server-
  rendered or client canvas) so shares don't all show the same banner.
  Pairs with the existing share button on milestones.

- **Grace-day visibility.** streak_logic already awards grace days but the
  user never sees it. Surface a "your streak was protected" toast/badge —
  turns invisible engineering into a delight moment. Small.

- **Site search.** 20+ content types (catechism, studies, prayers, psalms).
  A client-side index (prebuilt JSON, no backend) would answer "that prayer
  about anxiety…" queries. Medium-small.

## Content depth

- **Feast-day devotions.** `liturgy.py` computes ~50 keys but
  `daily_lectionary.json` covers a single cycle with no saints'/feast-day
  propers — the code is ahead of the data. Even a dozen major feasts
  (Reformation, All Saints, Ascension, Epiphany...) would be felt. Data
  entry + review, no new code.

- **Multi-year lectionary rotation.** Bigger cousin of the above; only
  worth it after feast days land.

## Platform (tracked elsewhere but related)

- **Native app shells** — see `native-apps.md`; blocked on Firebase auth
  migration Phase 4 + Sign in with Apple considerations.
- **PWA update prompt** — notify users when a new service-worker version is
  waiting instead of silently activating. Small.
- **JSON-LD structured data** — rich results for the public content pages
  now that robots.txt/sitemap.xml exist. Small.
