from __future__ import annotations
import sys, os, subprocess, tempfile, hashlib, urllib.request, shutil
import requests
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
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image=ImageTk=ImageDraw=None
import csv, shutil, threading, time
from datetime import datetime, timedelta
from scraper import providers as live_providers, parse_volume as live_parse_volume, edition_compatible as live_edition_compatible, DMMRegionError

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("Missing dependency: beautifulsoup4. Run: py -m pip install beautifulsoup4")

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.dates as mdates
    from matplotlib.ticker import MultipleLocator, FuncFormatter
except ImportError:
    Figure=FigureCanvasTkAgg=NavigationToolbar2Tk=mdates=MultipleLocator=FuncFormatter=None

APP_NAME = "Book Sale Notification 1.9.1-beta.6"
APP_VERSION = "1.9.1-beta.6"
# Set these before publishing GitHub releases.
GITHUB_OWNER = "PickledCakes"
GITHUB_REPO = "BookSaleNotification"
UPDATE_ASSET_PREFIX = "BookSaleNotification-Windows-"
MAIN_DEFAULT_GEOMETRY = "1420x780"
MAIN_MIN_WIDTH = 1320
MAIN_MIN_HEIGHT = 640
TABLE_PANE_MIN_WIDTH = 1000
ACTIVITY_PANE_MIN_WIDTH = 250
def app_data_dir():
    if getattr(sys,"frozen",False):
        base=Path(os.environ.get("LOCALAPPDATA",str(Path.home()/"AppData"/"Local")))
        p=base/"BookSaleNotification"; p.mkdir(parents=True,exist_ok=True); return p
    return Path(__file__).resolve().parent
DATA_DIR=app_data_dir()
DB_PATH=DATA_DIR/"books.db"
BW_SESSION_PATH=DATA_DIR/"bookwalker_session.dat"
BW_WEBVIEW_DIR=DATA_DIR/"bookwalker_webview"
BW_LOGIN_ERROR_PATH=DATA_DIR/"bookwalker_login_error.txt"
INSTANCE_PORT=47653
_SINGLE_INSTANCE_MUTEX=None

def _activate_existing_instance():
    """Ask the already-running app to restore/focus itself, including from tray."""
    import socket
    for _ in range(8):
        try:
            with socket.create_connection(("127.0.0.1",INSTANCE_PORT),timeout=0.25) as s:
                s.sendall(b"SHOW")
                return True
        except OSError:
            time.sleep(0.08)
    if os.name=="nt":
        try:
            import ctypes
            user32=ctypes.windll.user32
            found={"hwnd":0}
            WNDENUMPROC=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
            def enum_cb(hwnd,lparam):
                n=user32.GetWindowTextLengthW(hwnd)
                if n:
                    buf=ctypes.create_unicode_buffer(n+1)
                    user32.GetWindowTextW(hwnd,buf,n+1)
                    if buf.value.startswith("Book Sale Notification"):
                        found["hwnd"]=hwnd
                        return False
                return True
            user32.EnumWindows(WNDENUMPROC(enum_cb),0)
            if found["hwnd"]:
                user32.ShowWindow(found["hwnd"],9)  # SW_RESTORE
                user32.SetForegroundWindow(found["hwnd"])
                return True
        except Exception:
            pass
    return False

def acquire_single_instance():
    """Return False for a second main-app launch and activate the first instance."""
    global _SINGLE_INSTANCE_MUTEX
    if os.name!="nt":
        return True
    try:
        import ctypes
        kernel32=ctypes.windll.kernel32
        handle=kernel32.CreateMutexW(None,False,"Local\\BookSaleNotification_MainInstance")
        if not handle:
            return True
        if kernel32.GetLastError()==183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            _activate_existing_instance()
            return False
        _SINGLE_INSTANCE_MUTEX=handle
    except Exception:
        return True
    return True

def _dpapi_crypt(data, protect=True):
    """Protect BOOK☆WALKER session cookies with the current Windows user account."""
    if os.name!="nt":
        return data
    import ctypes
    from ctypes import wintypes
    class DATA_BLOB(ctypes.Structure):
        _fields_=[("cbData",wintypes.DWORD),("pbData",ctypes.POINTER(ctypes.c_byte))]
    src=ctypes.create_string_buffer(data)
    in_blob=DATA_BLOB(len(data),ctypes.cast(src,ctypes.POINTER(ctypes.c_byte)))
    out_blob=DATA_BLOB()
    if protect:
        ok=ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),None,None,None,None,0,ctypes.byref(out_blob))
    else:
        ok=ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),None,None,None,None,0,ctypes.byref(out_blob))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData,out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)

def save_bookwalker_cookies(records):
    records=[x for x in (records or []) if x.get("name") and x.get("value")]
    payload=json.dumps({"version":1,"saved_at":datetime.now().isoformat(timespec="seconds"),
                        "cookies":records},ensure_ascii=False).encode("utf-8")
    BW_SESSION_PATH.write_bytes(b"BSNDPAPI1"+_dpapi_crypt(payload,True))

def load_bookwalker_cookies():
    try:
        raw=BW_SESSION_PATH.read_bytes()
        if raw.startswith(b"BSNDPAPI1"):
            raw=_dpapi_crypt(raw[len(b"BSNDPAPI1"):],False)
        obj=json.loads(raw.decode("utf-8"))
        return [x for x in (obj.get("cookies") or [])
                if isinstance(x,dict) and "bookwalker.jp" in str(x.get("domain") or "").lower()]
    except Exception:
        return []

def check_bookwalker_session():
    """Return (status, detail) where status is signed_in/signed_out/unavailable."""
    records=load_bookwalker_cookies()
    if not records:
        return "signed_out","No saved BOOK☆WALKER session."
    s=requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
                      "Accept-Language":"ja-JP,ja;q=0.9,en;q=0.6"})
    for item in records:
        try:
            s.cookies.set(str(item.get("name") or ""),str(item.get("value") or ""),
                          domain=str(item.get("domain") or ".bookwalker.jp"),
                          path=str(item.get("path") or "/"))
        except Exception:
            pass
    try:
        r=s.get("https://bookwalker.jp/",timeout=15,allow_redirects=True)
        r.raise_for_status()
        if re.search(r"BW_IS_LOGIN\s*=\s*true",r.text,re.I):
            refreshed=[]
            for cookie in s.cookies:
                if "bookwalker.jp" in (cookie.domain or "").lower():
                    refreshed.append({"name":cookie.name,"value":cookie.value,
                                      "domain":cookie.domain or ".bookwalker.jp",
                                      "path":cookie.path or "/"})
            if refreshed:
                try: save_bookwalker_cookies(refreshed)
                except Exception: pass
            return "signed_in","BOOK☆WALKER session is valid."
        if re.search(r"BW_IS_LOGIN\s*=\s*false",r.text,re.I):
            return "signed_out","BOOK☆WALKER reports that this session is signed out."
        return "unavailable","BOOK☆WALKER login state could not be determined."
    except Exception as e:
        return "unavailable",f"{type(e).__name__}: {e}"

def check_dmm_access():
    """Return (status, detail) for DMM Books regional access."""
    try:
        r=requests.get("https://book.dmm.com/",timeout=15,allow_redirects=True,
                       headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
                                "Accept-Language":"ja-JP,ja;q=0.9,en;q=0.6"})
        final=urlparse(r.url)
        host=(final.hostname or "").lower()
        if host=="accounts.dmm.com" and final.path.startswith("/service/login/"):
            return "jp_required","DMM Books redirected to the DMM login/access page."
        r.raise_for_status()
        if host=="book.dmm.com" or host.endswith(".book.dmm.com"):
            return "available","DMM Books is reachable from this network."
        return "unavailable",f"Unexpected DMM destination: {r.url}"
    except Exception as e:
        return "unavailable",f"{type(e).__name__}: {e}"

def bookwalker_login_helper():
    """Run the real BOOK☆WALKER site in a persistent Edge WebView2 profile.

    pywebview owns this helper process's GUI thread. A separate monitor thread
    checks the authenticated session and closes the window once BOOK☆WALKER
    confirms login. The app never receives or stores the user's password.
    """
    try:
        if BW_LOGIN_ERROR_PATH.exists(): BW_LOGIN_ERROR_PATH.unlink()
    except Exception:
        pass
    try:
        import webview
        import requests as _requests
        result={"success":False}

        def cookie_records(window):
            records=[]
            for jar in window.get_cookies() or []:
                try:
                    items=jar.items()
                except Exception:
                    continue
                for name,morsel in items:
                    domain=(morsel["domain"] or ".bookwalker.jp").strip()
                    if "bookwalker.jp" not in domain.lower():
                        continue
                    records.append({"name":name,"value":morsel.value,
                                    "domain":domain,"path":(morsel["path"] or "/")})
            return records

        def session_is_logged_in(records):
            if not records:return False
            s=_requests.Session()
            s.headers.update({"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
                              "Accept-Language":"ja-JP,ja;q=0.9,en;q=0.6"})
            for item in records:
                try:
                    s.cookies.set(item["name"],item["value"],
                                  domain=item.get("domain") or ".bookwalker.jp",
                                  path=item.get("path") or "/")
                except Exception:
                    pass
            try:
                r=s.get("https://bookwalker.jp/",timeout=12,allow_redirects=True)
                return bool(re.search(r"BW_IS_LOGIN\s*=\s*true",r.text,re.I))
            except Exception:
                return False

        def monitor(window):
            # webview.start(func, ...) runs this logic in its own worker thread.
            # Do not perform cookie/JS calls from a synchronous closing handler:
            # Edge WebView2 can deadlock while the native window is shutting down.
            while True:
                try:
                    current=window.get_current_url() or ""
                except Exception:
                    break
                try:
                    host=(urlparse(current).hostname or "").lower()
                    if host=="bookwalker.jp" or host.endswith(".bookwalker.jp"):
                        records=cookie_records(window)
                        if session_is_logged_in(records):
                            save_bookwalker_cookies(records)
                            result["success"]=True
                            time.sleep(0.2)
                            window.destroy()
                            return
                except Exception:
                    pass
                time.sleep(1.0)

        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"]=False
        window=webview.create_window(
            "BOOK☆WALKER Sign In — sign in normally; this window closes when connected",
            "https://bookwalker.jp/",width=1050,height=780,resizable=True)
        webview.start(monitor,window,gui="edgechromium",private_mode=False,
                      storage_path=str(BW_WEBVIEW_DIR))
        return 0 if result["success"] else 2
    except Exception as e:
        try:
            BW_LOGIN_ERROR_PATH.write_text(f"{type(e).__name__}: {e}",encoding="utf-8")
        except Exception:
            pass
        return 1

STORES = ("BookLive", "BOOK☆WALKER", "DMM", "Amazon")
SEARCH_STORES = ("BookLive", "BOOK☆WALKER", "DMM")
MANUAL_URL_STORES = STORES
STORE_KEYS = {"BookLive":"booklive", "BOOK☆WALKER":"bookwalker", "DMM":"dmm", "Amazon":"amazon"}
TITLE_SOURCE_PRIORITY = ("BookLive","DMM","BOOK☆WALKER","Amazon")
COVER_SOURCE_PRIORITY = ("BookLive","Amazon","DMM","BOOK☆WALKER")

