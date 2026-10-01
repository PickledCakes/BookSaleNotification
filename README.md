# Book Sale Notification 1.2.8

Three-store live-scraper build: BookLive, BOOK☆WALKER, DMM Books.

## New in 1.2
- Live product-page price refresh for known store URLs.
- Live discovery for missing store matches.
- Accuracy-first title/volume resolver ported from the Calibre work.
- Numeric volumes, （N）, N巻, 第N巻, Vol.N, 上/中/下 and bonus/special-edition penalties.
- BOOK☆WALKER series-page expansion for grouped search results.
- Known/manual URLs remain authoritative and are never replaced by the matcher.
- Conservative 0.90 acceptance threshold: uncertain results remain blank.
- Shared rate-limited HTTP client with configurable minimum request delay.
- Active/purchased filtering: purchased books are not included in normal live update cycles.
- Every successful refresh becomes a price-history observation.

Amazon remains disabled for this phase.

## Test sequence
1. Start with a fresh database.
2. Import the three saved wishlist HTML files.
3. Select one book with missing stores and click **Find missing matches**.
4. Inspect its URLs using **Edit store URLs**.
5. Click **Update prices** to refresh all currently matched active products.
6. Check **History** after an update.

The scraper uses only public store/search/product pages. It does not use or store login cookies or credentials.

Live storefront markup changes over time. A parser failure should leave a book unmatched or an update failed rather than silently replacing a manually locked match.


## 1.2.1 hotfix
Fixed the Tkinter background-error callback so the original live-scraper exception is displayed instead of raising a secondary `NameError` after the `except` block exits.

## 1.2.2 hotfix
Fixed SQLite threading correctly: live matching and live price-update workers now create and close their own SQLite connections on the worker thread. The Tk GUI continues using its main-thread connection. This avoids sharing a SQLite connection across threads rather than disabling SQLite's thread check.


## 1.2.3 diagnostics
Fixed matching-dialog line breaks and added a right-side Activity console with request URLs, HTTP status/size/final URL, candidate counts/scores, accepted matches, update results and exceptions. Matching errors are no longer silently swallowed.


## 1.2.8 resolver + product-page parsing
- BOOK☆WALKER uses the exact product price block for current税込 price, tax-exclusive price, pre-sale price, and granted coins.
- DMM treats search hits as series entry points, inspects the product page sibling-volume list, and resolves the requested numbered volume before accepting a match.
- DMM price parsing prefers schema.org Product/DataFeed offers instead of arbitrary yen text on the page.
- BookLive searches the title without the volume suffix first, identifies the matching `title_id` family, then resolves and verifies the requested `vol_no`.
- BookLive price parsing prefers its embedded ecommerce `priceTax` value.
- The 0.90 confidence threshold remains unchanged; uncertain identity is still rejected rather than guessed.

## 1.2.8
- Library rows now support Ctrl+click and Shift+click multi-selection.
- Find missing matches and Update prices operate on all selected rows in one run; no selection keeps the all-active-books behavior.
- Successful lightweight matches are immediately resolved through the product page before saving, so BOOK☆WALKER price fields are populated on first match.
- DMM rejects moving `/latest/` aliases and prefers permanent content-specific URLs from structured series/product data.

## 1.2.8
- Fixed BOOK☆WALKER Japanese-title mojibake caused by heuristic response encoding detection.
- DMM now keeps `/latest/` only as a temporary discovery route for the newest numbered volume.
- When `/latest/` is the requested volume, DMM verifies the numbered title, reads `og:url`, and stores the permanent `/product/<series>/<content_id>/` URL.
- The strict 0.90 identity threshold remains unchanged.

### 1.2.8 price-view update
- BOOK☆WALKER now stores tax-inclusive and exact tax-exclusive prices independently.
- Toggling overseas-tax mode immediately redraws BOOK☆WALKER cells from stored data; it performs no network request.
- Toggling direct rewards immediately redraws DMM/BOOK☆WALKER cells.
- Rewards ON: DMM shows `¥price + N%pt`; BOOK☆WALKER shows `¥price + N coin`.
- Rewards OFF: store columns show only the current cash price (including ordinary cash-sale discounts).

