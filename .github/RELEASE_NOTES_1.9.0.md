# Book Sale Notification 1.9.0

This is the stable 1.9 release, promoted from the tested 1.9.0 beta series.

## What's new since 1.8.15

### BOOK☆WALKER account sign-in and personalized coins
- Added a **Sign in to BOOK☆WALKER** option in Settings.
- Sign-in happens on the real BOOK☆WALKER website in an Edge WebView2 window; the app does not collect or store your password.
- Authenticated session cookies are stored locally and protected with **Windows DPAPI**.
- Price refreshes can now use the signed-in session to read the normal account-specific BOOK☆WALKER coin amount.
- Signed-out pages no longer risk treating the large **新規限定** new-user bonus as the normal coin reward.
- Added BOOK☆WALKER session health checks, including a manual **Check now** button.
- Previously valid sessions are checked after startup and periodically while the app stays open.
- If a previously valid session expires, the app warns once and asks you to sign in again.
- Fixed the WebView login flow that could freeze during the early beta.

### DMM Books access detection
- Added a DMM Books connection health check in Settings.
- The app now distinguishes between:
  - **Japanese access available**
  - **Japanese IP required**
  - **Could not check**
- DMM region/login redirects are detected explicitly instead of being reported as zero search results.
- A DMM access problem no longer prevents the other stores from continuing their updates.

### Stable and pre-release update channels
- Added separate update channels:
  - **Stable only** (default)
  - **Nightly / pre-release versions (test builds)**
- Startup update checks and the manual update button respect the selected channel.
- Updates remain **manual**; the app never silently installs a new version.
- Fixed a SQLite cross-thread error discovered while testing the beta updater.

### System tray support
- The window close button now defaults to **Minimize to system tray**.
- Settings can switch the X button back to **Exit application**.
- The tray menu provides **Open** and **Exit**.
- Update installation still performs a real exit rather than hiding the app.
- Tray startup was hardened for packaged Windows builds.

### Sale notifications
- Price refreshes now apply the configured notification rule and can show desktop/tray alerts when a qualifying sale is found.
- Supported rules:
  - **Any sale**
  - **Lowest recorded price**
  - **Good deal** using the configured discount threshold
- Added **Test sale notification** in Settings so notification delivery can be checked without changing book data or price history.
- Sale alerts and BOOK☆WALKER session-expiry alerts share the same desktop/tray notification path.

### Settings and Japanese UI improvements
- Settings is now scrollable so the expanded 1.9 options fit on smaller displays.
- Added Japanese translations for the new update-channel, connection-health, tray, BOOK☆WALKER, and notification controls/statuses.
- Cleaned up several mixed English/Japanese states introduced during the beta.

## Upgrade notes
- Your database remains in `%LOCALAPPDATA%\BookSaleNotification\books.db`, outside the application folder.
- Existing watchlists, price history, store matches, settings, and archived books are preserved when replacing the application files.
- The Windows package is still a PyInstaller **onedir** build, so keep `Book Sale Notification.exe` together with its `_internal` folder.
- BOOK☆WALKER sign-in requires the Microsoft Edge WebView2 Runtime.

**Full changelog:** https://github.com/PickledCakes/BookSaleNotification/compare/v1.8.15...v1.9.0