UI_LANG="en"
JA_UI={
    "Book Sale Notification":"Book Sale Notification",
    "Settings":"設定","Check for Updates":"アップデート確認","Recently Deleted":"最近削除した項目",
    "Backup / Share":"バックアップ / 共有","Import HTML…":"HTMLを読み込む…",
    "Add from URL…":"URLから追加…","Import HTML folder…":"3ストアHTMLフォルダを読み込む…",
    "BookLive + BOOK☆WALKER + DMM live search • Amazon direct URL/HTML import + refresh (search disabled)":
        "BookLive + BOOK☆WALKER + DMM は検索対応 • Amazon はURL/HTML追加・更新対応（検索は無効）",
    "Search:":"検索:","Show only books on sale":"セール中の書籍のみ表示","Delete":"削除","History":"履歴","Mark purchased":"購入済みにする",
    "Edit store URLs":"ストアURLを編集","Find missing matches":"未登録ストアを検索","Update prices":"価格を更新",
    "Book":"書籍","Lowest cash price":"現金最安値","Latest sale":"最新セール","Matched":"一致数","Cover":"表紙",
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
    "DMM Books unavailable":"DMM Booksにアクセスできません",
    "DMM Books could not be reached from the current network. DMM Books requires a Japanese IP address. Connect through a Japanese IP/VPN and try again. Other stores can still be checked.":
        "現在のネットワークからDMM Booksにアクセスできません。DMM Booksには日本のIPアドレスが必要です。日本のIP/VPNに接続してから再試行してください。他のストアの確認は続行できます。",
    "Edit store URLs":"ストアURLを編集",
    "Edit the matched product URL for any store. Amazon URLs are automatically shortened to /dp/ASIN.":
        "各ストアの一致済み商品URLを編集できます。Amazon URLは自動的に /dp/ASIN 形式へ短縮されます。",
    "Open":"開く","Save changes":"変更を保存","Invalid store URL":"無効なストアURL",
    "Add book from store URL":"ストアURLから書籍を追加",
    "Add from BookLive / BOOK☆WALKER / DMM / Amazon URL":"BookLive / BOOK☆WALKER / DMM / Amazon のURLから追加",
    "Paste one product URL. Amazon links are reduced to the clean /dp/ASIN form automatically. Amazon itself is not searched, but an Amazon URL can be used as the source to search the other three stores.":
        "商品URLを1つ貼り付けてください。AmazonのURLは自動的に /dp/ASIN 形式へ短縮します。Amazon自体の検索は行いませんが、Amazon URLを元に他の3ストアを検索できます。",
    "Fetch all stores and add":"ストアを確認して追加","Cancel":"キャンセル",
    "Paste a valid BookLive, BOOK☆WALKER, DMM Books or Amazon.co.jp product URL.":
        "有効なBookLive、BOOK☆WALKER、DMM Books、またはAmazon.co.jpの商品URLを貼り付けてください。",
    "Import wishlist HTML":"ウィッシュリストHTMLを読み込む",
    "Choose folder containing saved wishlist/list HTML files":
        "保存したウィッシュリスト / リストHTMLが入ったフォルダを選択",
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
    "Test sale notification":"セール通知をテスト",
    "Test multiple sale notifications":"複数セール通知をテスト",
    "Simulates a 50% sale using the selected rule. No book data or price history is changed.":
        "選択中の通知ルールで50%オフのセールを模擬します。書籍データや価格履歴は変更されません。",
    "Simulates a 50% sale using the selected rule. The multiple test simulates three books going on sale at once. No book data or price history is changed.":
        "選択中の通知ルールで50%オフのセールを模擬します。複数テストでは3冊が同時にセールになった状況を再現します。書籍データや価格履歴は変更されません。",
    "Simulates three books going on sale at once to test grouped notifications.":
        "3冊が同時にセールになった状況を模擬し、まとめ通知をテストします。",
    "Books on sale":"冊の書籍がセール中",
    "qualifying books have new sale prices.":"冊の書籍で通知条件に合う新しいセール価格を検出しました。",
    "Show direct DMM points / BOOK☆WALKER coins / Amazon points in store price columns":
        "DMMポイント / BOOK☆WALKERコイン / Amazonポイントを価格欄に表示",
    "BOOK☆WALKER overseas tax mode (show stored tax-exclusive price when known)":
        "BOOK☆WALKER海外税モード（取得済みの税抜価格があれば表示）",
    "Cover display":"表紙表示","Show book covers":"表紙を表示","Cover size:":"表紙サイズ:",
    "Small":"小","Medium":"中","Large":"大","Stores":"ストア",
    "Disabled stores are hidden and skipped by matching, updates and cover fetching.":
        "無効にしたストアは非表示になり、照合・更新・表紙取得を行いません。",
    "Amazon (HTML import + direct price refresh only)":"Amazon（HTML読込・直接価格更新のみ）",
    "BOOK☆WALKER account":"BOOK☆WALKERアカウント",
    "Sign in to BOOK☆WALKER":"BOOK☆WALKERにログイン",
    "Saved BOOK☆WALKER session":"BOOK☆WALKERログイン保存済み",
    "Not signed in — cash prices still work; coins are hidden.":"未ログイン — 現金価格は取得できますが、コインは表示しません。",
    "Opening BOOK☆WALKER sign-in…":"BOOK☆WALKERのログイン画面を開いています…",
    "BOOK☆WALKER connected":"BOOK☆WALKERに接続しました",
    "BOOK☆WALKER sign-in was not completed.":"BOOK☆WALKERへのログインが完了しませんでした。",
    "BOOK☆WALKER connected. Future price updates will use the signed-in session for coin values.":
        "BOOK☆WALKERに接続しました。今後の価格更新ではログイン中のアカウントのコイン数を取得します。",
    "Your BOOK☆WALKER session has expired. Sign in again to continue receiving your account-specific coin amounts.":
        "BOOK☆WALKERのセッションが期限切れです。アカウント固有のコイン数を取得するには、もう一度ログインしてください。",
    "Sale notification test":"セール通知テスト",
    "Test Book":"テスト書籍",
    "Check for new versions on startup (never installs automatically)":"起動時に新しいバージョンを確認する（自動インストールはしません）",
    "Use nightly / pre-release versions (test builds)":"ナイトリー / プレリリース版（テストビルド）を使用する",
    "Off = stable releases only. Test builds may contain unfinished fixes.":
        "オフの場合は安定版のみです。テストビルドには未完成の修正が含まれる場合があります。",
    "Check now":"今すぐ確認",
    "Signed in":"ログイン済み",
    "Signed in (last known)":"ログイン済み（前回確認）",
    "Session expired":"セッション期限切れ",
    "Not signed in":"未ログイン",
    "Not checked":"未確認",
    "Checking…":"確認中…",
    "Japanese access available":"日本のIPでアクセス可能",
    "Japanese IP required":"日本のIPアドレスが必要",
    "Could not check":"確認できませんでした",
    "Close button (X):":"閉じるボタン (X):",
    "Minimize to system tray":"システムトレイに最小化",
    "Exit application":"アプリを終了",
    "BOOK☆WALKER sign-in required":"BOOK☆WALKERへの再ログインが必要",
    "System tray unavailable":"システムトレイを利用できません",
    "The system tray icon could not be created, so the app was left open.":
        "システムトレイのアイコンを作成できなかったため、アプリは開いたままです。",
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

AMAZON_PUBLISHER_HINTS=(
    "コミック","コミックス","COMIC","COMICS","文庫","マガジン","MAGAZINE",
    "DIGITAL","デジタル版","シリーズ","レーベル","電撃","角川","KADOKAWA",
    "チャンピオン","モーニング","デザート","フラワー","ガンガン","ビーム",
    "ヤング","アクション","シリウス","ゼノン","マーガレット","ドラゴン",
    "アルファポリス","ガルド","メテオ","トレイル","NOIPA","BLIC","MANGA",
    "HJコミックス","HJ文庫","MFコミックス","MF文庫","GA文庫","GAコミック","FLOS","アース・スター","トライゾン","異世界ヒロインファンタジー"
)

def amazon_title_for_match(title):
    """Remove only a likely trailing Amazon imprint/publisher tag.

    Parentheses are never removed generically: volume numbers often live in them.
    """
    s=unicodedata.normalize("NFKC",str(title or "")).strip()
    m=re.search(r"\s*[（(]([^()（）]{1,70})[）)]\s*$",s)
    if not m:return s
    tag=m.group(1).strip()
    # Never strip a terminal volume token or known edition/type marker.
    if re.fullmatch(r"\s*(?:第\s*)?\d+(?:\.\d+)?\s*(?:巻)?\s*",tag,re.I):
        return s
    if any(marker in tag for marker in ("特装版","合本版","単話版","無料版","セット版","分冊版","完全版","愛蔵版")):
        return s
    prefix=s[:m.start()].rstrip()
    tag_upper=tag.upper()
    publisherish=any(h.upper() in tag_upper for h in AMAZON_PUBLISHER_HINTS)
    # Unknown parenthetical text is preserved. Missing an automatic merge is safer
    # than deleting a legitimate subtitle/edition note.
    return prefix if publisherish else s

def cross_store_title_similarity(title_a,stores_a,title_b,stores_b):
    stores_a=set(stores_a or ()); stores_b=set(stores_b or ())
    amazon_a="Amazon" in stores_a; amazon_b="Amazon" in stores_b
    if amazon_a ^ amazon_b:
        aa=amazon_title_for_match(title_a) if amazon_a else title_a
        bb=amazon_title_for_match(title_b) if amazon_b else title_b
        if not live_edition_compatible(aa,bb):
            return 0.0
        _ab,av=live_parse_volume(aa); _bb,bv=live_parse_volume(bb)
        # Conservative Amazon reconciliation: if either side has a volume hint,
        # both sides must have the same one.
        if (av is None) != (bv is None): return 0.0
        if av is not None and str(av)!=str(bv): return 0.0
        return title_similarity(aa,bb)
    return title_similarity(title_a,title_b)

def canonical_url(url):
    if not url: return ""
    return url.split("?")[0].split("#")[0]

def canonical_store_url(store, url):
    """Return the stable product URL used by the database.

    Amazon product links are aggressively reduced to /dp/<ASIN> so locale slugs,
    search refs, query parameters and other tracking data are never stored.
    """
    raw=(url or "").strip()
    if store=="Amazon":
        try:
            u=urlparse(raw)
            host=(u.hostname or "").lower().rstrip(".")
            if not (host=="amazon.co.jp" or host.endswith(".amazon.co.jp")):
                return raw
            m=re.search(r"/dp/([A-Z0-9]{10})(?:/|$)",u.path,re.I)
            if m:
                return f"https://www.amazon.co.jp/dp/{m.group(1).upper()}"
        except Exception:
            return raw
    return canonical_url(raw)

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
    if store=="Amazon":
        return (host=="amazon.co.jp" or host.endswith(".amazon.co.jp")) and bool(re.search(r"/dp/[A-Z0-9]{10}(?:/|$)",path,re.I))
    return False

def parse_amazon(soup):
    out = []

    # Amazon.co.jp wishlist HTML.
    for item in soup.select(".g-item-sortable"):
        text=item.get_text(" ",strip=True)
        # Keep phase 1 Kindle/digital-only. A normal Amazon wishlist can also contain
        # physical books and unrelated products.
        if "Kindle" not in text and "Digital" not in text and "電子書籍" not in text:
            continue
        links=[a for a in item.find_all("a",href=True)
               if re.search(r"(?:amazon\.co\.jp)?/dp/[A-Z0-9]{10}",a["href"],re.I)
               and a.get_text(" ",strip=True)
               and a.get_text(" ",strip=True).lower() not in {"see all buying options"}]
        if not links:continue
        preferred=[a for a in links if "dp_it" in a.get("href","")]
        a=max(preferred or links,key=lambda x:len(x.get_text(" ",strip=True)))
        title=a.get_text(" ",strip=True)
        title=re.sub(r"\s*[（(]\s*Kindle(?:版| Edition)\s*[）)]\s*$","",title,flags=re.I)
        href=a.get("href","")
        mid=re.search(r"/dp/([A-Z0-9]{10})",href,re.I)
        if not mid:continue
        asin=mid.group(1).upper()
        url=f"https://www.amazon.co.jp/dp/{asin}"

        price=None
        for sel in (".a-price .a-offscreen",".itemPriceDrop",".a-price-whole"):
            node=item.select_one(sel)
            if node:
                price=yen(node.get_text(" ",strip=True))
                if price is not None:break
        if price is None:
            mm=re.search(r"[¥￥]\s*([0-9][0-9,]*)",text)
            price=int(mm.group(1).replace(",","")) if mm else None
        author=""
        ma=re.search(r"\bby\s+(.+?)\s+[（(]Kindle Edition[）)]",text,re.I)
        if ma:author=ma.group(1).strip()
        out.append(Offer("Amazon",title,url,price,author=author,store_id=asin,flags="amazon_html"))

    # 電子書籍の司書さん table/list view (SO=14 / 一覧表).
    # This layout has title + author + Amazon ASIN, but normally no price/cover.
    # Import the identity/metadata now; Update Prices can fill Amazon values later.
    for tr in soup.select("table.result2 tr"):
        a=tr.select_one('a[href*="amazon.co.jp/dp/"]')
        if not a:continue
        href=a.get("href","")
        mid=re.search(r"/dp/([A-Z0-9]{10})",href,re.I)
        if not mid:continue
        asin=mid.group(1).upper()
        title=a.get_text(" ",strip=True)
        if not title:continue

        author=""
        cells=tr.find_all("td",recursive=False)
        if len(cells)>=4:
            names=[x.get_text(" ",strip=True) for x in cells[3].find_all("a")
                   if x.get_text(" ",strip=True)]
            if names:
                author=" / ".join(dict.fromkeys(names))
            else:
                author=cells[3].get_text(" ",strip=True)

        cover=""
        img=tr.select_one('img[data-img]') or tr.select_one('img[src*="media-amazon.com"]')
        if img:
            cover=(img.get("data-img") or img.get("src") or "").strip()

        out.append(Offer("Amazon",title,f"https://www.amazon.co.jp/dp/{asin}",None,
                         author=author,cover_url=cover,store_id=asin,flags="xpg_html_table"))

    # 電子書籍の司書さん (k.xpg.jp) saved list HTML.
    # The visible top price is often cash minus points, e.g. ￥327 with
    # "(￥330-3pt)". Store cash=330 and reward=3 so Lowest remains cash-only.
    for li in soup.select("ol.result li"):
        a=li.select_one('h4 a[href*="amazon.co.jp/dp/"]')
        if not a:continue
        href=a.get("href","")
        mid=re.search(r"/dp/([A-Z0-9]{10})",href,re.I)
        if not mid:continue
        asin=mid.group(1).upper()
        title=a.get_text(" ",strip=True)
        price_node=li.select_one("li.price")
        ptext=price_node.get_text(" ",strip=True) if price_node else ""
        cash=reward=None
        pm=re.search(r"[（(]\s*[¥￥]\s*([0-9][0-9,]*)\s*-\s*([0-9][0-9,]*)\s*pt\s*[）)]",ptext,re.I)
        if pm:
            cash=int(pm.group(1).replace(",",""))
            reward=int(pm.group(2).replace(",",""))
        if cash is None:
            pm=re.search(r"[¥￥]\s*([0-9][0-9,]*)",ptext)
            if pm:cash=int(pm.group(1).replace(",",""))
        cover=""
        img=li.select_one("img[data-img]") or li.select_one('img[src*="media-amazon.com"]')
        if img:
            cover=(img.get("data-img") or img.get("src") or "").strip()
        out.append(Offer("Amazon",title,f"https://www.amazon.co.jp/dp/{asin}",cash,
                         reward_value=reward,cover_url=cover,store_id=asin,flags="xpg_html"))
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

    # Current DMM "あとで買う" list layout (2026+):
    # <ul class="fn-bookmarkList"><li class="fn-listContainer ...">...</li></ul>
    for row in soup.select("ul.fn-bookmarkList li.fn-listContainer"):
        a = row.select_one(".tmb a[href*='book.dmm.com/product/']")
        if not a:
            a = row.select_one("a[href*='book.dmm.com/product/']")
        if not a:
            continue
        url = canonical_url(a.get("href",""))
        mid = re.search(r'/product/(\d+)/([^/?#]+)', url, re.I)
        if not mid:
            continue

        title_node=row.select_one(".tmb .txt")
        title=(title_node.get_text(" ",strip=True) if title_node else "").strip()
        if not title:
            img=row.select_one(".tmb img[alt]")
            if img:title=(img.get("alt") or "").strip()
        if not title:
            title=a.get_text(" ",strip=True)
        if not title:
            continue

        p=None
        price_node=row.select_one(".value .price .price__val") or row.select_one(".price__val")
        if price_node:
            m=re.search(r'([0-9][0-9,]*)',price_node.get_text(" ",strip=True))
            if m:p=int(m.group(1).replace(",",""))
        if p is None:
            checkbox=row.select_one("input.fn-bookmarkItemCheck[param-price]")
            if checkbox:
                m=re.search(r'([0-9][0-9,]*)',checkbox.get("param-price",""))
                if m:p=int(m.group(1).replace(",",""))

        author=""
        author_node=row.select_one(".m-bookmarkItem__linkAuthor")
        if author_node:
            names=[x.get_text(" ",strip=True) for x in author_node.select("a")
                   if x.get_text(" ",strip=True)]
            author=" / ".join(dict.fromkeys(names))
            if not author:
                author=author_node.get_text(" ",strip=True).replace("他","").strip()

        rp=None
        campaign=row.select_one(".m-bookmarkItemCampaignText")
        campaign_text=campaign.get_text(" ",strip=True) if campaign else ""
        m=re.search(r'([0-9]+(?:\.[0-9]+)?)\s*%\s*pt還元',campaign_text,re.I)
        if m:rp=float(m.group(1))

        cover=""
        img=row.select_one(".m-bookImage--bookmark img[src]") or row.select_one(".tmb img[src]")
        if img:cover=(img.get("src") or "").strip()

        labels=" ".join(x.get_text(" ",strip=True) for x in row.select(".m-bookProductLabel"))
        flags=[]
        if "予約" in labels:flags.append("preorder")
        if "無料" in labels:flags.append("free")
        if "値引" in labels or "セール" in labels:flags.append("sale")

        sid=f"{mid.group(1)}:{mid.group(2)}"
        out.append(Offer("DMM",title,url,p,reward_pct=rp,author=author,
                         cover_url=cover,store_id=sid,flags=",".join(flags)))

    # Legacy DMM table layout retained for older saved HTML exports.
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
    if ("電子書籍の司書さん" in title and soup.select_one('a[href*="amazon.co.jp/dp/"]')) or soup.select_one("ol.result li h4 a[href*='amazon.co.jp/dp/']"):
        return "Amazon"
    if "amazon" in hay or soup.select_one(".g-item-sortable"): return "Amazon"
    if "bookwalker" in hay or soup.select_one(".bw_checklist_unit"): return "BOOK☆WALKER"
    if "dmm" in hay or soup.select_one("table.fn-bookmarkList") or soup.select_one("ul.fn-bookmarkList li.fn-listContainer"): return "DMM"
    if "ブックライブ" in hay or "booklive" in hay or soup.select_one("ul.save_list"): return "BookLive"
    return None

PARSERS = {"BookLive":parse_booklive, "BOOK☆WALKER":parse_bookwalker, "DMM":parse_dmm, "Amazon":parse_amazon}

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
        CREATE TABLE IF NOT EXISTS sale_state(
          offer_id INTEGER PRIMARY KEY REFERENCES offers(id) ON DELETE CASCADE,
          active INTEGER NOT NULL DEFAULT 0,
          reference_price INTEGER, sale_price INTEGER,
          detected_at TEXT, last_seen_at TEXT, ended_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sale_events(
          id INTEGER PRIMARY KEY,
          offer_id INTEGER NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
          book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
          store TEXT NOT NULL,
          detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          ended_at TEXT,
          sale_price INTEGER, reference_price INTEGER, discount_pct REAL,
          is_read INTEGER NOT NULL DEFAULT 0,
          active INTEGER NOT NULL DEFAULT 1
        );
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
        self._standardize_existing_titles_once()
        self._backfill_sale_state_once()
        self._compact_price_history_once()

    def _history_key(self,row):
        # Price History tracks cash/list-price changes. Reward-only changes do not
        # create another history event; the current offer still retains fresh rewards.
        return (row["price"],row["list_price"])

    def _record_history_if_changed(self,offer_id,price,list_price,reward_pct,reward_value,provenance="local"):
        """Store only meaningful changes; offers.observed_at still records every successful check."""
        last=self.cx.execute("""SELECT price,list_price,reward_pct,reward_value
            FROM price_history WHERE offer_id=? ORDER BY observed_at DESC,id DESC LIMIT 1""",(offer_id,)).fetchone()
        new_key=(price,list_price)
        if last is not None and self._history_key(last)==new_key:
            return False
        self.cx.execute("""INSERT INTO price_history
            (offer_id,price,list_price,reward_pct,reward_value,provenance)
            VALUES(?,?,?,?,?,?)""",(offer_id,price,list_price,reward_pct,reward_value,provenance))
        return True

    def _compact_price_history_once(self):
        """Collapse old consecutive duplicate observations into change events only."""
        marker="price_history_compacted_v1"
        if self.cx.execute("SELECT 1 FROM settings WHERE key=?",(marker,)).fetchone():
            return
        delete_ids=[]
        offer_ids=[r["offer_id"] for r in self.cx.execute(
            "SELECT DISTINCT offer_id FROM price_history ORDER BY offer_id").fetchall()]
        for oid in offer_ids:
            rows=self.cx.execute("""SELECT id,price,list_price,reward_pct,reward_value
                FROM price_history WHERE offer_id=? ORDER BY observed_at,id""",(oid,)).fetchall()
            previous=None
            for row in rows:
                key=self._history_key(row)
                if previous is not None and key==previous:
                    delete_ids.append(row["id"])
                else:
                    previous=key
        if delete_ids:
            d=DATA_DIR/"backups"; d.mkdir(parents=True,exist_ok=True)
            stamp=datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup=d/f"auto_{stamp}_history_compaction.db"
            dst=sqlite3.connect(backup)
            self.cx.backup(dst); dst.close()
            self.cx.executemany("DELETE FROM price_history WHERE id=?",[(x,) for x in delete_ids])
        self.cx.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                        (marker,str(len(delete_ids))))
        self.cx.commit()

    def delete_history_ids(self,ids):
        ids=[int(x) for x in ids]
        if not ids:return 0
        q=",".join("?" for _ in ids)
        cur=self.cx.execute(f"DELETE FROM price_history WHERE id IN ({q})",ids)
        self.cx.commit()
        return cur.rowcount

    def offer_identity(self, offer):
        return (offer.store, offer.store_id or "", canonical_store_url(offer.store,offer.url))

    def refresh_canonical_metadata(self, book_id, commit=False):
        """Standardize the displayed book title from the best matched storefront.

        Title priority is BookLive > DMM > BOOK☆WALKER > Amazon. Amazon therefore
        supplies the canonical title only while it is the only matched source.
        """
        rows=self.cx.execute("SELECT store,title,author FROM offers WHERE book_id=?",(book_id,)).fetchall()
        by_store={r["store"]:r for r in rows}
        chosen=None
        for store in TITLE_SOURCE_PRIORITY:
            r=by_store.get(store)
            if r and (r["title"] or "").strip():
                chosen=r; break
        if not chosen:return

        title=(chosen["title"] or "").strip()
        author=(chosen["author"] or "").strip()
        if not author:
            for store in TITLE_SOURCE_PRIORITY:
                r=by_store.get(store)
                if r and (r["author"] or "").strip():
                    author=(r["author"] or "").strip(); break

        self.cx.execute("UPDATE books SET title=?,norm_title=?,author=? WHERE id=?",
                        (title,normalize_title(title),author,book_id))
        if commit:self.cx.commit()

    def _standardize_existing_titles_once(self):
        marker="canonical_title_priority_v1"
        if self.cx.execute("SELECT 1 FROM settings WHERE key=?",(marker,)).fetchone():
            return
        ids=[r["id"] for r in self.cx.execute("SELECT id FROM books").fetchall()]
        for bid in ids:
            self.refresh_canonical_metadata(bid,commit=False)
        self.cx.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(marker,"1"))
        self.cx.commit()

    def _backfill_sale_state_once(self):
        """Seed sale state for existing offers with an explicit current list price.

        Historical price drops without a storefront/list-price signal are not guessed
        during migration; they will be learned naturally on the next real price change.
        Seeded events are marked read so upgrading does not create a wall of old alerts.
        """
        marker="sale_state_backfill_v1"
        if self.cx.execute("SELECT 1 FROM settings WHERE key=?",(marker,)).fetchone():
            return
        now=datetime.now().isoformat(" ",timespec="seconds")
        rows=self.cx.execute("""SELECT o.id offer_id,o.book_id,o.store,o.price,o.list_price,o.observed_at
                                FROM offers o JOIN books b ON b.id=o.book_id
                                WHERE b.status='active' AND o.price IS NOT NULL
                                  AND o.list_price IS NOT NULL AND o.list_price>o.price""").fetchall()
        for r in rows:
            detected=r["observed_at"] or now
            ref=int(r["list_price"]); price=int(r["price"])
            discount=100.0*(ref-price)/ref if ref else None
            self.cx.execute("""INSERT OR IGNORE INTO sale_state
                (offer_id,active,reference_price,sale_price,detected_at,last_seen_at,ended_at)
                VALUES(?,1,?,?,?,?,NULL)""",(r["offer_id"],ref,price,detected,now))
            self.cx.execute("""INSERT INTO sale_events
                (offer_id,book_id,store,detected_at,last_seen_at,sale_price,reference_price,discount_pct,is_read,active)
                SELECT ?,?,?,?,?,?,?,?,1,1
                WHERE NOT EXISTS(SELECT 1 FROM sale_events WHERE offer_id=? AND active=1)""",
                (r["offer_id"],r["book_id"],r["store"],detected,now,price,ref,discount,r["offer_id"]))
        self.cx.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(marker,"1"))
        self.cx.commit()

    def import_offer(self, offer, list_id=1):
        """Wishlist import: same-store identity only. Never fuzzy-merge titles."""
        url=canonical_store_url(offer.store,offer.url); offer.url=url
        r=self.cx.execute("SELECT id,book_id,locked FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",
                          (offer.store,offer.store_id,url)).fetchone()
        if r:
            bid=r['book_id']; oid=r['id']
            if not r['locked']:
                self.cx.execute("""UPDATE offers SET title=?,price=?,list_price=?,reward_pct=?,reward_value=?,tax_ex_price=?,author=?,flags=?,observed_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (offer.title,offer.price,offer.list_price,offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags,oid))
            self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) VALUES(?,?)",(list_id,bid))
            self.refresh_canonical_metadata(bid,commit=False)
            self.cx.commit(); return bid,False
        cur=self.cx.execute("INSERT INTO books(title,norm_title,author) VALUES(?,?,?)",(offer.title,normalize_title(offer.title),offer.author)); bid=cur.lastrowid
        cur=self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,price,list_price,reward_pct,reward_value,tax_ex_price,author,flags) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (bid,offer.store,offer.store_id,offer.title,url,offer.price,offer.list_price,offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags)); oid=cur.lastrowid
        self._record_history_if_changed(oid,offer.price,offer.list_price,offer.reward_pct,offer.reward_value)
        self.cx.execute("INSERT OR IGNORE INTO list_books(list_id,book_id) VALUES(?,?)",(list_id,bid))
        self.refresh_canonical_metadata(bid,commit=False)
        self.cx.commit(); return bid,True

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
            url=canonical_store_url(o.store,o.url)
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
            url=canonical_store_url(o.store,o.url)
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
            self._record_history_if_changed(oid,o.price,o.list_price,o.reward_pct,o.reward_value)

        self.refresh_canonical_metadata(bid,commit=False)
        self.cx.commit()
        return bid

    def find_book(self, offer):
        r=self.cx.execute("SELECT book_id FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",(offer.store,offer.store_id,canonical_store_url(offer.store,offer.url))).fetchone()
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
            (bid,offer.store,offer.store_id,offer.title,canonical_store_url(offer.store,offer.url),offer.price,offer.list_price,offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags)); oid=cur.lastrowid
        self._record_history_if_changed(oid,offer.price,offer.list_price,offer.reward_pct,offer.reward_value)
        self.refresh_canonical_metadata(bid,commit=False)
        self.cx.commit(); return bid

    def update_offer_for_book(self, book_id, store, offer):
        """Refresh one already-associated store offer without canonical rematching."""
        row=self.cx.execute("SELECT * FROM offers WHERE book_id=? AND store=?",(book_id,store)).fetchone()
        normalized_url=canonical_store_url(store,offer.url)
        if not row:
            # Defensive fallback for a known book/store slot: create it on THIS book only.
            cur=self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,price,list_price,
                reward_pct,reward_value,tax_ex_price,author,flags,locked,observed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,CURRENT_TIMESTAMP)""",
                (book_id,store,offer.store_id,offer.title,normalized_url,offer.price,offer.list_price,
                 offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags))
            oid=cur.lastrowid
        else:
            oid=row["id"]
            # Manual/locked URLs remain authoritative. For unlocked offers the provider's
            # canonical URL/ID may be refreshed, but the offer stays attached to this book.
            new_url=row["url"] if row["locked"] else (normalized_url or row["url"])
            new_store_id=row["store_id"] if row["locked"] and row["store_id"] else (offer.store_id or row["store_id"])
            self.cx.execute("""UPDATE offers SET store_id=?,title=?,url=?,price=?,list_price=?,
                reward_pct=?,reward_value=?,tax_ex_price=?,author=?,flags=?,observed_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (new_store_id,offer.title or row["title"],new_url,offer.price,offer.list_price,
                 offer.reward_pct,offer.reward_value,offer.tax_ex_price,offer.author,offer.flags,oid))
        self._record_history_if_changed(oid,offer.price,offer.list_price,offer.reward_pct,offer.reward_value)
        self.refresh_canonical_metadata(book_id,commit=False)
        self.cx.commit()
        return book_id

    def update_sale_state_for_refresh(self,book_id,store,new_price,new_list_price):
        """Persist whether this store offer is currently on sale.

        A sale remains active across refreshes even when the storefront later omits
        its list price. The remembered reference price is cleared only when the
        cash price returns to or above that reference.
        """
        offer=self.cx.execute("SELECT id,price,list_price FROM offers WHERE book_id=? AND store=?",
                              (book_id,store)).fetchone()
        if not offer or new_price is None:return None
        state=self.cx.execute("SELECT * FROM sale_state WHERE offer_id=?",(offer["id"],)).fetchone()
        old_active=bool(state and state["active"])
        remembered=state["reference_price"] if state else None

        reference=None
        for candidate in (new_list_price,offer["list_price"],remembered,offer["price"]):
            if candidate is not None and candidate>new_price:
                reference=int(candidate); break

        active=reference is not None and new_price<reference
        now=datetime.now().isoformat(" ",timespec="seconds")
        if active:
            detected=(state["detected_at"] if old_active and state and state["detected_at"] else now)
            self.cx.execute("""INSERT INTO sale_state(offer_id,active,reference_price,sale_price,detected_at,last_seen_at,ended_at)
                VALUES(?,1,?,?,?,?,NULL)
                ON CONFLICT(offer_id) DO UPDATE SET active=1,reference_price=excluded.reference_price,
                sale_price=excluded.sale_price,detected_at=excluded.detected_at,last_seen_at=excluded.last_seen_at,ended_at=NULL""",
                (offer["id"],reference,new_price,detected,now))
            discount=100.0*(reference-new_price)/reference if reference else None
            if not old_active:
                self.cx.execute("""INSERT INTO sale_events
                    (offer_id,book_id,store,detected_at,last_seen_at,sale_price,reference_price,discount_pct,is_read,active)
                    VALUES(?,?,?,?,?,?,?,?,0,1)""",
                    (offer["id"],book_id,store,now,now,new_price,reference,discount))
            else:
                self.cx.execute("""UPDATE sale_events SET last_seen_at=?,sale_price=?,reference_price=?,discount_pct=?,active=1,ended_at=NULL
                    WHERE id=(SELECT id FROM sale_events WHERE offer_id=? AND active=1 ORDER BY id DESC LIMIT 1)""",
                    (now,new_price,reference,discount,offer["id"]))
        else:
            self.cx.execute("""INSERT INTO sale_state(offer_id,active,reference_price,sale_price,detected_at,last_seen_at,ended_at)
                VALUES(?,0,?,?,NULL,?,?)
                ON CONFLICT(offer_id) DO UPDATE SET active=0,sale_price=excluded.sale_price,
                last_seen_at=excluded.last_seen_at,ended_at=excluded.ended_at""",
                (offer["id"],remembered,new_price,now,now))
            if old_active:
                self.cx.execute("UPDATE sale_events SET active=0,ended_at=?,last_seen_at=? WHERE offer_id=? AND active=1",
                                (now,now,offer["id"]))

        return {"offer_id":offer["id"],"active":active,"started":active and not old_active,
                "reference":reference,"price":new_price}

    def active_sale_rows(self,book_id=None):
        sql="""SELECT ss.*,o.book_id,o.store,o.url,o.price,o.list_price,b.title
               FROM sale_state ss JOIN offers o ON o.id=ss.offer_id
               JOIN books b ON b.id=o.book_id
               WHERE ss.active=1 AND b.status='active'"""
        args=[]
        if book_id is not None:
            sql+=" AND o.book_id=?"; args.append(book_id)
        sql+=" ORDER BY ss.detected_at DESC,o.store"
        return self.cx.execute(sql,args).fetchall()

    def active_sale_book_ids(self):
        return {r["book_id"] for r in self.cx.execute("""SELECT DISTINCT o.book_id
            FROM sale_state ss JOIN offers o ON o.id=ss.offer_id JOIN books b ON b.id=o.book_id
            WHERE ss.active=1 AND b.status='active'""")}

    def sale_inbox_books(self):
        return self.cx.execute("""SELECT b.id book_id,b.title,MAX(se.detected_at) latest_sale,
            SUM(CASE WHEN se.is_read=0 THEN 1 ELSE 0 END) unread_events,
            SUM(CASE WHEN se.active=1 THEN 1 ELSE 0 END) active_events
            FROM sale_events se JOIN books b ON b.id=se.book_id
            GROUP BY b.id,b.title ORDER BY latest_sale DESC""").fetchall()

    def unread_sale_count(self):
        return self.cx.execute("SELECT COUNT(DISTINCT book_id) n FROM sale_events WHERE is_read=0").fetchone()["n"]

    def mark_sale_book_read(self,book_id):
        self.cx.execute("UPDATE sale_events SET is_read=1 WHERE book_id=?",(book_id,)); self.cx.commit()

    def mark_all_sales_read(self):
        self.cx.execute("UPDATE sale_events SET is_read=1"); self.cx.commit()

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
        """Exact supported Calibre identifier -> canonical book mapping (bl/bw/dmm/amazon_jp)."""
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
            elif r["store"]=="Amazon":
                raw=sid
                if raw.lower().startswith("amazon_jp:"): raw=raw.split(":",1)[1]
                if not raw:
                    m=re.search(r'/dp/([A-Z0-9]{10})(?:/|$)',url,re.I)
                    if m: raw=m.group(1)
                if raw and re.fullmatch(r'[A-Z0-9]{10}',raw,re.I):
                    keys.append(("amazon_jp:"+raw).lower())
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
        if store not in MANUAL_URL_STORES or not valid_store_url(store,url):
            raise ValueError(f"Invalid or non-editable {store} product URL")
        url=canonical_store_url(store,url)

        # A manually replaced URL is a new product identity. Keep store_id in sync
        # immediately rather than leaving the old matched ID attached to the new URL.
        store_id=""
        if store=="Amazon":
            m=re.search(r"/dp/([A-Z0-9]{10})(?:/|$)",url,re.I)
            if m:store_id=m.group(1).upper()
        elif store=="BOOK☆WALKER":
            m=re.search(r"/(de[0-9a-f-]{30,})/?$",url,re.I)
            if m:store_id=m.group(1).lower()
        elif store=="BookLive":
            m=re.search(r"/product/index/title_id/(\d+)/vol_no/(\d+)",url,re.I)
            if m:store_id=f"{m.group(1)}:{m.group(2).zfill(3)}"
        elif store=="DMM":
            m=re.search(r"/product/(\d+)/([^/?#]+)/?",url,re.I)
            if m and m.group(2).lower()!="latest":
                store_id=f"{m.group(1)}:{m.group(2)}"

        row=self.cx.execute("SELECT * FROM offers WHERE book_id=? AND store=?",(book_id,store)).fetchone()

        # Give the UI a useful error instead of allowing SQLite UNIQUE violations
        # to escape silently from a Tk button callback.
        args=[store,url]
        sql="SELECT o.book_id,b.title FROM offers o JOIN books b ON b.id=o.book_id WHERE o.store=? AND o.url=?"
        if row:
            sql+=" AND o.id!=?"; args.append(row["id"])
        duplicate=self.cx.execute(sql,args).fetchone()
        if duplicate:
            raise ValueError(
                f"This {store} product URL is already attached to another book:\n\n"
                f"{duplicate['title']}\n\n"
                "Remove or correct that existing match first."
            )
        if store_id:
            args=[store,store_id]
            sql="""SELECT o.book_id,b.title FROM offers o JOIN books b ON b.id=o.book_id
                   WHERE o.store=? AND o.store_id=?"""
            if row:
                sql+=" AND o.id!=?"; args.append(row["id"])
            duplicate=self.cx.execute(sql,args).fetchone()
            if duplicate:
                raise ValueError(
                    f"This {store} product is already attached to another book:\n\n"
                    f"{duplicate['title']}\n\n"
                    "Remove or correct that existing match first."
                )

        try:
            if row:
                self.cx.execute("UPDATE offers SET url=?,store_id=?,locked=1 WHERE id=?",
                                (url,store_id,row["id"]))
            else:
                self.cx.execute("""INSERT INTO offers(book_id,store,store_id,title,url,locked)
                                   SELECT ?,?,?,title,?,1 FROM books WHERE id=?""",
                                (book_id,store,store_id,url,book_id))
            self.refresh_canonical_metadata(book_id,commit=False)
            self.cx.commit()
        except Exception:
            self.cx.rollback()
            raise

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
        self.cx.execute("DELETE FROM books WHERE id=?",(drop,))
        self.refresh_canonical_metadata(keep,commit=False)
        self.cx.commit(); return True

    def history_for_book(self,book_id):
        return self.cx.execute("""SELECT h.id,h.offer_id,h.observed_at,o.store,h.price,h.list_price,h.reward_pct,h.reward_value,h.provenance
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
        self.db=DB()
        self._tray_icon=None
        self._tray_thread=None
        self._tray_ready=None
        self._bw_health_schedule_started=False
        self._auto_price_after_id=None
        self._auto_price_update_running=False
        self._open_windows={}
        self._sort_state={}
        self._instance_socket=None
        self.minsize(MAIN_MIN_WIDTH,MAIN_MIN_HEIGHT)
        self._restore_window_geometry()
        self.protocol("WM_DELETE_WINDOW",self._on_close)

        global UI_LANG
        UI_LANG=self.db.get_setting("ui_language","en")
        self.title(APP_NAME)
        self.current_list_id=1; self.archived_view=False
        self.show_sales_only=tk.BooleanVar(value=False)
        self.providers=live_providers(float(self.db.get_setting("request_delay_seconds","1.25")),
                                      self.log,load_bookwalker_cookies())
        self._build()
        self.apply_theme()
        # Let Tk finish laying out the panes before calculating column widths/wrapping.
        self.update_idletasks()
        self._restore_main_pane()
        self._resize_table_columns()
        self.refresh()
        if getattr(sys,"frozen",False):
            try:
                marker_path=Path(sys.executable).parent/".update-installed"
                if marker_path.exists():
                    installed=marker_path.read_text(encoding="utf-8-sig").strip()
                    marker_path.unlink(missing_ok=True)
                    self.log(f"[Updater] Installed update marker: {installed}; running {APP_VERSION}")
            except Exception as e:
                self.log(f"[Updater] Could not read update marker: {e}")
        if self.db.get_setting("main_window_state","normal")=="zoomed":
            self.after_idle(lambda:self.state("zoomed"))
        if self.db.get_setting("check_updates_on_startup","1")=="1":
            self.after(1800,lambda:self.check_for_updates(silent=True,automatic=True))
        # If this user previously had a BOOK☆WALKER session, verify it shortly
        # after startup and then every six hours while the app remains running.
        if load_bookwalker_cookies():
            self._start_bookwalker_health_schedule()
        self._start_instance_listener()
        self._schedule_auto_price_update()

    def _schedule_auto_price_update(self):
        """Schedule the next automatic all-offer price refresh.

        The first run on an installation happens shortly after startup. Later runs
        honor the configured interval and persist their completion time so restarting
        the app does not reset the clock.
        """
        if self._auto_price_after_id is not None:
            try:self.after_cancel(self._auto_price_after_id)
            except Exception:pass
            self._auto_price_after_id=None
        try:
            hours=max(0.25,float(self.db.get_setting("update_interval_hours","6")))
        except Exception:
            hours=6.0
        interval_seconds=hours*60*60
        last=self.db.get_setting("last_auto_price_update_at","")
        delay_seconds=60.0
        if last:
            try:
                last_dt=datetime.fromisoformat(last)
                elapsed=max(0.0,(datetime.now()-last_dt).total_seconds())
                delay_seconds=max(5.0,interval_seconds-elapsed)
            except Exception:
                delay_seconds=60.0
        self._auto_price_after_id=self.after(
            int(min(delay_seconds,interval_seconds)*1000),self._run_auto_price_update)

    def _run_auto_price_update(self):
        self._auto_price_after_id=None
        if self._auto_price_update_running:
            self.log("[Auto Update] Previous price update is still running; retrying later")
            self._schedule_auto_price_update()
            return
        self._auto_price_update_running=True

        def work():
            worker_db=DB()
            ok=0; failed=[]; lowered_books=set(); sale_events=[]; total=0
            dmm_region_blocked=False
            try:
                enabled=set(self.enabled_stores())
                jobs=worker_db.cx.execute("""SELECT o.book_id,o.store,o.url,o.price
                    FROM offers o JOIN books b ON b.id=o.book_id
                    WHERE b.status='active' AND o.url!=''
                    ORDER BY o.book_id,o.store""").fetchall()
                jobs=[r for r in jobs if r["store"] in enabled and r["store"] in self.providers]
                total=len(jobs)
                if total:
                    self.log(f"[Auto Update] Starting scheduled price update • {total} offer(s)")
                for bid_store in jobs:
                    bid=bid_store["book_id"]; store=bid_store["store"]; url=bid_store["url"]
                    old_price=bid_store["price"]
                    try:
                        r=self.providers[store].product(url)
                        if not r.title:
                            brow=worker_db.cx.execute("SELECT title FROM books WHERE id=?",(bid,)).fetchone()
                            r.title=brow["title"] if brow else ""
                        fetched=self._offer_from_live(r)
                        # Keep the associated URL authoritative for scheduled refreshes;
                        # provider canonicalization still updates its parsed store ID.
                        fetched.url=url
                        worker_db.update_sale_state_for_refresh(bid,store,r.price,r.list_price)
                        sale_event=self._sale_event_for_refresh(worker_db,bid,store,r.price,r.list_price)
                        saved_bid=worker_db.update_offer_for_book(bid,store,fetched)
                        ok+=1
                        if old_price is not None and r.price is not None and r.price < old_price:
                            lowered_books.add(bid)
                        if sale_event:sale_events.append(sale_event)
                        if getattr(r,"cover_url",""):
                            self.after(0,lambda bid=saved_bid,store=store,url=r.cover_url:self.cache_cover(bid,store,url))
                    except DMMRegionError as e:
                        dmm_region_blocked=True
                        failed.append("DMM: Japanese IP required")
                        self.log(f"[DMM] AUTO UPDATE BLOCKED: {e}")
                    except Exception as e:
                        failed.append(f"{store}: {type(e).__name__}: {e}")
                        self.log(f"[{store}] AUTO UPDATE ERROR {type(e).__name__}: {e}")
            finally:
                worker_db.cx.close()

            completed=datetime.now()
            def finish():
                self._auto_price_update_running=False
                self.db.set_setting("last_auto_price_update_at",completed.isoformat(timespec="seconds"))
                self.refresh()
                self.status.set("Ready")
                drop_count=len(lowered_books)
                if total==0:
                    summary="[Auto Update] Finished • no active matched offers to check"
                else:
                    summary=f"[Auto Update] Finished • {ok}/{total} offer(s) checked"
                    if drop_count:
                        summary+=f" • {drop_count} book{'s' if drop_count!=1 else ''} price went down"
                    else:
                        summary+=" • no price drops"
                    if failed:
                        summary+=f" • {len(failed)} failed"
                self.log(summary)
                if sale_events:
                    self._dispatch_sale_events(list(sale_events))
                self._schedule_auto_price_update()
            self.after(0,finish)

        threading.Thread(target=work,daemon=True).start()

    def _start_instance_listener(self):
        import socket
        try:
            srv=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            srv.bind(("127.0.0.1",INSTANCE_PORT)); srv.listen(2)
            self._instance_socket=srv
        except OSError as e:
            self.log(f"[Instance] Activation listener unavailable: {e}")
            return
        def listen():
            while True:
                try:
                    conn,_=srv.accept()
                    with conn:
                        data=conn.recv(32)
                    if data.startswith(b"SHOW"):
                        self.after(0,self._restore_from_tray)
                except OSError:
                    break
                except Exception:
                    pass
        threading.Thread(target=listen,daemon=True).start()

    def _single_window(self,key,title,geometry=None,resizable=True,transient=True,grab=False):
        existing=self._open_windows.get(key)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify(); existing.lift(); existing.focus_force()
                return None
        except Exception:
            self._open_windows.pop(key,None)
        w=tk.Toplevel(self); self._open_windows[key]=w; w.title(title)
        if geometry:w.geometry(geometry)
        if isinstance(resizable,tuple):w.resizable(*resizable)
        else:w.resizable(bool(resizable),bool(resizable))
        if transient:w.transient(self)
        if grab:w.grab_set()
        def cleanup(event=None):
            if event is None or event.widget is w:
                if self._open_windows.get(key) is w:self._open_windows.pop(key,None)
        w.bind("<Destroy>",cleanup,add="+")
        return w

    def _restore_window_geometry(self):
        saved=self.db.get_setting("main_window_geometry",MAIN_DEFAULT_GEOMETRY)
        m=re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)",saved or "")
        if not m:
            self.geometry(MAIN_DEFAULT_GEOMETRY)
            return
        w=max(MAIN_MIN_WIDTH,int(m.group(1)))
        h=max(MAIN_MIN_HEIGHT,int(m.group(2)))
        x=int(m.group(3)); y=int(m.group(4))
        # Keep at least part of the title bar on the primary screen after monitor
        # changes, while still allowing negative coordinates used by left-side monitors.
        sw=max(1,self.winfo_screenwidth()); sh=max(1,self.winfo_screenheight())
        if x>=sw-80: x=max(0,sw-w)
        if y>=sh-50: y=max(0,sh-h)
        self.geometry(f"{w}x{h}{x:+d}{y:+d}")

    def _save_window_state(self):
        try:
            state=self.state()
            # Save the normal geometry. When maximized, Windows/Tk may report the
            # maximized rectangle; retaining the previous normal geometry is safer.
            if state=="normal":
                self.db.set_setting("main_window_geometry",self.geometry())
            self.db.set_setting("main_window_state","zoomed" if state=="zoomed" else "normal")
            if hasattr(self,"main_pane") and self.main_pane.winfo_exists():
                total=self.main_pane.winfo_width()
                sash=self.main_pane.sashpos(0)
                if total>0 and sash>0:
                    self.db.set_setting("main_activity_width",max(ACTIVITY_PANE_MIN_WIDTH,total-sash))
        except Exception:
            pass

    def _tray_image(self):
        if Image is None:return None
        img=Image.new("RGBA",(64,64),(38,91,150,255))
        if ImageDraw is not None:
            d=ImageDraw.Draw(img)
            d.rounded_rectangle((12,10,52,54),radius=5,fill=(255,255,255,255))
            d.line((32,12,32,52),fill=(38,91,150,255),width=3)
            d.line((18,21,28,21),fill=(38,91,150,255),width=3)
            d.line((36,21,46,21),fill=(38,91,150,255),width=3)
            d.line((18,31,28,31),fill=(38,91,150,255),width=3)
            d.line((36,31,46,31),fill=(38,91,150,255),width=3)
        return img

    def _ensure_tray_icon(self):
        if self._tray_icon is not None:return True
        try:
            import pystray
            image=self._tray_image()
            if image is None:return False
            open_text="開く" if UI_LANG=="ja" else "Open Book Sale Notification"
            exit_text="終了" if UI_LANG=="ja" else "Exit"
            menu=pystray.Menu(
                pystray.MenuItem(open_text,lambda icon,item:self.after(0,self._restore_from_tray),default=True),
                pystray.MenuItem(exit_text,lambda icon,item:self.after(0,self._exit_application))
            )
            icon=pystray.Icon("BookSaleNotification",image,APP_NAME,menu)
            ready=threading.Event()
            started={"ok":False}
            def setup(i):
                i.visible=True
                started["ok"]=True
                ready.set()
            def runner():
                try: icon.run(setup=setup)
                except Exception as e:
                    self.log(f"[Tray] System tray backend failed: {type(e).__name__}: {e}")
                    ready.set()
            thread=threading.Thread(target=runner,daemon=True)
            thread.start()
            if not ready.wait(2.0) or not started["ok"]:
                try: icon.stop()
                except Exception: pass
                return False
            self._tray_icon=icon
            self._tray_thread=thread
            return True
        except Exception as e:
            self.log(f"[Tray] Could not create system tray icon: {type(e).__name__}: {e}")
            return False

    def _hide_to_tray(self):
        self._save_window_state()
        if not self._ensure_tray_icon():
            messagebox.showwarning("System tray unavailable",
                                   "The system tray icon could not be created, so the app was left open.")
            return
        self.withdraw()

    def _restore_from_tray(self):
        try:
            if self._tray_icon is not None:
                self._tray_icon.stop()
        except Exception:
            pass
        self._tray_icon=None
        self.deiconify()
        if self.db.get_setting("main_window_state","normal")=="zoomed":
            try:self.state("zoomed")
            except Exception:pass
        self.lift()
        try:self.focus_force()
        except Exception:pass

    def _exit_application(self):
        try:
            if self.state()!="withdrawn":self._save_window_state()
        except Exception:
            pass
        try:
            if self._tray_icon is not None:self._tray_icon.stop()
        except Exception:
            pass
        self._tray_icon=None
        try:
            if self._instance_socket is not None:self._instance_socket.close()
        except Exception:pass
        self.destroy()

    def _on_close(self):
        if self.db.get_setting("close_button_behavior","tray")=="tray":
            self._hide_to_tray()
        else:
            self._exit_application()

    def toggle_language(self):
        global UI_LANG
        UI_LANG="ja" if UI_LANG!="ja" else "en"
        self.db.set_setting("ui_language",UI_LANG)
        # Rebuild the visible UI from the same database/session so the change is immediate.
        for child in list(self.winfo_children()):
            child.destroy()
        self._open_windows.clear()
        self._build()
        self.apply_theme()
        self.update_idletasks()
        self._restore_main_pane()
        self._resize_table_columns()
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
        ttk.Button(top,text="Import HTML folder…",command=self.import_folder).pack(side="right",padx=4)

        phase=ttk.Frame(self,padding=(10,0,10,7)); phase.pack(fill="x")
        ttk.Label(phase,text="BookLive + BOOK☆WALKER + DMM live search • Amazon direct URL/HTML import + refresh (search disabled)",
                  font=("Segoe UI",9,"bold")).pack(anchor="w")
        self.list_tabs=ttk.Notebook(self); self.list_tabs.pack(fill="x",padx=10,pady=(0,6))
        self.rebuild_list_tabs()
        bar=ttk.Frame(self,padding=(10,0,10,8)); bar.pack(fill="x")
        ttk.Label(bar,text="Search:").pack(side="left")
        self.search=tk.StringVar(); e=ttk.Entry(bar,textvariable=self.search,width=38); e.pack(side="left",padx=6)
        e.bind("<KeyRelease>",lambda _e:self.refresh())
        ttk.Checkbutton(bar,text="Show only books on sale",variable=self.show_sales_only,
                        command=self.refresh).pack(side="left",padx=(8,4))

        ttk.Button(bar,text="Delete",command=self.delete_selected).pack(side="right",padx=4)
        ttk.Button(bar,text="History",command=self.show_history).pack(side="right",padx=4)
        ttk.Button(bar,text="Mark purchased",command=self.mark_purchased).pack(side="right",padx=4)
        ttk.Button(bar,text="Edit store URLs",command=self.edit_url).pack(side="right",padx=4)
        ttk.Button(bar,text="Find missing matches",command=self.find_missing_matches).pack(side="right",padx=4)
        ttk.Button(bar,text="Update prices",command=self.update_prices).pack(side="right",padx=4)

        cols=("title","booklive","bookwalker","dmm","amazon","lowest","latest_sale","stores")
        headings={"title":"Book","booklive":"BookLive","bookwalker":"BOOK☆WALKER",
                  "dmm":"DMM","amazon":"Amazon","lowest":"Lowest cash price","latest_sale":"Latest sale","stores":"Matched"}
        widths={"title":500,"booklive":115,"bookwalker":135,"dmm":115,"amazon":115,"lowest":150,"latest_sale":145,"stores":70}

        # Main table and live activity console. Keep enough width for the complete
        # price table so the rightmost Matched column cannot disappear behind Activity.
        self.main_pane=ttk.Panedwindow(self,orient="horizontal")
        self.main_pane.pack(fill="both",expand=True,padx=10,pady=(0,8))
        self.table_frame=ttk.Frame(self.main_pane)
        self.activity_frame=ttk.Frame(self.main_pane,width=320)
        self.main_pane.add(self.table_frame,weight=4)
        self.main_pane.add(self.activity_frame,weight=1)
        self.main_pane.bind("<Configure>",self._on_main_pane_configure,add="+")
        self.main_pane.bind("<ButtonRelease-1>",self._on_main_pane_configure,add="+")

        self.tree=ttk.Treeview(self.table_frame,columns=cols,show="tree headings",selectmode="extended")
        self.tree.tag_configure("sale",background="#fff3bf")
        for c in cols:
            self.tree.heading(c,text=headings[c],command=lambda x=c:self.sort_by(x))
            saved=self.db.get_setting("column_width_"+c,"")
            try:initial=max(55,int(saved)) if saved else widths[c]
            except Exception:initial=widths[c]
            self.tree.column(c,width=initial,minwidth=55,stretch=False,
                             anchor="w" if c=="title" else "center")
        self.tree.column("title",minwidth=190)
        self.tree.column("lowest",minwidth=125)
        self.tree.column("latest_sale",minwidth=120)
        self.tree.column("stores",minwidth=72)
        self.tree.heading("#0",text="Cover")
        self._cover_photos={}
        self.apply_cover_view()
        self.apply_store_columns()

        sy=ttk.Scrollbar(self.table_frame,orient="vertical",command=self.tree.yview)
        sx=ttk.Scrollbar(self.table_frame,orient="horizontal",command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        self.tree.grid(row=0,column=0,sticky="nsew")
        sy.grid(row=0,column=1,sticky="ns")
        sx.grid(row=1,column=0,sticky="ew")
        self.table_frame.rowconfigure(0,weight=1)
        self.table_frame.columnconfigure(0,weight=1)
        self.table_frame.bind("<Configure>",self._on_table_configure,add="+")
        self.tree.bind("<Double-1>",self.double_click)
        self.tree.bind("<Control-a>",self.select_all_visible)
        self.tree.bind("<Control-A>",self.select_all_visible)
        self.tree.bind("<ButtonRelease-1>",lambda _e:self.after_idle(self._save_column_widths),add="+")

        ah=ttk.Frame(self.activity_frame); ah.pack(fill="x",pady=(0,4))
        ttk.Label(ah,text="Activity",font=("Segoe UI",10,"bold")).pack(side="left")
        ttk.Button(ah,text="Clear",command=lambda:self.activity_clear()).pack(side="right")
        self.activity=tk.Text(self.activity_frame,width=38,wrap="word",font=("Consolas",9),state="disabled")
        ay=ttk.Scrollbar(self.activity_frame,orient="vertical",command=self.activity.yview)
        self.activity.configure(yscrollcommand=ay.set)
        ay.pack(side="right",fill="y"); self.activity.pack(side="left",fill="both",expand=True)

        self.status=UIStatusVar(value=ui_tr("Ready"))
        ttk.Label(self,textvariable=self.status,relief="sunken",anchor="w",padding=5).pack(side="bottom",fill="x")
        self.log("Ready — live scraper activity will appear here.")

    def _restore_main_pane(self):
        if not hasattr(self,"main_pane"): return
        self.update_idletasks()
        total=self.main_pane.winfo_width()
        if total<=1:return
        try: activity_w=int(float(self.db.get_setting("main_activity_width","320") or 320))
        except Exception: activity_w=320
        activity_w=max(ACTIVITY_PANE_MIN_WIDTH,activity_w)
        sash=max(TABLE_PANE_MIN_WIDTH,total-activity_w)
        sash=min(sash,max(TABLE_PANE_MIN_WIDTH,total-ACTIVITY_PANE_MIN_WIDTH))
        try:self.main_pane.sashpos(0,sash)
        except Exception:pass

    def _on_main_pane_configure(self,event=None):
        if not hasattr(self,"main_pane"):return
        try:
            total=self.main_pane.winfo_width()
            if total<=1:return
            sash=self.main_pane.sashpos(0)
            lo=min(TABLE_PANE_MIN_WIDTH,max(1,total-ACTIVITY_PANE_MIN_WIDTH))
            hi=max(lo,total-ACTIVITY_PANE_MIN_WIDTH)
            target=max(lo,min(sash,hi))
            if target!=sash:self.main_pane.sashpos(0,target)
        except Exception:
            pass

    def _on_table_configure(self,event=None):
        if getattr(self,"_table_resize_job",None):
            try:self.after_cancel(self._table_resize_job)
            except Exception:pass
        self._table_resize_job=self.after(90,self._finish_table_resize)

    def _finish_table_resize(self):
        self._table_resize_job=None
        old=self.tree.column("title","width") if hasattr(self,"tree") else 0
        self._resize_table_columns()
        new=self.tree.column("title","width") if hasattr(self,"tree") else 0
        # Re-wrap titles after a meaningful width change. This is cheap compared with
        # leaving text clipped, and is debounced while the user drags/resizes.
        if old and abs(new-old)>=8:
            self.refresh()

    def _save_column_widths(self):
        if not hasattr(self,"tree"):return
        for col in ("title","booklive","bookwalker","dmm","amazon","lowest","latest_sale","stores"):
            try:
                width=int(self.tree.column(col,"width"))
                self.db.set_setting("column_width_"+col,width)
            except Exception:
                pass

    def _fit_columns_to_content(self):
        """Expand visible columns enough for the widest displayed line; never shrink."""
        if not hasattr(self,"tree"):return
        try:font=tkfont.nametofont("TkDefaultFont")
        except Exception:return
        raw=self.tree.cget("displaycolumns")
        displayed=list(self.tk.splitlist(raw)) if isinstance(raw,str) else list(raw)
        headings={"booklive":"BookLive","bookwalker":"BOOK☆WALKER","dmm":"DMM","amazon":"Amazon",
                  "lowest":ui_tr("Lowest cash price"),"latest_sale":ui_tr("Latest sale"),"stores":ui_tr("Matched")}
        for col in displayed:
            if col=="title":continue
            required=font.measure(headings.get(col,col))+26
            for iid in self.tree.get_children(""):
                text=str(self.tree.set(iid,col) or "")
                for line in text.splitlines() or [""]:
                    required=max(required,font.measure(line)+26)
            try:
                current=int(self.tree.column(col,"width"))
                saved=self.db.get_setting("column_width_"+col,"")
                saved_w=int(saved) if saved else 0
                target=max(current,saved_w,required)
                if target>current:
                    self.tree.column(col,width=target)
                    self.db.set_setting("column_width_"+col,target)
            except Exception:
                pass

    def _resize_table_columns(self):
        if not hasattr(self,"tree") or not hasattr(self,"table_frame"):return
        raw_display=self.tree.cget("displaycolumns")
        displayed=set(self.tk.splitlist(raw_display)) if isinstance(raw_display,str) else set(raw_display)
        show_cover=self.db.get_setting("show_covers","1")=="1"
        fixed=0
        for col in ("booklive","bookwalker","dmm","amazon","lowest","latest_sale","stores"):
            if col not in displayed:continue
            try:
                saved=self.db.get_setting("column_width_"+col,"")
                if saved:
                    w=max(int(self.tree.column(col,"width")),int(saved))
                    self.tree.column(col,width=w,stretch=False)
                fixed+=int(self.tree.column(col,"width"))
            except Exception:pass
        try:
            saved_title=self.db.get_setting("column_width_title","")
            if saved_title:
                self.tree.column("title",width=max(190,int(saved_title)),minwidth=190,stretch=False)
            else:
                available=max(1,self.table_frame.winfo_width()-22)
                cover_w=self.tree.column("#0","width") if show_cover else 0
                self.tree.column("title",width=max(190,available-fixed-cover_w),minwidth=190,stretch=False)
        except Exception:pass

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
        w=self._single_window("match_results",'Match Results','900x650',resizable=(False,False))
        if w is None:return
        t=tk.Text(w,wrap='word',font=('Consolas',9)); t.insert('1.0',content); t.configure(state='disabled'); t.pack(fill='both',expand=True,padx=10,pady=10)
        def copy(): self.clipboard_clear(); self.clipboard_append(content)
        ttk.Button(w,text='Close',command=w.destroy).pack(side='right',padx=10,pady=(0,10)); ttk.Button(w,text='Copy Log',command=copy).pack(side='right',pady=(0,10))

    def recently_deleted(self):
        w=self._single_window("recently_deleted",'Recently Deleted','900x560',resizable=(False,False))
        if w is None:return
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

        if hasattr(self,"tree"):
            self.tree.tag_configure("sale",background=("#3a3215" if mode=="dark" else "#fff3bf"))

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

    def price_text(self,o,sale=False,cheapest=False,book_on_sale=False):
        if not o: return "—"
        price=o["price"]
        if o["store"]=="BOOK☆WALKER" and self.db.get_setting("bw_overseas_tax","0")=="1":
            # Overseas mode changes only the displayed cash price, and only when
            # BOOK☆WALKER supplied an exact tax-exclusive amount.
            if o["tax_ex_price"] is not None:
                price=o["tax_ex_price"]
        if price is None: return "?"
        s=f"¥{price:,}"
        if sale and cheapest:
            s="SALE • ★ LOWEST "+s
        elif sale:
            s="SALE "+s
        elif book_on_sale and cheapest:
            s="★ LOWEST "+s
        if self.db.get_setting("include_direct_rewards","1")=="1":
            if o["store"]=="DMM":
                if o["reward_value"]:
                    s+=f"  +{o['reward_value']:,} pt"
                elif o["reward_pct"]:
                    s+=f"  +{o['reward_pct']:g}%pt"
            elif o["store"]=="BOOK☆WALKER" and o["reward_value"]:
                s+=f"  +{o['reward_value']:,} coin"
            elif o["store"]=="Amazon" and o["reward_value"]:
                s+=f"  +{o['reward_value']:,} pt"
        if o["observed_at"]:
            s += "\n" + str(o["observed_at"])[:16]
        return s

    def cache_cover(self,bid,store,url):
        if not self.store_enabled(store): return
        if not url or Image is None: return

        # Cover priority: BookLive > Amazon > DMM > BOOK☆WALKER. A store may replace its
        # own cached cover when its image URL changes (important for DMM preorders,
        # which can initially expose a placeholder and add the real cover later).
        def source_for(u):
            u=(u or "").lower()
            if "booklive" in u: return "BookLive"
            if "bookwalker" in u: return "BOOK☆WALKER"
            if "dmm" in u: return "DMM"
            if "amazon" in u or "media-amazon" in u: return "Amazon"
            return ""
        priority={"BOOK☆WALKER":1,"DMM":2,"Amazon":3,"BookLive":4}

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
        keys={"BookLive":"store_booklive_enabled","BOOK☆WALKER":"store_bookwalker_enabled","DMM":"store_dmm_enabled","Amazon":"store_amazon_enabled"}
        key=keys.get(store)
        return True if not key else self.db.get_setting(key,"1")=="1"

    def enabled_stores(self):
        return [s for s in STORES if self.store_enabled(s)]

    def apply_store_columns(self):
        visible=["title"]
        store_columns={"BookLive":"booklive","BOOK☆WALKER":"bookwalker","DMM":"dmm","Amazon":"amazon"}
        for store,column_id in store_columns.items():
            if self.store_enabled(store):
                visible.append(column_id)
        visible += ["lowest","latest_sale","stores"]
        self.tree.configure(displaycolumns=visible)
        if hasattr(self,"table_frame"):
            self.after_idle(self._resize_table_columns)

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
        # Price cells contain a second line for timestamps and long titles may wrap.
        # Treeview has one row height for the whole widget, so size it for the tallest
        # visible wrapped title while never making it shorter than the cover itself.
        content_h=no_cover_rowheight or 46
        ttk.Style(self).configure("Treeview",rowheight=max(rh,content_h) if show else content_h)

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
        self.update_idletasks()
        self._resize_table_columns()
        self._cover_photos={}
        show_covers,cover_size,(cover_w,cover_h,_cw,_rh)=self.cover_view()
        for x in self.tree.get_children(): self.tree.delete(x)
        rows=self.db.rows(self.search.get().strip(),False,self.current_list_id,self.archived_view)
        active_sales=self.db.active_sale_rows()
        sale_by_book={}
        for sr in active_sales:sale_by_book.setdefault(sr["book_id"],{})[sr["store"]]=sr
        if self.show_sales_only.get() and not self.archived_view:
            rows=[item for item in rows if item[0]["id"] in sale_by_book]
        wrapped_titles={}
        max_lines=2  # store price + observation timestamp already needs two lines
        title_width=self.tree.column("title","width") or 500
        for b,_offers in rows:
            wrapped,nlines=self._wrap_tree_text(b["title"],title_width)
            wrapped_titles[b["id"]]=wrapped
            max_lines=max(max_lines,nlines)
        # ttk.Treeview supports one rowheight for the whole table, so all visible rows
        # share the height needed by the tallest wrapped title. This prevents clipping.
        self.apply_cover_view(8+19*max_lines)
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
            book_sales=sale_by_book.get(b["id"],{})
            latest_sale=max((str(r["detected_at"] or "") for r in book_sales.values()),default="")
            cheapest_overall=set(cheapest) if book_sales else set()
            vals=(wrapped_titles.get(b["id"],b["title"]),
                  self.price_text(offers.get("BookLive"),"BookLive" in book_sales,"BookLive" in cheapest_overall,bool(book_sales)),
                  self.price_text(offers.get("BOOK☆WALKER"),"BOOK☆WALKER" in book_sales,"BOOK☆WALKER" in cheapest_overall,bool(book_sales)),
                  self.price_text(offers.get("DMM"),"DMM" in book_sales,"DMM" in cheapest_overall,bool(book_sales)),
                  self.price_text(offers.get("Amazon"),"Amazon" in book_sales,"Amazon" in cheapest_overall,bool(book_sales)),
                  lowtxt,latest_sale[:16],len(enabled_matched))
            photo=""
            cp=b["cover_path"] if "cover_path" in b.keys() else ""
            if show_covers and cp and Image is not None and Path(cp).exists():
                try:
                    im=Image.open(cp).copy()
                    im.thumbnail((cover_w,cover_h),Image.Resampling.LANCZOS)
                    photo=ImageTk.PhotoImage(im); self._cover_photos[b["id"]]=photo
                except Exception: pass
            tags=("sale",) if book_sales else ()
            self.tree.insert("", "end", iid=str(b["id"]), image=photo, values=vals,tags=tags)
        self._fit_columns_to_content()
        self.status.set(f"{len(rows)} canonical books shown • Double-click a store cell to open its public product page")

    def parse_file(self,path,forced_store=None):
        with open(path,"r",encoding="utf-8",errors="ignore") as f: soup=BeautifulSoup(f,"html.parser")
        store=forced_store or detect_store(soup,os.path.basename(path))
        if not store: raise ValueError("Could not identify the store from this HTML file.")
        offers=PARSERS[store](soup); added=0; existing=0
        for o in offers:
            _bid,isnew=self.db.import_offer(o,self.current_list_id)
            added += 1 if isnew else 0; existing += 0 if isnew else 1
        return store,len(offers),added,existing

    def _store_from_product_url(self, url):
        url=(url or "").strip()
        for store in MANUAL_URL_STORES:
            if valid_store_url(store,url):
                return store
        return None

    def manual_add_url(self):
        win=self._single_window("manual_add","Add book from store URL","720x205",resizable=(False,False),grab=True)
        if win is None:return

        f=ttk.Frame(win,padding=16); f.pack(fill="both",expand=True)
        ttk.Label(f,text="Add from BookLive / BOOK☆WALKER / DMM / Amazon URL",
                  font=("Segoe UI",11,"bold")).pack(anchor="w")
        ttk.Label(f,text=("Paste one product URL. Amazon links are reduced to the clean /dp/ASIN form automatically. "
                          "Amazon itself is not searched, but an Amazon URL can be used as the source to search the other three stores."),
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
                "Paste a valid BookLive, BOOK☆WALKER, DMM Books or Amazon.co.jp product URL.")
            return

        url=canonical_store_url(source_store,url)
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

                # Amazon search itself remains disabled. When Amazon is the supplied
                # source, normalize its title before searching the other three stores.
                search_title=amazon_title_for_match(primary.title) if source_store=="Amazon" else primary.title
                for store in SEARCH_STORES:
                    if store==source_store: continue
                    self.after(0,lambda st=store:self.status.set(f"Searching {st}…"))
                    self.log(f"[Manual add] Searching {store} for: {search_title}")
                    try:
                        result=self.providers[store].best(search_title,primary.author)
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
            for store in COVER_SOURCE_PRIORITY:
                o=found.get(store)
                if o and o.cover_url:
                    self.cache_cover(bid,store,o.cover_url)
                    break

            self.refresh()
            lines=[]
            summary_stores=STORES if "Amazon" in found else SEARCH_STORES
            for store in summary_stores:
                o=found.get(store)
                if not o:
                    lines.append(f"{store}: no confident match")
                    continue
                price=f"¥{o.price:,}" if o.price is not None else "price unavailable"
                lines.append(f"{store}: {price}\n{o.url}")
            messagebox.showinfo("Book added",
                f"{primary.title}\n\nChecked all available store matches before adding.\n\n" + "\n\n".join(lines))
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
        d=filedialog.askdirectory(title="Choose folder containing saved wishlist/list HTML files")
        if not d:return
        self.auto_backup()
        totals={}; errors=[]
        for p in Path(d).glob("*.htm*"):
            try:
                with open(p,"r",encoding="utf-8",errors="ignore") as f: soup=BeautifulSoup(f,"html.parser")
                st=detect_store(soup,p.name)
                if st and st in PARSERS:
                    offers=PARSERS[st](soup); added=existing=0
                    for o in offers:
                        _bid,isnew=self.db.import_offer(o,self.current_list_id)
                        added+=1 if isnew else 0; existing+=0 if isnew else 1
                    rec=totals.setdefault(st,[0,0,0,0])
                    rec[0]+=1; rec[1]+=len(offers); rec[2]+=added; rec[3]+=existing
            except Exception as e: errors.append(f"{p.name}: {e}")
        self.refresh()
        msg="\n".join(f"{s}: {v[0]} file(s) • {v[1]} parsed • {v[2]} new • {v[3]} existing"
                      for s,v in totals.items()) or "No recognized wishlist HTML found."
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

        win=self._single_window(("edit_url",bid),"Edit store URLs","900x350",resizable=(False,False),grab=True)
        if win is None:return

        outer=ttk.Frame(win,padding=14); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text=book["title"],font=("Segoe UI",11,"bold"),wraplength=850).pack(anchor="w",pady=(0,12))
        ttk.Label(outer,text="Edit the matched product URL for any store. Amazon URLs are automatically shortened to /dp/ASIN.",
                  foreground="#555").pack(anchor="w",pady=(0,10))

        vars={}
        grid=ttk.Frame(outer); grid.pack(fill="x",expand=True)
        for i,store in enumerate(STORES):
            ttk.Label(grid,text=store,width=14).grid(row=i,column=0,sticky="w",pady=5)
            v=tk.StringVar(value=current.get(store,""))
            vars[store]=v
            ent=ttk.Entry(grid,textvariable=v)
            ent.grid(row=i,column=1,sticky="ew",padx=(8,6),pady=5)
            def open_url(v=v,store=store):
                u=v.get().strip()
                if not u:return
                if not valid_store_url(store,u):
                    messagebox.showerror("Invalid store URL",f"Blocked untrusted or invalid {store} URL.\n\n{u}")
                    return
                webbrowser.open(u)
            ttk.Button(grid,text="Open",command=open_url,width=8).grid(row=i,column=2,pady=5)
        grid.columnconfigure(1,weight=1)

        buttons=ttk.Frame(outer); buttons.pack(fill="x",pady=(14,0))
        def save():
            try:
                invalid=[]
                planned=[]
                for store,v in vars.items():
                    newurl=v.get().strip()
                    oldurl=current.get(store,"")
                    if newurl and newurl != oldurl and not valid_store_url(store,newurl):
                        invalid.append((store,newurl))
                    canonical=canonical_store_url(store,newurl) if newurl else ""
                    if canonical != oldurl:
                        planned.append((store,oldurl,canonical))
                if invalid:
                    store,url=invalid[0]
                    expected={"BookLive":"a BookLive product URL (booklive.jp)",
                              "BOOK☆WALKER":"a BOOK☆WALKER product URL (bookwalker.jp/de… or r18.bookwalker.jp/de…)",
                              "DMM":"a DMM Books product URL (book.dmm.com/product/…)",
                              "Amazon":"an Amazon.co.jp product URL containing /dp/ASIN"}[store]
                    messagebox.showerror("Invalid store URL",
                        f"The URL entered for {store} is not {expected}.\n\n{url}\n\nNo changes were saved.")
                    return
                if not planned:
                    win.destroy()
                    return

                removals=[store for store,oldurl,newurl in planned if oldurl and not newurl]
                if removals:
                    names=", ".join(removals)
                    if not messagebox.askyesno("Remove store match",
                        f"Remove the {names} match{'es' if len(removals)>1 else ''} from this book?\n\n"
                        "This permanently clears that store's URL, product ID, current price, rewards and price history. "
                        "The canonical book and its other store matches are not affected."):
                        return

                # URL replacement is a potentially destructive identity correction too,
                # so protect all manual edits, not just removals.
                self.auto_backup("edit_store_url")
                for store,oldurl,newurl in planned:
                    if newurl:
                        self.db.set_url(bid,store,newurl)
                        self.log(f"[Manual URL] {store}: updated product URL")
                    elif oldurl:
                        self.db.remove_store_match(bid,store)
                        self.log(f"[Manual URL] {store}: removed store match")
                self.refresh()
                win.destroy()
            except Exception as e:
                self.log(f"[Manual URL] Save failed: {type(e).__name__}: {e}")
                messagebox.showerror("Could not save store URL",
                    f"The store URL changes could not be saved.\n\n{e}")
        ttk.Button(buttons,text="Cancel",command=win.destroy).pack(side="right")
        ttk.Button(buttons,text="Save changes",command=save).pack(side="right",padx=(0,8))

    def open_store(self):
        bid=self.selected()
        if not bid:return
        store=simpledialog.askstring("Open store","Store name: BookLive, BOOK☆WALKER, DMM, or Amazon")
        if store not in STORES:return
        row=self.db.cx.execute("SELECT url FROM offers WHERE book_id=? AND store=?",(bid,store)).fetchone()
        if row and row["url"]:
            if valid_store_url(store,row["url"]): webbrowser.open(row["url"])
            else: messagebox.showerror("Invalid store URL","Blocked an invalid or untrusted stored URL.")

    def double_click(self,event):
        row=self.tree.identify_row(event.y); col=self.tree.identify_column(event.x)
        if not row or not col.startswith("#"):return
        try:
            display_index=int(col[1:])-1
            if display_index<0:return
            raw=self.tree.cget("displaycolumns")
            displayed=list(self.tk.splitlist(raw)) if isinstance(raw,str) else list(raw)
            column_id=displayed[display_index]
        except Exception:return
        store={"booklive":"BookLive","bookwalker":"BOOK☆WALKER","dmm":"DMM","amazon":"Amazon"}.get(column_id)
        if not store:return
        o=self.db.cx.execute("SELECT url FROM offers WHERE book_id=? AND store=?",(int(row),store)).fetchone()
        if o and o["url"]:
            if valid_store_url(store,o["url"]): webbrowser.open(o["url"])
            else: messagebox.showerror("Invalid store URL","Blocked an invalid or untrusted stored URL.")

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
        if Figure is None or FigureCanvasTkAgg is None:
            messagebox.showerror("Price history","Matplotlib is not available in this build.")
            return
        book=self.db.cx.execute("SELECT title FROM books WHERE id=?",(bid,)).fetchone()
        if not book:return
        w=self._single_window(("history",bid),"Price history — "+book["title"],"1180x780",resizable=True)
        if w is None:return
        w.minsize(900,620)

        enabled=self.enabled_stores()
        def load_history_rows():
            rows=[dict(r) for r in self.db.history_for_book(bid) if r["store"] in enabled]
            for r in rows:
                try:r["_dt"]=datetime.fromisoformat(str(r["observed_at"]).replace("Z","+00:00")).replace(tzinfo=None)
                except Exception:
                    try:r["_dt"]=datetime.strptime(str(r["observed_at"])[:19],"%Y-%m-%d %H:%M:%S")
                    except Exception:r["_dt"]=datetime.now()
            rows.sort(key=lambda r:r["_dt"])
            return rows
        all_rows=load_history_rows()
        offer_now={r["store"]:dict(r) for r in self.db.cx.execute(
            "SELECT store,price,list_price FROM offers WHERE book_id=?",(bid,)).fetchall() if r["store"] in enabled}

        outer=ttk.Frame(w,padding=10); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text=book["title"],font=("Segoe UI",12,"bold"),wraplength=1100).pack(anchor="w",pady=(0,6))
        if not enabled:
            ttk.Label(outer,text="No stores are enabled in Settings. Enable a store to show its saved history.").pack(anchor="w")
            return

        controls=ttk.Frame(outer); controls.pack(fill="x",pady=(0,6))
        range_var=tk.StringVar(value="6m")
        ranges=[("1 Month","1m"),("3 Months","3m"),("6 Months","6m"),("1 Year","1y"),("All","all")]
        store_vars={s:tk.BooleanVar(value=True) for s in enabled}
        show_list=tk.BooleanVar(value=False)

        notebook=ttk.Notebook(outer); notebook.pack(fill="both",expand=True)
        graph_tab=ttk.Frame(notebook); data_tab=ttk.Frame(notebook)
        notebook.add(graph_tab,text="Graph"); notebook.add(data_tab,text="Data")

        graph_host=ttk.Frame(graph_tab); graph_host.pack(fill="both",expand=True)
        summary_host=ttk.Frame(graph_tab); summary_host.pack(fill="x",pady=(6,0))

        fig=Figure(figsize=(10,5),dpi=100)
        ax=fig.add_subplot(111)
        canvas=FigureCanvasTkAgg(fig,master=graph_host)
        canvas.get_tk_widget().pack(fill="both",expand=True)
        toolbar=NavigationToolbar2Tk(canvas,graph_host,pack_toolbar=False)
        toolbar.update(); toolbar.pack(fill="x")

        summary_cols=("store","current","low","high","avg","changed")
        summary=ttk.Treeview(summary_host,columns=summary_cols,show="headings",height=max(1,len(enabled)))
        for col,label,width in (("store","Store",145),("current","Current",100),("low","Lowest",100),
                                ("high","Highest",100),("avg","Average",100),("changed","Last changed",175)):
            summary.heading(col,text=label); summary.column(col,width=width,anchor="center")
        summary.pack(fill="x")

        data_controls=ttk.Frame(data_tab,padding=(4,4)); data_controls.pack(fill="x")
        data_cols=("date","store","price","list","reward","source")
        data_tree=ttk.Treeview(data_tab,columns=data_cols,show="headings")
        for col,label,width in (("date","Observed",175),("store","Store",140),("price","Cash price",105),
                                ("list","List price",105),("reward","Reward",140),("source","Source",130)):
            data_tree.heading(col,text=label); data_tree.column(col,width=width,anchor="center")
        data_sy=ttk.Scrollbar(data_tab,orient="vertical",command=data_tree.yview)
        data_tree.configure(yscrollcommand=data_sy.set)
        data_tree.pack(side="left",fill="both",expand=True,padx=(4,0),pady=(0,4))
        data_sy.pack(side="right",fill="y",pady=(0,4))

        def collapsed(store):
            rows=[r for r in all_rows if r["store"]==store]
            out=[]; prev_key=None; prev_price=None
            for r in rows:
                key=(r.get("price"),r.get("list_price"))
                if not out or key!=prev_key:
                    item=dict(r); item["_previous_price"]=prev_price
                    out.append(item)
                    prev_key=key
                if r.get("price") is not None:prev_price=r.get("price")
            return out

        def cutoff_for(value):
            now=datetime.now()
            return {"1m":now-timedelta(days=31),"3m":now-timedelta(days=92),
                    "6m":now-timedelta(days=183),"1y":now-timedelta(days=366)}.get(value)

        def range_points(points):
            cutoff=cutoff_for(range_var.get())
            if cutoff is None:return list(points)
            before=[p for p in points if p["_dt"]<cutoff]
            after=[p for p in points if p["_dt"]>=cutoff]
            if before:after.insert(0,before[-1])
            return after

        hover={"points":[],"annotation":None}
        def render_graph():
            ax.clear(); hover["points"]=[]
            mode=self.db.get_setting("appearance","system")
            dark=mode=="dark"
            fig.patch.set_facecolor("#121212" if dark else "white")
            ax.set_facecolor("#1b1b1b" if dark else "white")
            fg="#f2f2f2" if dark else "#222222"
            grid="#444444" if dark else "#dddddd"
            ax.tick_params(colors=fg)
            for spine in ax.spines.values():spine.set_color(grid)
            ax.grid(True,alpha=.35)
            ax.set_ylabel("Price (¥)",color=fg)
            ax.set_title("Cash price history",color=fg,pad=10)

            visible_values=[]
            plotted=False
            summary.delete(*summary.get_children())
            for store in enabled:
                pts_all=collapsed(store)
                pts=range_points(pts_all)
                price_pts=[p for p in pts if p.get("price") is not None]
                stats_pts=[p for p in pts if p.get("price") is not None]
                if stats_pts:
                    values=[int(p["price"]) for p in stats_pts]
                    current=offer_now.get(store,{}).get("price")
                    low=min(values); high=max(values); avg=round(sum(values)/len(values))
                    last_change=pts_all[-1]["_dt"].strftime("%Y-%m-%d %H:%M") if pts_all else ""
                    summary.insert("","end",values=(store,
                        f"¥{current:,}" if current is not None else "—",
                        f"¥{low:,}",f"¥{high:,}",f"¥{avg:,}",last_change))
                else:
                    summary.insert("","end",values=(store,"—","—","—","—","—"))

                if not store_vars[store].get() or not price_pts:continue
                xs=[p["_dt"] for p in price_pts]; ys=[p["price"] for p in price_pts]
                line,=ax.step(xs,ys,where="post",label=store,linewidth=1.8)
                ax.scatter(xs,ys,s=26,color=line.get_color(),zorder=3)
                for p in price_pts:
                    hover["points"].append((store,p))
                visible_values.extend(ys); plotted=True

                if show_list.get():
                    list_pts=[p for p in pts if p.get("list_price") is not None]
                    if list_pts:
                        ax.step([p["_dt"] for p in list_pts],[p["list_price"] for p in list_pts],
                                where="post",linestyle="--",alpha=.55,color=line.get_color(),
                                label=f"{store} regular")
                        visible_values.extend([p["list_price"] for p in list_pts])

            if visible_values:
                lo=min(visible_values); hi=max(visible_values); span=max(1,hi-lo)
                step=100 if span<=3000 and hi<=5000 else (500 if span<=12000 else 1000)
                ymin=max(0,(int(lo)//step)*step-step)
                ymax=((int(hi)+step-1)//step)*step+step
                if ymax<=ymin:ymax=ymin+step*4
                ax.set_ylim(ymin,ymax)
                ax.yaxis.set_major_locator(MultipleLocator(step))
                ax.yaxis.set_major_formatter(FuncFormatter(lambda y,_:f"¥{int(y):,}"))
            locator=mdates.AutoDateLocator(minticks=4,maxticks=10)
            ax.xaxis.set_major_locator(locator); ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            if plotted:
                leg=ax.legend(loc="best",fontsize=8)
                if leg:
                    legend_bg="#242424" if dark else "white"
                    legend_edge="#666666" if dark else "#bbbbbb"
                    for text_item in leg.get_texts():text_item.set_color(fg)
                    frame=leg.get_frame()
                    frame.set_facecolor(legend_bg); frame.set_edgecolor(legend_edge); frame.set_alpha(.96)
            else:
                ax.text(.5,.5,"No visible price history for this range.",ha="center",va="center",
                        transform=ax.transAxes,color=fg)
            tip_bg="#242424" if dark else "white"
            tip_fg="#f2f2f2" if dark else "#222222"
            hover["annotation"]=ax.annotate("",xy=(0,0),xytext=(12,12),textcoords="offset points",
                color=tip_fg,bbox=dict(boxstyle="round",fc=tip_bg,ec=grid,alpha=.97),
                arrowprops=dict(arrowstyle="->",color=grid))
            hover["annotation"].set_visible(False)
            fig.autofmt_xdate(); fig.tight_layout()
            canvas.draw_idle()

        def hover_move(event):
            ann=hover.get("annotation")
            if ann is None:return
            if event.inaxes is not ax or event.x is None or event.y is None:
                if ann.get_visible():
                    ann.set_visible(False); canvas.draw_idle()
                return
            nearest=None; nearest_dist=13.0
            for store,p in hover["points"]:
                price=p.get("price")
                if price is None:continue
                px,py=ax.transData.transform((mdates.date2num(p["_dt"]),price))
                dist=((px-event.x)**2+(py-event.y)**2)**0.5
                if dist<nearest_dist:
                    nearest=(store,p); nearest_dist=dist
            if nearest is not None:
                store,p=nearest
                price=p.get("price"); previous=p.get("_previous_price"); regular=p.get("list_price")
                lines=[store,p["_dt"].strftime("%Y-%m-%d %H:%M"),f"¥{price:,}" if price is not None else "Price unavailable"]
                if previous is not None and price is not None and previous!=price:
                    lines.append(f"Was ¥{previous:,}")
                ref=regular if regular is not None and price is not None and regular>price else previous
                if ref is not None and price is not None and ref>price:
                    lines.append(f"{(ref-price)*100/ref:.0f}% off")
                ann.xy=(mdates.date2num(p["_dt"]),price)
                # Keep the tooltip inside the axes: flip left/right and up/down
                # according to the hovered point's on-screen position.
                bbox=ax.get_window_extent()
                px,py=ax.transData.transform((mdates.date2num(p["_dt"]),price))
                horizontal=-14 if px > bbox.x0 + bbox.width*0.72 else 14
                vertical=-14 if py > bbox.y0 + bbox.height*0.78 else 14
                ann.set_position((horizontal,vertical))
                ann.set_ha("right" if horizontal<0 else "left")
                ann.set_va("top" if vertical<0 else "bottom")
                ann.set_text("\n".join(lines)); ann.set_visible(True)
                canvas.draw_idle(); return
            if ann.get_visible():
                ann.set_visible(False); canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event",hover_move)

        def refresh_data():
            data_tree.delete(*data_tree.get_children())
            for r in sorted(all_rows,key=lambda x:x["_dt"],reverse=True):
                reward=(f"{r['reward_pct']:g}% pt" if r.get("reward_pct") else
                        f"{r['reward_value']} coin/pt" if r.get("reward_value") else "")
                data_tree.insert("","end",iid=str(r["id"]),values=(
                    r["_dt"].strftime("%Y-%m-%d %H:%M:%S"),r["store"],
                    f"¥{r['price']:,}" if r.get("price") is not None else "",
                    f"¥{r['list_price']:,}" if r.get("list_price") is not None else "",
                    reward,r.get("provenance","")))

        def delete_history_selected():
            selected=list(data_tree.selection())
            if not selected:
                messagebox.showinfo("Price history","Select one or more history records first.")
                return
            count=len(selected)
            if not messagebox.askyesno("Delete history records",
                f"Permanently delete {count} selected price-history record{'s' if count!=1 else ''}?\n\n"
                "This removes only the selected historical observations. The current store price is not changed. "
                "An automatic database backup will be created first."):
                return
            self.auto_backup("delete_price_history")
            self.db.delete_history_ids([int(x) for x in selected])
            all_rows[:]=load_history_rows()
            refresh_data(); render_graph()
            self.refresh()

        for label,value in ranges:
            ttk.Radiobutton(controls,text=label,variable=range_var,value=value,
                            command=render_graph).pack(side="left",padx=(0,4))
        ttk.Separator(controls,orient="vertical").pack(side="left",fill="y",padx=6)
        for store in enabled:
            ttk.Checkbutton(controls,text=store,variable=store_vars[store],
                            command=render_graph).pack(side="left",padx=(0,5))
        ttk.Checkbutton(controls,text="Show regular/list price",variable=show_list,
                        command=render_graph).pack(side="right")
        ttk.Label(data_controls,text="Price-change events only. Repeated unchanged refreshes are not stored.").pack(side="left")
        ttk.Button(data_controls,text="Delete selected records",command=delete_history_selected).pack(side="right")

        render_graph(); refresh_data()

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
        w=self._single_window("backup_share","Backup, restore & sharing","540x520",resizable=(False,False))
        if w is None:return
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
                        if kind in ("bl","bw","dmm","amazon_jp") and value:
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
            f"Supported unique identifiers (bl/bw/dmm/amazon_jp): {len(supported)}",
            f"Active books to archive: {len(matches)}",
            f"Already archived exact matches: {len(already)}",
            f"Supported identifiers not present in wishlist: {len(unmatched)}",
            "",
            "MATCHING POLICY",
            "Exact identifiers only: bl:, bw:, dmm:, amazon_jp:",
            "Titles/authors/series/ISBN are NOT used as fallback matches. Amazon matches use exact amazon_jp:ASIN identifiers only.",
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
        try:
            data=json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Import failed",f"Could not read shared list:\n{e}"); return
        if not isinstance(data,dict) or data.get("type") not in (None,"book_list"):
            messagebox.showerror("Import failed","This is not a supported shared book-list file."); return
        books=data.get("books",[])
        if not isinstance(books,list):
            messagebox.showerror("Import failed","Shared list has an invalid books structure."); return

        # Treat shared files as untrusted input. Preview only sane store names; every
        # URL is validated again before it can enter the database.
        preview=[]
        for b in books:
            if not isinstance(b,dict):continue
            stores=[x.get("store","") for x in b.get("offers",[]) if isinstance(x,dict) and x.get("store") in STORES]
            preview.append((str(b.get("title",""))[:500],", ".join(stores)))

        w=tk.Toplevel(self); w.title("Shared List — View only"); w.geometry("900x560")
        w.resizable(False,False)
        ttk.Label(w,text=f"VIEW ONLY • {len(preview)} books • Nothing is imported until you press Import All",
                  font=("Segoe UI",10,"bold")).pack(anchor="w",padx=10,pady=8)
        t=ttk.Treeview(w,columns=("title","stores"),show="headings")
        t.heading("title",text="Book"); t.heading("stores",text="Known stores")
        t.column("title",width=650); t.column("stores",width=180)
        for i,(title,stores) in enumerate(preview):
            t.insert("","end",iid=str(i),values=(title,stores))
        t.pack(fill="both",expand=True,padx=10)

        def do_import():
            self.auto_backup('shared_list_import'); added=0; rejected=0; amazon_skipped=0
            name=Path(p).stem; list_id=self.db.create_list(name if name else 'Imported List')
            for b in books:
                if not isinstance(b,dict):rejected+=1; continue
                for od in b.get("offers",[]):
                    if not isinstance(od,dict):rejected+=1; continue
                    store=od.get("store","")
                    url=str(od.get("url","") or "").strip()
                    if store=="Amazon":
                        # Phase 1 Amazon data may only enter through saved HTML.
                        amazon_skipped+=1; continue
                    if store not in SEARCH_STORES or not valid_store_url(store,url):
                        rejected+=1; continue
                    o=Offer(store=store,title=str(od.get("title") or b.get("title",""))[:1000],
                            url=url,price=od.get("price"),list_price=od.get("list_price"),
                            reward_pct=od.get("reward_pct"),reward_value=od.get("reward_value"),
                            tax_ex_price=od.get("tax_ex_price"),
                            author=str(od.get("author") or b.get("author",""))[:500],
                            store_id=str(od.get("store_id","") or "")[:200])
                    self.db.import_offer(o,list_id); added+=1
            self.rebuild_list_tabs(); self.refresh(); w.destroy()
            extra=[]
            if rejected:extra.append(f"Rejected invalid/untrusted records: {rejected}")
            if amazon_skipped:extra.append(f"Amazon records skipped (HTML import only in this phase): {amazon_skipped}")
            suffix=("\n\n"+"\n".join(extra)) if extra else ""
            messagebox.showinfo("Import complete",f"Imported {added} validated store records.{suffix}")
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
        try:
            data=json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("Import failed",f"Could not read price history:\n{e}"); return
        obs=data.get("observations",[]) if isinstance(data,dict) else []
        if not isinstance(obs,list):
            messagebox.showerror("Import failed","Price-history file has an invalid structure."); return
        self.auto_backup(); n=0; rejected=0; amazon_skipped=0
        for x in obs:
            if not isinstance(x,dict):rejected+=1; continue
            store=x.get("store",""); url=str(x.get("url","") or "").strip()
            if store=="Amazon":
                amazon_skipped+=1; continue
            if store not in SEARCH_STORES or not valid_store_url(store,url):
                rejected+=1; continue
            o=Offer(store=store,title=str(x.get("title",""))[:1000],url=url,
                    price=x.get("price"),list_price=x.get("list_price"),
                    reward_pct=x.get("reward_pct"),reward_value=x.get("reward_value"),
                    store_id=str(x.get("store_id","") or "")[:200])
            bid=self.db.add_offer(o)
            orow=self.db.cx.execute("SELECT id FROM offers WHERE book_id=? AND store=?",(bid,o.store)).fetchone()
            if orow:
                self.db.cx.execute("""INSERT OR IGNORE INTO price_history
                    (offer_id,observed_at,price,list_price,reward_pct,reward_value,provenance)
                    VALUES(?,?,?,?,?,?,?)""",(orow["id"],x.get("observed_at") or datetime.now().isoformat(" "),
                    x.get("price"),x.get("list_price"),x.get("reward_pct"),x.get("reward_value"),"shared"))
                n+=1
        self.db.cx.commit(); self.refresh()
        extra=[]
        if rejected:extra.append(f"Rejected invalid/untrusted records: {rejected}")
        if amazon_skipped:extra.append(f"Amazon records skipped (HTML import only in this phase): {amazon_skipped}")
        suffix=("\n\n"+"\n".join(extra)) if extra else ""
        messagebox.showinfo("History imported",f"Merged {n} historical observations.{suffix}")

    def _desktop_notification(self,title,message):
        """Show the same desktop/tray notification path used for sale alerts."""
        title=ui_tr(title); message=ui_tr(message)
        try:
            if self._ensure_tray_icon():
                self._tray_icon.notify(message,title)
                self.log(f"[Notification] {title}: {message}")
                return True
        except Exception as e:
            self.log(f"[Notification] Tray notification failed: {type(e).__name__}: {e}")
        messagebox.showinfo(title,message)
        return False

    def _test_sale_notification(self,rule=None,threshold_text=None,multiple=False):
        rule=rule or self.db.get_setting("notification_rule","any_sale")
        try: threshold=float(threshold_text if threshold_text is not None else self.db.get_setting("deal_threshold","20"))
        except Exception: threshold=20.0
        reason={"historical_low":"historical_low","good_deal":"good_deal"}.get(rule,"any_sale")
        count=3 if multiple else 1
        events=[]
        samples=[
            (900001,"Test Book 1","BookLive",396,792),
            (900002,"Test Book 2","BOOK☆WALKER",330,660),
            (900003,"Test Book 3","DMM",440,880),
        ]
        for book_id,title,store,price,reference in samples[:count]:
            events.append({
                "book_id":book_id,"title":title,"store":store,"price":price,
                "reference":reference,"discount":50.0,"prior_low":reference,
                "reason":reason,"test_threshold":threshold,
            })
        self._dispatch_sale_events(events,test=True)

    def _notify_bookwalker_expired(self):
        msg="Your BOOK☆WALKER session has expired. Sign in again to continue receiving your account-specific coin amounts."
        self.log("[BOOK☆WALKER] Saved session expired; sign in again for coin values")
        self._desktop_notification("BOOK☆WALKER sign-in required",msg)

    def _run_bookwalker_health_check(self,status_var=None,notify_expiry=False):
        previous=self.db.get_setting(
            "bookwalker_session_state","valid" if load_bookwalker_cookies() else "never")
        if status_var is not None:status_var.set(ui_tr("Checking…"))
        def work():
            status,detail=check_bookwalker_session()
            def finish():
                if status=="signed_in":
                    self.db.set_setting("bookwalker_session_state","valid")
                    if status_var is not None:status_var.set(ui_tr("Signed in"))
                    self.log("[BOOK☆WALKER] Login health check: signed in")
                elif status=="signed_out":
                    self.db.set_setting("bookwalker_session_state","expired" if previous=="valid" else "never")
                    if status_var is not None:
                        status_var.set(ui_tr("Session expired" if previous=="valid" else "Not signed in"))
                    self.log("[BOOK☆WALKER] Login health check: signed out")
                    if notify_expiry and previous=="valid":
                        self._notify_bookwalker_expired()
                else:
                    if status_var is not None:status_var.set(ui_tr("Could not check"))
                    self.log(f"[BOOK☆WALKER] Login health check unavailable: {detail}")
            self.after(0,finish)
        threading.Thread(target=work,daemon=True).start()

    def _start_bookwalker_health_schedule(self):
        if self._bw_health_schedule_started:return
        self._bw_health_schedule_started=True
        self.after(8000,self._scheduled_bookwalker_health_check)

    def _scheduled_bookwalker_health_check(self):
        state=self.db.get_setting(
            "bookwalker_session_state","valid" if load_bookwalker_cookies() else "never")
        if state=="valid" and load_bookwalker_cookies():
            self._run_bookwalker_health_check(notify_expiry=True)
        self.after(6*60*60*1000,self._scheduled_bookwalker_health_check)

    def _run_dmm_health_check(self,status_var=None):
        if status_var is not None:status_var.set(ui_tr("Checking…"))
        def work():
            status,detail=check_dmm_access()
            def finish():
                if status=="available":
                    text="Japanese access available"
                    self.log("[DMM] Health check: Japanese access available")
                elif status=="jp_required":
                    text="Japanese IP required"
                    self.log("[DMM] Health check: Japanese IP required")
                else:
                    text="Could not check"
                    self.log(f"[DMM] Health check unavailable: {detail}")
                if status_var is not None:status_var.set(ui_tr(text))
            self.after(0,finish)
        threading.Thread(target=work,daemon=True).start()

    def _start_bookwalker_signin(self,status_var=None,button=None):
        if os.name!="nt":
            messagebox.showerror("BOOK☆WALKER","BOOK☆WALKER sign-in is currently available in the Windows build.")
            return
        if button is not None:
            try: button.configure(state="disabled")
            except Exception: pass
        if status_var is not None: status_var.set(ui_tr("Opening BOOK☆WALKER sign-in…"))
        try:
            if getattr(sys,"frozen",False):
                cmd=[sys.executable,"--bookwalker-login-helper"]
            else:
                cmd=[sys.executable,str(Path(__file__).resolve()),"--bookwalker-login-helper"]
            proc=subprocess.Popen(cmd,cwd=str(DATA_DIR),
                                  creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except Exception as e:
            if button is not None:
                try: button.configure(state="normal")
                except Exception: pass
            messagebox.showerror("BOOK☆WALKER",f"Could not open the sign-in window.\n\n{type(e).__name__}: {e}")
            return

        def wait_for_login():
            code=proc.wait()
            cookies=load_bookwalker_cookies()
            def finish():
                if button is not None:
                    try: button.configure(state="normal")
                    except Exception: pass
                if code==0 and cookies:
                    if status_var is not None: status_var.set(ui_tr("Signed in"))
                    self.db.set_setting("bookwalker_session_state","valid")
                    self._start_bookwalker_health_schedule()
                    try:
                        delay=float(self.db.get_setting("request_delay_seconds","1.25"))
                        self.providers=live_providers(delay,self.log,cookies)
                    except Exception:
                        pass
                    self.log("[BOOK☆WALKER] Signed-in session connected; future updates can use account coin values")
                    messagebox.showinfo("BOOK☆WALKER","BOOK☆WALKER connected. Future price updates will use the signed-in session for coin values.")
                elif code==2:
                    if status_var is not None: status_var.set(ui_tr("Not signed in — cash prices still work; coins are hidden."))
                    messagebox.showinfo("BOOK☆WALKER","BOOK☆WALKER sign-in was not completed.")
                else:
                    detail=""
                    try: detail=BW_LOGIN_ERROR_PATH.read_text(encoding="utf-8").strip()
                    except Exception: pass
                    msg="Could not open the BOOK☆WALKER sign-in window. The Microsoft Edge WebView2 Runtime is required."
                    if detail: msg+=f"\n\n{detail}"
                    if status_var is not None: status_var.set(ui_tr("Not signed in — cash prices still work; coins are hidden."))
                    messagebox.showerror("BOOK☆WALKER",msg)
            self.after(0,finish)
        threading.Thread(target=wait_for_login,daemon=True).start()

    def settings_dialog(self):
        w=self._single_window("settings","Settings","660x800",resizable=True)
        if w is None:return
        w.minsize(620,620)
        savebar=ttk.Frame(w,padding=(16,4,16,12)); savebar.pack(fill="x",side="bottom")
        body=ttk.Frame(w); body.pack(fill="both",expand=True)
        canvas_bg="#121212" if self.db.get_setting("appearance","system")=="dark" else "#f0f0f0"
        canvas=tk.Canvas(body,highlightthickness=0,bg=canvas_bg)
        scroll=ttk.Scrollbar(body,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y"); canvas.pack(side="left",fill="both",expand=True)
        f=ttk.Frame(canvas,padding=16)
        settings_window=canvas.create_window((0,0),window=f,anchor="nw")
        f.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(settings_window,width=e.width))
        notify=tk.StringVar(value=self.db.get_setting("notification_rule","any_sale"))
        threshold=tk.StringVar(value=self.db.get_setting("deal_threshold","20"))
        rewards=tk.BooleanVar(value=self.db.get_setting("include_direct_rewards","1")=="1")
        bw_tax=tk.BooleanVar(value=self.db.get_setting("bw_overseas_tax","0")=="1")
        show_covers=tk.BooleanVar(value=self.db.get_setting("show_covers","1")=="1")
        cover_size=tk.StringVar(value=self.db.get_setting("cover_size","medium"))
        store_booklive=tk.BooleanVar(value=self.db.get_setting("store_booklive_enabled","1")=="1")
        store_bookwalker=tk.BooleanVar(value=self.db.get_setting("store_bookwalker_enabled","1")=="1")
        store_dmm=tk.BooleanVar(value=self.db.get_setting("store_dmm_enabled","1")=="1")
        store_amazon=tk.BooleanVar(value=self.db.get_setting("store_amazon_enabled","1")=="1")
        interval=tk.StringVar(value=self.db.get_setting("update_interval_hours","6"))
        reqdelay=tk.StringVar(value=self.db.get_setting("request_delay_seconds","1.25"))
        appearance=tk.StringVar(value=self.db.get_setting("appearance","system"))
        retention=tk.StringVar(value=self.db.get_setting("trash_retention_days","14"))
        check_updates=tk.BooleanVar(value=self.db.get_setting("check_updates_on_startup","1")=="1")
        use_prerelease=tk.BooleanVar(value=self.db.get_setting("use_prerelease_updates","0")=="1")
        close_behavior=tk.StringVar(value=self.db.get_setting("close_button_behavior","tray"))
        ttk.Label(f,text="Notification rule",font=("Segoe UI",10,"bold")).pack(anchor="w")
        for text,val in [("Any sale","any_sale"),("Lowest recorded price","historical_low"),("Good deal","good_deal")]:
            ttk.Radiobutton(f,text=text,variable=notify,value=val).pack(anchor="w")
        row=ttk.Frame(f); row.pack(fill="x",pady=6)
        ttk.Label(row,text="Good-deal threshold (> %):").pack(side="left")
        ttk.Entry(row,textvariable=threshold,width=8).pack(side="left",padx=6)
        test_row=ttk.Frame(f); test_row.pack(fill="x",pady=(0,2))
        ttk.Button(test_row,text="Test sale notification",
                   command=lambda:self._test_sale_notification(notify.get(),threshold.get())).pack(side="left")
        ttk.Button(test_row,text="Test multiple sale notifications",
                   command=lambda:self._test_sale_notification(notify.get(),threshold.get(),True)).pack(side="left",padx=(6,0))
        ttk.Label(f,text="Simulates a 50% sale using the selected rule. The multiple test simulates three books going on sale at once. No book data or price history is changed.",
                  wraplength=520).pack(anchor="w",pady=(0,6))
        def apply_price_view():
            self.db.set_setting("include_direct_rewards","1" if rewards.get() else "0")
            self.db.set_setting("bw_overseas_tax","1" if bw_tax.get() else "0")
            self.refresh()
        ttk.Checkbutton(f,text="Show direct DMM points / BOOK☆WALKER coins / Amazon points in store price columns",
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
            self.db.set_setting("store_amazon_enabled","1" if store_amazon.get() else "0")
            self.apply_store_columns(); self.refresh()
        ttk.Checkbutton(f,text="BookLive",variable=store_booklive,command=apply_store_settings).pack(anchor="w")
        ttk.Checkbutton(f,text="BOOK☆WALKER",variable=store_bookwalker,command=apply_store_settings).pack(anchor="w")
        bw_login=ttk.Frame(f); bw_login.pack(fill="x",padx=(22,0),pady=(2,5))
        bw_state=self.db.get_setting("bookwalker_session_state","valid" if load_bookwalker_cookies() else "never")
        bw_initial=("Signed in (last known)" if bw_state=="valid" and load_bookwalker_cookies()
                    else "Session expired" if bw_state=="expired"
                    else "Not signed in — cash prices still work; coins are hidden.")
        bw_status=tk.StringVar(value=ui_tr(bw_initial))
        bw_button=ttk.Button(bw_login,text="Sign in to BOOK☆WALKER")
        bw_button.pack(side="left")
        ttk.Button(bw_login,text="Check now",
                   command=lambda:self._run_bookwalker_health_check(bw_status,notify_expiry=True)).pack(side="left",padx=(6,0))
        ttk.Label(bw_login,textvariable=bw_status,wraplength=250).pack(side="left",padx=(10,0))
        bw_button.configure(command=lambda:self._start_bookwalker_signin(bw_status,bw_button))

        ttk.Checkbutton(f,text="DMM",variable=store_dmm,command=apply_store_settings).pack(anchor="w")
        dmm_health=ttk.Frame(f); dmm_health.pack(fill="x",padx=(22,0),pady=(2,5))
        dmm_status=tk.StringVar(value=ui_tr("Not checked"))
        ttk.Button(dmm_health,text="Check now",command=lambda:self._run_dmm_health_check(dmm_status)).pack(side="left")
        ttk.Label(dmm_health,textvariable=dmm_status,wraplength=330).pack(side="left",padx=(10,0))
        ttk.Checkbutton(f,text="Amazon (HTML import + direct price refresh only)",variable=store_amazon,command=apply_store_settings).pack(anchor="w")
        row2=ttk.Frame(f); row2.pack(fill="x",pady=8)
        ttk.Label(row2,text="Automatic update interval (hours):").pack(side="left")
        ttk.Combobox(row2,textvariable=interval,values=("3","6","12","24"),width=6,state="readonly").pack(side="left",padx=6)
        row3=ttk.Frame(f); row3.pack(fill="x",pady=5)
        ttk.Label(row3,text="Minimum delay between store requests (seconds):").pack(side="left")
        ttk.Entry(row3,textvariable=reqdelay,width=7).pack(side="left",padx=6)
        ttk.Checkbutton(f,text="Check for new versions on startup (never installs automatically)",
                        variable=check_updates).pack(anchor="w",pady=(5,2))
        ttk.Checkbutton(f,text="Use nightly / pre-release versions (test builds)",
                        variable=use_prerelease).pack(anchor="w",pady=(2,0))
        ttk.Label(f,text="Off = stable releases only. Test builds may contain unfinished fixes.",
                  wraplength=500).pack(anchor="w",pady=(0,4))
        close_row=ttk.Frame(f); close_row.pack(fill="x",pady=(3,2))
        ttk.Label(close_row,text="Close button (X):").pack(side="left")
        ttk.Radiobutton(close_row,text="Minimize to system tray",variable=close_behavior,value="tray").pack(side="left",padx=(10,0))
        ttk.Radiobutton(close_row,text="Exit application",variable=close_behavior,value="exit").pack(side="left",padx=(10,0))
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
            self.db.set_setting("store_amazon_enabled","1" if store_amazon.get() else "0")
            self.db.set_setting("update_interval_hours",interval.get())
            self.db.set_setting("request_delay_seconds",reqdelay.get())
            self.db.set_setting("check_updates_on_startup","1" if check_updates.get() else "0")
            self.db.set_setting("use_prerelease_updates","1" if use_prerelease.get() else "0")
            self.db.set_setting("close_button_behavior",close_behavior.get())
            chosen_appearance=appearance_display.get(); appearance.set({"システム":"system","ライト":"light","ダーク":"dark"}.get(chosen_appearance,chosen_appearance))
            self.db.set_setting("appearance",appearance.get()); self.db.set_setting("trash_retention_days",retention.get())
            self.apply_theme()
            try:self.providers=live_providers(float(reqdelay.get()), self.log,load_bookwalker_cookies())
            except:pass
            self._schedule_auto_price_update()
            w.destroy()
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
            checked=found=merged=0; report=[]; dmm_region_blocked=False; worker_db=DB()
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
                        # Amazon often appends an imprint/publisher in a final parenthetical.
                        # Use the Amazon offer title itself when available, strip only a likely
                        # trailing publisher tag, require compatible volume hints, and use a
                        # stricter threshold than ordinary cross-store reconciliation.
                        bt=b['title']; ct=c['title']
                        if "Amazon" in bs:
                            ar=worker_db.cx.execute("SELECT title FROM offers WHERE book_id=? AND store='Amazon'",(b['id'],)).fetchone()
                            if ar:bt=ar['title']
                        if "Amazon" in cs:
                            ar=worker_db.cx.execute("SELECT title FROM offers WHERE book_id=? AND store='Amazon'",(c['id'],)).fetchone()
                            if ar:ct=ar['title']
                        score=cross_store_title_similarity(bt,bs,ct,cs)
                        threshold=.985 if (("Amazon" in bs) ^ ("Amazon" in cs)) else .965
                        if score>=threshold and bs.isdisjoint(cs):
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
                    # Prefer a non-Amazon title as the search anchor. If this is an
                    # Amazon-only import, remove only its likely trailing publisher tag.
                    source=next((existing[s] for s in TITLE_SOURCE_PRIORITY if s!="Amazon" and s in existing),None)
                    if source is None:source=existing.get("Amazon") or next(iter(existing.values()),None)
                    qtitle=source['title'] if source else b['title']
                    if source and source['store']=="Amazon":qtitle=amazon_title_for_match(qtitle)
                    qauthor=(source['author'] if source and source['author'] else b['author']) or ''
                    # Amazon discovery/search stays disabled. Imported Amazon-only books
                    # may search the other three stores, but we never search Amazon.
                    for store in SEARCH_STORES:
                        if store not in enabled_stores or store in existing:continue
                        p=self.providers.get(store)
                        if not p:continue
                        try:
                            r=p.best(qtitle,qauthor); checked+=1
                            if r:
                                # If this exact store product was imported as its own canonical entry, merge that entry instead of duplicating offer.
                                er=worker_db.cx.execute("SELECT book_id FROM offers WHERE store=? AND ((store_id!='' AND store_id=?) OR url=?)",(store,r.store_id,canonical_store_url(store,r.url))).fetchone()
                                if er and er['book_id']!=book_id:
                                    other=er['book_id']; ob=worker_db.cx.execute("SELECT title FROM books WHERE id=?",(other,)).fetchone()
                                    if worker_db.merge_books(book_id,other):
                                        merged+=1; report.append(f"MERGED via {store} exact product\n  Kept: {b['title']}\n  Merged: {ob['title'] if ob else other}\n  URL: {r.url}")
                                else:
                                    # Force attachment to this book rather than fuzzy choosing another canonical row.
                                    worker_db.update_offer_for_book(book_id,store,self._offer_from_live(r)); found+=1
                                    report.append(f"MATCHED {store} ({r.confidence:.3f})\n  {b['title']}\n  {r.url}")
                            else: report.append(f"NO MATCH {store}\n  {b['title']}")
                        except DMMRegionError as e:
                            dmm_region_blocked=True
                            report.append(f"DMM UNAVAILABLE — Japanese IP required\n  {b['title']}\n  {e}")
                        except Exception as e: report.append(f"ERROR {store}\n  {b['title']}\n  {type(e).__name__}: {e}")
            finally:worker_db.cx.close()
            textlog=f"Find Missing Matches complete\nChecked slots: {checked}\nNew matches: {found}\nBooks merged: {merged}\n\n"+"\n\n".join(report)
            self.after(0,self.refresh); self.after(0,lambda:self.show_match_report(textlog))
            if dmm_region_blocked:
                self.after(0,lambda:messagebox.showwarning(
                    "DMM Books unavailable",
                    "DMM Books could not be reached from the current network. DMM Books requires a Japanese IP address. "
                    "Connect through a Japanese IP/VPN and try again. Other stores can still be checked."
                ))
        self._run_background(work)

    def _sale_event_for_refresh(self,db,book_id,store,new_price,new_list_price):
        """Evaluate the configured notification rule before saving a refreshed price."""
        if new_price is None:return None
        row=db.cx.execute("SELECT id,price,list_price FROM offers WHERE book_id=? AND store=?",
                          (book_id,store)).fetchone()
        if not row:return None
        book=db.cx.execute("SELECT title FROM books WHERE id=?",(book_id,)).fetchone()
        title=(book["title"] if book else "") or "Book"
        old_price=row["price"]; old_list=row["list_price"]
        prior=db.cx.execute("SELECT MIN(price) low FROM price_history WHERE offer_id=? AND price IS NOT NULL",
                            (row["id"],)).fetchone()
        prior_low=prior["low"] if prior else None

        # Prefer a current list price as the discount reference. If a store omits
        # it, a genuine downward move from the previously observed cash price can
        # still count as a sale.
        reference=None
        for candidate in (new_list_price,old_list,old_price):
            if candidate is not None and candidate>new_price:
                reference=candidate; break
        discount=(100.0*(reference-new_price)/reference) if reference else None
        changed=(old_price!=new_price) or (old_list!=new_list_price)

        rule=db.get_setting("notification_rule","any_sale")
        try:threshold=float(db.get_setting("deal_threshold","20"))
        except Exception:threshold=20.0
        reason=None
        if rule=="historical_low":
            if prior_low is not None and new_price<prior_low:
                reason="historical_low"
        elif rule=="good_deal":
            if changed and discount is not None and discount>=threshold:
                reason="good_deal"
        else:
            if changed and reference is not None and new_price<reference:
                reason="any_sale"
        if not reason:return None
        return {"book_id":book_id,"title":title,"store":store,"price":new_price,
                "reference":reference,"discount":discount,"prior_low":prior_low,
                "reason":reason}

    def _dispatch_sale_events(self,events,test=False):
        events=list(events or [])
        if not events:return

        # A refresh can produce one event per store offer. Group first by book so
        # a title on sale at multiple stores still counts as one book notification.
        books={}
        for event in events:
            key=event.get("book_id")
            if key is None:key=("title",event.get("title",""))
            books.setdefault(key,[]).append(event)

        if len(books)>1:
            count=len(books)
            titles=[]
            for grouped in books.values():
                title=(grouped[0].get("title") or "Book").strip()
                if title and title not in titles:titles.append(title)
            preview=titles[:3]
            remaining=max(0,count-len(preview))
            if UI_LANG=="ja":
                heading=f"{count}冊の書籍がセール中"
                msg="\n".join("• "+x for x in preview)
                if remaining:msg+=f"\n…ほか {remaining}冊"
                msg+=f"\n\nアプリで「セール中の書籍のみ表示」をオンにすると詳細を確認できます。"
            else:
                heading=f"{count} books on sale"
                msg="\n".join("• "+x for x in preview)
                if remaining:msg+=f"\n…and {remaining} more"
                msg+="\n\nTurn on Show only books on sale in the app for details."
            if test:
                msg+=("\nまとめ通知のテストです。" if UI_LANG=="ja" else "\nThis is a grouped notification test.")
            self._desktop_notification(heading,msg)
            self.log(f"[Notification] Grouped {len(events)} sale event(s) across {count} book(s)")
            return

        # One qualifying book keeps the detailed notification. If more than one
        # store triggered for that book, use the first/best event for now; phase 3
        # will expose all matching store sale entries in the notification center.
        event=next(iter(books.values()))[0]
        title=event["title"]; store=event["store"]; price=event["price"]
        ref=event.get("reference"); discount=event.get("discount")
        if UI_LANG=="ja":
            heading="セールを検出"
            if event["reason"]=="historical_low":
                msg=f"{title}\n{store}：¥{price:,}（記録上の最安値）"
            elif discount is not None:
                if test and event.get("reason")=="good_deal" and event.get("test_threshold") is not None:
                    msg=f"{title}\n{store}：¥{price:,}（{discount:.0f}%オフ、設定しきい値 {event['test_threshold']:g}%）"
                else:
                    msg=f"{title}\n{store}：¥{price:,}（{discount:.0f}%オフ）"
            else:
                msg=f"{title}\n{store}：¥{price:,}"
        else:
            heading="Book sale found"
            if event["reason"]=="historical_low":
                msg=f"{title}\n{store}: ¥{price:,} — new recorded low"
            elif discount is not None and ref is not None:
                if test and event.get("reason")=="good_deal" and event.get("test_threshold") is not None:
                    msg=f"{title}\n{store}: ¥{price:,} ({discount:.0f}% off, was ¥{ref:,}) — threshold {event['test_threshold']:g}%"
                else:
                    msg=f"{title}\n{store}: ¥{price:,} ({discount:.0f}% off, was ¥{ref:,})"
            else:
                msg=f"{title}\n{store}: ¥{price:,}"
        self._desktop_notification(heading,msg)

    def update_prices(self):
        selected=set(self.selected_ids())
        if not selected:
            messagebox.showinfo("Update","Select one or more books first.")
            return

        w=self._single_window("update_prices","Update selected books","520x330",resizable=(False,False),grab=True)
        if w is None:return
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
            ok=0; failed=[]; dmm_region_blocked=False; sale_events=[]; worker_db=DB()
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
                        sale_state=worker_db.update_sale_state_for_refresh(bid,store,r.price,r.list_price)
                        sale_event=self._sale_event_for_refresh(worker_db,bid,store,r.price,r.list_price)
                        saved_bid=worker_db.update_offer_for_book(bid,store,fetched); ok+=1
                        if sale_event:sale_events.append(sale_event)
                        if getattr(r,"cover_url",""):
                            self.after(0,lambda bid=saved_bid,store=store,url=r.cover_url:self.cache_cover(bid,store,url))
                        shown=("¥"+format(r.price,",")) if r.price is not None else "price not parsed"
                        self.log(f"[{store}] Updated: {r.title or url} — {shown}")
                    except DMMRegionError as e:
                        dmm_region_blocked=True
                        failed.append("DMM: Japanese IP required")
                        self.log(f"[DMM] UPDATE BLOCKED: {e}")
                    except Exception as e:
                        failed.append(f"{store}: {type(e).__name__}: {e}")
                        self.log(f"[{store}] UPDATE ERROR {type(e).__name__}: {e}")
            finally:
                worker_db.cx.close()
            self.after(0,self.refresh); self.after(0,lambda:self.status.set("Ready"))
            if sale_events:
                self.after(0,lambda events=list(sale_events):self._dispatch_sale_events(events))
            label={"covers":"cover page(s) checked","missing_price":"missing-price offer(s) updated","everything":"product page(s) updated"}[mode]
            msg=f"{ok}/{len(jobs)} {label}."
            if failed:msg+="\n\nFailed:\n"+"\n".join(failed[:12])
            if dmm_region_blocked:
                msg+="\n\nDMM Books requires a Japanese IP address. Connect through a Japanese IP/VPN and try DMM again."
                self.after(0,lambda m=msg:messagebox.showwarning("DMM Books unavailable",m))
            else:
                self.after(0,lambda m=msg:messagebox.showinfo("Update complete",m))
        self._run_background(work)


    def _version_key(self, value):
        """Comparable key for stable and prerelease tags such as 1.9.0-beta.2."""
        s=str(value or "").strip().lstrip("vV")
        m=re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-.]?(.+))?$",s)
        if not m:
            nums=[int(x) for x in re.findall(r"\d+",s)[:3]]
            while len(nums)<3: nums.append(0)
            return (*nums,0,0)
        major,minor,patch=(int(m.group(i)) for i in (1,2,3))
        pre=(m.group(4) or "").lower()
        if not pre:
            return (major,minor,patch,4,0)
        if pre.startswith(("rc","releasecandidate")): rank=3
        elif pre.startswith(("beta","b")): rank=2
        elif pre.startswith(("alpha","a")): rank=1
        else: rank=0
        nums=re.findall(r"\d+",pre)
        serial=int(nums[-1]) if nums else 0
        return (major,minor,patch,rank,serial)

    def _pick_update_release(self, releases, allow_prerelease):
        usable=[r for r in releases if isinstance(r,dict) and not r.get("draft")]
        if not allow_prerelease:
            usable=[r for r in usable if not r.get("prerelease")]
        if not usable:return None
        return max(usable,key=lambda r:self._version_key(str(r.get("tag_name",""))))

    def check_for_updates(self, silent=False, automatic=False):
        if not GITHUB_OWNER or not GITHUB_REPO:
            if not silent: messagebox.showinfo("Updates","GitHub updates are not configured in this build yet.")
            return
        # SQLite connection belongs to Tk's main thread. Read update-channel state
        # before launching the network worker so the worker never touches self.db.
        allow_prerelease=self.db.get_setting("use_prerelease_updates","0")=="1"
        reminder_version=self.db.get_setting("last_update_reminder_version","") if automatic else ""
        reminder_date=self.db.get_setting("last_update_reminder_date","") if automatic else ""
        self.status.set("Checking for updates…")
        def work():
            try:
                if allow_prerelease:
                    api=f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases?per_page=30"
                    req=urllib.request.Request(api,headers={"Accept":"application/vnd.github+json","User-Agent":APP_NAME})
                    with urllib.request.urlopen(req,timeout=15) as r:
                        releases=json.loads(r.read().decode("utf-8"))
                    release=self._pick_update_release(releases,True)
                else:
                    api=f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
                    req=urllib.request.Request(api,headers={"Accept":"application/vnd.github+json","User-Agent":APP_NAME})
                    with urllib.request.urlopen(req,timeout=15) as r:
                        release=json.loads(r.read().decode("utf-8"))

                if not release:
                    if not silent:
                        self.after(0,lambda:messagebox.showinfo("Updates","No release is available on the selected update channel yet."))
                    return

                latest=str(release.get("tag_name","")).lstrip("vV")
                if self._version_key(latest)<=self._version_key(APP_VERSION):
                    if not silent:
                        channel="pre-release" if allow_prerelease else "stable"
                        self.after(0,lambda latest=latest,channel=channel:messagebox.showinfo(
                            "Updates",f"You're already using the latest {channel} version ({latest or APP_VERSION})."))
                    return

                asset=next((x for x in (release.get("assets") or [])
                            if x.get("name","").startswith(UPDATE_ASSET_PREFIX) and x.get("name","").endswith(".zip")),None)
                if not asset:
                    if not silent:
                        self.after(0,lambda latest=latest:messagebox.showinfo(
                            "Update not ready yet",
                            f"Version {latest} has been published, but the Windows build is still being prepared.\n\n"
                            "Please try again in a few minutes."))
                    return

                if automatic:
                    today=datetime.now().date().isoformat()
                    if reminder_version==latest and reminder_date==today:
                        return
                    # Persist reminder bookkeeping back on Tk's main thread.
                    self.after(0,lambda latest=latest,today=today:(
                        self.db.set_setting("last_update_reminder_version",latest),
                        self.db.set_setting("last_update_reminder_date",today)
                    ))

                body=(release.get("body") or "").strip()
                is_pre=bool(release.get("prerelease"))
                def prompt():
                    kind="Pre-release" if is_pre else "Version"
                    msg=f"{kind} {latest} is available.\n\n"
                    if is_pre:
                        msg+="This is a test build and may still contain unfinished fixes.\n\n"
                    if body and not automatic:
                        msg+=body[:1600]+"\n\n"
                    msg+="Would you like to download and install it now?\n\nNothing is installed unless you choose Yes."
                    if messagebox.askyesno("Update available",msg):
                        self._download_and_install_update(latest,asset)
                self.after(0,prompt)
            except Exception as e:
                if not silent:
                    self.after(0,lambda e=e:messagebox.showerror(
                        "Update check failed",
                        "Could not check for updates right now. Please try again later.\n\n"
                        f"{type(e).__name__}: {e}"))
            finally:
                self.after(0,lambda:self.status.set("Ready"))
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
                script = """$ErrorActionPreference = 'Stop'
$pidToWait = __PID__
$zip = '__ZIP__'
$install = '__INSTALL__'
$exe = '__EXE__'
$expectedVersion = '__VERSION__'
$log = Join-Path '__TMP__' 'update.log'

function Log($msg) { Add-Content -LiteralPath $log -Value ((Get-Date -Format s) + "  " + $msg) }

try {
    Log "Waiting for source process PID $pidToWait"
    while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 250 }

    $targetExe = [System.IO.Path]::GetFullPath((Join-Path $install $exe))
    $deadline = (Get-Date).AddSeconds(20)
    do {
        $others = @(Get-CimInstance Win32_Process -Filter "Name='$exe'" -ErrorAction SilentlyContinue | Where-Object {
            $_.ExecutablePath -and ([System.IO.Path]::GetFullPath($_.ExecutablePath) -ieq $targetExe)
        })
        if ($others.Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    if ($others.Count -gt 0) {
        throw "Another Book Sale Notification instance from this install folder is still running. Close it from the system tray and run the update again."
    }

    $stage = Join-Path '__TMP__' 'stage'
    if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force
    $items = @(Get-ChildItem -LiteralPath $stage)
    $src = $stage
    if ($items.Count -eq 1 -and $items[0].PSIsContainer) { $src = $items[0].FullName }

    $sourceExe = Join-Path $src $exe
    if (-not (Test-Path -LiteralPath $sourceExe)) { throw "Downloaded update does not contain $exe." }

    Log "Copying update into $install"
    Copy-Item -Path (Join-Path $src '*') -Destination $install -Recurse -Force

    if (-not (Test-Path -LiteralPath $targetExe)) { throw "Updated executable was not found after copying." }
    $marker = Join-Path $install '.update-installed'
    Set-Content -LiteralPath $marker -Value $expectedVersion -Encoding UTF8
    Log "Update copy completed: $expectedVersion"
    Start-Sleep -Milliseconds 500
    Start-Process -FilePath $targetExe -WorkingDirectory $install
}
catch {
    Log ("UPDATE FAILED: " + $_.Exception.Message)
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show(
        "Book Sale Notification could not finish the update." + [Environment]::NewLine + [Environment]::NewLine + $_.Exception.Message +
        [Environment]::NewLine + [Environment]::NewLine + "Please close every Book Sale Notification window/tray icon and try again.",
        "Update failed", "OK", "Error"
    ) | Out-Null
}
"""
                esc=lambda x:str(x).replace("'","''")
                script=script.replace("__PID__",str(os.getpid())).replace("__ZIP__",esc(zpath)).replace("__INSTALL__",esc(exe.parent)).replace("__EXE__",esc(exe.name)).replace("__TMP__",esc(tmp)).replace("__VERSION__",esc(version))
                ps.write_text(script,encoding="utf-8")
                subprocess.Popen(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ps)],
                                 creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                self.after(0,self._exit_application)
            except Exception as e:
                self.after(0,lambda e=e:messagebox.showerror("Update failed",f"{type(e).__name__}: {e}"))
                self.after(0,lambda:self.status.set("Ready"))
        self._run_background(work)

    def sort_by(self,col):
        children=list(self.tree.get_children(""))
        previous=self._sort_state.get(col)
        if previous is None:
            reverse=(col=="latest_sale")
        else:
            reverse=not previous
        self._sort_state[col]=reverse
        def key(iid):
            value=str(self.tree.set(iid,col) or "")
            if col=="latest_sale":
                try:return datetime.fromisoformat(value).timestamp()
                except Exception:return float("-inf")
            m=re.search(r'¥([0-9,]+)',value)
            if m:return (0,int(m.group(1).replace(",","")))
            return (1,value.casefold())
        children.sort(key=key,reverse=reverse)
        for i,iid in enumerate(children):self.tree.move(iid,"",i)


if __name__=="__main__":
    if "--bookwalker-login-helper" in sys.argv:
        raise SystemExit(bookwalker_login_helper())
    if not acquire_single_instance():
        raise SystemExit(0)
    App().mainloop()
