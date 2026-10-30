# Install on iPhone

## Use the hosted application

1. Deploy GRIDIRON AI using the [deployment guide](DEPLOYMENT.md), or use the HTTPS URL provided with the delivery if one is available.
2. Open that URL in **Safari** on your iPhone. Sign in to your account.
3. Tap Safari's Share button, then **Add to Home Screen**. If the action is hidden, scroll down or choose Edit Actions.
4. Keep the name GRIDIRON AI and tap **Add**.
5. Open the new icon. The manifest uses standalone display, so the app opens without Safari's normal address bar. iOS still controls status and safe-area behavior; websites cannot force every system element away.

On supported Android browsers, use Install app or Add to Home screen. Desktop Chromium browsers offer an install icon. Browser support and prompts vary. Installation requires HTTPS outside localhost.

## Save the complete source ZIP to Files

1. Tap the downloadable `gridiron-ai-v4-source.zip` link in the delivery.
2. In Safari, choose Download. If the archive opens in a preview, tap Share and **Save to Files**.
3. Select iCloud Drive or On My iPhone and choose a folder. Tap Save.
4. Open Files → Downloads (or your chosen folder). Tap the ZIP once to extract it.
5. Keep the archive as a source backup or transfer the extracted project to a computer/server for development.

**Saving or extracting source files on an iPhone does not run Node.js, a database, background jobs, or the OpenAI integration.** The installed PWA connects to a hosted backend. iOS Files is storage, not a backend execution environment.

## Offline behavior

After one online visit, the service worker caches public icons, static JavaScript/CSS, and a dedicated offline page. It never caches authenticated API responses. If navigation fails, the app shows the offline page. Writes, live data, sign-in, and AI require a connection.

For historical ledger access, open Settings while online and explicitly save an encrypted offline snapshot with a separate passphrase. On the offline page, enter that passphrase to unlock the read-only historical copy. The snapshot uses AES-256-GCM and PBKDF2, stays on that device, displays its saved time, and does not update automatically. The key is not saved. Use Remove device snapshot to delete it. Account deletion also removes the device copy. Exports/backups are separate from this device snapshot; no offline writes are synchronized later.

Automatic background synchronization, offline transaction editing, biometrics, and guaranteed push delivery are not enabled in this release. On a shared iPhone, use a device passcode, sign out after use, and do not keep unencrypted financial exports in a shared iCloud folder.

## Troubleshooting

- Missing Add to Home Screen: open the page directly in Safari rather than an in-app browser.
- Old interface after deployment: close and reopen the app. If needed, remove the Home Screen app and clear that site's Safari data, then reinstall.
- Sign-in lost: installed apps and Safari may use separate session behavior depending on iOS. Sign in again; records remain on the backend.
- Feed data missing: open source status and check server configuration; installing the PWA does not grant sportsbook data access.
