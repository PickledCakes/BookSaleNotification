# Book Sale Notification

A Windows desktop app for keeping a personal Japanese ebook watchlist across:

- **BookLive**
- **BOOK☆WALKER**
- **DMM Books**

The app imports books from saved wishlist HTML or from a single product URL, tries to match the same volume across the other supported stores, records prices over time, and gives you one place to compare the current cash price.

> **Current version: 1.7.2**
>
> Amazon is intentionally disabled for now.

---

## What the program can do

### Import a wishlist from any supported store

You can save your wishlist / saved-books page from BookLive, BOOK☆WALKER, or DMM Books as an HTML file and import it into the app.

Wishlist import is deliberately conservative:

- the app uses the store's product URL / product ID as the identity;
- importing the same store item again updates/reuses that item instead of creating another copy;
- **titles are not fuzzy-merged during HTML import**;
- two different product IDs from the same store are treated as different products even when their titles look almost identical.

This avoids accidentally combining things such as a normal volume, a split/serial edition, a special edition, or another genuinely different product.

### Add a book manually from a product URL

Click **Add from URL…** and paste a product URL from any one of the three stores.

The app will:

1. fetch the exact pasted product;
2. read its title, author, current price and available metadata;
3. use that book as the anchor;
4. search the other two supported stores;
5. fetch the matched product pages so price/reward metadata is populated;
6. only then add the book to the current list.

This is useful when you only want to add one new volume and do not want to export a fresh wishlist HTML file.

### Find the same book on the other stores

Select one or more books and click **Find missing matches**.

The matcher searches missing stores using the title/volume information it already has. It is intentionally accuracy-first: if a result is not confident enough, the store is left blank rather than guessed.

The matcher understands common volume formats such as:

- trailing numbers;
- `（3）`;
- `3巻` / `第3巻`;
- `Vol.3`;
- `上` / `中` / `下`.

Product/edition markers are treated as hard compatibility rules. A normal edition will not be accepted as the same product as markers such as:

- `分冊版`
- `単話版`
- `合本版`
- `特装版`
- `無料版`
- `セット版`

After a matching run, the app shows a copyable audit report with matches, misses and merges.

### Compare current prices

Each canonical book can hold one matched offer for each supported store.

The table shows:

- BookLive price;
- BOOK☆WALKER price;
- DMM price;
- the lowest current **cash** price;
- which store is cheapest;
- how many enabled stores are currently matched;
- the last observation time;
- an optional cached cover.

DMM points and BOOK☆WALKER coins can be displayed beside the cash price, but they do **not** reduce the value used for **Lowest cash price**.

### Refresh prices and covers

Select one or more books and click **Update prices**.

You can choose:

- **Update covers only**
- **Update books without price**
- **Update everything selected**

Existing store associations are refreshed in place. An ordinary price refresh does not rematch the book to a different product.

Each successful price refresh becomes a price-history observation.

### Keep price history

Click **History** on a selected book to see recorded observations for its store offers.

The app can show the lowest price it has personally recorded. This is **not guaranteed to be the store's all-time historical low**; it only knows prices observed while using this database or imported through shared history.

### Edit or remove store matches manually

Select a book and click **Edit store URLs**.

Manual URLs are validated by store:

- BookLive fields accept BookLive product links;
- BOOK☆WALKER fields accept BOOK☆WALKER product links;
- DMM fields accept DMM Books product links.

A manually changed URL is treated as authoritative.

If you clear an existing store URL and save, that store match is removed entirely, including:

- the store URL;
- product ID;
- current price/reward data;
- that offer's price history.

The canonical book and its other store matches remain intact.

### Archive purchased books

Use **Mark purchased** to move books out of the active list and into **Archived**.

Archived books keep their metadata and price history but are excluded from normal matching and update work.

They can be restored later.

### Recently Deleted and recovery

Deleting a book moves it to **Recently Deleted** rather than immediately destroying it.

The default retention period is 14 days and can be changed in Settings.

You can restore deleted items during the retention window or permanently delete them manually.

Merges performed by reconciliation are also recorded so absorbed books can be restored.

### Multiple lists

The tabs across the top work like simple spreadsheet tabs.

- **My List** is the default list.
- Click **+** to create another list.
- **Archived** contains purchased books.

Shared lists are imported into their own list tab rather than silently mixing everything into your main list.

### Backup and sharing

**Backup / Share** includes:

- Save Backup As…
- Restore Backup…
- Export shared book list
- View/import shared book list
- Export price history
- Import price history
- Calibre purchase sync

Before destructive or bulk operations, the app also creates automatic database snapshots and keeps the newest five.

Shared-list files contain public book/store metadata. They do not intentionally contain store passwords, cookies or login sessions.

### Calibre purchase sync