## 1.2.8
- BOOK☆WALKER tax-inclusive, tax-exclusive and coin values are stored separately and the settings toggle redraws immediately.
- DMM parses the product cashback display such as `38%(144pt)還元` and stores the exact point amount.
- Reward toggle shows/hides DMM points and BOOK☆WALKER coins without a network request.
- Ctrl+A selects all visible rows.
- Delete applies to all selected rows.

## 1.2.9
- Fixed BOOK☆WALKER direct-coin extraction by parsing the numeric coin value independently of currency parsing.
- Added a fallback around the `付与コイン` text for alternate BOOK☆WALKER markup.
- Activity now logs BOOK☆WALKER cash/tax-exclusive/coin values.
- Removed the old `v1.2.5` and `1.1 testing phase` version labels. Only the window title shows `1.2.9`.

## 1.3.0
- Cover column on the far left. BookLive is preferred; BOOK☆WALKER/DMM only fill a missing cover.
- Covers are cached locally as JPEG and capped at 800x1200; table thumbnails are about 50x70.
- Each store price now includes its last successful update timestamp underneath.
- Lowest cash price respects BOOK☆WALKER overseas-tax mode and ignores coins/points.

## 1.3.1
- Fixed the remaining literal `\\n` display bugs globally, including timestamps and confirmation/error dialogs.
- Added an instant `Show book covers` setting.
- Added Small / Medium / Large cover display sizes.
  - Small: 50x70 (the original 1.3.0 size)
  - Medium: 75x105 (default)
  - Large: 100x140
- Turning covers off collapses the cover column and restores compact rows.
- Cover size changes reuse the existing local cache and never redownload images.

## 1.3.2
- Lowest cash price names the cheapest enabled store underneath.
- If every enabled/matched store has the same cash price, it says `Same`; partial ties list the tied stores.
- Settings can independently disable BookLive, BOOK☆WALKER and DMM.
- Disabled stores are hidden and skipped by matching, price updates, lowest-price calculations and cover fetching.
- Existing disabled-store matches, prices and history remain stored for later re-enabling.

## 1.3.3
- Fixed manual store URLs showing `?` even when the live scraper successfully parsed a price.
- Price refreshes for already-associated products now update the exact `(book, store)` offer in place.
- Refreshing an existing product no longer runs through canonical-book matching/merge logic.
- Locked/manual URLs remain authoritative and are never replaced by the fetched page.
- Price, list price, rewards, tax-exclusive price, title/author metadata and observation timestamp are refreshed normally.
- Price history continues to be recorded against the existing offer.

## 1.3.4
- Update prices now also refreshes a book's cover when the store's cover URL changes.
- Fixes DMM preorder books retaining an early placeholder/missing-cover image after the real cover is published.
- Cover source priority remains BookLive > BOOK☆WALKER > DMM, so a DMM refresh cannot overwrite a BookLive cover.
- Same-store cover changes are allowed, so DMM can replace its own earlier preorder image.


## 1.4
- Wishlist HTML import is identity-only: same store URL/ID is a duplicate; titles are never fuzzy-merged during import.
- Find Missing Matches is now the explicit reconciliation/merge step and produces a copyable audit report.
- Same-store different product identities are protected from fuzzy merging.
- Automatic database snapshot before destructive/bulk operations; newest 5 retained.
- Recently Deleted supports restoring deleted books and books absorbed by merges; default retention 14 days.
- Purchased books move to Archived and are excluded from normal matching/updates.
- Excel-style list tabs, custom list creation, and shared-list import into a separate tab.
- Light/dark appearance setting.
- Price update continues refreshing changed covers (including DMM preorder cover changes).

## 1.4.1
- Reworked Dark appearance into a complete high-contrast ttk theme.
- Explicit dark styling for buttons, tabs, headers, entries, comboboxes, check/radio controls, scrollbars, tables and activity console.
- Fixed Settings footer so Save and Cancel are always visible and labelled.
- Fixed Recently Deleted footer with visible Restore selected, Permanently delete selected and Close buttons.
- Recently Deleted displays the configured retention period.

## 1.4.2
- Fixed Light mode retaining Dark-mode ttk state mappings after changing appearance.
- Light mode now explicitly resets normal, hover/active, pressed, selected, readonly and disabled colors.
- Added a dedicated Settings button style so Save and Cancel labels remain visible in both themes.
- Dark mode palette from 1.4.1 is otherwise unchanged.

