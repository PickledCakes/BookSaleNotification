from __future__ import annotations
import sys, os, subprocess, tempfile, hashlib, urllib.request, shutil
import json, os, re, sqlite3, sys, unicodedata, webbrowser
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse
import tkinter as tk
import tkinter.font as tkfont
import urllib.request
from io import BytesIO
from tkinter import ttk, filedialog, messagebox, simpledialog
try:
    from PIL import Image, ImageTk
except ImportError:
    Image=ImageTk=None
import csv, shutil, threading, time
from datetime import datetime
from scraper import providers as live_providers

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("Missing dependency: beautifulsoup4. Run: py -m pip install beautifulsoup4")

APP_NAME = "Book Sale Notification 1.7.2"
APP_VERSION = "1.7.2"
# Set these before publishing GitHub releases.
GITHUB_OWNER = "PickledCakes"
GITHUB_REPO = "BookSaleNotification"
UPDATE_ASSET_PREFIX = "BookSaleNotification-Windows-"
def app_data_dir():
    if getattr(sys,"frozen",False):
        base=Path(os.environ.get("LOCALAPPDATA",str(Path.home()/"AppData"/"Local")))
        p=base/"BookSaleNotification"; p.mkdir(parents=True,exist_ok=True); return p
    return Path(__file__).resolve().parent
DATA_DIR=app_data_dir()
DB_PATH=DATA_DIR/"books.db"
STORES = ("BookLive", "BOOK☆WALKER", "DMM")
STORE_KEYS = {"BookLive":"booklive", "BOOK☆WALKER":"bookwalker", "DMM":"dmm"}

UI_LANG="en"
JA_UI={
    "Book Sale Notification":"Book Sale Notification",
    "Settings":"設定","Check for Updates":"アップデート確認","Recently Deleted":"最近削除した項目",
    "Backup / Share":"バックアップ / 共有","Import HTML…":"HTMLを読み込む…",
    "Add from URL…":"URLから追加…","Import 3-store folder…":"3ストアHTMLフォルダを読み込む…",
    "BookLive + BOOK☆WALKER + DMM active • Amazon intentionally disabled":
        "BookLive + BOOK☆WALKER + DMM 対応 • Amazon は現在無効",
    "Search:":"検索:","Delete":"削除","History":"履歴","Mark purchased":"購入済みにする",
    "Edit store URLs":"ストアURLを編集","Find missing matches":"未登録ストアを検索","Update prices":"価格を更新",
    "Book":"書籍","Lowest cash price":"現金最安値","Matched":"一致数","Cover":"表紙",
    "Activity":"アクティビティ","Clear":"クリア","My List":"マイリスト","Archived":"アーカイブ",
    "Match Results":"照合結果","Close":"閉じる","Copy Log":"ログをコピー",
    "Reason":"理由","Deleted":"削除日時","Restore selected":"選択項目を復元",
    "Permanently delete selected":"選択項目を完全に削除",
    "New list":"新しいリスト","List name:":"リスト名:",
    "Select a book":"書籍を選択","Select a book first.":"先に書籍を選択してください。",
    "Select a book first, then click Edit store URLs.":"先に書籍を選択してから「ストアURLを編集」を押してください。",
    "Select one or more books first.":"1冊以上の書籍を選択してください。",
    "Delete books":"書籍を削除","Update":"更新","Updates":"アップデート",
    "Update selected books":"選択した書籍を更新","Start update":"更新開始",
    "Update covers only":"表紙のみ更新","Update books without price":"価格未取得のみ更新",
    "Update everything selected":"選択したすべてを更新",
    "Fetch product pages only to refresh/cache cover images. Prices and price history are not changed.":
        "商品ページから表紙のみを更新・キャッシュします。価格と価格履歴は変更しません。",
    "Only update matched store offers whose current price is missing.":
        "現在価格が未取得の一致済みストアだけを更新します。",
    "Refresh price, rewards and cover for every matched offer on the selected books.":
        "選択した書籍の一致済みストアについて、価格・特典・表紙をすべて更新します。",
    "Choose what should be refreshed. Only enabled stores with an existing product URL are contacted.":
        "更新内容を選択してください。既存の商品URLがある有効なストアだけにアクセスします。",
    "No matched product pages meet the selected update mode.":"選択した更新条件に該当する商品ページがありません。",
    "Edit store URLs":"ストアURLを編集",
    "Current database URLs for the three active stores. Editing a URL manually locks that store match.":
        "3ストアの現在の登録URLです。URLを手動編集すると、そのストアの照合結果は固定されます。",
    "Open":"開く","Save changes":"変更を保存","Invalid store URL":"無効なストアURL",
    "Add book from store URL":"ストアURLから書籍を追加",
    "Add from BookLive / BOOK☆WALKER / DMM URL":"BookLive / BOOK☆WALKER / DMM のURLから追加",
    "Paste one product URL. The app will fetch that exact product, then search the other two stores and fetch their product pages before adding anything to the list.":
        "商品URLを1つ貼り付けてください。その商品を取得後、残り2ストアも検索し、商品ページを取得してからリストに追加します。",
    "Fetch all stores and add":"3ストアを確認して追加","Cancel":"キャンセル",
    "Paste a valid BookLive, BOOK☆WALKER or DMM Books product URL.":
        "有効なBookLive、BOOK☆WALKER、またはDMM Booksの商品URLを貼り付けてください。",
    "Import wishlist HTML":"ウィッシュリストHTMLを読み込む",
    "Choose folder containing DMM, BookLive and BOOK☆WALKER HTML files":
        "DMM・BookLive・BOOK☆WALKERのHTMLが入ったフォルダを選択",
    "Import complete":"読み込み完了","Import failed":"読み込み失敗","Folder import":"フォルダ読み込み",
    "Price history — ":"価格履歴 — ","Observed":"取得日時","Store":"ストア","Cash price":"現金価格",
    "List price":"通常価格","Reward":"特典","Source":"取得元",
    "Backup, restore & sharing":"バックアップ・復元・共有","Private recovery":"個人用バックアップ",
    "Save Backup As…":"バックアップを保存…","Restore Backup…":"バックアップを復元…",
    "Portable sharing":"共有","Export shared book list…":"共有用書籍リストを書き出す…",
    "View / import shared book list…":"共有用書籍リストを表示 / 読み込む…",
    "Export price history…":"価格履歴を書き出す…","Import price history…":"価格履歴を読み込む…",
    "Calibre library":"Calibreライブラリ","Sync purchased books from Calibre CSV…":"Calibre CSVから購入済みを同期…",
    "Share files contain public book/store data only — no source HTML, cookies, login state or account data.":
        "共有ファイルには公開されている書籍・ストア情報のみが含まれます。HTML、Cookie、ログイン情報、アカウント情報は含みません。",
    "Backup":"バックアップ","Backup saved.":"バックアップを保存しました。",
    "Restore":"復元","Restore this backup? Current state was safety-backed-up first.":
        "このバックアップを復元しますか？現在の状態は先に安全バックアップされています。",
    "Shared List — View only":"共有リスト — 表示のみ","Known stores":"登録ストア",
    "Import All":"すべて読み込む","Close without importing":"読み込まず閉じる",
    "Exported":"書き出し完了","History imported":"履歴の読み込み完了",
    "Calibre Sync":"Calibre同期","Calibre Sync Preview":"Calibre同期プレビュー",
    "Select Calibre CSV export":"CalibreのCSV書き出しを選択",
    "CSV must contain an 'identifiers' column.":"CSVには 'identifiers' 列が必要です。",
    "Copy Preview":"プレビューをコピー","Archive matched books":"一致した書籍をアーカイブ",
    "No active wishlist books matched exact Calibre identifiers.":
        "有効なウィッシュリスト内にCalibre識別子と完全一致する書籍がありません。",
    "Notification rule":"通知ルール","Any sale":"セールなら通知","Lowest recorded price":"記録上の最安値",
    "Good deal":"お得な価格","Good-deal threshold (> %):":"お得判定の割引率 (> %):",
    "Show direct DMM points / BOOK☆WALKER coins in store price columns":
        "DMMポイント / BOOK☆WALKERコインを価格欄に表示",
    "BOOK☆WALKER overseas tax mode (show stored tax-exclusive price when known)":
        "BOOK☆WALKER海外税モード（取得済みの税抜価格があれば表示）",
    "Cover display":"表紙表示","Show book covers":"表紙を表示","Cover size:":"表紙サイズ:",
    "Small":"小","Medium":"中","Large":"大","Stores":"ストア",
    "Disabled stores are hidden and skipped by matching, updates and cover fetching.":
        "無効にしたストアは非表示になり、照合・更新・表紙取得を行いません。",
    "Automatic update interval (hours):":"自動更新間隔（時間）:",
    "Minimum delay between store requests (seconds):":"ストアへの最低アクセス間隔（秒）:",
    "Appearance:":"外観:","Recently Deleted retention (days):":"最近削除した項目の保持日数:",
    "Live matching is accuracy-first. A low-confidence result is left blank rather than attached to the wrong volume.":
        "照合は正確さを優先します。確信度が低い場合は、誤った巻を登録せず空欄のままにします。",
    "Save":"保存","System":"システム","Light":"ライト","Dark":"ダーク",
    "Recently Deleted retention (days):":"最近削除した項目の保持日数:",
    "Check for Updates":"アップデート確認","Update available":"アップデートがあります",
    "Update failed":"アップデート失敗","Update check failed":"アップデート確認失敗",
    "Automatic installation is available in the packaged Windows build.":
        "自動インストールは配布版Windowsアプリで利用できます。",
    "GitHub updates are not configured in this build yet.":"このビルドではGitHubアップデートが設定されていません。",
    "Release asset has no download URL.":"リリースファイルのダウンロードURLがありません。",
    "Ready":"準備完了","Same":"同額","price unavailable":"価格未取得",
    "HTML files":"HTMLファイル","All files":"すべてのファイル","CSV files":"CSVファイル","JSON":"JSON",
    "Book Sale shared list":"Book Sale共有リスト","Book Sale history":"Book Sale価格履歴",
    "No book is selected. Match/reconcile ALL active books in this list?":
        "書籍が選択されていません。このリスト内の有効な書籍をすべて照合しますか？",
    "delete":"削除","merge":"統合"
}

def ui_tr(value):
    if UI_LANG!="ja" or not isinstance(value,str):
        return value
    if value in JA_UI:
        return JA_UI[value]
    # Common dynamic UI strings.
    patterns=[
        (r"^Update (\d+) selected book\(s\)$", lambda m:f"選択した {m.group(1)} 冊を更新"),
        (r"^Items are kept for (\d+) days\.$", lambda m:f"項目は {m.group(1)} 日間保持されます。"),
        (r"^(\d+) canonical books shown • Double-click a store cell to open its public product page$",
            lambda m:f"{m.group(1)} 冊表示 • ストア欄をダブルクリックすると商品ページを開きます"),
        (r"^Version (.+) is available\.", lambda m:f"バージョン {m.group(1)} を利用できます。"),
        (r"^Downloading (.+)…$", lambda m:f"{m.group(1)} をダウンロード中…"),
        (r"^Searching (.+)…$", lambda m:f"{m.group(1)} を検索中…"),
        (r"^Reading (.+) product…$", lambda m:f"{m.group(1)} の商品情報を取得中…"),
        (r"^Updating (\d+)/(\d+) • (.+)$", lambda m:f"更新中 {m.group(1)}/{m.group(2)} • {m.group(3)}"),
        (r"^VIEW ONLY • (\d+) books • Nothing is imported until you press Import All$",
            lambda m:f"表示のみ • {m.group(1)} 冊 • 「すべて読み込む」を押すまで変更されません"),
        (r"^Exported (\d+) books\.$", lambda m:f"{m.group(1)} 冊を書き出しました。"),
        (r"^Exported (\d+) observations\.$", lambda m:f"{m.group(1)} 件の履歴を書き出しました。"),
        (r"^Merged (\d+) historical observations\.$", lambda m:f"{m.group(1)} 件の履歴を統合しました。"),
    ]
    for pat,fn in patterns:
        m=re.match(pat,value,re.S)
        if m:return fn(m)
    return value

def _install_i18n_hooks():
    """Translate ordinary Tk/ttk UI text without changing stored data values."""
    if getattr(_install_i18n_hooks,"done",False): return
    _install_i18n_hooks.done=True

    def patch_init(cls):
        original=cls.__init__
        def wrapped(self,*args,**kwargs):
            if "text" in kwargs: kwargs["text"]=ui_tr(kwargs["text"])
            return original(self,*args,**kwargs)
        cls.__init__=wrapped

    for cls in (ttk.Label,ttk.Button,ttk.Checkbutton,ttk.Radiobutton,tk.Label,tk.Button):
        patch_init(cls)

    original_heading=ttk.Treeview.heading
    def heading(self,column,option=None,**kwargs):
        if "text" in kwargs: kwargs["text"]=ui_tr(kwargs["text"])
        return original_heading(self,column,option,**kwargs)
    ttk.Treeview.heading=heading

    original_add=ttk.Notebook.add
    def add(self,child,**kwargs):
        if "text" in kwargs: kwargs["text"]=ui_tr(kwargs["text"])
        return original_add(self,child,**kwargs)
    ttk.Notebook.add=add

    original_title=tk.Wm.title
    def title(self,string=None):
        return original_title(self,ui_tr(string)) if string is not None else original_title(self)
    tk.Wm.title=title

    for name in ("showinfo","showerror","askyesno","showwarning"):
        original=getattr(messagebox,name)
        def make(orig):
            def wrapped(title,message,*args,**kwargs):
                return orig(ui_tr(title),ui_tr(message),*args,**kwargs)
            return wrapped
        setattr(messagebox,name,make(original))

    for name in ("askopenfilename","asksaveasfilename","askdirectory"):
        original=getattr(filedialog,name)
        def make(orig):
            def wrapped(*args,**kwargs):
                if "title" in kwargs: kwargs["title"]=ui_tr(kwargs["title"])
                if "filetypes" in kwargs:
                    kwargs["filetypes"]=[(ui_tr(label),pat) for label,pat in kwargs["filetypes"]]
                return orig(*args,**kwargs)
            return wrapped
        setattr(filedialog,name,make(original))

    original_askstring=simpledialog.askstring
    def askstring(title,prompt,*args,**kwargs):
        return original_askstring(ui_tr(title),ui_tr(prompt),*args,**kwargs)
    simpledialog.askstring=askstring

class UIStatusVar(tk.StringVar):
    def set(self,value):
        super().set(ui_tr(value))

_install_i18n_hooks()