If your Calibre library contains store identifiers, Book Sale Notification can use a Calibre CSV export to archive books you already own.

Supported exact identifiers are:

- `bl:<title_id>:<vol_no>`
- `bw:<BOOKWALKER product UUID>`
- `dmm:<DMM content ID>`

The CSV must contain an `identifiers` column.

Calibre sync uses **exact identifiers only**. It does not use title, author, ISBN or fuzzy matching as a fallback.

A preview is shown before anything is changed.

### Covers

Covers are downloaded from matched product pages and cached locally.

Cover priority is:

1. BookLive
2. BOOK☆WALKER
3. DMM

This prevents a lower-priority source from replacing a good BookLive cover, while still allowing the same store to refresh its own cover later—for example when a preorder placeholder is replaced by the final artwork.

Cover display can be disabled or changed between Small, Medium and Large.

### Light and dark appearance

Settings provides:

- System
- Light
- Dark

The current System option uses the app's conservative light appearance rather than trying to infer Windows dark mode unreliably.

### GitHub updates

Packaged Windows builds include **Check for Updates**.

The app checks the latest release from:

`PickledCakes/BookSaleNotification`

When a newer packaged release is available, the app can download the Windows release ZIP and restart into the new version.

Source-code launches do not self-replace.

---

# Installing the Windows version

The easiest way to use the program is to download the newest Windows package from the GitHub **Releases** page.

The release asset is named similarly to:

`BookSaleNotification-Windows-1.7.1.zip`

1. Download the ZIP.
2. Extract the ZIP somewhere writable, for example your Desktop or Documents folder.
3. Open the extracted **Book Sale Notification** folder.
4. Run **Book Sale Notification.exe**.

The Windows build currently uses PyInstaller's **onedir** format, so the EXE needs the accompanying `_internal` folder. Do not move only the EXE out of the extracted folder.

### Windows SmartScreen

The tester builds are not currently code-signed. Windows may therefore show a SmartScreen / unknown publisher warning even when the file was built by this repository's GitHub Actions workflow.

Only download builds from this repository's Releases page if you want to use the distributed version.

---

# Where your data is stored

The packaged Windows build stores its database separately from the application files:

`%LOCALAPPDATA%\BookSaleNotification\`

This is intentional. Replacing or updating the application folder should not replace your personal database.

Automatic backups are stored below the app data directory.

Cover images are cached separately in the user's home directory under:

`~/.book_sale_notification/covers/`

When running directly from source rather than from the packaged EXE, the database is kept beside the source files.

---

# Saving wishlist HTML

HTML import is meant as a convenient way to seed the database with a large existing wishlist.

You must save the page that actually contains the books. Saving a store homepage, search page, account landing page, or an empty wishlist page will not work.

## General browser steps

For all three stores:

1. Sign in to the store normally in your browser.
2. Open the wishlist / saved-books page containing the books you want to import.
3. Make sure the books are actually visible on the page.
4. If the site uses pagination, import each relevant page or change the site to show as many books per page as possible.
5. If the site lazy-loads items while scrolling, scroll through the list first so the entries have loaded.
6. Press **Ctrl+S** in Chrome/Edge.
7. Save the page as an `.html` / `.htm` file.
   - **Webpage, HTML Only** is the simplest option.
   - **Webpage, Complete** is also fine; the app only reads the HTML file and does not need the companion asset folder.
8. In Book Sale Notification, click **Import HTML…** and choose the saved file.

You can also put one saved HTML file from each store into the same folder and use **Import 3-store folder…**.

## BookLive

1. Sign in to BookLive.
2. Open your BookLive saved/wishlist page containing the books you want to track.
3. Make sure the individual saved-book rows are visible.
4. Load/scroll through all entries you expect to import.
5. Press **Ctrl+S** and save the page as HTML.
6. Import that HTML with **Import HTML…**.

The current parser expects BookLive's saved-list layout and product links containing:

`/product/index/title_id/.../vol_no/...`

If BookLive redesigns that page, HTML import may temporarily stop recognizing entries until the parser is updated.

## BOOK☆WALKER

1. Sign in to BOOK☆WALKER.
2. Open the page containing your saved/favourite books.
3. Ensure the book list itself is visible, not just an account/menu screen.
4. Scroll/load the complete set you want to capture.
5. Save the page with **Ctrl+S**.
6. Import the resulting HTML.

The current wishlist parser recognizes BOOK☆WALKER's saved-item cards and product identities. If the saved file contains only part of a dynamically loaded list, only that part can be imported.

## DMM Books

1. Sign in to DMM Books.
2. Open **あとで買う**.
3. Make sure all books you want are visible on the page.
4. Load/scroll through the relevant entries.
5. Press **Ctrl+S** and save the page as HTML.
6. Import that HTML into Book Sale Notification.

DMM occasionally exposes the newest volume through a moving `/latest/` URL. The live matcher/product scraper resolves that to DMM's permanent content-specific URL before storing it whenever possible.

---

# Recommended first-time workflow

For a large existing wishlist, a good first run is:

1. Save your wishlist HTML from BookLive, BOOK☆WALKER and/or DMM.
2. Import each HTML file.
3. Look over the imported titles before doing matching.
4. Select a small sample and click **Find missing matches**.
5. Inspect the Match Results report.
6. Use **Edit store URLs** to verify any books you are unsure about.
7. Once you are happy with the results, run **Find missing matches** on a larger selection.
8. Select books and use **Update prices → Update everything selected**.
9. Use **History** over time to build your own price record.

For one new book, **Add from URL…** is faster than exporting HTML again.

---

# Main controls

## Import HTML…

Imports one saved wishlist HTML file.

Duplicate detection is based on same-store product identity, not fuzzy title matching.

## Import 3-store folder…

Scans a folder for recognizable BookLive, BOOK☆WALKER and DMM wishlist HTML files and imports them.

## Add from URL…

Adds one product manually and checks all three supported stores before saving it.

## Find missing matches

Searches enabled stores that are missing from the selected books.

- With selected rows: works on those rows.
- With no selection: asks whether to process all active books in the current list.

The operation can also reconcile duplicate canonical entries when they came from different stores and confidently represent the same volume.

## Update prices

Requires one or more selected books.

Choose between:

- covers only;
- only offers currently missing a price;
- everything selected.

## Edit store URLs

Lets you inspect, open, correct, lock or remove individual store associations.

## History

Shows recorded price observations for the selected canonical book.

## Mark purchased

Moves selected active books to Archived.

## Delete

Moves selected books to Recently Deleted.

## Ctrl+A

Selects all currently visible rows.

## Double-click a store cell

Opens that store's public product page for the book.

---

# Settings

## Direct rewards

When enabled:

- DMM can display direct points;
- BOOK☆WALKER can display granted coins.

These rewards are displayed separately and are not subtracted from the lowest cash price.

## BOOK☆WALKER overseas tax mode

When the scraper has an exact stored tax-exclusive price, this setting can display that value for BOOK☆WALKER instead of the domestic tax-inclusive value.

The app does **not** blindly estimate the tax-exclusive amount by subtracting 10%.

## Store toggles

BookLive, BOOK☆WALKER and DMM can be enabled or disabled independently.

A disabled store is:

- hidden from the main comparison view;
- skipped by normal missing-match searches;
- skipped by normal price updates;
- skipped for cover fetching.

Its existing data is not deleted.

The explicit **Add from URL…** workflow checks all three stores because its purpose is to build a complete manual match set.

## Request delay

The minimum delay between store requests can be adjusted.

Please do not set this aggressively low. The app intentionally spaces requests because storefronts may rate-limit or block rapid automated traffic.

## Recently Deleted retention

Controls how long deleted/merged recovery records are retained before cleanup.

## Notification rule / automatic update interval

The settings UI currently contains notification-rule and automatic-update-interval options.

**Important:** in 1.7.1, the normal desktop app does not yet implement an unattended background scheduler or Windows sale-notification service. Price checks are still initiated through the app's update controls. Treat these settings as groundwork for the future notification system rather than a guarantee that the app will wake itself up and notify you.

---

# Matching behaviour and important quirks

## Matching is deliberately conservative

A missing match is better than attaching the wrong volume.

If a store remains blank, inspect the Activity log and try the product manually with **Edit store URLs** or **Add from URL…**.

## HTML import and live matching intentionally behave differently

Wishlist HTML import only trusts exact same-store identity.

It does **not** fuzzy-merge titles.

Cross-store matching happens explicitly through **Find missing matches** or **Add from URL…**.

This separation is deliberate.

## Same-store IDs are important

Two same-store products with different permanent IDs are assumed to be different products, even if their visible titles are very similar.

Do not expect the program to merge those automatically.

## Special editions are not interchangeable

The matcher rejects incompatible edition markers such as `分冊版` versus the normal collected volume.

This is a safety feature, not a failed fuzzy match.

## Manual URLs are authoritative

If you manually replace a store URL, that association becomes locked so ordinary matching does not silently replace your correction.

Clearing the URL is different: it removes that store offer and its history.

## Store pages can change

All three storefront scrapers rely on public webpage markup.

A site redesign can break:

- wishlist HTML import;
- title extraction;
- prices;
- points/coins;
- covers;
- search/matching.

When this happens, check the **Activity** panel. The preferred failure mode is to leave data blank or report an error rather than guess.

## A 403 is not necessarily a bad URL

A storefront may sometimes reject an automated request even though the URL works in your browser.

The matcher will log request failures in Activity and may continue trying other candidates.

## BOOK☆WALKER prices

The app stores domestic and exact tax-exclusive BOOK☆WALKER values separately when the site exposes both.

Tax display mode changes the view; it does not make a new web request.

## DMM points and BOOK☆WALKER coins

Reward values can change independently from the cash price.

They are informational and do not determine the **Lowest cash price** column.

## DMM `/latest/`

DMM can use `/latest/` as a moving alias. That is not a safe permanent identity.

The scraper attempts to resolve it to the permanent product URL before saving.

## Covers are not used to decide matches

Cover-assisted matching is intentionally not implemented at this stage.

A visually identical cover is not treated as identity proof.

## Recorded low means recorded by this app

A historical-low marker only refers to observations present in your database.

It does not claim to know prices from before you started tracking the book.

## Saved HTML can contain private account-page data

Book Sale Notification does not intentionally import cookies or credentials from wishlist HTML, but the raw HTML file itself came from a signed-in browser page and may contain account-related page content.

Do **not** share your saved raw wishlist HTML files publicly.

Use the app's **Export shared book list…** feature when you want to share a list with another user.

## Do not commit your database to GitHub

The repository's `.gitignore` excludes `*.db`.

Your personal `books.db` contains your watchlist/history and should stay local.

---

# Backups and recovery

The app automatically creates a backup before risky operations such as:

- deleting books;
- store-match removal;
- matching/reconciliation;
- manual URL addition;
- shared-list import;
- Calibre bulk archive;
- other bulk updates that can alter stored state.

The newest five automatic backups are retained.

For an extra manual copy, use:

**Backup / Share → Save Backup As…**

before large experiments or testing a new build.

---

# Sharing with another tester

To send your list to somebody without sending your database or signed-in HTML:

1. Open **Backup / Share**.
2. Click **Export shared book list…**.
3. Send the resulting `.bscshare` file.
4. The recipient opens **Backup / Share → View / import shared book list…**.
5. They get a read-only preview first.
6. Nothing is imported until they explicitly click **Import All**.

Price-history observations can be exchanged separately with `.bschistory` files.

---

# Building from source

Python 3.12 is used by the GitHub Actions Windows build.

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Run the source version:

```powershell
py app.py
```

A helper batch file is also included for installing dependencies and another for building with PyInstaller.

---

# Building the Windows release on GitHub

The repository contains:

`.github/workflows/windows-release.yml`

There are two normal ways to use it.

## Test build

Go to:

**GitHub → Actions → Build Windows Release → Run workflow**

This produces a downloadable Actions artifact without publishing a release.

## Public release build

Create/publish a version tag such as:

`v1.7.1`

The workflow builds the Windows package and attaches:

`BookSaleNotification-Windows-1.7.1.zip`

to the GitHub Release.

The packaged application's updater uses published GitHub Releases, not ordinary workflow artifacts.

---

# Privacy and storefront access

The live scraper uses public search/product pages.

The app is not designed to store your store login credentials, account passwords or browser cookies.

Wishlist import is performed from HTML files you explicitly save yourself.

No guarantee is made that storefronts will keep the same public markup or permit the same request behaviour forever.

---

# Current limitations

- Amazon support is disabled.
- Matching is heuristic and intentionally conservative.
- Cover images are not used for identity matching.
- Storefront HTML/search markup can change without warning.
- Some books may require manual URL correction.
- Some product pages may temporarily return HTTP errors or block automated requests.
- The Windows build is currently unsigned.
- Background unattended sale checking / Windows sale notifications are not yet implemented in 1.7.1 despite the presence of related settings.
- This is still a tester-oriented build; keep backups when experimenting.

---

# Feedback

When reporting a problem, the most useful information is:

1. app version;
2. affected book title;
3. affected store;
4. the product URL, if known;
5. what you expected;
6. what happened instead;
7. the relevant text from the **Activity** panel or Match Results report.

Please avoid posting signed-in wishlist HTML publicly. If an HTML sample is required to debug a parser problem, review it for personal/account information first.


## 1.7.2

- Added an in-app **English / 日本語** UI toggle. The selected language is saved and restored on the next launch.
- Japanese mode translates the main window, table headings, tabs, buttons, Settings, backup/share dialogs, manual URL add, update dialogs, recovery dialogs, common message boxes and file-picker labels.
- The diagnostic Activity log may still contain technical English from the live storefront scrapers.
- Fixed the no-cover table layout: rows no longer collapse to a single 24 px line while price/timestamp cells contain multiple lines.
- When covers are hidden, book titles are wrapped to the visible Book column width and the table row height expands to fit the tallest wrapped visible title, while still reserving room for two-line price/timestamp cells.
- Tk's Treeview uses one row height for the whole table, so all currently visible rows share the calculated height rather than having independent Excel-style row heights.