## 1.4.3 hotfix
- Replaced the Settings Save/Cancel footer controls with explicitly coloured native buttons so their labels are always visible.
- Fixed dark-mode disabled and read-only Entry text contrast.
- Fixed dark-mode Combobox disabled/read-only text contrast.
- Light-mode styling from 1.4.2 is unchanged.

## 1.4.4
- Fixed the main vertical scrollbar throwing `invalid command name ".!treeview"`.
- The main Treeview is now created only once in its final container; the scrollbar is bound afterward to that live widget.
- Enlarged Settings Save and Cancel buttons with wider labels and substantially more vertical/horizontal click padding.

### 1.4.4 button-height hotfix
- Settings Save and Cancel now use fixed 120×36 pixel hosts so Windows/Tk cannot collapse their height.

### 1.4.4 Hotfix 2
- Settings window is now a fixed 590×750 px and non-resizable.
- Provides enough vertical room for all current settings plus the full 120×36 Save/Cancel footer without Tk compressing the controls.

## 1.5
- Added Calibre Library Sync under Backup / Share.
- Imports a Calibre CSV export and reads only the `identifiers` column for matching.
- Supported exact identifiers: `bl:`, `bw:`, and `dmm:`.
- No title, author, series, ISBN, ASIN, or fuzzy fallback matching is performed.
- One exact supported identifier is enough to archive the entire canonical book, including its other matched stores.
- Preview shows books to archive, already archived matches, and supported identifiers not found in the wishlist.
- Creates an automatic database backup before applying the bulk archive.
- Completion report is copyable and records the exact identifier(s) responsible for each archive.

### 1.5 fixed-window hotfix
- All app-created secondary/Toplevel windows now use an explicit fixed size and are non-resizable.
- Backup / Share enlarged to 540×520 so the Calibre Library sync control is fully visible.

## 1.5.1
- Calibre Sync preview no longer lists every supported identifier that is absent from the wishlist.
- The unmatched total is still shown in the summary.
- Exact matched books and the identifiers responsible for those matches remain visible.
- Includes the 1.5 fixed-window changes for all secondary dialogs.

## 1.6
- Update Prices now opens a fixed options dialog for selected books:
  - Update covers only
  - Update books without price
  - Update everything selected
- Clearing an existing store URL in Edit store URLs now removes that store match entirely, including store ID, price/reward data and that offer's price history, while preserving the canonical book and other stores.
- A confirmation and automatic backup are performed before store-match removal.
- Matching now treats edition/product markers such as 分冊版, 単話版, 合本版, 特装版, 無料版 and セット版 as hard compatibility rules instead of small fuzzy-score penalties.
- BookLive direct volume resolution applies the same edition guard, preventing a failed normal-volume candidate from falling through to a 分冊版 candidate.
- Cover-assisted matching remains disabled/not implemented.

## 1.6.1
- Edit store URLs validates manually entered links before saving.
- BookLive accepts BookLive product URLs only.
- BOOK☆WALKER accepts BOOK☆WALKER `/de…` product URLs only.
- DMM accepts DMM Books product URLs only.
- Wrong-store or malformed URLs block the entire save and leave the database unchanged.
- Clearing an existing URL still removes that store match as introduced in 1.6.


## 1.7.0 — Tester distribution

This release adds Windows distribution infrastructure.

### Windows packaged build
The PyInstaller build is an `onedir` application. Tester data is stored separately under:

`%LOCALAPPDATA%\BookSaleNotification\`

This keeps the database and backups outside the application folder so a program update does not replace user data.

### GitHub Actions
`.github/workflows/windows-release.yml` builds the Windows package on GitHub's Windows runner.

- **Actions → Build Windows Release → Run workflow** creates a downloadable test artifact.
- Pushing a tag such as `v1.7.0` builds the Windows package and attaches `BookSaleNotification-Windows-1.7.0.zip` to a GitHub Release.

### Enable automatic updates
Before publishing the repository, set `GITHUB_OWNER` and `GITHUB_REPO` near the top of `app.py`.

The packaged app's **Check for Updates** button checks the repository's latest published GitHub Release. If a newer version exists, it can download the Windows release ZIP, verify the GitHub-provided SHA-256 digest when available, close the app, replace the application files, and restart it.

Source builds intentionally do not self-replace.