@dataclass
class Offer:
    store: str
    title: str
    url: str
    price: int | None = None
    list_price: int | None = None
    reward_pct: float | None = None
    reward_value: int | None = None
    tax_ex_price: int | None = None
    cover_url: str = ""
    author: str = ""
    store_id: str = ""
    flags: str = ""

def yen(text):
    if not text: return None
    m = re.search(r'(?:¥|￥)?\s*([0-9][0-9,]*)\s*円?', text)
    return int(m.group(1).replace(",", "")) if m else None

def normalize_title(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r'[\s　]+', '', s)
    s = re.sub(r'[【】\[\]（）()「」『』〈〉《》:：・･!！?？,，.。~〜～\-—―_]+', '', s)
    # Remove common store-only promotional decorations, not meaningful edition text.
    s = re.sub(r'(kindleedition|マーガレットコミックスdigital)$', '', s)
    return s

def title_similarity(a, b):
    a, b = normalize_title(a), normalize_title(b)
    if not a or not b: return 0
    if a == b: return 1.0
    return SequenceMatcher(None, a, b).ratio()

def canonical_url(url):
    if not url: return ""
    return url.split("?")[0].split("#")[0]

def valid_store_url(store, url):
    """Validate that a manually entered URL belongs to the selected storefront."""
    try:
        u=urlparse((url or "").strip())
        host=(u.hostname or "").lower().rstrip(".")
        path=u.path or "/"
    except Exception:
        return False
    if u.scheme not in ("http","https") or not host:
        return False
    if store=="BookLive":
        return (host=="booklive.jp" or host.endswith(".booklive.jp")) and "/product/" in path
    if store=="BOOK☆WALKER":
        return (host=="bookwalker.jp" or host.endswith(".bookwalker.jp")) and bool(re.search(r"/de[0-9A-Za-z-]+/?",path,re.I))
    if store=="DMM":
        return (host=="book.dmm.com" or host.endswith(".book.dmm.com")) and "/product/" in path
    return False

def parse_amazon(soup):
    out = []
    for item in soup.select(".g-item-sortable"):
        text = item.get_text(" ", strip=True)
        if "Kindle" not in text and "Digital" not in text:
            continue
        links = [a for a in item.find_all("a", href=True)
                 if "/dp/" in a["href"] and a.get_text(" ", strip=True)
                 and a.get_text(" ", strip=True).lower() not in {"see all buying options"}]
        if not links: continue
        # Wishlist title links normally use the dp_it ref. Prefer them over action links.
        preferred = [a for a in links if "dp_it" in a.get("href","")]
        a = max(preferred or links, key=lambda x: len(x.get_text(" ", strip=True)))
        title = a.get_text(" ", strip=True)
        title = re.sub(r'\s*\(Kindle Edition\)\s*$', '', title, flags=re.I)
        # Prefer explicit price spans when present.
        p = None
        for sel in (".a-price .a-offscreen", ".itemPriceDrop", ".a-price-whole"):
            node = item.select_one(sel)
            if node:
                p = yen(node.get_text(" ", strip=True))
                if p is not None: break
        if p is None:
            m = re.search(r'[¥￥]\s*([0-9][0-9,]*)', text)
            p = int(m.group(1).replace(",","")) if m else None
        author = ""
        m = re.search(r'\bby\s+(.+?)\s+\(Kindle Edition\)', text, re.I)
        if m: author = m.group(1).strip()
        url = canonical_url(a["href"])
        mid = re.search(r'/dp/([A-Z0-9]{10})', url, re.I)
        out.append(Offer("Amazon", title, url, p, author=author,
                         store_id=mid.group(1).upper() if mid else ""))
    return dedupe(out)

def parse_booklive(soup):
    out = []
    for row in soup.select("ul.save_list"):
        li = row.select_one("li.title")
        if not li: continue
        a = li.select_one("p.book_name a[href*='/product/index/title_id/']")
        if not a: continue
        title = a.get_text(" ", strip=True)
        url = canonical_url(a.get("href",""))
        text = row.get_text(" ", strip=True)
        price_node = row.select_one("li.price")
        p = yen(price_node.get_text(" ", strip=True)) if price_node else None
        authors = []
        tw = li.select_one(".title_wrap")
        if tw:
            for aa in tw.select("a"):
                href = aa.get("href","")
                if "/author/" in href or "/search/" in href:
                    t = aa.get_text(" ", strip=True)
                    if t and t != title: authors.append(t)
        m = re.search(r'title_id/(\d+)/vol_no/(\d+)', url)
        sid = f"{m.group(1)}:{m.group(2)}" if m else ""
        flags = "sale" if "値引き" in text or "無料" in text else ""
        out.append(Offer("BookLive", title, url, p, author=" / ".join(dict.fromkeys(authors)),
                         store_id=sid, flags=flags))
    return dedupe(out)

def parse_bookwalker(soup):
    out = []
    for unit in soup.select(".bw_checklist_unit"):
        links = [a for a in unit.find_all("a", href=True)
                 if re.search(r'bookwalker\.jp/[0-9a-f-]{30,}/?$', canonical_url(a["href"]), re.I)]
        if not links: continue
        a = max(links, key=lambda x: len(x.get_text(" ", strip=True)))
        title = a.get_text(" ", strip=True)
        if not title:
            candidates = [x.get_text(" ", strip=True) for x in links if x.get_text(" ", strip=True)]
            title = max(candidates, key=len) if candidates else ""
        text = unit.get_text(" ", strip=True)
        prices = [int(x.replace(",","")) for x in re.findall(r'([0-9][0-9,]*)\s*円', text)]
        price = prices[-1] if prices else None
        list_price = prices[0] if len(prices) >= 2 and price is not None and prices[0] > price else None
        tax_ex_price = None
        cb=unit.select_one("[pricewithouttax]")
        if cb:
            tax_ex_price=yen(cb.get("pricewithouttax",""))
            attr_price=yen(cb.get("price",""))
            if attr_price is not None: price=attr_price
        reward = None
        mcoin = re.search(r'([0-9][0-9,]*)\s*(?:コイン|coin)', text, re.I)
        if mcoin: reward = int(mcoin.group(1).replace(",",""))
        author = ""
        ma = re.search(r'著者[：:]\s*(.+?)(?=\s+[0-9][0-9,]*\s*円|\s+削除|\s+カート|$)', text)
        if ma: author = ma.group(1).strip()
        url = canonical_url(a["href"])
        sid = url.rstrip("/").split("/")[-1]
        out.append(Offer("BOOK☆WALKER", title, url, price, list_price=list_price,
                         reward_value=reward, tax_ex_price=tax_ex_price, author=author, store_id=sid))
    return dedupe(out)

def parse_dmm(soup):
    out = []
    for row in soup.select("table.fn-bookmarkList tr.fn-listContainer"):
        a = row.select_one("a.m-bookmarkListTitleSection__titleContainer[href*='book.dmm.com/product/']")
        if not a: continue
        raw = a.get_text(" ", strip=True)
        title = re.sub(r'^(?:還元\s*)?(?:予約\s*)?', '', raw).strip()
        text = row.get_text(" ", strip=True)
        price_node = row.select_one("span.price")
        p = yen(price_node.get_text(" ", strip=True)) if price_node else None
        rp = None
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)%\s*pt還元', text, re.I)
        if m: rp = float(m.group(1))
        url = canonical_url(a["href"])
        mid = re.search(r'/product/(\d+)/([^/]+)', url)
        sid = f"{mid.group(1)}:{mid.group(2)}" if mid else ""
        flags = "preorder" if "予約" in raw else ""
        out.append(Offer("DMM", title, url, p, reward_pct=rp, store_id=sid, flags=flags))
    return dedupe(out)

def dedupe(items):
    seen, out = set(), []
    for x in items:
        key = x.store_id or canonical_url(x.url) or normalize_title(x.title)
        if key in seen: continue
        seen.add(key); out.append(x)
    return out

def detect_store(soup, filename=""):
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    hay = (title + " " + filename).lower()
    if "amazon" in hay or soup.select_one(".g-item-sortable"): return "Amazon (disabled in 1.1)"
    if "bookwalker" in hay or soup.select_one(".bw_checklist_unit"): return "BOOK☆WALKER"
    if "dmm" in hay or soup.select_one("table.fn-bookmarkList"): return "DMM"
    if "ブックライブ" in hay or "booklive" in hay or soup.select_one("ul.save_list"): return "BookLive"
    return None

PARSERS = {"BookLive":parse_booklive, "BOOK☆WALKER":parse_bookwalker, "DMM":parse_dmm}

