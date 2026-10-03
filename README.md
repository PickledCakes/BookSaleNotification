# Book Sale Notification

A Windows desktop app for tracking Japanese ebook prices across:

- **BookLive**
- **BOOK☆WALKER**
- **DMM Books**
- **Amazon Kindle** — direct URL / HTML import + direct refresh of known Amazon URLs; Amazon search is still disabled

> Current version: **1.9.1-beta.9**

Book Sale Notification keeps one combined watchlist, matches the same volume across stores, compares current cash prices, records price history, stores covers, and lets you archive books you have already bought.

## Main features

- Import wishlists from saved HTML.

- `電子書籍の司書さん` imports support both the card/list layout and the **一覧表** table layout. Table-layout imports may not contain prices; those can be filled later with **Update prices**.
- Add individual BookLive / BOOK☆WALKER / DMM / Amazon books by product URL.
- Match the same book across supported stores.
- Canonical titles prefer **BookLive → DMM → BOOK☆WALKER → Amazon**.
- Cover source priority is **BookLive → Amazon → DMM → BOOK☆WALKER**.
- Compare current cash prices in one table.
- Show DMM points, BOOK☆WALKER coins, and Amazon points separately.
- Keep local price history and recorded lows.
- Refresh prices and covers.
- Archive purchased books and restore recently deleted items.
- Use multiple lists.
- Backup, restore, and share lists.
- Sync purchased books from Calibre CSV identifiers.
- English / Japanese UI toggle.
- Remembers the main window size, position, maximized state, and table/activity split.
- Light / dark appearance.
- GitHub-based application updates for packaged Windows builds.
- Update checks can run automatically on startup, but installation is always manual and can be disabled in Settings.
- Settings can opt into the nightly/pre-release update channel for test builds; stable users stay on normal releases.
- The window close button can minimize to the system tray (default) or exit immediately, configurable in Settings.
- Settings includes BOOK☆WALKER and DMM connection health checks; previously valid BOOK☆WALKER sessions are monitored and users are warned once if the session expires.
- Settings includes **Test sale notification** and **Test multiple sale notifications** controls that simulate one or three qualifying books without changing the database or price history.
- When multiple distinct books qualify during one price refresh, sale alerts are grouped into a single desktop/tray summary instead of sending one notification per book.
- Active sale state is persisted per store offer. Sale books are highlighted in the main table, sale stores are marked, and the lowest current store is called out.
- **Show only books on sale** filters the main list to currently active sales; **Latest sale** can be sorted newest-first.
- Sale labels distinguish `SALE`, `★ LOWEST`, and the combined `SALE • ★ LOWEST` state.
- Main-table column widths are remembered and auto-expand when visible content would otherwise be clipped.
- Only one application instance can run; repeat launches restore/focus the existing app, and major utility windows are single-instance.
- Updater now detects duplicate running copies from the same install folder, aborts with a visible error instead of silently partially updating, and records a successful install marker before relaunch.
- Price History uses an interactive step graph with time ranges, enabled-store filtering, per-store visibility toggles, hover details, a summary table, and a Data tab.
- History now stores price-change events only. Existing repeated unchanged observations are compacted once on upgrade after an automatic database backup, and future unchanged refreshes do not add rows.
- History graph hover uses nearest-point snapping so a single recorded observation is still inspectable, and dark-mode legend/tooltips use readable themed colors.
- History Data supports deleting selected historical records with confirmation and an automatic backup; deleting history does not alter the current store price.
- DMM HTML import supports both selectable DMM "あとで買う" display layouts.
- BOOK☆WALKER R-18 is used as a fallback catalog only when the normal BOOK☆WALKER search does not produce a confident match; signed-in session cookies are reused for R-18 product refreshes.
- Automatic price updates now actually run on the configured interval and always write a completion summary to Activity, including how many books dropped in price.
- Manual store-URL editing now reports save failures instead of silently doing nothing, refreshes store product IDs for BookLive / BOOK☆WALKER / DMM / Amazon, and backs up before URL identity changes.
- Price History tooltips automatically flip left/right and up/down near chart edges so hover details stay inside the graph.

Matching is intentionally conservative. It is better for the app to leave a store blank than attach the wrong volume or edition.

## Installing

Download the latest Windows ZIP from the GitHub **Releases** page, extract the whole folder, and run:

`Book Sale Notification.exe`

Do not move only the EXE; the packaged build also needs its `_internal` folder.

The Windows build is currently unsigned, so SmartScreen may show an unknown-publisher warning.

Your personal database is stored separately under:

`%LOCALAPPDATA%\BookSaleNotification\`

Updating the application should therefore not replace your watchlist.

## Importing wishlist HTML

The easiest way to import a large existing list is to save the wishlist page from your browser.

General steps:

1. Sign in to the store.
2. Open the page containing the books you want to import.
3. Make sure the entries are actually loaded. Scroll through lazy-loaded lists first.
4. If the list has multiple pages, save each page.
5. Press **Ctrl+S** in Chrome or Edge.
6. Save as **HTML only** or **Webpage, Complete**.
7. Import the saved HTML into Book Sale Notification.

You can also put several saved HTML files in one folder and use the folder importer. This is especially useful for multi-page lists.

### BookLive

Save the BookLive wishlist / saved-books page containing the individual book entries.

### BOOK☆WALKER

Save the page containing your saved or favourite books after all entries you want are visible.

### DMM Books

Open **あとで買う**, load the books you want, then save that page as HTML.

### Amazon Kindle

Amazon is being added gradually.

For now:

- Amazon search/discovery is disabled.
- Amazon books can be imported from supported HTML **or added directly from an Amazon.co.jp product URL**.
- Once an ASIN is known, the app can refresh that exact product page directly.
- Long Amazon URLs are normalized before storing. Locale/title slugs, `/ref=...`, query parameters, and tracking data are removed.

For example, URLs such as:

`https://www.amazon.co.jp/-/en/some-title/dp/B07FWTQN6R/ref=sr_1_1?...tracking...`

