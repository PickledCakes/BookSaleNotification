# Book Sale Notification — Project Handoff

## Purpose

Book Sale Notification is a Windows Tkinter application for tracking Japanese ebook prices across:

- BookLive
- BOOK☆WALKER
- DMM Books
- Amazon Kindle Japan

The app keeps one canonical book record with per-store offers, price history, reward/point data, cover art, list/archive state, backups/sharing, Calibre matching, and manual/store-assisted reconciliation.

Repository:

- `PickledCakes/BookSaleNotification`
- Default branch: `main`

---

## Current release state

### Stable

Current stable line before the 1.9 beta work:

- **1.8.15**

### Pre-release

Current test build:

- **1.9.0-beta.4**

GitHub pre-release publishing is now part of the workflow.

The intended release process from 1.9 onward is:

`beta.1 -> beta.2 -> ... -> rc.1 -> 1.9.0 stable`

Small fixes should stay in GitHub **Pre-releases** until the specific fix has been confirmed working. Do not create a new normal stable release for every small bug.

The app has two update channels in Settings:

- **Stable only** — default
- **Nightly / pre-release versions (test builds)** — opt-in

The update button and startup update check respect the selected channel. Installation is always manual; the app never silently installs updates.

The controlled pre-release publishing version is stored in:

`.github/PRERELEASE_VERSION`

The Windows release workflow publishes a hyphenated version such as `1.9.0-beta.4` as a GitHub prerelease.

---

## Data location

The main SQLite database is stored outside the installation folder:

`%LOCALAPPDATA%\BookSaleNotification\books.db`

Normally:

`C:\Users\<username>\AppData\Local\BookSaleNotification\books.db`

This database contains books, offers, price history, lists, settings, etc.

BOOK☆WALKER session data is also kept under the same app data directory and is protected with Windows DPAPI.

The cover cache remains separate under the user's profile.

---

## Packaging

The application is currently packaged with PyInstaller in **onedir** mode, so the install contains:

- `Book Sale Notification.exe`
- `_internal\`

The database is not stored inside `_internal`.

A future packaging goal is to consider switching to a **single EXE / PyInstaller onefile** build. If this is done, the updater must also be changed so it replaces the single executable instead of copying an entire extracted app directory.

Do not move the SQLite database into the EXE.

---

## Current storefront behavior

### BookLive

Live search and product refresh are enabled.

Important matching fixes already made:

- visible product heading is preferred over BookLive `og:title`
- exact `title_id + /vol_no/NNN` resolution is trusted
- generic similarity scoring no longer downgrades an already-verified exact BookLive volume

Example that motivated the fix:

`JKと捨て子の赤ちゃん1`

BookLive search found series `504964`, resolved `/vol_no/001`, and now the exact volume match is preserved instead of being reduced to ~0.88 confidence.

### BOOK☆WALKER

Live search and product refresh are enabled.

Important reward rule:

- signed-out pages show a large **新規限定** first-purchase signup bonus
- this must **never** be treated as the normal coin reward
- if the user is not authenticated, BOOK☆WALKER cash price may update but coins must remain hidden / unknown

The signed-out page exposes `BW_IS_LOGIN = false`.

The signed-in page exposes `BW_IS_LOGIN = true` and the normal grant-coin value.

#### 1.9 login feature

Settings now contains a BOOK☆WALKER sign-in button.

Behavior:

- opens the real BOOK☆WALKER site in an Edge WebView2 window
- user signs in normally
- the app does not collect or store the user's password
- the helper captures only the authenticated BOOK☆WALKER session cookies
- saved cookies are protected using Windows DPAPI
- live BOOK☆WALKER requests reuse the authenticated session so personalized normal coin values can be read

The original beta.1 helper could freeze after login because of WebView callback/threading behavior. That was rewritten in beta.2 so login monitoring runs separately and validates the saved cookies against BOOK☆WALKER before closing the login window.

This still needs real-user testing.

#### BOOK☆WALKER session health

Implemented in beta.4:

- if the user has never signed in, do not nag
- if the user previously had a valid session, track it as valid
- a background health check runs shortly after startup and then every 6 hours while the app remains open
- if a previously-valid session becomes signed out, warn the user once
- when minimized to tray, the expiry warning should use a tray notification
- Settings includes **Check now**
- Settings shows last-known status / expired / not signed in / could not check

When a valid session is confirmed, the stored cookies may be refreshed.

### DMM Books

Live search and product refresh are enabled when DMM Books is reachable.

DMM Books effectively requires a Japanese IP for this app's access pattern.

Observed non-Japanese behavior:

- request begins at `book.dmm.com`
- DMM redirects to `accounts.dmm.com/service/login/password?...book.dmm.com...`

The app now detects the **final redirect URL** and raises a specific DMM region/access error instead of reporting zero matches.

User-facing behavior:

- Find Missing Matches reports DMM unavailable / Japanese IP required
- Update Prices reports DMM unavailable / Japanese IP required
- other stores continue normally

#### DMM health check

Implemented in beta.4:

- Settings includes **Check now**
- the check opens a DMM Books page
- if final destination stays on `book.dmm.com`, show **Japanese access available**
- if redirected to the DMM login/access page, show **Japanese IP required**
- timeout/network/server problems show **Could not check** instead of blaming the IP

DMM should not proactively nag users just because their VPN is off. The health state is informational unless a DMM operation is actually attempted.

### Amazon Kindle Japan

Amazon support is intentionally limited:

- saved Amazon HTML import
- 電子書籍の司書さん HTML import
- direct Amazon product URL add
- direct known-product price / point / title / cover refresh
- Amazon search/discovery remains disabled

Amazon can still be used as the source book when searching the other three stores.

Amazon URLs are canonicalized to:

`https://www.amazon.co.jp/dp/<ASIN>`

