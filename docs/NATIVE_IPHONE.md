# GRIDIRON AI: private native iPhone application

The existing Next.js application is preserved. The new `ios/` directory is a real Capacitor iOS Xcode project using Swift Package Manager and a custom Swift authentication bridge. It is for personal development/ad-hoc installation, not App Store submission or TestFlight.

## What exists and what was verified

- Capacitor iOS project and pinned native dependencies generated successfully on Linux.
- Original GRIDIRON app icon exported as opaque 1024×1024 PNG; dark branded splash assets and a native session-restoration gate are included.
- Native Swift Keychain storage captures only approved HTTPS, HttpOnly, root-path cookies: `gridiron_session`, `gridiron_sb_access`, `gridiron_sb_refresh`, `gridiron_backend`.
- Credentials are device-only, accessible only while unlocked, and never returned through JavaScript. Passwords are not stored. Cookies are restored before constructing the application WebView. A native cookie-store observer persists rotated access/refresh cookies and flushes pending capture when the app backgrounds; it does not wait for a changed user ID. Explicit logout removes authentication cookies while retaining the selected cloud/legacy workspace preference.
- Custom native navigation checks the exact configured HTTPS scheme/host/port, rather than trusting a hostname prefix. External links leave the app. App-bound domains and strict App Transport Security remain enabled.
- Native lifecycle, back/forward gestures, status bar, splash dismissal, haptics and allow-listed `gridironai://open?view=bankroll` links are implemented.
- Notification registration is an explicit Settings action. Tokens are encrypted server-side when a server encryption key is configured. Registration alone does not create an APNs sender or an injury feed.
- Thirteen Node tests cover origin/deep-link policy, encrypted token storage and source/artifact safeguards, including rotation-observer and workspace-retention structure. XML/plists, the project structure and PNG dimensions were checked. These are **not** an Xcode compilation, device Keychain test, APNs delivery test or signed-IPA verification.

This authoring environment is Linux and has no macOS, Xcode, iOS SDK, Apple signing identity or physical iPhone. No signed IPA is claimed or fabricated. The private archive script refuses to run on Linux.

## Backend requirement

Deploy the existing application and its persistent database first. An iPhone does not execute Next.js, SQLite server code or Python simulations. The native app securely connects to your own actual HTTPS origin.

Never put an OpenAI key, Supabase service-role key, database password, simulation token, APNs signing key or other server secret into Capacitor configuration, Info.plist or JavaScript. The HTTPS application URL and bundle identifier are public configuration. Keep the URL, bundle identifier, database project and Keychain access identity stable across updates.

## Prepare the native project

Use the locked Node dependencies (`npm ci`). Configure `GRIDIRON_NATIVE_URL` to the actual deployed HTTPS **origin**, without a path, query or fragment. Configure `GRIDIRON_IOS_BUNDLE_ID` if you need a different unique reverse-domain identifier; the project default is `ai.gridiron.personal`.

```sh
npm run ios:prepare
npm run ios:open
```

`ios:prepare` synchronizes the local shell/plugins, updates the single trusted host and native Info.plist, preserves the custom Swift files, and records non-secret preparation status in `native/preparation.json`. It refuses to silently use a placeholder release server.

For source validation without a configured backend only:

```sh
node scripts/ios-prepare.mjs --unconfigured
```

That builds configuration for a bundled setup screen, not a production release. It is useful on Linux and must not be represented as a connected signed app.

## Required Apple-side inputs

On a Mac, install a version of Xcode supporting the pinned Capacitor 8 iOS project and its iOS SDK, accept its license, and select the Xcode Command Line Tools. Resolve Swift packages in Xcode.

Open `ios/App/App.xcodeproj`, select target **App**, set your Apple team in Signing & Capabilities, confirm the unique bundle identifier, and connect/trust your own iPhone. Enable Developer Mode on the iPhone when required. Use Xcode Run for the first physical-device verification.

A free Apple personal team may allow direct development installation with short-lived provisioning, commonly seven days. It does not establish entitlement to ad-hoc distribution or every push capability. A paid Developer Program membership may be required for a reusable exported IPA or APNs, depending on Apple's current policies. No membership purchase is initiated by this project.

For the private archive script, provide these through your local trusted environment:

- `GRIDIRON_NATIVE_URL`: actual HTTPS backend origin.
- `APPLE_TEAM_ID`: your ten-character Apple team identifier.
- `APPLE_DEVICE_UDID`: your own registered iPhone identifier.
- `GRIDIRON_ALLOW_APPLE_SIGNING=1`: explicit authorization for local Apple signing after configuring Xcode.
- `GRIDIRON_IOS_EXPORT_METHOD`: `debugging` for private development, or `release-testing` for an eligible ad-hoc profile. App Store export methods are rejected.

Do not send private signing keys or Apple passwords in chat or commit them to source.

```sh
npm run ios:archive
```

The script creates a new, unique directory under `artifacts/ios/`, archives and exports through Xcode, verifies the native code signature, checks the embedded profile's team, expiration and personal device registration, and records a SHA-256 verification manifest. It removes an invalid new IPA and never overwrites a previous verified build. A genuine IPA is only claimed when those operations succeed.

## Optional native push

Push is disabled in the default native entitlement file. To build a push-capable app, enable Push Notifications for the App ID/profile in Apple's tooling, set `GRIDIRON_IOS_PUSH=1`, and set `GRIDIRON_APNS_ENV` to `development` or `production` matching the actual exported profile. The archive verifies that the configured environment matches the profile.

The backend needs a random `DEVICE_TOKEN_ENCRYPTION_KEY` of at least 32 characters to encrypt APNs tokens; the key remains server-only. `/api/devices` requires the authenticated owner, returns registration metadata without token values, supports deletion, and reports that delivery is not configured. The cloud and legacy application modes both use the same privacy boundary.

The app's native Settings card requests iPhone permission only after you tap Enable native notifications. It can register with APNs and save the encrypted device registration. Actual sending requires separately configured APNs credentials and a delivery worker. No live delivery was tested here. Disabling registrations unregisters APNs and removes saved owner registrations. On a shared/reassigned device, disable registration before signing out and remove the app's server-side device records when necessary.

## Private installation and update

Use Xcode's Devices and Simulators workflow or another Apple-supported local installation method that accepts your properly signed development/ad-hoc IPA and matching device profile. A ZIP saved to Files is not an installed native app. App Store Connect and TestFlight are not required or configured.

Verify on the actual iPhone: launch/splash, sign-in, force-quit/relaunch Keychain restoration, cloud/legacy workspace identity, logout/deletion, screen safe areas, back gestures, external link handling, notifications if enabled, offline behavior and upgrade continuity. Keep server data and backups intact. Reinstalling an app can affect device-local snapshots; personal records remain on the persistent backend.
