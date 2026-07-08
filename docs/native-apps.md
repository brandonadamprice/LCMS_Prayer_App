# Native App Plan (Android / iOS)

Goal: ship Android and iOS apps by wrapping the existing PWA rather than
rebuilding. The site is server-rendered Flask, so the "native app" is a thin
shell around the live site plus native capabilities where they matter.

## Starting position (already in place)

- Valid `manifest.json` (standalone display, icons, theme color, shortcuts).
- Service worker with offline caching and push handling.
- Push notifications already via **FCM** (`/save_fcm_token` backend), which has
  first-class native SDKs on both platforms — the existing token storage
  carries straight over. Messages carry both a `notification` block (so the OS
  displays them for a native shell in the background — data-only messages
  never show natively) and the `data` duplicate that the web service worker
  renders from; native tokens can therefore share the same `fcm_tokens` array
  and send path.
- Firebase Auth session bridge (`/auth/firebase`) — built specifically so a
  native shell can sign in via the native Firebase SDK and exchange the ID
  token for the normal web session. See
  [firebase-auth-migration.md](firebase-auth-migration.md).

## Approach: Capacitor for both platforms

**Decision: use Capacitor from the start, for Android and iOS alike.** One
shell codebase, one plugin set (`@capacitor-firebase/authentication`,
`@capacitor/push-notifications`), the same deep-link/update story on both
platforms — and everything built for the Android launch carries directly into
the iOS one.

Alternatives considered and rejected:

| Approach | Why not |
|---|---|
| **TWA** (Trusted Web Activity, via Bubblewrap/PWABuilder) | Android-only, so it becomes throwaway work the day iOS ships: it runs the PWA in Chrome with **web** push and browser sign-in, while the Capacitor shell uses **native** FCM and the native Firebase auth plugin — none of the TWA wiring transfers. Cheaper to ship, but a dead end. |
| Hand-built native shells | Overkill for a wrapped web app. |

The Capacitor WebView loads the live site via `server.url` (remote-URL mode) —
the app stays server-rendered Flask; nothing is bundled locally except the
shell.

## Known blockers and their mitigations

1. **Google OAuth is blocked inside embedded webviews**
   (`disallowed_useragent`). *Mitigation (shipped):* the Firebase Auth
   migration. The native shell signs in with the OS-level Google flow via the
   native Firebase plugin (e.g. `@capacitor-firebase/authentication`), then
   POSTs the ID token to `/auth/firebase`. The web popup flow has the same
   property — sign-in happens outside the webview.

2. **Apple App Store Guideline 4.2** (minimum functionality): Apple rejects
   apps that are "just a website in a wrapper." *Mitigation:* ship genuine
   native value — native push (have it), and candidates like a home-screen
   widget (verse/streak), biometric lock for personal prayers, or share
   extensions. Plan App Review pushback into the iOS timeline. Google Play is
   far more lenient.

3. **iOS web push** only works for home-screen-installed PWAs (16.4+) and is
   less reliable than native APNs; a Capacitor shell using native FCM→APNs is
   the more dependable notification path on iOS.

4. **Apple sign-in requirement**: if the iOS app offers third-party login
   (Google), Apple requires offering **Sign in with Apple** too. Firebase Auth
   supports it as a provider; the `/auth/firebase` bridge handles any Firebase
   provider, but `firebase_auth_logic` matching rules should be reviewed when
   adding it (Apple's email-relay addresses won't match existing doc emails).

## Web APIs already used that map to plugins

`navigator.share`, `navigator.vibrate` (milestone modal) — both have direct
Capacitor plugin equivalents; the web fallbacks keep working inside the shell.

## Sequencing

1. ✅ Firebase Auth phases 1–2 (session bridge + Google sign-in) — shipped to
   prod and proven.
2. ✅ Firebase Auth phase 3 (email/password) — 3a live in prod since
   2026-06-11 (all password users imported, canary-verified); 3b (legacy
   flow deletion) done on `dev`, pending promote. The shell never needs the
   legacy form flows.
3. ✅ Push payload made native-ready: messages carry a `notification` block
   (data-only messages are never displayed for a backgrounded native app)
   plus Android high priority; web SW display path unchanged.
4. **Capacitor shell — Android first**: scaffold the project (remote-URL
   mode), wire `@capacitor-firebase/authentication` → `/auth/firebase` and
   native FCM token registration → `/save_fcm_token`, handle the
   notification-tap `url` deep link; Play Store submission.
5. **iOS follow-on from the same shell**: add Sign in with Apple (review
   `firebase_auth_logic` matching first — Apple's relay emails won't match
   existing docs), APNs setup, and the Guideline 4.2 native-value items
   (widget / biometric lock candidates); App Store submission.