and:

`https://www.amazon.co.jp/some-japanese-title/dp/B07FWTQN6R`

are both stored as:

`https://www.amazon.co.jp/dp/B07FWTQN6R`

Supported Amazon HTML sources:

- saved Amazon.co.jp Kindle wishlist HTML
- saved **電子書籍の司書さん** list HTML from `k.xpg.jp/my/list.fcgi`

If a list has multiple pages, save every page and import the folder.

## Amazon title matching

Amazon often appends a publisher or imprint to the title, for example:

`僕の部屋がダンジョンの休憩所になってしまった件【パートカラー版】 （２） (バンブーコミックス 異世界BC)`

For matching only, the app may remove a recognised trailing publisher/imprint tag.

It does **not** simply remove all parentheses because volume numbers may also appear there, such as `（２）` or `(2)`.

Amazon matching uses stricter rules than the other stores. If volume information conflicts or the title is not close enough, the app leaves the books separate.

## Prices and rewards

The **Lowest cash price** column compares cash prices only.

Rewards are shown separately and do not reduce the cash comparison:
- Signed-out BOOK☆WALKER pages may advertise a **新規限定** first-purchase bonus. The app ignores that promotional amount rather than treating it as the normal coin reward.
- **1.9 beta:** Settings includes BOOK☆WALKER account connection through an Edge WebView2 window. Connected sessions can provide normal coin values; otherwise coins stay hidden while cash prices still update.

- DMM points
- BOOK☆WALKER coins
- Amazon points

For example, if an Amazon source shows an effective `¥327` together with `¥330 - 3pt`, the app stores:

- cash price: `¥330`
- points: `3 pt`

The recorded low is the lowest price **this app has observed**, not necessarily the store's historical all-time low.

## Matching and editions

The app uses store product IDs and URLs for same-store identity and fuzzy title matching only when reconciling different stores.

Different same-store product IDs are treated as different products.

The matcher also treats edition markers conservatively. A normal volume will not be silently merged with things such as:

- `分冊版`
- `単話版`
- `合本版`
- `特装版`
- `無料版`
- `セット版`

Cover images are **not** used to decide whether two books are the same.

## Backups, sharing, and safety

Automatic backups are created before risky operations, and the newest five are kept.

Shared list/history files are treated as untrusted input:

- store URLs are validated before import
- wrong-domain or malformed URLs are rejected
- stored URLs are validated again before opening them in the browser
- Amazon records from shared files are currently skipped during phase 1

Do not share raw HTML saved from a signed-in storefront page publicly. It may contain account-related page data even though the app itself does not use login cookies or passwords.

## Calibre sync

Calibre CSV sync can archive books you already own when the `identifiers` column contains exact supported IDs:

- `bl:<title_id>:<vol_no>`
- `bw:<BOOKWALKER product UUID>`
- `dmm:<DMM content ID>`
- `amazon_jp:<Amazon ASIN>`

Calibre sync does not use fuzzy title matching.

## Current limitations

- Amazon search/discovery is still disabled; direct Amazon product URLs are supported.
- Storefront HTML and page layouts can change and may temporarily break parsing.
- Some pages may return 403 or other request errors even when they open normally in a browser.
- Matching is heuristic and intentionally conservative.
- The main window has a minimum size so the comparison columns cannot be squeezed behind the Activity panel.
- Background unattended sale notifications are not yet implemented.
- The Windows build is not code-signed yet.

## Running from source

Python 3.12 is recommended.

```powershell
py -m pip install -r requirements.txt
py app.py
```

GitHub Actions is configured to compile-check pushes and build Windows release packages.

### 1.9.1-beta.8

- BOOK☆WALKER R-18 authorization is handled separately from ordinary account login using the same persistent WebView2 profile; R-18 certification redirects are reported explicitly instead of being treated as successful product refreshes.
- Interrupted scheduled price updates can resume from their saved checkpoint when the app is reopened before the configured auto-update interval expires. If the checkpoint is older than the current interval, it is discarded and a fresh full run starts.
- Automatic price-update checkpoints persist completed offer IDs, failures, detected price-drop books, and pending sale notifications. Deleted/archived/disabled offers are safely skipped when resuming.
- The Activity pane now has a compact automatic-job status strip with spinner, determinate progress bar, finished/remaining book counts, failure count, and a persisted last-run summary.

### 1.9.1-beta.9

- Fixes the Windows self-updater when the application is installed in a directory containing Japanese or other non-ASCII characters.
- The updater no longer embeds filesystem paths directly in a BOM-less PowerShell script. Install path, ZIP path, temp path, executable name, and target version are encoded as UTF-8/Base64 and decoded inside an ASCII-only PowerShell script, avoiding Windows PowerShell 5.1 ANSI-codepage mojibake.
- Example paths such as `E:\\JD\\[]いただきもの\\[]AVIF元ファイル置き場\\[]Book Sale Notification` are now supported by the updated installer logic.
- Important upgrade note: beta.8 itself still contains the old updater. If beta.8 is already installed in a non-ASCII directory and its in-app update fails, manually replace it with the beta.9 ZIP once. Updates launched by beta.9 and later use the Unicode-safe updater.