#### Amazon title / cover priority

Canonical display title priority:

1. BookLive
2. DMM
3. BOOK☆WALKER
4. Amazon

Cover priority:

1. BookLive
2. Amazon
3. DMM
4. BOOK☆WALKER

#### Amazon price parser

The parser was hardened after several failures.

Current intended price extraction:

1. use Amazon's Kindle format swatch when available
2. locate the format row independently of Amazon.co.jp page language
3. use `.slot-price .ebook-price-value`
4. parse the price from `aria-label`
5. support Japanese / English / Chinese Amazon.co.jp UI

Examples that must all parse as 396 yen:

- Japanese: `￥396`
- English: `¥396`
- Chinese: `JP¥396`

Amazon language labels currently include:

- `Kindle版 (電子書籍) 形式:`
- `Kindle (Digital) Format:`
- `Kindle电子书 格式：`

The parser should rely on the stable Kindle structure / presence of “Kindle”, not translated “Format” wording.

There is also an ASIN-bound embedded purchase-price fallback.

Points are read from the Kindle row's `slot-buyingPoints`.

Important past bugs:

- `85% OFF` was accidentally parsed as `¥85`
- Kindle Unlimited/free display could surface `¥0`
- some parser iterations failed to find the visible Kindle price
- a missing `html_lib` import caused Amazon refresh to throw a NameError

Those have been addressed, but Amazon should continue to be tested because its markup changes frequently.

#### Corrupted historical lows

Earlier Amazon bugs may already have written false historical prices such as `¥85` or `¥0` into existing databases.

Do not automatically delete all suspicious historical lows because a genuine sale could theoretically be very cheap.

A future feature should provide a deliberate way to remove / repair bad price-history observations per book/store.

---

## Matching philosophy

The application is accuracy-first.

General rule:

- a low-confidence result should remain unmatched rather than attach the wrong volume

Wishlist HTML imports use same-store identity and do not fuzzy-merge books automatically.

**Find Missing Matches** is the explicit reconciliation operation.

Same-store different product identities must not be fuzzy-merged.

---

## Current Settings / UI state

The Settings window was made scrollable in beta.4 because new options made the dialog too tall.

Current relevant Settings controls include:

- notification rule
- cover display
- store enable/disable toggles
- BOOK☆WALKER sign in
- BOOK☆WALKER login health **Check now**
- DMM access health **Check now**
- request delay
- startup update checking
- nightly / pre-release update channel
- close-button behavior
- appearance
- recently deleted retention

### Translation issue still visible

The Japanese UI currently still shows several newer beta controls in English, including items such as:

- `Check now`
- `Signed in (last known)`
- update-channel explanatory text in some builds
- close-button behavior text in some contexts

Some new strings have Japanese mappings, but the Settings screenshot from beta.4 still shows a mixed Japanese/English UI.

This needs a cleanup pass before stable 1.9.0.

---

## Close-to-tray behavior

Implemented in beta.4.

Default X-button behavior:

- **Minimize to system tray**

Settings lets the user choose:

- Minimize to system tray
- Exit application

When minimized to tray:

- the main window is hidden
- the process remains running
- tray menu contains Open and Exit
- only tray **Exit** actually terminates the application

The updater bypasses close-to-tray behavior and performs a real application exit when applying an update.

Tray support uses `pystray`.

The tray icon currently uses a generated simple book icon rather than a polished application icon.

This needs Windows testing for:

- X hides the window
- tray icon always appears
- double-click/default Open restores the window
- Exit terminates the process
- updater still exits cleanly
- BOOK☆WALKER expiry notification works when hidden

---

## Update-system history

The 1.9 update-channel work exposed one important threading bug.

In beta.1 the update checker accessed `self.db` from its background network worker, causing:

`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`

This was fixed by reading the update-channel state on the Tk/main thread before starting the worker and returning reminder-setting writes to the Tk thread.

This fix is in beta.3+.

---

## Release workflow

The repository currently uses:

`.github/workflows/windows-release.yml`

The prerelease trigger version is:

`.github/PRERELEASE_VERSION`

Updating that file to something such as:

`1.9.0-beta.5`

triggers the Windows build and publishes the resulting ZIP as a GitHub prerelease.

A plain stable tag/version such as:

`v1.9.0`

is intended to become the normal stable release.

Before publishing any stable release:

1. confirm the specific bugs/features in a prerelease build
2. do not promote merely because Python compile validation passed
3. test the Windows packaged build
4. only then publish the stable version

---

## Current beta dependency additions

1.9 adds:

- `pywebview` for BOOK☆WALKER login through Edge WebView2
- `pystray` for system tray support

The PyInstaller spec includes the needed pywebview/pythonnet and pystray modules.

---

## Immediate testing checklist for the next chat

The 1.9 beta checklist was completed successfully before promoting **1.9.0** to stable. Future work should continue from the stable 1.9.0 baseline:

1. **BOOK☆WALKER login**
   - login window opens
   - normal login completes without freezing
   - helper closes automatically after a valid session is detected
   - subsequent Update Prices uses signed-in normal coins
   - signed-out users never see the 新規限定 signup bonus as normal coins

2. **BOOK☆WALKER expiry**
   - Settings Check now correctly reports valid / expired / unavailable
   - a previously-valid session later becoming invalid triggers one warning
   - no repetitive nagging after the expired state has already been recorded
   - tray notification works if the main window is hidden

3. **DMM health**
   - JP IP shows available
   - non-JP IP redirects and shows Japanese IP required
   - network failure shows could not check
   - normal DMM matching/update still reports the specific region warning

4. **System tray**
   - X defaults to minimizing to tray
   - tray Open restores the app
   - tray Exit really terminates it
   - Settings can switch X behavior to immediate exit
   - updater still performs a real exit/restart

5. **Stable / nightly updater**
   - stable channel ignores prereleases
   - prerelease channel offers the next beta
   - beta version ordering works
   - startup reminder does not hit SQLite threading errors
   - update button works from beta.3/beta.4 onward

6. **Japanese UI**
   - finish translations for all new 1.9 Settings / health / tray / update strings

7. **Amazon**
   - confirm the multilingual Kindle price parser in real packaged builds
   - confirm Japanese, English and Chinese Amazon.co.jp pages
   - consider a user-facing history repair tool for old bad Amazon observations

8. **Packaging**
   - decide whether 1.9 stable should switch from onedir to onefile
   - if switching, update and test the self-updater accordingly

---

## Important source files

- `app.py`
  - Tk UI
  - SQLite DB layer
  - update checker/updater
  - settings
  - BOOK☆WALKER login helper
  - BOOK☆WALKER/DMM health UI
  - system tray behavior

- `scraper.py`
  - BookLive / BOOK☆WALKER / DMM / Amazon live scraping and matching
  - BOOK☆WALKER session cookie injection
  - Amazon multilingual price parsing
  - DMM redirect/region detection

- `BookSaleNotification.spec`
  - PyInstaller configuration

- `requirements.txt`
  - runtime/build Python dependencies

- `.github/workflows/windows-release.yml`
  - Windows packaging and GitHub release publishing

- `.github/PRERELEASE_VERSION`
  - controlled prerelease version trigger

---

## Working style / release rule

Do not treat a successful GitHub compile workflow as proof that a runtime bug is fixed.

For 1.9:

- implement fix
- publish next prerelease
- test the packaged Windows build
- confirm behavior with the user
- only then consider it fixed
- keep stable releases clean and infrequent


---

## 1.9.1 notification work

### beta.1 — Grouped sale notifications

- Sale events from one refresh are grouped by canonical book ID before desktop notification delivery.
- One qualifying book keeps the detailed store/price notification.
- Two or more distinct qualifying books produce one summary notification with the total number of books, preventing notification spam during large sale periods.
- Multiple store events for the same book count as one book.
- Settings includes a three-book grouped-notification simulation for testing without changing price/history data.
- This is phase 1 of the notification upgrade. Sale highlighting/filtering and an in-app sale notification center are planned for later phases after beta.1 testing.