class DB:
    def __init__(self, path=DB_PATH):
        self.cx = sqlite3.connect(path)
        self.cx.row_factory = sqlite3.Row
        self.cx.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS books(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, norm_title TEXT NOT NULL,
          author TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'active',
          cover_url TEXT DEFAULT '', cover_path TEXT DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS offers(
          id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
          store TEXT NOT NULL, store_id TEXT DEFAULT '', title TEXT NOT NULL, url TEXT NOT NULL,
          price INTEGER, list_price INTEGER, reward_pct REAL, reward_value INTEGER,
          tax_ex_price INTEGER, author TEXT DEFAULT '', flags TEXT DEFAULT '', locked INTEGER NOT NULL DEFAULT 0,
          observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(store, store_id), UNIQUE(store, url)
        );
        CREATE TABLE IF NOT EXISTS price_history(
          id INTEGER PRIMARY KEY, offer_id INTEGER NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
          observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, price INTEGER, list_price INTEGER,
          reward_pct REAL, reward_value INTEGER, provenance TEXT NOT NULL DEFAULT 'local',
          UNIQUE(offer_id, observed_at, price, reward_pct, reward_value)
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lists(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, sort_order INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS list_books(list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE, book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE, PRIMARY KEY(list_id,book_id));
        CREATE TABLE IF NOT EXISTS trash(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL, deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        """)
        self.cx.execute("INSERT OR IGNORE INTO lists(id,name,sort_order) VALUES(1,'My List',0)")
        self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) SELECT 1,id FROM books WHERE status!='purchased'")
        try:
            self.cx.execute("ALTER TABLE price_history ADD COLUMN provenance TEXT NOT NULL DEFAULT 'local'")
        except sqlite3.OperationalError:
            pass
        try:
            self.cx.execute("ALTER TABLE offers ADD COLUMN tax_ex_price INTEGER")
        except sqlite3.OperationalError:
            pass
        for col in ("cover_url TEXT DEFAULT ''","cover_path TEXT DEFAULT ''"):
            try: self.cx.execute("ALTER TABLE books ADD COLUMN "+col)
            except sqlite3.OperationalError: pass
        self.cx.commit()

    def offer_identity(self, offer):
        return (offer.store, offer.store_id or "", canonical_url(offer.url))

    def import_offer(self, offer, list_id=1):
        """Wishlist import: same-store identity only. Never fuzzy-merge titles."""
        url=canonical_url(offer.url); offer.url=url
        r=self.cx.execute("SELECT id,book_id,locked FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",
                          (offer.store,offer.store_id,url)).fetchone()
        if r:
            bid=r['book_id']; oid=r['id']
            if not r['locked']:
                self.cx.execute("""UPDATE offers SET title=?,price=?,list_price=?,reward_pct=?,reward_value=?,tax_ex_price=?,author=?,flags=?,observed_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (offer.title,offer.price,offer.list_price,offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags,oid))
            self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) VALUES(?,?)",(list_id,bid))
            self.cx.commit(); return bid,False
        cur=self.cx.execute("INSERT INTO books(title,norm_title,author) VALUES(?,?,?)",(offer.title,normalize_title(offer.title),offer.author)); bid=cur.lastrowid
        cur=self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,price,list_price,reward_pct,reward_value,tax_ex_price,author,flags) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bid,offer.store,offer.store_id,offer.title,url,offer.price,offer.list_price,offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags)); oid=cur.lastrowid
        self.cx.execute("INSERT OR IGNORE INTO price_history(offer_id,price,list_price,reward_pct,reward_value) VALUES(?,?,?,?,?)",(oid,offer.price,offer.list_price,offer.reward_pct,offer.reward_value))
        self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) VALUES(?,?)",(list_id,bid)); self.cx.commit(); return bid,True

    def import_manual_bundle(self, primary, offers, list_id=1):
        """Atomically add one manually supplied product and exact cross-store matches.

        Unlike wishlist HTML import, this is an explicit reconciliation operation:
        the supplied product is authoritative and the other store offers have already
        been matched by the live providers before this method is called.
        """
        offers=[o for o in offers if o and o.store in STORES]
        if not offers:
            raise ValueError("No valid store products were found.")

        # If any exact product identity is already known, reuse that canonical book.
        existing_ids=set()
        for o in offers:
            url=canonical_url(o.url)
            row=self.cx.execute(
                "SELECT book_id FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",
                (o.store,o.store_id or "",url)
            ).fetchone()
            if row: existing_ids.add(row["book_id"])
        if len(existing_ids)>1:
            raise ValueError("The matched store products already belong to different books. Use Find Missing Matches first.")
        if existing_ids:
            bid=next(iter(existing_ids))
        else:
            cur=self.cx.execute("INSERT INTO books(title,norm_title,author) VALUES(?,?,?)",
                                (primary.title,normalize_title(primary.title),primary.author or ""))
            bid=cur.lastrowid

        self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) VALUES(?,?)",(list_id,bid))

        for o in offers:
            url=canonical_url(o.url)
            exact=self.cx.execute(
                "SELECT id,book_id FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",
                (o.store,o.store_id or "",url)
            ).fetchone()
            if exact:
                if exact["book_id"]!=bid:
                    raise ValueError(f"{o.store} exact product is already attached to another book.")
                oid=exact["id"]
                self.cx.execute("""UPDATE offers SET title=?,url=?,price=?,list_price=?,reward_pct=?,
                    reward_value=?,tax_ex_price=?,author=?,flags=?,observed_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (o.title,url,o.price,o.list_price,o.reward_pct,o.reward_value,o.tax_ex_price,
                     o.author,o.flags,oid))
            else:
                same_store=self.cx.execute("SELECT id FROM offers WHERE book_id=? AND store=?",(bid,o.store)).fetchone()
                if same_store:
                    # Never replace a different same-store identity implicitly.
                    continue
                cur=self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,price,list_price,
                    reward_pct,reward_value,tax_ex_price,author,flags,locked,observed_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,CURRENT_TIMESTAMP)""",
                    (bid,o.store,o.store_id,o.title,url,o.price,o.list_price,o.reward_pct,
                     o.reward_value,o.tax_ex_price,o.author,o.flags))
                oid=cur.lastrowid
            self.cx.execute("""INSERT OR IGNORE INTO price_history
                (offer_id,price,list_price,reward_pct,reward_value) VALUES(?,?,?,?,?)""",
                (oid,o.price,o.list_price,o.reward_pct,o.reward_value))

        self.cx.execute("UPDATE books SET title=?,norm_title=?,author=? WHERE id=?",
                        (primary.title,normalize_title(primary.title),primary.author or "",bid))
        self.cx.commit()
        return bid

    def find_book(self, offer):
        r=self.cx.execute("SELECT book_id FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",(offer.store,offer.store_id,canonical_url(offer.url))).fetchone()
        if r:return r['book_id'],1.0
        rows=self.cx.execute("SELECT id,title FROM books WHERE status='active'").fetchall(); best=None;score=0
        for row in rows:
            s=title_similarity(offer.title,row['title'])
            if s>score:best,score=row['id'],s
        return (best,score) if score>=.965 else (None,score)

    def add_offer(self, offer):
        """Matcher path only: attach cross-store result to a canonical book when possible."""
        bid,score=self.find_book(offer)
        if bid is None:
            return self.import_offer(offer,1)[0]
        same=self.cx.execute("SELECT id FROM offers WHERE book_id=? AND store=?",(bid,offer.store)).fetchone()
        if same:return bid
        cur=self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,price,list_price,reward_pct,reward_value,tax_ex_price,author,flags) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bid,offer.store,offer.store_id,offer.title,canonical_url(offer.url),offer.price,offer.list_price,offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags)); oid=cur.lastrowid
        self.cx.execute("INSERT OR IGNORE INTO price_history(offer_id,price,list_price,reward_pct,reward_value) VALUES(?,?,?,?,?)",(oid,offer.price,offer.list_price,offer.reward_pct,offer.reward_value)); self.cx.commit(); return bid

    def update_offer_for_book(self, book_id, store, offer):
        """Refresh one already-associated store offer without canonical rematching."""
        row=self.cx.execute("SELECT * FROM offers WHERE book_id=? AND store=?",(book_id,store)).fetchone()
        if not row:
            # Defensive fallback for a known book/store slot: create it on THIS book only.
            cur=self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,price,list_price,
                reward_pct,reward_value,tax_ex_price,author,flags,locked,observed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,CURRENT_TIMESTAMP)""",
                (book_id,store,offer.store_id,offer.title,offer.url,offer.price,offer.list_price,
                 offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags))
            oid=cur.lastrowid
        else:
            oid=row["id"]
            # Manual/locked URLs remain authoritative. For unlocked offers the provider's
            # canonical URL/ID may be refreshed, but the offer stays attached to this book.
            new_url=row["url"] if row["locked"] else (offer.url or row["url"])
            new_store_id=row["store_id"] if row["locked"] and row["store_id"] else (offer.store_id or row["store_id"])
            self.cx.execute("""UPDATE offers SET store_id=?,title=?,url=?,price=?,list_price=?,
                reward_pct=?,reward_value=?,tax_ex_price=?,author=?,flags=?,observed_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (new_store_id,offer.title or row["title"],new_url,offer.price,offer.list_price,
                 offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags,oid))
        self.cx.execute("""INSERT OR IGNORE INTO price_history(offer_id,price,list_price,reward_pct,reward_value)
                           VALUES(?,?,?,?,?)""",
                        (oid,offer.price,offer.list_price,offer.reward_pct,offer.reward_value))
        self.cx.commit()
        return book_id

    def set_cover(self,bid,url,path):
        self.cx.execute("UPDATE books SET cover_url=?,cover_path=? WHERE id=?",(url,path,bid)); self.cx.commit()

    def rows(self, search="", include_purchased=False, list_id=1, archived=False):
        where = "b.status='purchased'" if archived else ("1=1" if include_purchased else "b.status='active'")
        args = []
        if not archived:
            where += " AND EXISTS(SELECT 1 FROM list_books lb WHERE lb.book_id=b.id AND lb.list_id=?)"; args.append(list_id)
        if search:
            where += " AND b.title LIKE ?"; args.append("%"+search+"%")
        books = self.cx.execute(f"SELECT * FROM books b WHERE {where} ORDER BY b.title COLLATE NOCASE",args).fetchall()
        out=[]
        for b in books:
            offers=self.cx.execute("SELECT * FROM offers WHERE book_id=?",(b["id"],)).fetchall()
            out.append((b, {o["store"]:o for o in offers}))
        return out

    def calibre_identifier_index(self):
        """Exact supported Calibre identifier -> canonical book mapping."""
        idx={}
        rows=self.cx.execute("SELECT o.book_id,o.store,o.store_id,o.url,b.title,b.status FROM offers o JOIN books b ON b.id=o.book_id").fetchall()
        for r in rows:
            sid=(r["store_id"] or "").strip()
            url=r["url"] or ""
            keys=[]
            if r["store"]=="BookLive":
                # Stored identity is normally bl:title_id:vol_no. Also derive from URL if needed.
                if sid.startswith("bl:"): keys.append(sid.lower())
                m=re.search(r'/product/index/title_id/(\d+)/vol_no/(\d+)',url,re.I)
                if m: keys.append(f"bl:{m.group(1)}:{m.group(2)}".lower())
            elif r["store"]=="BOOK☆WALKER":
                raw=sid
                if raw.lower().startswith("bw:"): raw=raw[3:]
                if not raw:
                    m=re.search(r'/de([0-9a-f-]{20,})/?',url,re.I)
                    if m: raw=m.group(1)
                if raw: keys.append(("bw:"+raw).lower())
            elif r["store"]=="DMM":
                raw=sid
                if raw.lower().startswith("dmm:"): raw=raw[4:]
                if not raw:
                    m=re.search(r'/product/\d+/([^/?#]+)/?',url,re.I)
                    if m and m.group(1).lower()!="latest": raw=m.group(1)
                if raw: keys.append(("dmm:"+raw).lower())
            for key in keys:
                idx[key]={"book_id":r["book_id"],"title":r["title"],"status":r["status"],"store":r["store"]}
        return idx

    def set_purchased(self, book_id, purchased=True):
        self.cx.execute("UPDATE books SET status=? WHERE id=?",("purchased" if purchased else "active",book_id)); self.cx.commit()

    def remove_store_match(self, book_id, store):
        """Remove one store association and all data/history belonging to that offer."""
        row=self.cx.execute("SELECT id FROM offers WHERE book_id=? AND store=?",(book_id,store)).fetchone()
        if not row:return False
        self.cx.execute("DELETE FROM price_history WHERE offer_id=?",(row["id"],))
        self.cx.execute("DELETE FROM offers WHERE id=?",(row["id"],))
        self.cx.commit()
        return True

    def set_url(self, book_id, store, url):
        row=self.cx.execute("SELECT * FROM offers WHERE book_id=? AND store=?",(book_id,store)).fetchone()
        if row:
            self.cx.execute("UPDATE offers SET url=?,locked=1 WHERE id=?",(url,row["id"]))
        else:
            self.cx.execute("""INSERT INTO offers(book_id,store,title,url,locked) 
                               SELECT ?,?,title,?,1 FROM books WHERE id=?""",(book_id,store,url,book_id))
        self.cx.commit()

    def get_setting(self,key,default=""):
        r=self.cx.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self,key,value):
        self.cx.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key,str(value))); self.cx.commit()

    def delete_book(self,book_id):
        self.snapshot_book(book_id,'delete'); self.cx.execute("DELETE FROM books WHERE id=?",(book_id,)); self.cx.commit()

    def list_rows(self):
        return self.cx.execute("SELECT * FROM lists ORDER BY sort_order,id").fetchall()

    def create_list(self,name):
        cur=self.cx.execute("INSERT INTO lists(name,sort_order) VALUES(?,(SELECT COALESCE(MAX(sort_order),0)+1 FROM lists))",(name,)); self.cx.commit(); return cur.lastrowid

    def snapshot_book(self,bid,kind='delete'):
        b=self.cx.execute("SELECT * FROM books WHERE id=?",(bid,)).fetchone()
        if not b:return
        offers=[dict(x) for x in self.cx.execute("SELECT * FROM offers WHERE book_id=?",(bid,))]
        histories=[]
        for o in offers: histories += [dict(x) for x in self.cx.execute("SELECT * FROM price_history WHERE offer_id=?",(o['id'],))]
        lists=[x['list_id'] for x in self.cx.execute("SELECT list_id FROM list_books WHERE book_id=?",(bid,))]
        payload=json.dumps({'book':dict(b),'offers':offers,'history':histories,'lists':lists},ensure_ascii=False)
        self.cx.execute("INSERT INTO trash(kind,title,payload) VALUES(?,?,?)",(kind,b['title'],payload)); self.cx.commit()

    def restore_trash(self,tid):
        r=self.cx.execute("SELECT * FROM trash WHERE id=?",(tid,)).fetchone(); d=json.loads(r['payload']); b=d['book']
        cur=self.cx.execute("INSERT INTO books(title,norm_title,author,status,cover_url,cover_path,created_at) VALUES(?,?,?,?,?,?,?)",(b['title'],b['norm_title'],b['author'],b['status'],b.get('cover_url',''),b.get('cover_path',''),b['created_at'])); nb=cur.lastrowid
        omap={}
        for o in d['offers']:
            cur=self.cx.execute("""INSERT OR IGNORE INTO offers(book_id,store,store_id,title,url,price,list_price,reward_pct,reward_value,tax_ex_price,author,flags,locked,observed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(nb,o['store'],o['store_id'],o['title'],o['url'],o['price'],o['list_price'],o['reward_pct'],o['reward_value'],o.get('tax_ex_price'),o['author'],o['flags'],o['locked'],o['observed_at']))
            if cur.lastrowid:omap[o['id']]=cur.lastrowid
        for h in d['history']:
            if h['offer_id'] in omap:self.cx.execute("INSERT OR IGNORE INTO price_history(offer_id,observed_at,price,list_price,reward_pct,reward_value,provenance) VALUES(?,?,?,?,?,?,?)",(omap[h['offer_id']],h['observed_at'],h['price'],h['list_price'],h['reward_pct'],h['reward_value'],h.get('provenance','local')) )
        for lid in d.get('lists',[1]):self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) VALUES(?,?)",(lid,nb))
        self.cx.execute("DELETE FROM trash WHERE id=?",(tid,)); self.cx.commit(); return nb

    def merge_books(self,keep,drop):
        if keep==drop:return False
        # Refuse if both canonical books already contain different products from the same store.
        ks={x['store']:x for x in self.cx.execute("SELECT * FROM offers WHERE book_id=?",(keep,))}; ds={x['store']:x for x in self.cx.execute("SELECT * FROM offers WHERE book_id=?",(drop,))}
        if any(s in ks for s in ds):return False
        self.snapshot_book(drop,'merge')
        self.cx.execute("UPDATE offers SET book_id=? WHERE book_id=?",(keep,drop))
        self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) SELECT list_id,? FROM list_books WHERE book_id=?",(keep,drop))
        self.cx.execute("DELETE FROM books WHERE id=?",(drop,)); self.cx.commit(); return True

    def history_for_book(self,book_id):
        return self.cx.execute("""SELECT h.observed_at,o.store,h.price,h.list_price,h.reward_pct,h.reward_value,h.provenance
            FROM price_history h JOIN offers o ON o.id=h.offer_id WHERE o.book_id=?
            ORDER BY h.observed_at DESC""",(book_id,)).fetchall()

    def lowest_for_book(self,book_id):
        return self.cx.execute("""SELECT MIN(h.price) low FROM price_history h JOIN offers o ON o.id=h.offer_id
                                  WHERE o.book_id=? AND h.price IS NOT NULL""",(book_id,)).fetchone()["low"]

    def backup_to(self,path):
        dst=sqlite3.connect(path)
        self.cx.backup(dst); dst.close()

    def restore_from(self,path):
        src=sqlite3.connect(path)
        src.backup(self.cx); src.close(); self.cx.commit()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1420x780"); self.minsize(1000,560)
        self.db=DB()
        global UI_LANG
        UI_LANG=self.db.get_setting("ui_language","en")
        self.title(APP_NAME)
        self.current_list_id=1; self.archived_view=False
        self.providers=live_providers(float(self.db.get_setting("request_delay_seconds","1.25")), self.log)
        self._build(); self.apply_theme(); self.refresh()

    def toggle_language(self):
        global UI_LANG
        UI_LANG="ja" if UI_LANG!="ja" else "en"
        self.db.set_setting("ui_language",UI_LANG)
        # Rebuild the visible UI from the same database/session so the change is immediate.
        for child in list(self.winfo_children()):
            child.destroy()
        self._build()
        self.apply_theme()
        self.refresh()

    def _build(self):
        style=ttk.Style(self)
        try: style.theme_use("vista")
        except: pass
        top=ttk.Frame(self,padding=10); top.pack(fill="x")
        ttk.Label(top,text="Book Sale Notification",font=("Segoe UI",18,"bold")).pack(side="left")
        ttk.Button(top,text=("English" if UI_LANG=="ja" else "日本語"),width=8,
                   command=self.toggle_language).pack(side="left",padx=(12,0))
        ttk.Button(top,text="Settings",command=self.settings_dialog).pack(side="right",padx=4)
        ttk.Button(top,text="Check for Updates",command=self.check_for_updates).pack(side="right",padx=4)
        ttk.Button(top,text="Recently Deleted",command=self.recently_deleted).pack(side="right",padx=4)
        ttk.Button(top,text="Backup / Share",command=self.backup_share_dialog).pack(side="right",padx=4)
        ttk.Button(top,text="Import HTML…",command=self.import_html).pack(side="right",padx=4)
        ttk.Button(top,text="Add from URL…",command=self.manual_add_url).pack(side="right",padx=4)
        ttk.Button(top,text="Import 3-store folder…",command=self.import_folder).pack(side="right",padx=4)

        phase=ttk.Frame(self,padding=(10,0,10,7)); phase.pack(fill="x")
        ttk.Label(phase,text="BookLive + BOOK☆WALKER + DMM active • Amazon intentionally disabled",
                  font=("Segoe UI",9,"bold")).pack(anchor="w")
        self.list_tabs=ttk.Notebook(self); self.list_tabs.pack(fill="x",padx=10,pady=(0,6))
        self.rebuild_list_tabs()
        bar=ttk.Frame(self,padding=(10,0,10,8)); bar.pack(fill="x")
        ttk.Label(bar,text="Search:").pack(side="left")
        self.search=tk.StringVar(); e=ttk.Entry(bar,textvariable=self.search,width=38); e.pack(side="left",padx=6)
        e.bind("<KeyRelease>",lambda _e:self.refresh())

        ttk.Button(bar,text="Delete",command=self.delete_selected).pack(side="right",padx=4)
        ttk.Button(bar,text="History",command=self.show_history).pack(side="right",padx=4)
        ttk.Button(bar,text="Mark purchased",command=self.mark_purchased).pack(side="right",padx=4)
        ttk.Button(bar,text="Edit store URLs",command=self.edit_url).pack(side="right",padx=4)
        ttk.Button(bar,text="Find missing matches",command=self.find_missing_matches).pack(side="right",padx=4)
        ttk.Button(bar,text="Update prices",command=self.update_prices).pack(side="right",padx=4)

        cols=("title","booklive","bookwalker","dmm","lowest","stores")
        headings={"title":"Book","booklive":"BookLive","bookwalker":"BOOK☆WALKER",
                  "dmm":"DMM","lowest":"Lowest cash price","stores":"Matched"}
        widths={"title":590,"booklive":125,"bookwalker":145,"dmm":125,"lowest":155,"stores":75}

        # Main table and live activity console.  Create the final Treeview directly
        # in table_frame so the scrollbar can never retain a callback to a destroyed widget.
        pane=ttk.Panedwindow(self,orient="horizontal")
        pane.pack(fill="both",expand=True,padx=10,pady=(0,8))
        table_frame=ttk.Frame(pane); activity_frame=ttk.Frame(pane,width=390)
        pane.add(table_frame,weight=4); pane.add(activity_frame,weight=1)

        self.tree=ttk.Treeview(table_frame,columns=cols,show="tree headings",selectmode="extended")
        for c in cols:
            self.tree.heading(c,text=headings[c],command=lambda x=c:self.sort_by(x))
            self.tree.column(c,width=widths[c],anchor="w" if c=="title" else "center")
        self.tree.heading("#0",text="Cover")
        self._cover_photos={}
        self.apply_cover_view()
        self.apply_store_columns()
        sy=ttk.Scrollbar(table_frame,orient="vertical",command=self.tree.yview)
        self.tree.configure(yscrollcommand=sy.set)
        self.tree.pack(side="left",fill="both",expand=True); sy.pack(side="right",fill="y")
        self.tree.bind("<Double-1>",self.double_click)
        self.tree.bind("<Control-a>",self.select_all_visible)
        self.tree.bind("<Control-A>",self.select_all_visible)

        ah=ttk.Frame(activity_frame); ah.pack(fill="x",pady=(0,4))
        ttk.Label(ah,text="Activity",font=("Segoe UI",10,"bold")).pack(side="left")
        ttk.Button(ah,text="Clear",command=lambda:self.activity_clear()).pack(side="right")
        self.activity=tk.Text(activity_frame,width=45,wrap="word",font=("Consolas",9),state="disabled")
        ay=ttk.Scrollbar(activity_frame,orient="vertical",command=self.activity.yview)
        self.activity.configure(yscrollcommand=ay.set)
        ay.pack(side="right",fill="y"); self.activity.pack(side="left",fill="both",expand=True)

        self.status=UIStatusVar(value=ui_tr("Ready"))
        ttk.Label(self,textvariable=self.status,relief="sunken",anchor="w",padding=5).pack(side="bottom",fill="x")
        self.log("Ready — live scraper activity will appear here.")

    def rebuild_list_tabs(self):
        for tab in self.list_tabs.tabs(): self.list_tabs.forget(tab)
        self._tab_map={}
        for r in self.db.list_rows():
            f=ttk.Frame(self.list_tabs); self.list_tabs.add(f,text=r['name']); self._tab_map[str(f)]=(r['id'],False)
        f=ttk.Frame(self.list_tabs); self.list_tabs.add(f,text='Archived'); self._tab_map[str(f)]=(1,True)
        plus=ttk.Frame(self.list_tabs); self.list_tabs.add(plus,text='+'); self._tab_map[str(plus)]=('new',False)
        self.list_tabs.bind('<<NotebookTabChanged>>',self.on_tab_changed)

    def on_tab_changed(self,event=None):
        key=self.list_tabs.select(); target=self._tab_map.get(key)
        if not target:return
        if target[0]=='new':
            name=simpledialog.askstring('New list','List name:')
            if name:
                try:self.current_list_id=self.db.create_list(name)
                except Exception as e:messagebox.showerror('New list',str(e))
            self.rebuild_list_tabs(); self.refresh(); return
        self.current_list_id,self.archived_view=target; self.refresh()

    def show_match_report(self,content):
        w=tk.Toplevel(self); w.title('Match Results'); w.geometry('900x650')
        w.resizable(False,False)
        t=tk.Text(w,wrap='word',font=('Consolas',9)); t.insert('1.0',content); t.configure(state='disabled'); t.pack(fill='both',expand=True,padx=10,pady=10)
        def copy(): self.clipboard_clear(); self.clipboard_append(content)
        ttk.Button(w,text='Close',command=w.destroy).pack(side='right',padx=10,pady=(0,10)); ttk.Button(w,text='Copy Log',command=copy).pack(side='right',pady=(0,10))

    def recently_deleted(self):
        w=tk.Toplevel(self); w.title('Recently Deleted'); w.geometry('900x560')
        w.resizable(False,False)
        t=ttk.Treeview(w,columns=('kind','title','date'),show='headings',selectmode='extended')
        for c,h,wd in [('kind','Reason',100),('title','Book',580),('date','Deleted',170)]:t.heading(c,text=h);t.column(c,width=wd)
        retention=int(self.db.get_setting('trash_retention_days','14') or 14)
        self.db.cx.execute("DELETE FROM trash WHERE deleted_at < datetime('now',?)",(f'-{retention} days',)); self.db.cx.commit()
        for r in self.db.cx.execute('SELECT * FROM trash ORDER BY deleted_at DESC'):t.insert('', 'end',iid=str(r['id']),values=(ui_tr(r['kind']),r['title'],r['deleted_at']))
        t.pack(fill='both',expand=True,padx=10,pady=(10,6))
        def restore():
            for x in t.selection():
                try:self.db.restore_trash(int(x))
                except Exception as e:messagebox.showerror('Restore',str(e))
            self.refresh();w.destroy()
        def purge():
            for x in t.selection():self.db.cx.execute('DELETE FROM trash WHERE id=?',(int(x),))
            self.db.cx.commit();w.destroy()
        footer=ttk.Frame(w,padding=(10,4,10,10)); footer.pack(fill='x',side='bottom')
        ttk.Label(footer,text=f'Items are kept for {retention} days.').pack(side='left')
        ttk.Button(footer,text='Close',command=w.destroy).pack(side='right',padx=(6,0))
        ttk.Button(footer,text='Permanently delete selected',command=purge).pack(side='right',padx=(6,0))
        ttk.Button(footer,text='Restore selected',command=restore).pack(side='right')

    def apply_theme(self):
        mode=self.db.get_setting('appearance','system')
        if mode=='system':
            # Tk does not expose the Windows app-mode setting reliably; keep System
            # conservative rather than pretending it is dark.
            mode='light'
        style=ttk.Style(self)
        try: style.theme_use('clam')
        except tk.TclError: pass

        if mode=='dark':
            bg='#121212'; panel='#1b1b1b'; field='#202020'; raised='#2a2a2a'
            border='#3a3a3a'; fg='#f2f2f2'; muted='#b8b8b8'; sel='#0e639c'
            self.configure(bg=bg)

            style.configure('.',background=panel,foreground=fg)
            style.configure('TFrame',background=panel)
            style.configure('TLabel',background=panel,foreground=fg)
            style.configure('TSeparator',background=border)
            style.configure('TButton',background=raised,foreground=fg,bordercolor=border,
                            lightcolor=raised,darkcolor=raised,padding=(8,4))
            style.map('TButton',
                      background=[('pressed','#3a3a3a'),('active','#333333'),('disabled','#202020')],
                      foreground=[('disabled','#777777'),('!disabled',fg)])
            style.configure('Settings.TButton',background=raised,foreground='#ffffff',
                            bordercolor=border,lightcolor=raised,darkcolor=raised,padding=(8,4))
            style.map('Settings.TButton',
                      background=[('pressed','#3a3a3a'),('active','#333333'),('disabled','#202020')],
                      foreground=[('disabled','#777777'),('pressed','#ffffff'),('active','#ffffff'),('!disabled','#ffffff')])
            style.configure('TEntry',fieldbackground=field,foreground=fg,insertcolor=fg,
                            bordercolor=border,lightcolor=border,darkcolor=border)
            style.map('TEntry',
                      fieldbackground=[('disabled','#181818'),('readonly','#202020')],
                      foreground=[('disabled','#9a9a9a'),('readonly','#e0e0e0'),('!disabled',fg)])
            style.configure('TCombobox',fieldbackground=field,background=raised,foreground=fg,
                            arrowcolor=fg,bordercolor=border,lightcolor=border,darkcolor=border)
            style.map('TCombobox',
                      fieldbackground=[('readonly',field),('disabled','#181818')],
                      background=[('readonly',raised),('active','#333333'),('disabled','#202020')],
                      foreground=[('readonly','#f2f2f2'),('disabled','#9a9a9a'),('!disabled',fg)],
                      selectbackground=[('readonly',field)],selectforeground=[('readonly','#f2f2f2')])
            style.configure('TCheckbutton',background=panel,foreground=fg)
            style.map('TCheckbutton',background=[('active',panel)],foreground=[('disabled','#777777')])
            style.configure('TRadiobutton',background=panel,foreground=fg)
            style.map('TRadiobutton',background=[('active',panel)],foreground=[('disabled','#777777')])
            style.configure('TNotebook',background=bg,bordercolor=border)
            style.configure('TNotebook.Tab',background=raised,foreground=fg,padding=(12,5))
            style.map('TNotebook.Tab',
                      background=[('selected','#3a3a3a'),('active','#333333')],
                      foreground=[('selected','#ffffff'),('!disabled',fg)])
            style.configure('Treeview',background=field,foreground=fg,fieldbackground=field,
                            bordercolor=border,lightcolor=border,darkcolor=border)
            style.map('Treeview',background=[('selected',sel)],foreground=[('selected','#ffffff')])
            style.configure('Treeview.Heading',background=raised,foreground=fg,relief='flat',
                            bordercolor=border,lightcolor=border,darkcolor=border)
            style.map('Treeview.Heading',background=[('active','#333333')],foreground=[('active','#ffffff')])
            style.configure('TPanedwindow',background=bg)
            style.configure('TScrollbar',background=raised,troughcolor=field,bordercolor=border,
                            arrowcolor=fg,darkcolor=raised,lightcolor=raised)
            style.map('TScrollbar',background=[('active','#3a3a3a')])
            # Native Tk widgets are not ttk and need explicit colors.
            if hasattr(self,'activity'):
                self.activity.configure(bg='#0f0f0f',fg=fg,insertbackground=fg,
                                        selectbackground=sel,selectforeground='#ffffff',
                                        highlightbackground=border,highlightcolor=border)
            # Option database also covers Tk menus/listboxes created by ttk controls.
            self.option_add('*Toplevel.background',bg)
            self.option_add('*Text.background','#0f0f0f')
            self.option_add('*Text.foreground',fg)
            self.option_add('*Text.insertBackground',fg)
            self.option_add('*Listbox.background',field)
            self.option_add('*Listbox.foreground',fg)
            self.option_add('*Listbox.selectBackground',sel)
            self.option_add('*Listbox.selectForeground','#ffffff')
        else:
            bg='#f0f0f0'; panel='#f0f0f0'; field='#ffffff'; raised='#f4f4f4'
            border='#a9a9a9'; fg='#111111'; sel='#0078d7'
            self.configure(bg=bg)

            # IMPORTANT: configure AND map every style modified by Dark mode.
            # ttk maps persist across configure() calls, so omitting these is what
            # caused dark hover/active states to leak into Light mode.
            style.configure('.',background=panel,foreground=fg)
            style.configure('TFrame',background=panel)
            style.configure('TLabel',background=panel,foreground=fg)
            style.configure('TSeparator',background='#bcbcbc')
            style.configure('TButton',background=raised,foreground=fg,bordercolor=border,
                            lightcolor='#ffffff',darkcolor='#d0d0d0',padding=(8,4))
            style.map('TButton',
                      background=[('pressed','#d9d9d9'),('active','#e8e8e8'),('disabled','#eeeeee')],
                      foreground=[('disabled','#888888'),('pressed',fg),('active',fg),('!disabled',fg)])
            style.configure('Settings.TButton',background=raised,foreground=fg,bordercolor=border,
                            lightcolor='#ffffff',darkcolor='#d0d0d0',padding=(8,4))
            style.map('Settings.TButton',
                      background=[('pressed','#d9d9d9'),('active','#e8e8e8'),('disabled','#eeeeee')],
                      foreground=[('disabled','#888888'),('pressed',fg),('active',fg),('!disabled',fg)])
            style.configure('TEntry',fieldbackground=field,foreground=fg,insertcolor=fg,
                            bordercolor=border,lightcolor='#ffffff',darkcolor='#d0d0d0')
            style.map('TEntry',
                      fieldbackground=[('disabled','#eeeeee'),('readonly','#f7f7f7')],
                      foreground=[('disabled','#888888'),('!disabled',fg)])
            style.configure('TCombobox',fieldbackground=field,background=raised,foreground=fg,
                            arrowcolor=fg,bordercolor=border,lightcolor='#ffffff',darkcolor='#d0d0d0')
            style.map('TCombobox',
                      fieldbackground=[('readonly',field),('disabled','#eeeeee')],
                      background=[('readonly',raised),('active','#e8e8e8'),('disabled','#eeeeee')],
                      foreground=[('readonly',fg),('disabled','#888888'),('!disabled',fg)],
                      selectbackground=[('readonly',field)],selectforeground=[('readonly',fg)])
            style.configure('TCheckbutton',background=panel,foreground=fg)
            style.map('TCheckbutton',background=[('active',panel)],foreground=[('disabled','#888888'),('!disabled',fg)])
            style.configure('TRadiobutton',background=panel,foreground=fg)
            style.map('TRadiobutton',background=[('active',panel)],foreground=[('disabled','#888888'),('!disabled',fg)])
            style.configure('TNotebook',background=bg,bordercolor=border)
            style.configure('TNotebook.Tab',background='#e5e5e5',foreground=fg,padding=(12,5))
            style.map('TNotebook.Tab',
                      background=[('selected','#ffffff'),('active','#eeeeee'),('disabled','#eeeeee')],
                      foreground=[('selected',fg),('active',fg),('disabled','#888888'),('!disabled',fg)])
            style.configure('Treeview',background=field,foreground=fg,fieldbackground=field,
                            bordercolor=border,lightcolor='#ffffff',darkcolor='#d0d0d0')
            style.map('Treeview',background=[('selected',sel)],foreground=[('selected','#ffffff')])
            style.configure('Treeview.Heading',background='#eeeeee',foreground=fg,relief='flat',
                            bordercolor=border,lightcolor='#ffffff',darkcolor='#d0d0d0')
            style.map('Treeview.Heading',
                      background=[('active','#e0e0e0')],foreground=[('active',fg),('!disabled',fg)])
            style.configure('TPanedwindow',background=bg)
            style.configure('TScrollbar',background='#e5e5e5',troughcolor='#f5f5f5',bordercolor=border,
                            arrowcolor=fg,darkcolor='#d0d0d0',lightcolor='#ffffff')
            style.map('TScrollbar',background=[('active','#d6d6d6'),('pressed','#c8c8c8')])
            if hasattr(self,'activity'):
                self.activity.configure(bg='white',fg='black',insertbackground='black',
                                        selectbackground=sel,selectforeground='white',
                                        highlightbackground=border,highlightcolor=border)
            # Replace the dark option-database values as well.
            self.option_add('*Toplevel.background',bg)
            self.option_add('*Text.background','white')
            self.option_add('*Text.foreground','black')
            self.option_add('*Text.insertBackground','black')
            self.option_add('*Listbox.background','white')
            self.option_add('*Listbox.foreground','black')
            self.option_add('*Listbox.selectBackground',sel)
            self.option_add('*Listbox.selectForeground','white')

        # Existing and subsequently-created child windows inherit ttk styles.
        # Explicitly color any current Tk/Toplevel surfaces.
        def paint_native(widget):
            try:
                if isinstance(widget,(tk.Tk,tk.Toplevel)):
                    widget.configure(bg=('#121212' if mode=='dark' else '#f0f0f0'))
                for child in widget.winfo_children(): paint_native(child)
            except tk.TclError: pass
        paint_native(self)

    def activity_clear(self):
        self.activity.configure(state="normal"); self.activity.delete("1.0","end"); self.activity.configure(state="disabled")

    def log(self,message):
        stamp=datetime.now().strftime("%H:%M:%S")
        def append(msg=str(message),ts=stamp):
            self.activity.configure(state="normal")
            self.activity.insert("end",f"{ts}  {msg}\n")
            self.activity.see("end")
            self.activity.configure(state="disabled")
        if threading.current_thread() is threading.main_thread(): append()
        else: self.after(0,append)

    def price_text(self,o):
        if not o: return "—"
        price=o["price"]
        if o["store"]=="BOOK☆WALKER" and self.db.get_setting("bw_overseas_tax","0")=="1":
            # Overseas mode changes only the displayed cash price, and only when
            # BOOK☆WALKER supplied an exact tax-exclusive amount.
            if o["tax_ex_price"] is not None:
                price=o["tax_ex_price"]
        if price is None: return "?"
        s=f"¥{price:,}"
        if self.db.get_setting("include_direct_rewards","1")=="1":
            if o["store"]=="DMM":
                if o["reward_value"]:
                    s+=f"  +{o['reward_value']:,} pt"
                elif o["reward_pct"]:
                    s+=f"  +{o['reward_pct']:g}%pt"
            elif o["store"]=="BOOK☆WALKER" and o["reward_value"]:
                s+=f"  +{o['reward_value']:,} coin"
        if o["observed_at"]:
            s += "\n" + str(o["observed_at"])[:16]
        return s

    def cache_cover(self,bid,store,url):
        if not self.store_enabled(store): return
        if not url or Image is None: return

        # Cover priority: BookLive > BOOK☆WALKER > DMM.  A store may replace its
        # own cached cover when its image URL changes (important for DMM preorders,
        # which can initially expose a placeholder and add the real cover later).
        def source_for(u):
            u=(u or "").lower()
            if "booklive" in u: return "BookLive"
            if "bookwalker" in u: return "BOOK☆WALKER"
            if "dmm" in u: return "DMM"
            return ""
        priority={"DMM":1,"BOOK☆WALKER":2,"BookLive":3}

        row=self.db.cx.execute("SELECT cover_url,cover_path FROM books WHERE id=?",(bid,)).fetchone()
        if row and row["cover_path"] and Path(row["cover_path"]).exists():
            old_url=row["cover_url"] or ""
            old_source=source_for(old_url)
            if old_url == url:
                return
            # Never let a lower-priority source replace a known higher-priority cover.
            if old_source and priority.get(store,0) < priority.get(old_source,0):
                return
            # Unknown legacy cover source: preserve it unless BookLive is supplying
            # the replacement, which remains authoritative.
            if not old_source and store!="BookLive":
                return
        try:
            data=urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"image/*"}),timeout=20).read()
            im=Image.open(BytesIO(data)).convert("RGB")
            im.thumbnail((800,1200),Image.Resampling.LANCZOS)
            d=Path.home()/".book_sale_notification"/"covers"; d.mkdir(parents=True,exist_ok=True)
            p=d/f"{bid}.jpg"; im.save(p,"JPEG",quality=82,optimize=True)
            self.db.set_cover(bid,url,str(p))
            self.log(f"[Cover] {store}: refreshed cover")
        except Exception as e:
            self.log(f"[Cover] {store}: {e}")

    def store_enabled(self,store):
        keys={"BookLive":"store_booklive_enabled","BOOK☆WALKER":"store_bookwalker_enabled","DMM":"store_dmm_enabled"}
        key=keys.get(store)
        return True if not key else self.db.get_setting(key,"1")=="1"

    def enabled_stores(self):
        return [s for s in STORES if self.store_enabled(s)]

    def apply_store_columns(self):
        visible=["title"]
        store_columns={"BookLive":"booklive","BOOK☆WALKER":"bookwalker","DMM":"dmm"}
        for store,column_id in store_columns.items():
            if self.store_enabled(store):
                visible.append(column_id)
        visible += ["lowest","stores"]
        self.tree.configure(displaycolumns=visible)

    def cover_view(self):
        show=self.db.get_setting("show_covers","1")=="1"
        size=self.db.get_setting("cover_size","medium")
        sizes={"small":(50,70,62,78),"medium":(75,105,87,113),"large":(100,140,112,148)}
        return show,size,sizes.get(size,sizes["medium"])

    def apply_cover_view(self, no_cover_rowheight=None):
        show,size,(iw,ih,cw,rh)=self.cover_view()
        self.tree.heading("#0",text="Cover" if show else "")
        self.tree.column("#0",width=cw if show else 0,minwidth=cw if show else 0,
                         stretch=False,anchor="center")
        # Price cells contain a second line for timestamps. Never collapse no-cover
        # rows to a single 24px line; use the calculated wrapped-content height.
        ttk.Style(self).configure("Treeview",rowheight=rh if show else (no_cover_rowheight or 46))

    def _wrap_tree_text(self,text,pixel_width):
        """Pixel-aware full wrapping for Japanese/English text displayed in Treeview cells."""
        text=str(text or "")
        if not text:return text,1
        try: font=tkfont.nametofont("TkDefaultFont")
        except Exception: return text,1
        width=max(80,int(pixel_width)-14)
        lines=[]; current=""
        for ch in text:
            if ch=="\n":
                lines.append(current); current=""; continue
            trial=current+ch
            if current and font.measure(trial)>width:
                lines.append(current)
                current=ch
            else:
                current=trial
        if current or not lines:lines.append(current)
        return "\n".join(lines),max(1,len(lines))

    def refresh(self):
        self.apply_store_columns()
        self._cover_photos={}
        show_covers,cover_size,(cover_w,cover_h,_cw,_rh)=self.cover_view()
        for x in self.tree.get_children(): self.tree.delete(x)
        rows=self.db.rows(self.search.get().strip(),False,self.current_list_id,self.archived_view)
        wrapped_titles={}
        max_lines=2  # store price + observation timestamp already needs two lines
        if not show_covers:
            title_width=self.tree.column("title","width") or 590
            for b,_offers in rows:
                wrapped,nlines=self._wrap_tree_text(b["title"],title_width)
                wrapped_titles[b["id"]]=wrapped
                max_lines=max(max_lines,nlines)
            # ttk.Treeview only supports one rowheight per widget, so size the current
            # view to the tallest wrapped visible row rather than clipping individual rows.
            self.apply_cover_view(8+19*max_lines)
        else:
            self.apply_cover_view()
        for b,offers in rows:
            cash=[]
            for st,o in offers.items():
                if not self.store_enabled(st): continue
                p=o["price"]
                if st=="BOOK☆WALKER" and self.db.get_setting("bw_overseas_tax","0")=="1" and o["tax_ex_price"] is not None:
                    p=o["tax_ex_price"]
                if p is not None: cash.append((p,st))
            low=min((p for p,_ in cash),default=None)
            cheapest=[st for p,st in cash if p==low] if low is not None else []
            enabled_matched=[st for st,o in offers.items() if self.store_enabled(st) and o["price"] is not None]
            recorded=self.db.lowest_for_book(b["id"])
            lowtxt = (f"¥{low:,}" if low is not None else "—")
            if recorded is not None and low is not None:
                lowtxt += "  ★" if low <= recorded else f"  (low ¥{recorded:,})"
            if low is not None:
                lowtxt += "\n" + (ui_tr("Same") if len(enabled_matched)>=2 and len(cheapest)==len(enabled_matched)
                                   else " · ".join(cheapest))
            vals=(wrapped_titles.get(b["id"],b["title"]),self.price_text(offers.get("BookLive")),
                  self.price_text(offers.get("BOOK☆WALKER")),self.price_text(offers.get("DMM")),
                  lowtxt,len(enabled_matched))
            photo=""
            cp=b["cover_path"] if "cover_path" in b.keys() else ""
            if show_covers and cp and Image is not None and Path(cp).exists():
                try:
                    im=Image.open(cp).copy()
                    im.thumbnail((cover_w,cover_h),Image.Resampling.LANCZOS)
                    photo=ImageTk.PhotoImage(im); self._cover_photos[b["id"]]=photo
                except Exception: pass
            self.tree.insert("", "end", iid=str(b["id"]), image=photo, values=vals)
        self.status.set(f"{len(rows)} canonical books shown • Double-click a store cell to open its public product page")

    def parse_file(self,path,forced_store=None):
        with open(path,"r",encoding="utf-8",errors="ignore") as f: soup=BeautifulSoup(f,"html.parser")
        store=forced_store or detect_store(soup,os.path.basename(path))
        if not store: raise ValueError("Could not identify the store from this HTML file.")
        if store.startswith("Amazon"):
            raise ValueError("Amazon parsing is intentionally disabled in 1.1. This phase tests DMM, BookLive and BOOK☆WALKER only.")
        offers=PARSERS[store](soup); added=0; existing=0
        for o in offers:
            _bid,isnew=self.db.import_offer(o,self.current_list_id)
            added += 1 if isnew else 0; existing += 0 if isnew else 1
        return store,len(offers),added,existing

    def _store_from_product_url(self, url):
        url=(url or "").strip()
        for store in STORES:
            if valid_store_url(store,url):
                return store
        return None

    def manual_add_url(self):
        win=tk.Toplevel(self)
        win.title("Add book from store URL")
        win.geometry("720x205")
        win.resizable(False,False)
        win.transient(self)
        win.grab_set()

        f=ttk.Frame(win,padding=16); f.pack(fill="both",expand=True)
        ttk.Label(f,text="Add from BookLive / BOOK☆WALKER / DMM URL",
                  font=("Segoe UI",11,"bold")).pack(anchor="w")
        ttk.Label(f,text=("Paste one product URL. The app will fetch that exact product, then search the other "
                          "two stores and fetch their product pages before adding anything to the list."),
                  wraplength=675).pack(anchor="w",pady=(5,10))
        urlvar=tk.StringVar()
        ent=ttk.Entry(f,textvariable=urlvar,width=92); ent.pack(fill="x",pady=(0,12)); ent.focus_set()

        footer=ttk.Frame(f); footer.pack(fill="x",side="bottom")
        ttk.Button(footer,text="Cancel",command=win.destroy).pack(side="right")
        ttk.Button(footer,text="Fetch all stores and add",
                   command=lambda:self._start_manual_add(urlvar.get(),win)).pack(side="right",padx=(0,8))
        ent.bind("<Return>",lambda _e:self._start_manual_add(urlvar.get(),win))

    def _start_manual_add(self, url, dialog):
        url=(url or "").strip()
        source_store=self._store_from_product_url(url)
        if not source_store:
            messagebox.showerror("Invalid store URL",
                "Paste a valid BookLive, BOOK☆WALKER or DMM Books product URL.")
            return

        dialog.destroy()
        self.status.set(f"Reading {source_store} product…")
        self.log(f"[Manual add] Source: {source_store} • {url}")

        def work():
            try:
                source_result=self.providers[source_store].product(url)
                if not source_result or not source_result.title:
                    raise RuntimeError(f"{source_store} did not return usable product metadata.")

                primary=self._offer_from_live(source_result)
                found={source_store:primary}
                self.log(f"[Manual add] Anchor title: {primary.title}")

                # Explicit manual add always checks all three stores, regardless of the
                # automatic-update enable/disable toggles.
                for store in STORES:
                    if store==source_store: continue
                    self.after(0,lambda st=store:self.status.set(f"Searching {st}…"))
                    self.log(f"[Manual add] Searching {store} for: {primary.title}")
                    try:
                        result=self.providers[store].best(primary.title,primary.author)
                        if result:
                            found[store]=self._offer_from_live(result)
                            self.log(f"[Manual add] Matched {store}: {result.title} • {result.url}")
                        else:
                            self.log(f"[Manual add] No confident {store} match")
                    except Exception as e:
                        self.log(f"[Manual add] {store} failed: {type(e).__name__}: {e}")

                # Nothing is persisted until every store has been attempted.
                self.after(0,lambda:self._finish_manual_add(primary,found))
            except Exception as e:
                self.after(0,lambda e=e:messagebox.showerror("Manual add failed",f"{type(e).__name__}: {e}"))
                self.after(0,lambda:self.status.set("Ready"))

        self._run_background(work)

    def _finish_manual_add(self, primary, found):
        try:
            self.auto_backup("manual_add_url")
            bid=self.db.import_manual_bundle(primary,list(found.values()),self.current_list_id)

            # Download the best available cover after the database transaction.
            for store in ("BookLive","BOOK☆WALKER","DMM"):
                o=found.get(store)
                if o and o.cover_url:
                    self.cache_cover(bid,store,o.cover_url)
                    break

            self.refresh()
            lines=[]
            for store in STORES:
                o=found.get(store)
                if not o:
                    lines.append(f"{store}: no confident match")
                    continue
                price=f"¥{o.price:,}" if o.price is not None else "price unavailable"
                lines.append(f"{store}: {price}\n{o.url}")
            messagebox.showinfo("Book added",
                f"{primary.title}\n\nChecked all three stores before adding.\n\n" + "\n\n".join(lines))
        except Exception as e:
            messagebox.showerror("Manual add failed",f"{type(e).__name__}: {e}")
        finally:
            self.status.set("Ready")

    def import_html(self):
        p=filedialog.askopenfilename(title="Import wishlist HTML",filetypes=[("HTML files","*.html *.htm"),("All files","*.*")])
        if not p:return
        try:
            self.auto_backup()
            st,n,added,existing=self.parse_file(p); self.refresh()
            messagebox.showinfo("Import complete",f"{st}: parsed {n} wishlist item(s).\nNew books: {added}\nAlready in database (same store URL/ID): {existing}\n\nNo fuzzy title merging is performed during wishlist import.")
        except Exception as e: messagebox.showerror("Import failed",str(e))

    def import_folder(self):
        d=filedialog.askdirectory(title="Choose folder containing DMM, BookLive and BOOK☆WALKER HTML files")
        if not d:return
        self.auto_backup()
        results=[]; errors=[]
        for p in Path(d).glob("*.htm*"):
            try:
                with open(p,"r",encoding="utf-8",errors="ignore") as f: soup=BeautifulSoup(f,"html.parser")
                st=detect_store(soup,p.name)
                if st and st in PARSERS and not any(x[0]==st for x in results):
                    offers=PARSERS[st](soup); added=0
                    for o in offers:
                        _bid,isnew=self.db.import_offer(o,self.current_list_id); added+=1 if isnew else 0
                    results.append((st,len(offers),added))
            except Exception as e: errors.append(f"{p.name}: {e}")
        self.refresh()
        msg="\n".join(f"{s}: {n} parsed • {added} new" for s,n,added in results) or "No recognized wishlist HTML found."
        if errors: msg+="\n\nErrors:\n"+"\n".join(errors[:5])
        messagebox.showinfo("Folder import",msg)

    def select_all_visible(self,event=None):
        rows=self.tree.get_children("")
        if rows: self.tree.selection_set(rows)
        return "break"

    def selected_ids(self):
        return [int(x) for x in self.tree.selection()]

    def selected(self):
        s=self.selected_ids()
        return s[0] if s else None

    def mark_purchased(self):
        ids=self.selected_ids()
        if not ids:return
        self.auto_backup('mark_purchased')
        for bid in ids:self.db.set_purchased(bid,not self.archived_view)
        self.refresh()

    def edit_url(self):
        bid=self.selected()
        if not bid:
            messagebox.showinfo("Select a book", "Select a book first, then click Edit store URLs.")
            return

        book=self.db.cx.execute("SELECT title FROM books WHERE id=?",(bid,)).fetchone()
        rows=self.db.cx.execute("SELECT store,url,locked FROM offers WHERE book_id=?",(bid,)).fetchall()
        current={r["store"]:(r["url"] or "") for r in rows}

        win=tk.Toplevel(self)
        win.title("Edit store URLs")
        win.geometry("900x310")
        win.resizable(False,False)
        win.transient(self)
        win.grab_set()

        outer=ttk.Frame(win,padding=14); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text=book["title"],font=("Segoe UI",11,"bold"),wraplength=850).pack(anchor="w",pady=(0,12))
        ttk.Label(outer,text="Current database URLs for the three active stores. Editing a URL manually locks that store match.",
                  foreground="#555").pack(anchor="w",pady=(0,10))

        vars={}
        grid=ttk.Frame(outer); grid.pack(fill="x",expand=True)
        for i,store in enumerate(STORES):
            ttk.Label(grid,text=store,width=14).grid(row=i,column=0,sticky="w",pady=5)
            v=tk.StringVar(value=current.get(store,""))
            vars[store]=v
            ent=ttk.Entry(grid,textvariable=v)
            ent.grid(row=i,column=1,sticky="ew",padx=(8,6),pady=5)
            def open_url(v=v):
                u=v.get().strip()
                if u: webbrowser.open(u)
            ttk.Button(grid,text="Open",command=open_url,width=8).grid(row=i,column=2,pady=5)
        grid.columnconfigure(1,weight=1)

        buttons=ttk.Frame(outer); buttons.pack(fill="x",pady=(14,0))
        def save():
            invalid=[]
            for store,v in vars.items():
                newurl=v.get().strip()
                if newurl and newurl != current.get(store,"") and not valid_store_url(store,newurl):
                    invalid.append((store,newurl))
            if invalid:
                store,url=invalid[0]
                expected={"BookLive":"a BookLive product URL (booklive.jp)",
                          "BOOK☆WALKER":"a BOOK☆WALKER product URL (bookwalker.jp/de…)",
                          "DMM":"a DMM Books product URL (book.dmm.com/product/…)"}[store]
                messagebox.showerror("Invalid store URL",
                    f"The URL entered for {store} is not {expected}.\n\n{url}\n\nNo changes were saved.")
                return
            removals=[store for store,v in vars.items() if current.get(store,"") and not v.get().strip()]
            if removals:
                names=", ".join(removals)
                if not messagebox.askyesno("Remove store match",
                    f"Remove the {names} match{'es' if len(removals)>1 else ''} from this book?\n\n"
                    "This permanently clears that store's URL, product ID, current price, rewards and price history. "
                    "The canonical book and its other store matches are not affected."):
                    return
                self.auto_backup("remove_store_match")
            for store,v in vars.items():
                newurl=v.get().strip()
                oldurl=current.get(store,"")
                if newurl != oldurl:
                    if newurl:
                        self.db.set_url(bid,store,newurl)
                    elif oldurl:
                        self.db.remove_store_match(bid,store)
            self.refresh()
            win.destroy()
        ttk.Button(buttons,text="Cancel",command=win.destroy).pack(side="right")
        ttk.Button(buttons,text="Save changes",command=save).pack(side="right",padx=(0,8))

    def open_store(self):
        bid=self.selected()
        if not bid:return
        store=simpledialog.askstring("Open store","Store name: BookLive, BOOK☆WALKER, or DMM")
        if store not in STORES:return
        row=self.db.cx.execute("SELECT url FROM offers WHERE book_id=? AND store=?",(bid,store)).fetchone()
        if row and row["url"]: webbrowser.open(row["url"])

    def double_click(self,event):
        row=self.tree.identify_row(event.y); col=self.tree.identify_column(event.x)
        if not row:return
        mapping={"#2":"BookLive","#3":"BOOK☆WALKER","#4":"DMM"}
        store=mapping.get(col)
        if not store:return
        o=self.db.cx.execute("SELECT url FROM offers WHERE book_id=? AND store=?",(int(row),store)).fetchone()
        if o and o["url"]: webbrowser.open(o["url"])

    def delete_selected(self):
        ids=self.selected_ids()
        if not ids:
            messagebox.showinfo("Delete","Select one or more books first.")
            return
        label="this book" if len(ids)==1 else f"{len(ids)} selected books"
        if not messagebox.askyesno("Delete books",f"Move {label} to Recently Deleted? They can be restored during the retention period."):
            return
        self.auto_backup('delete')
        for bid in ids: self.db.delete_book(bid)
        self.refresh()

    def show_history(self):
        bid=self.selected()
        if not bid:
            messagebox.showinfo("Select a book","Select a book first."); return
        book=self.db.cx.execute("SELECT title FROM books WHERE id=?",(bid,)).fetchone()
        rows=self.db.history_for_book(bid)
        w=tk.Toplevel(self); w.title("Price history — "+book["title"]); w.geometry("900x500")
        w.resizable(False,False)
        cols=("date","store","price","list","reward","source")
        t=ttk.Treeview(w,columns=cols,show="headings")
        for c,h,width in [("date","Observed",165),("store","Store",130),("price","Cash price",100),
                          ("list","List price",100),("reward","Reward",130),("source","Source",130)]:
            t.heading(c,text=h); t.column(c,width=width,anchor="center")
        for r in rows:
            reward = (f"{r['reward_pct']:g}% pt" if r["reward_pct"] else
                      f"{r['reward_value']} coin/pt" if r["reward_value"] else "")
            t.insert("","end",values=(r["observed_at"],r["store"],
                     f"¥{r['price']:,}" if r["price"] is not None else "",
                     f"¥{r['list_price']:,}" if r["list_price"] is not None else "",
                     reward,r["provenance"]))
        t.pack(fill="both",expand=True,padx=10,pady=10)

    def auto_backup(self,operation="operation"):
        d=DATA_DIR/"backups"; d.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe=re.sub(r"[^A-Za-z0-9_-]+","_",operation)
        path=d/f"auto_{stamp}_{safe}.db"
        self.db.backup_to(path)
        files=sorted(d.glob("auto_*.db"),key=lambda x:x.stat().st_mtime,reverse=True)
        for old in files[5:]:
            try: old.unlink()
            except: pass
        return path

    def backup_share_dialog(self):
        w=tk.Toplevel(self); w.title("Backup, restore & sharing"); w.geometry("540x520"); w.resizable(False,False)
        f=ttk.Frame(w,padding=16); f.pack(fill="both",expand=True)
        ttk.Label(f,text="Private recovery",font=("Segoe UI",11,"bold")).pack(anchor="w")
        ttk.Button(f,text="Save Backup As…",command=self.save_backup).pack(fill="x",pady=4)
        ttk.Button(f,text="Restore Backup…",command=self.restore_backup).pack(fill="x",pady=4)
        ttk.Separator(f).pack(fill="x",pady=12)
        ttk.Label(f,text="Portable sharing",font=("Segoe UI",11,"bold")).pack(anchor="w")
        ttk.Label(f,text="Share files contain public book/store data only — no source HTML, cookies, login state or account data.",
                  wraplength=480).pack(anchor="w",pady=(3,8))
        ttk.Button(f,text="Export shared book list…",command=self.export_share).pack(fill="x",pady=4)
        ttk.Button(f,text="View / import shared book list…",command=self.import_share).pack(fill="x",pady=4)
        ttk.Button(f,text="Export price history…",command=self.export_history).pack(fill="x",pady=4)
        ttk.Button(f,text="Import price history…",command=self.import_history).pack(fill="x",pady=4)
        ttk.Separator(f).pack(fill="x",pady=12)
        ttk.Label(f,text="Calibre library",font=("Segoe UI",11,"bold")).pack(anchor="w")
        ttk.Button(f,text="Sync purchased books from Calibre CSV…",command=self.calibre_sync).pack(fill="x",pady=4)

    def calibre_sync(self):
        p=filedialog.askopenfilename(title="Select Calibre CSV export",
                                     filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not p:return
        try:
            # utf-8-sig handles Calibre/Excel-style UTF-8 BOM exports without changing data.
            with open(p,"r",encoding="utf-8-sig",newline="") as fh:
                reader=csv.DictReader(fh)
                if not reader.fieldnames or "identifiers" not in [x.strip().lower() for x in reader.fieldnames]:
                    messagebox.showerror("Calibre Sync","CSV must contain an 'identifiers' column.")
                    return
                idcol=next(x for x in reader.fieldnames if x.strip().lower()=="identifiers")
                parsed=[]
                supported=set()
                for rowno,row in enumerate(reader,start=2):
                    raw=(row.get(idcol) or "").strip()
                    ids=[]
                    for part in raw.split(","):
                        part=part.strip()
                        if ":" not in part: continue
                        kind,value=part.split(":",1)
                        kind=kind.strip().lower(); value=value.strip()
                        if kind in ("bl","bw","dmm") and value:
                            key=f"{kind}:{value}".lower()
                            ids.append(key); supported.add(key)
                    parsed.append((rowno,raw,ids))
        except Exception as e:
            messagebox.showerror("Calibre Sync",f"Could not read CSV:\n{e}"); return

        index=self.db.calibre_identifier_index()
        matches={}       # book_id -> matched identifiers
        already={}       # book_id -> matched identifiers
        unmatched=set()
        for key in supported:
            hit=index.get(key)
            if not hit:
                unmatched.add(key); continue
            target=already if hit["status"]=="purchased" else matches
            target.setdefault(hit["book_id"],[]).append(key)

        def title_for(bid):
            r=self.db.cx.execute("SELECT title FROM books WHERE id=?",(bid,)).fetchone()
            return r["title"] if r else f"Book {bid}"

        preview=[
            "CALIBRE PURCHASE SYNC — PREVIEW","",
            f"CSV rows scanned: {len(parsed)}",
            f"Supported unique identifiers (bl/bw/dmm): {len(supported)}",
            f"Active books to archive: {len(matches)}",
            f"Already archived exact matches: {len(already)}",
            f"Supported identifiers not present in wishlist: {len(unmatched)}",
            "",
            "MATCHING POLICY",
            "Exact identifiers only: bl:, bw:, dmm:",
            "Titles/authors/series/ISBN/ASIN are NOT used as fallback matches.",
            ""
        ]
        if matches:
            preview += ["WILL ARCHIVE","-"*72]
            for bid,keys in sorted(matches.items(),key=lambda x:title_for(x[0]).casefold()):
                preview += [title_for(bid), "  Matched: "+", ".join(sorted(keys)), ""]
        if already:
            preview += ["ALREADY ARCHIVED","-"*72]
            for bid,keys in sorted(already.items(),key=lambda x:title_for(x[0]).casefold()):
                preview += [title_for(bid), "  Matched: "+", ".join(sorted(keys)), ""]
        # Do not dump every unmatched Calibre identifier into the preview.
        # Large libraries can contain tens of thousands of identifiers that are
        # irrelevant to the current wishlist; the summary count above is enough.
        content="\n".join(preview)

        w=tk.Toplevel(self); w.title("Calibre Sync Preview"); w.geometry("900x650"); w.resizable(False,False)
        t=tk.Text(w,wrap="word",font=("Consolas",9)); t.insert("1.0",content); t.configure(state="disabled")
        t.pack(fill="both",expand=True,padx=10,pady=10)
        footer=ttk.Frame(w,padding=(10,0,10,10)); footer.pack(fill="x")
        def copy_preview():
            self.clipboard_clear(); self.clipboard_append(content)
        def apply_sync():
            if not matches:
                messagebox.showinfo("Calibre Sync","No active wishlist books matched exact Calibre identifiers.")
                return
            if not messagebox.askyesno("Calibre Sync",f"Archive {len(matches)} exactly matched book(s)?\n\nAn automatic database backup will be created first."):
                return
            backup=self.auto_backup("calibre_sync")
            archived=[]
            try:
                for bid,keys in matches.items():
                    self.db.set_purchased(bid,True)
                    archived.append((title_for(bid),sorted(keys)))
            except Exception as e:
                messagebox.showerror("Calibre Sync",f"Sync stopped:\n{e}\n\nBackup: {backup}")
                return
            result=[
                "CALIBRE PURCHASE SYNC — COMPLETE","",
                f"Archived: {len(archived)}",
                f"Already archived: {len(already)}",
                f"Backup: {backup}","",
                "ARCHIVED","-"*72
            ]
            for title,keys in archived:
                result += [title,"  Matched: "+", ".join(keys),""]
            result_text="\n".join(result)
            self.refresh(); w.destroy()
            self.show_match_report(result_text)
        ttk.Button(footer,text="Archive matched books",command=apply_sync).pack(side="right")
        ttk.Button(footer,text="Cancel",command=w.destroy).pack(side="right",padx=(0,8))
        ttk.Button(footer,text="Copy Preview",command=copy_preview).pack(side="left")

    def save_backup(self):
        p=filedialog.asksaveasfilename(defaultextension=".db",filetypes=[("Book Sale backup","*.db")])
        if p: self.db.backup_to(p); messagebox.showinfo("Backup","Backup saved.")

    def restore_backup(self):
        p=filedialog.askopenfilename(filetypes=[("Book Sale backup","*.db"),("All files","*.*")])
        if not p:return
        safety=self.auto_backup()
        if messagebox.askyesno("Restore","Restore this backup? Current state was safety-backed-up first."):
            self.db.restore_from(p); self.refresh(); messagebox.showinfo("Restored",f"Restored.\nSafety backup: {safety}")

    def export_share(self):
        p=filedialog.asksaveasfilename(defaultextension=".bscshare",filetypes=[("Book Sale shared list","*.bscshare")])
        if not p:return
        books=[]
        for b,offers in self.db.rows("",True):
            books.append({"title":b["title"],"author":b["author"],"status":b["status"],
                          "offers":[{"store":o["store"],"store_id":o["store_id"],"title":o["title"],
                                     "url":o["url"],"price":o["price"],"list_price":o["list_price"],
                                     "reward_pct":o["reward_pct"],"reward_value":o["reward_value"],
                                     "tax_ex_price":o["tax_ex_price"],"author":o["author"]} for o in offers.values()]})
        Path(p).write_text(json.dumps({"schema_version":1,"type":"book_list","books":books},
                                      ensure_ascii=False,indent=2),encoding="utf-8")
        messagebox.showinfo("Exported",f"Exported {len(books)} books.")

    def import_share(self):
        p=filedialog.askopenfilename(filetypes=[("Book Sale shared list","*.bscshare"),("JSON","*.json")])
        if not p:return
        data=json.loads(Path(p).read_text(encoding="utf-8"))
        books=data.get("books",[])
        # Read-only preview first; nothing changes until explicit Import All.
        w=tk.Toplevel(self); w.title("Shared List — View only"); w.geometry("900x560")
        w.resizable(False,False)
        ttk.Label(w,text=f"VIEW ONLY • {len(books)} books • Nothing is imported until you press Import All",
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=10,pady=8)
        t=ttk.Treeview(w,columns=("title","stores"),show="headings")
        t.heading("title",text="Book"); t.heading("stores",text="Known stores")
        t.column("title",width=650); t.column("stores",width=180)
        for i,b in enumerate(books):
            t.insert("","end",iid=str(i),values=(b.get("title",""),", ".join(x.get("store","") for x in b.get("offers",[]))))
        t.pack(fill="both",expand=True,padx=10)
        def do_import():
            self.auto_backup('shared_list_import'); added=0
            name=Path(p).stem; list_id=self.db.create_list(name if name else 'Imported List')
            for b in books:
                for od in b.get("offers",[]):
                    o=Offer(od.get("store",""),od.get("title") or b.get("title",""),od.get("url",""),
                            od.get("price"),od.get("list_price"),od.get("reward_pct"),od.get("reward_value"),
                            od.get("author") or b.get("author",""),od.get("store_id",""))
                    if o.store in STORES:
                        self.db.import_offer(o,list_id); added+=1
            self.rebuild_list_tabs(); self.refresh(); w.destroy()
            messagebox.showinfo("Import complete",f"Merged {len(books)} shared books ({added} store records).")
        ttk.Button(w,text="Import All",command=do_import).pack(side="right",padx=10,pady=10)
        ttk.Button(w,text="Close without importing",command=w.destroy).pack(side="right",pady=10)

    def export_history(self):
        p=filedialog.asksaveasfilename(defaultextension=".bschistory",filetypes=[("Book Sale history","*.bschistory")])
        if not p:return
        rows=self.db.cx.execute("""SELECT b.title,o.store,o.store_id,o.url,h.observed_at,h.price,h.list_price,
                                  h.reward_pct,h.reward_value,h.provenance
                                  FROM price_history h JOIN offers o ON o.id=h.offer_id
                                  JOIN books b ON b.id=o.book_id ORDER BY h.observed_at""").fetchall()
        payload={"schema_version":1,"type":"price_history","observations":[dict(r) for r in rows]}
        Path(p).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        messagebox.showinfo("Exported",f"Exported {len(rows)} observations.")

    def import_history(self):
        p=filedialog.askopenfilename(filetypes=[("Book Sale history","*.bschistory"),("JSON","*.json")])
        if not p:return
        data=json.loads(Path(p).read_text(encoding="utf-8")); obs=data.get("observations",[])
        self.auto_backup(); n=0
        for x in obs:
            o=Offer(x.get("store",""),x.get("title",""),x.get("url",""),x.get("price"),x.get("list_price"),
                    x.get("reward_pct"),x.get("reward_value"),store_id=x.get("store_id",""))
            if o.store not in STORES: continue
            bid=self.db.add_offer(o)
            orow=self.db.cx.execute("SELECT id FROM offers WHERE book_id=? AND store=?",(bid,o.store)).fetchone()
            if orow:
                self.db.cx.execute("""INSERT OR IGNORE INTO price_history
                    (offer_id,observed_at,price,list_price,reward_pct,reward_value,provenance)
                    VALUES(?,?,?,?,?,?,?)""",(orow["id"],x.get("observed_at") or datetime.now().isoformat(" "),
                    x.get("price"),x.get("list_price"),x.get("reward_pct"),x.get("reward_value"),"shared"))
                n+=1
        self.db.cx.commit(); self.refresh(); messagebox.showinfo("History imported",f"Merged {n} historical observations.")

    def settings_dialog(self):
        w=tk.Toplevel(self); w.title("Settings"); w.geometry("590x750"); w.resizable(False,False)
        f=ttk.Frame(w,padding=16); f.pack(fill="both",expand=True)
        notify=tk.StringVar(value=self.db.get_setting("notification_rule","any_sale"))
        threshold=tk.StringVar(value=self.db.get_setting("deal_threshold","20"))
        rewards=tk.BooleanVar(value=self.db.get_setting("include_direct_rewards","1")=="1")
        bw_tax=tk.BooleanVar(value=self.db.get_setting("bw_overseas_tax","0")=="1")
        show_covers=tk.BooleanVar(value=self.db.get_setting("show_covers","1")=="1")
        cover_size=tk.StringVar(value=self.db.get_setting("cover_size","medium"))
        store_booklive=tk.BooleanVar(value=self.db.get_setting("store_booklive_enabled","1")=="1")
        store_bookwalker=tk.BooleanVar(value=self.db.get_setting("store_bookwalker_enabled","1")=="1")
        store_dmm=tk.BooleanVar(value=self.db.get_setting("store_dmm_enabled","1")=="1")
        interval=tk.StringVar(value=self.db.get_setting("update_interval_hours","6"))
        reqdelay=tk.StringVar(value=self.db.get_setting("request_delay_seconds","1.25"))
        appearance=tk.StringVar(value=self.db.get_setting("appearance","system"))
        retention=tk.StringVar(value=self.db.get_setting("trash_retention_days","14"))
        ttk.Label(f,text="Notification rule",font=("Segoe UI",10,"bold")).pack(anchor="w")
        for text,val in [("Any sale","any_sale"),("Lowest recorded price","historical_low"),("Good deal","good_deal")]:
            ttk.Radiobutton(f,text=text,variable=notify,value=val).pack(anchor="w")
        row=ttk.Frame(f); row.pack(fill="x",pady=6)
        ttk.Label(row,text="Good-deal threshold (> %):").pack(side="left")
        ttk.Entry(row,textvariable=threshold,width=8).pack(side="left",padx=6)
        def apply_price_view():
            self.db.set_setting("include_direct_rewards","1" if rewards.get() else "0")
            self.db.set_setting("bw_overseas_tax","1" if bw_tax.get() else "0")
            self.refresh()
        ttk.Checkbutton(f,text="Show direct DMM points / BOOK☆WALKER coins in store price columns",
                        variable=rewards,command=apply_price_view).pack(anchor="w",pady=5)
        ttk.Checkbutton(f,text="BOOK☆WALKER overseas tax mode (show stored tax-exclusive price when known)",
                        variable=bw_tax,command=apply_price_view).pack(anchor="w",pady=5)
        def apply_cover_setting():
            self.db.set_setting("show_covers","1" if show_covers.get() else "0")
            self.db.set_setting("cover_size",cover_size.get())
            self.refresh()
        ttk.Separator(f,orient="horizontal").pack(fill="x",pady=(10,8))
        ttk.Label(f,text="Cover display",font=("Segoe UI",10,"bold")).pack(anchor="w")
        ttk.Checkbutton(f,text="Show book covers",variable=show_covers,
                        command=apply_cover_setting).pack(anchor="w",pady=4)
        size_row=ttk.Frame(f); size_row.pack(fill="x",pady=(0,6))
        ttk.Label(size_row,text="Cover size:").pack(side="left")
        for label,value in (("Small","small"),("Medium","medium"),("Large","large")):
            ttk.Radiobutton(size_row,text=label,variable=cover_size,value=value,
                            command=apply_cover_setting).pack(side="left",padx=(8,0))
        ttk.Separator(f,orient="horizontal").pack(fill="x",pady=(10,8))
        ttk.Label(f,text="Stores",font=("Segoe UI",10,"bold")).pack(anchor="w")
        ttk.Label(f,text="Disabled stores are hidden and skipped by matching, updates and cover fetching.",
                  wraplength=500).pack(anchor="w",pady=(0,4))
        def apply_store_settings():
            self.db.set_setting("store_booklive_enabled","1" if store_booklive.get() else "0")
            self.db.set_setting("store_bookwalker_enabled","1" if store_bookwalker.get() else "0")
            self.db.set_setting("store_dmm_enabled","1" if store_dmm.get() else "0")
            self.apply_store_columns(); self.refresh()
        ttk.Checkbutton(f,text="BookLive",variable=store_booklive,command=apply_store_settings).pack(anchor="w")
        ttk.Checkbutton(f,text="BOOK☆WALKER",variable=store_bookwalker,command=apply_store_settings).pack(anchor="w")
        ttk.Checkbutton(f,text="DMM",variable=store_dmm,command=apply_store_settings).pack(anchor="w")
        row2=ttk.Frame(f); row2.pack(fill="x",pady=8)
        ttk.Label(row2,text="Automatic update interval (hours):").pack(side="left")
        ttk.Combobox(row2,textvariable=interval,values=("3","6","12","24"),width=6,state="readonly").pack(side="left",padx=6)
        row3=ttk.Frame(f); row3.pack(fill="x",pady=5)
        ttk.Label(row3,text="Minimum delay between store requests (seconds):").pack(side="left")
        ttk.Entry(row3,textvariable=reqdelay,width=7).pack(side="left",padx=6)
        ttk.Separator(f).pack(fill="x",pady=(8,6))
        ar=ttk.Frame(f); ar.pack(fill="x"); ttk.Label(ar,text="Appearance:").pack(side="left")
        appearance_values=("system","light","dark") if UI_LANG!="ja" else ("システム","ライト","ダーク")
        appearance_display=tk.StringVar(value=(appearance.get() if UI_LANG!="ja" else {"system":"システム","light":"ライト","dark":"ダーク"}.get(appearance.get(),"システム")))
        appearance_box=ttk.Combobox(ar,textvariable=appearance_display,values=appearance_values,state="readonly",width=10)
        appearance_box.pack(side="left",padx=6)
        rr=ttk.Frame(f); rr.pack(fill="x",pady=5); ttk.Label(rr,text="Recently Deleted retention (days):").pack(side="left"); ttk.Entry(rr,textvariable=retention,width=6).pack(side="left",padx=6)
        ttk.Label(f,text="Live matching is accuracy-first. A low-confidence result is left blank rather than attached to the wrong volume.",wraplength=470).pack(anchor="w",pady=8)
        def save():
            self.db.set_setting("notification_rule",notify.get()); self.db.set_setting("deal_threshold",threshold.get())
            self.db.set_setting("include_direct_rewards","1" if rewards.get() else "0")
            self.db.set_setting("bw_overseas_tax","1" if bw_tax.get() else "0")
            self.db.set_setting("show_covers","1" if show_covers.get() else "0")
            self.db.set_setting("cover_size",cover_size.get())
            self.db.set_setting("store_booklive_enabled","1" if store_booklive.get() else "0")
            self.db.set_setting("store_bookwalker_enabled","1" if store_bookwalker.get() else "0")
            self.db.set_setting("store_dmm_enabled","1" if store_dmm.get() else "0")
            self.db.set_setting("update_interval_hours",interval.get())
            self.db.set_setting("request_delay_seconds",reqdelay.get())
            chosen_appearance=appearance_display.get(); appearance.set({"システム":"system","ライト":"light","ダーク":"dark"}.get(chosen_appearance,chosen_appearance))
            self.db.set_setting("appearance",appearance.get()); self.db.set_setting("trash_retention_days",retention.get())
            self.apply_theme()
            try:self.providers=live_providers(float(reqdelay.get()), self.log)
            except:pass
            w.destroy()
        savebar=ttk.Frame(w,padding=(16,4,16,12)); savebar.pack(fill="x",side="bottom")
        footer_dark=(self.db.get_setting("appearance","system")=="dark")
        btn_bg="#2a2a2a" if footer_dark else "#f4f4f4"
        btn_fg="#ffffff" if footer_dark else "#111111"
        btn_active_bg="#3a3a3a" if footer_dark else "#e8e8e8"
        btn_active_fg="#ffffff" if footer_dark else "#111111"
        # Fixed-size hosts guarantee a real 120x36 click target on Windows; tk.Button
        # character sizing/pady can otherwise collapse to a very short native control.
        save_host=tk.Frame(savebar,width=120,height=36,bg=btn_bg)
        save_host.pack(side="right"); save_host.pack_propagate(False)
        tk.Button(save_host,text="Save",command=save,bg=btn_bg,fg=btn_fg,
                  activebackground=btn_active_bg,activeforeground=btn_active_fg,
                  disabledforeground="#777777",relief="solid",bd=1).pack(fill="both",expand=True)

        cancel_host=tk.Frame(savebar,width=120,height=36,bg=btn_bg)
        cancel_host.pack(side="right",padx=(0,10)); cancel_host.pack_propagate(False)
        tk.Button(cancel_host,text="Cancel",command=w.destroy,bg=btn_bg,fg=btn_fg,
                  activebackground=btn_active_bg,activeforeground=btn_active_fg,
                  disabledforeground="#777777",relief="solid",bd=1).pack(fill="both",expand=True)

    def _offer_from_live(self,r):
        return Offer(store=r.store,title=r.title,url=r.url,price=r.price,list_price=r.list_price,
                     reward_pct=r.reward_pct,reward_value=r.reward_value,
                     tax_ex_price=getattr(r,"tax_ex_price",None),cover_url=getattr(r,"cover_url",""),
                     author=r.author,store_id=r.store_id)

    def _run_background(self,fn):
        def runner():
            try: fn()
            except Exception as e:
                error_message = str(e)
                self.after(0, lambda msg=error_message: messagebox.showerror("Live scraper", msg))
        threading.Thread(target=runner,daemon=True).start()

    def find_missing_matches(self):
        targets=self.selected_ids()
        enabled_stores=set(self.enabled_stores())
        if not targets:
            if not messagebox.askyesno("Find missing matches","No book is selected. Match/reconcile ALL active books in this list?"): return
            targets=[b['id'] for b,_ in self.db.rows('',False,self.current_list_id,False)]
        self.auto_backup('find_missing_matches')
        def work():
            checked=found=merged=0; report=[]; worker_db=DB()
            try:
                # First reconcile duplicate canonical entries across DIFFERENT stores only.
                books=[worker_db.cx.execute("SELECT * FROM books WHERE id=?",(x,)).fetchone() for x in targets]
                books=[x for x in books if x]
                consumed=set()
                for i,b in enumerate(books):
                    if b['id'] in consumed:continue
                    bs={x['store'] for x in worker_db.cx.execute("SELECT store FROM offers WHERE book_id=?",(b['id'],))}
                    for c in books[i+1:]:
                        if c['id'] in consumed:continue
                        cs={x['store'] for x in worker_db.cx.execute("SELECT store FROM offers WHERE book_id=?",(c['id'],))}
                        score=title_similarity(b['title'],c['title'])
                        if score>=.965 and bs.isdisjoint(cs):
                            urls1=[f"{x['store']}: {x['url']}" for x in worker_db.cx.execute("SELECT store,url FROM offers WHERE book_id=?",(b['id'],))]
                            urls2=[f"{x['store']}: {x['url']}" for x in worker_db.cx.execute("SELECT store,url FROM offers WHERE book_id=?",(c['id'],))]
                            if worker_db.merge_books(b['id'],c['id']):
                                merged+=1; consumed.add(c['id']); bs|=cs
                                report.append(f"MERGED ({score:.3f})\n  Kept: {b['title']}\n    "+"\n    ".join(urls1)+f"\n  Merged: {c['title']}\n    "+"\n    ".join(urls2))
                for book_id in targets:
                    if book_id in consumed:continue
                    b=worker_db.cx.execute("SELECT * FROM books WHERE id=?",(book_id,)).fetchone()
                    if not b:continue
                    existing={r['store']:r for r in worker_db.cx.execute("SELECT * FROM offers WHERE book_id=?",(book_id,))}
                    source=next(iter(existing.values()),None); qtitle=source['title'] if source else b['title']; qauthor=(source['author'] if source and source['author'] else b['author']) or ''
                    for store,p in self.providers.items():
                        if store not in enabled_stores or store in existing:continue
                        try:
                            r=p.best(qtitle,qauthor); checked+=1
                            if r:
                                # If this exact store product was imported as its own canonical entry, merge that entry instead of duplicating offer.
                                er=worker_db.cx.execute("SELECT book_id FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",(store,r.store_id,canonical_url(r.url))).fetchone()
                                if er and er['book_id']!=book_id:
                                    other=er['book_id']; ob=worker_db.cx.execute("SELECT title FROM books WHERE id=?",(other,)).fetchone()
                                    if worker_db.merge_books(book_id,other):
                                        merged+=1; report.append(f"MERGED via {store} exact product\n  Kept: {b['title']}\n  Merged: {ob['title'] if ob else other}\n  URL: {r.url}")
                                else:
                                    # Force attachment to this book rather than fuzzy choosing another canonical row.
                                    worker_db.update_offer_for_book(book_id,store,self._offer_from_live(r)); found+=1
                                    report.append(f"MATCHED {store} ({r.confidence:.3f})\n  {b['title']}\n  {r.url}")
                            else: report.append(f"NO MATCH {store}\n  {b['title']}")
                        except Exception as e: report.append(f"ERROR {store}\n  {b['title']}\n  {type(e).__name__}: {e}")
            finally:worker_db.cx.close()
            textlog=f"Find Missing Matches complete\nChecked slots: {checked}\nNew matches: {found}\nBooks merged: {merged}\n\n"+"\n\n".join(report)
            self.after(0,self.refresh); self.after(0,lambda:self.show_match_report(textlog))
        self._run_background(work)

    def update_prices(self):
        selected=set(self.selected_ids())
        if not selected:
            messagebox.showinfo("Update","Select one or more books first.")
            return

        w=tk.Toplevel(self); w.title("Update selected books"); w.geometry("520x330"); w.resizable(False,False)
        w.transient(self); w.grab_set()
        f=ttk.Frame(w,padding=18); f.pack(fill="both",expand=True)
        ttk.Label(f,text=f"Update {len(selected)} selected book(s)",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,8))
        ttk.Label(f,text="Choose what should be refreshed. Only enabled stores with an existing product URL are contacted.",
                  wraplength=475).pack(anchor="w",pady=(0,14))

        mode=tk.StringVar(value="missing_price")
        options=[
            ("covers","Update covers only","Fetch product pages only to refresh/cache cover images. Prices and price history are not changed."),
            ("missing_price","Update books without price","Only update matched store offers whose current price is missing."),
            ("everything","Update everything selected","Refresh price, rewards and cover for every matched offer on the selected books."),
        ]
        for value,label,desc in options:
            row=ttk.Frame(f); row.pack(fill="x",pady=4)
            ttk.Radiobutton(row,text=label,value=value,variable=mode).pack(anchor="w")
            ttk.Label(row,text=desc,wraplength=445).pack(anchor="w",padx=(24,0))

        footer=ttk.Frame(f); footer.pack(fill="x",side="bottom",pady=(14,0))
        ttk.Button(footer,text="Cancel",command=w.destroy).pack(side="right")
        ttk.Button(footer,text="Start update",command=lambda:self._start_update_prices(selected,mode.get(),w)).pack(side="right",padx=(0,8))

    def _start_update_prices(self, selected, mode, dialog):
        rows=self.db.rows("",False,self.current_list_id,False)
        jobs=[]
        for b,offers in rows:
            if b["id"] not in selected:continue
            for store,o in offers.items():
                if not self.store_enabled(store) or store not in self.providers or not o["url"]:continue
                if mode=="missing_price" and o["price"] is not None:continue
                jobs.append((b["id"],store,o["url"],o["locked"]))
        if not jobs:
            messagebox.showinfo("Update","No matched product pages meet the selected update mode.")
            return
        dialog.destroy()
        self.auto_backup("update_"+mode)

        def work():
            ok=0; failed=[]; worker_db=DB()
            try:
                for i,(bid,store,url,locked) in enumerate(jobs,1):
                    self.after(0,lambda i=i,st=store:self.status.set(f"Updating {i}/{len(jobs)} • {st}"))
                    try:
                        r=self.providers[store].product(url)
                        if mode=="covers":
                            if getattr(r,"cover_url",""):
                                self.after(0,lambda bid=bid,store=store,url=r.cover_url:self.cache_cover(bid,store,url))
                            ok+=1
                            self.log(f"[{store}] Cover checked: {r.title or url}")
                            continue
                        if not r.title:
                            brow=worker_db.cx.execute("SELECT title FROM books WHERE id=?",(bid,)).fetchone()
                            r.title=brow["title"] if brow else ""
                        fetched=self._offer_from_live(r); fetched.url=url
                        saved_bid=worker_db.update_offer_for_book(bid,store,fetched); ok+=1
                        if getattr(r,"cover_url",""):
                            self.after(0,lambda bid=saved_bid,store=store,url=r.cover_url:self.cache_cover(bid,store,url))
                        shown=("¥"+format(r.price,",")) if r.price is not None else "price not parsed"
                        self.log(f"[{store}] Updated: {r.title or url} — {shown}")
                    except Exception as e:
                        failed.append(f"{store}: {type(e).__name__}: {e}")
                        self.log(f"[{store}] UPDATE ERROR {type(e).__name__}: {e}")
            finally:
                worker_db.cx.close()
            self.after(0,self.refresh); self.after(0,lambda:self.status.set("Ready"))
            label={"covers":"cover page(s) checked","missing_price":"missing-price offer(s) updated","everything":"product page(s) updated"}[mode]
            msg=f"{ok}/{len(jobs)} {label}."
            if failed:msg+="\n\nFailed:\n"+"\n".join(failed[:12])
            self.after(0,lambda m=msg:messagebox.showinfo("Update complete",m))
        self._run_background(work)


    def _version_tuple(self, value):
        nums=re.findall(r"\d+",str(value or ""))
        return tuple(int(x) for x in nums[:3]) if nums else (0,)

    def check_for_updates(self, silent=False):
        if not GITHUB_OWNER or not GITHUB_REPO:
            if not silent: messagebox.showinfo("Updates","GitHub updates are not configured in this build yet.")
            return
        self.status.set("Checking for updates…")
        def work():
            try:
                api=f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
                req=urllib.request.Request(api,headers={"Accept":"application/vnd.github+json","User-Agent":APP_NAME})
                with urllib.request.urlopen(req,timeout=15) as r:
                    release=json.loads(r.read().decode("utf-8"))
                latest=str(release.get("tag_name","")).lstrip("vV")
                if self._version_tuple(latest)<=self._version_tuple(APP_VERSION):
                    if not silent:self.after(0,lambda:messagebox.showinfo("Updates",f"{APP_NAME} is up to date."))
                    return
                asset=next((x for x in (release.get("assets") or [])
                            if x.get("name","").startswith(UPDATE_ASSET_PREFIX) and x.get("name","").endswith(".zip")),None)
                if not asset: raise RuntimeError("Latest release has no Windows update ZIP.")
                body=(release.get("body") or "").strip()
                def prompt():
                    msg=f"Version {latest} is available.\n\n"
                    if body: msg+=body[:1600]+"\n\n"
                    msg+="Download and install it now? The application will restart automatically."
                    if messagebox.askyesno("Update available",msg): self._download_and_install_update(latest,asset)
                self.after(0,prompt)
            except Exception as e:
                if not silent:self.after(0,lambda e=e:messagebox.showerror("Update check failed",f"{type(e).__name__}: {e}"))
            finally:self.after(0,lambda:self.status.set("Ready"))
        self._run_background(work)

    def _download_and_install_update(self, version, asset):
        if not getattr(sys,"frozen",False):
            messagebox.showinfo("Update available","Automatic installation is available in the packaged Windows build.")
            return
        url=asset.get("browser_download_url"); digest=str(asset.get("digest") or "")
        if not url: messagebox.showerror("Update failed","Release asset has no download URL."); return
        self.status.set(f"Downloading {version}…")
        def work():
            try:
                tmp=Path(tempfile.mkdtemp(prefix="bsn_update_")); zpath=tmp/"update.zip"
                req=urllib.request.Request(url,headers={"User-Agent":APP_NAME})
                with urllib.request.urlopen(req,timeout=90) as r, open(zpath,"wb") as f: shutil.copyfileobj(r,f)
                if digest.startswith("sha256:"):
                    actual=hashlib.sha256(zpath.read_bytes()).hexdigest()
                    if actual.lower()!=digest.split(":",1)[1].lower(): raise RuntimeError("SHA-256 verification failed.")
                exe=Path(sys.executable)
                ps=tmp/"apply_update.ps1"
                script = """$pidToWait = __PID__
$zip = '__ZIP__'
$install = '__INSTALL__'
$exe = '__EXE__'
while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 250 }
$stage = Join-Path '__TMP__' 'stage'
Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force
$items = Get-ChildItem -LiteralPath $stage
$src = $stage
if ($items.Count -eq 1 -and $items[0].PSIsContainer) { $src = $items[0].FullName }
Copy-Item -Path (Join-Path $src '*') -Destination $install -Recurse -Force
Start-Process -FilePath (Join-Path $install $exe) -WorkingDirectory $install
"""
                esc=lambda x:str(x).replace("'","''")
                script=script.replace("__PID__",str(os.getpid())).replace("__ZIP__",esc(zpath)).replace("__INSTALL__",esc(exe.parent)).replace("__EXE__",esc(exe.name)).replace("__TMP__",esc(tmp))
                ps.write_text(script,encoding="utf-8")
                subprocess.Popen(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ps)],
                                 creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                self.after(0,self.destroy)
            except Exception as e:
                self.after(0,lambda e=e:messagebox.showerror("Update failed",f"{type(e).__name__}: {e}"))
                self.after(0,lambda:self.status.set("Ready"))
        self._run_background(work)

    def sort_by(self,col):
        data=[(self.tree.set(k,col),k) for k in self.tree.get_children("")]
        def key(x):
            m=re.search(r'¥([0-9,]+)',x[0])
            return (0,int(m.group(1).replace(",",""))) if m else (1,x[0].lower())
        data.sort(key=key)
        for i,(_,k) in enumerate(data): self.tree.move(k,"",i)

if __name__=="__main__":
    App().mainloop()
