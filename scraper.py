from __future__ import annotations
import re, time, unicodedata, json
import html as html_lib
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import quote, urljoin, urlparse
import requests
from bs4 import BeautifulSoup

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"
SPECIAL=("特装版","合本版","単話版","無料版","セット版","分冊版")

def edition_compatible(wanted,candidate):
    """Distinct product/edition markers must agree; similarity cannot override them."""
    w=nfkc(wanted); c=nfkc(candidate)
    return all((marker in w)==(marker in c) for marker in SPECIAL)
@dataclass
class Result:
    store:str; title:str; url:str; store_id:str=""; author:str=""; price:int|None=None
    list_price:int|None=None; reward_pct:float|None=None; reward_value:int|None=None
    tax_ex_price:int|None=None; cover_url:str=""; confidence:float=0.0

def space(s): return re.sub(r"\s+"," ",str(s or "")).strip()
def nfkc(s): return unicodedata.normalize("NFKC",space(s))
def key(s): return re.sub(r"[\W_]+","",nfkc(s).casefold(),flags=re.UNICODE)
def money(s):
    if not s:return None
    text=nfkc(s)
    for pat in (
        r"[¥￥]\s*([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s*円",
    ):
        m=re.search(pat,text)
        if m:return int(m.group(1).replace(",",""))
    # Only accept a bare number when the whole field is numeric. This prevents
    # labels such as "85% OFF" from ever becoming a price.
    m=re.fullmatch(r"\s*([0-9][0-9,]*)\s*",text)
    return int(m.group(1).replace(",","")) if m else None

def yen_money(s):
    """Strict yen parser for Amazon price labels; never accepts percentages."""
    if not s:return None
    text=nfkc(s)
    for pat in (
        r"[¥￥]\s*([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s*円",
    ):
        m=re.search(pat,text)
        if m:return int(m.group(1).replace(",",""))
    return None

def parse_volume(title):
    s=nfkc(title)
    hits=[]
    for pat in (r"[（(]\s*(\d+(?:\.\d+)?)\s*[）)]",r"(?:第\s*)?(\d+(?:\.\d+)?)\s*巻",
                r"\bvol(?:ume)?\.?\s*(\d+(?:\.\d+)?)"):
        for m in re.finditer(pat,s,re.I):
            if m.start()>0:hits.append((m.start(),float(m.group(1))))
    if hits:
        pos,n=max(hits,key=lambda x:x[0]); return s[:pos].strip(" ,，-–—―:："), int(n) if n.is_integer() else n
    m=re.search(r"^(.*?)[\s　]+(上|中|下|前編|後編)(?=\s*(?:$|【|\[))",s)
    if m:return m.group(1).strip(),m.group(2)
    # Bare trailing/bonus-adjacent volume number; mirrors the conservative Calibre resolver.
    ms=list(re.finditer(r"(?<!\d)(\d{1,3})(?!\d)",s))
    for m in reversed(ms):
        pre,tail=s[:m.start()],s[m.end():]
        if pre and (pre[-1].isspace() or pre[-1] in "）)]】』」") and re.match(r"^\s*(?:$|【|\[|[~～〜―—-])",tail):
            return pre.strip(),int(m.group(1))
    return s,None

def score(wanted,candidate,wanted_author="",candidate_author=""):
    if not edition_compatible(wanted,candidate):
        return 0.0
    wb,wv=parse_volume(wanted); cb,cv=parse_volume(candidate)
    sim=SequenceMatcher(None,key(wb),key(cb)).ratio()
    if key(wb)==key(cb): sim=max(sim,.99)
    if wv is not None:
        if cv is not None and str(wv)==str(cv): sim+=.08
        elif cv is not None: sim-=.35
        else: sim-=.12
    if wanted_author and candidate_author:
        wa=key(wanted_author); ca=key(candidate_author)
        if wa and ca and (wa in ca or ca in wa): sim+=.05
    return max(0,min(1,sim))

class Client:
    def __init__(self,delay=1.25,timeout=20,logger=None):
        self.s=requests.Session(); self.s.headers.update({"User-Agent":UA,"Accept-Language":"ja-JP,ja;q=0.9,en;q=0.6"})
        self.delay=delay; self.timeout=timeout; self.last=0; self.last_url=""; self.logger=logger or (lambda m:None)
    def get(self,url):
        wait=self.delay-(time.monotonic()-self.last)
        if wait>0:time.sleep(wait)
        self.logger("GET "+url)
        r=self.s.get(url,timeout=self.timeout,allow_redirects=True); self.last=time.monotonic(); self.last_url=r.url
        self.logger(f"HTTP {r.status_code} • {len(r.content):,} bytes • {r.url}")
        r.raise_for_status()
        # These Japanese storefronts are UTF-8. requests' apparent_encoding can
        # mis-detect some BOOK☆WALKER pages and turn valid Japanese into mojibake.
        enc=(r.encoding or "").lower()
        if not enc or enc in ("iso-8859-1","latin-1"):
            r.encoding="utf-8"
        return r.text

class Provider:
    store=""
    def __init__(self,client):self.c=client
    def search(self,title,author=""):raise NotImplementedError
    def product(self,url):raise NotImplementedError
    def best(self,title,author=""):
        candidates=self.search(title,author)
        self.c.logger(f"[{self.store}] Parsed {len(candidates)} candidate(s)")
        for x in candidates:x.confidence=score(title,x.title,author,x.author)
        candidates.sort(key=lambda x:x.confidence,reverse=True)
        for x in candidates[:3]:
            self.c.logger(f"[{self.store}] candidate {x.confidence:.3f} • {x.title}")
        if not candidates or candidates[0].confidence < .90:
            return None
        best=candidates[0]
        # Search/series pages are for identity.  Before persisting a new match, fetch the
        # actual product page so price/reward/tax fields are populated immediately.
        if best.price is None and best.url:
            try:
                self.c.logger(f"[{self.store}] Fetching matched product details: {best.url}")
                full=self.product(best.url)
                if full and full.title:
                    full.confidence=best.confidence
                    return full
            except Exception as e:
                self.c.logger(f"[{self.store}] Product detail fetch failed: {type(e).__name__}: {e}")
        return best

class BookLive(Provider):
    store="BookLive"; base="https://booklive.jp"

    def _search_rows(self, soup):
        """Return BookLive product links visible in search results."""
        out={}
        for a in soup.select('a[href*="/product/index/title_id/"]'):
            href=a.get("href","")
            m=re.search(r"/product/index/title_id/(\d+)/vol_no/(\d+)",href)
            if not m: continue
            t=space(a.get("title","") or a.get_text(" ",strip=True))
            if not t: continue
            u=urljoin(self.base,href.split("?")[0])
            out[u]=Result(self.store,t,u,f"{m.group(1)}:{m.group(2).zfill(3)}")
        return list(out.values())

    def search(self,title,author=""):
        stem,wanted_vol=parse_volume(title)
        queries=[]
        # BookLive often returns no useful hit when the volume suffix is included.
        for q in (stem,title):
            if q and q not in queries: queries.append(q)
        out={}
        for q in queries:
            url=f"{self.base}/search/keyword/keyword/{quote(q,safe='')}/sort/t3"
            soup=BeautifulSoup(self.c.get(url),"html.parser")
            rows=self._search_rows(soup)
            self.c.logger(f"[{self.store}] Search exposed {len(rows)} product/series candidate(s)")
            # A search result for vol.1 identifies the BookLive title_id (series family).
            # Once we know that family, resolve the requested vol_no directly and verify it.
            ranked=[]
            for r in rows:
                rb,_=parse_volume(r.title)
                ranked.append((SequenceMatcher(None,key(stem),key(rb)).ratio(),r))
            ranked.sort(key=lambda x:x[0],reverse=True)
            if wanted_vol is not None:
                for sim,r in ranked[:8]:
                    if sim < .72: continue
                    m=re.search(r"title_id/(\d+)/vol_no/(\d+)",r.url)
                    if not m: continue
                    target=f"{self.base}/product/index/title_id/{m.group(1)}/vol_no/{int(wanted_vol):03d}"
                    try:
                        self.c.logger(f"[{self.store}] Resolving series {m.group(1)} volume {int(wanted_vol):03d}")
                        full=self.product(target)
                        fb,fv=parse_volume(full.title)
                        base_sim=SequenceMatcher(None,key(stem),key(fb)).ratio()
                        um=re.search(r"/vol_no/(\d+)",full.url or target,re.I)
                        url_vol=int(um.group(1)) if um else None
                        # Prefer an explicit volume in the title when present, but also
                        # trust the exact canonical /vol_no/NNN URL we deliberately fetched.
                        # This covers BookLive metadata variants where og:title omits "1".
                        volume_ok=(fv==wanted_vol) or (fv is None and url_vol==wanted_vol)
                        if volume_ok and base_sim>=.80:
                            if not edition_compatible(title,full.title):
                                self.c.logger(f"[{self.store}] Rejected resolved volume: edition/type mismatch • {full.title}")
                                continue
                            self.c.logger(f"[{self.store}] Exact requested volume found: {full.title}")
                            return [full]
                    except Exception as e:
                        self.c.logger(f"[{self.store}] Volume resolve failed: {type(e).__name__}: {e}")
            for r in rows: out[r.url]=r
            if out: break
        return list(out.values())

    def product(self,url):
        html=self.c.get(url); soup=BeautifulSoup(html,"html.parser")
        # Prefer the visible product heading. BookLive's og:title can be a series-level
        # title that omits the volume number even when the actual page heading includes it.
        h=(soup.select_one("h1#product_display_1") or
           soup.select_one(".product_title h1") or
           soup.select_one("h1"))
        title=space(h.get_text(" ",strip=True)) if h else ""
        if not title:
            og=soup.select_one('meta[property="og:title"]')
            title=space(og.get("content","") if og else "")
        title=re.sub(r"\s*[|｜]\s*ブックライブ.*$","",title)
        can=soup.select_one('link[rel="canonical"]'); u=can.get("href",url) if can else url
        m=re.search(r"title_id/(\d+)/vol_no/(\d+)",u)

        # BookLive embeds the exact product price in its ecommerce dataLayer.
        price=None; listp=None
        pm=re.search(r'"id"\s*:\s*"(?:\d+)-(?:\d+)".*?"price"\s*:\s*"?([0-9,]+)"?.*?"priceTax"\s*:\s*"?([0-9,]+)"?',html,re.S)
        if pm:
            price=int(pm.group(2).replace(",",""))
        if price is None:
            for sel in (".price_area .price", ".price_area .font_bl", ".product_price .price", "span.font_bl"):
                n=soup.select_one(sel)
                if n:
                    price=money(n.get_text(" ",strip=True))
                    if price is not None: break
        # Restrict original/list-price discovery to the product price area.
        pa=soup.select_one(".price_area")
        if pa:
            vals=[int(x.replace(",","")) for x in re.findall(r"([0-9][0-9,]*)\s*円",pa.get_text(" ",strip=True))]
            higher=[x for x in vals if price is not None and x>price]
            if higher: listp=max(higher)
        cover=""
        ci=soup.select_one('meta[property="og:image"]')
        if ci: cover=(ci.get("content") or "").strip()
        authors=[]
        for a in soup.select("dl.author dd a, .product_info_author a"):
            t=space(a.get_text(" ",strip=True))
            if t: authors.append(t)
        return Result(self.store,title,u,f"{m.group(1)}:{m.group(2).zfill(3)}" if m else "",
                      " / ".join(dict.fromkeys(authors)),price,listp,cover_url=cover)

class BookWalker(Provider):
    store="BOOK☆WALKER"; base="https://bookwalker.jp"

    def _product_result(self, href, title=""):
        clean=href.split("?")[0]
        if not (re.search(r"bookwalker\.jp/de[0-9a-f-]{30,}/?$",clean,re.I) or
                re.match(r"^/de[0-9a-f-]{30,}/?$",clean,re.I)):
            return None
        u=urljoin(self.base,clean)
        sid=u.rstrip("/").split("/")[-1]
        t=space(title)
        if not t or t in ("試し読み","購入","カートに入れる","お気に入り"):
            return None
        # Purchase bonuses are separate content, not volumes in the requested series.
        if "購入特典" in t or "限定書き下ろし" in t:
            return None
        return Result(self.store,t,u,sid)

    def _series_products(self, su):
        """Extract actual saleable book cards from a BW series list, not every /de link."""
        soup=BeautifulSoup(self.c.get(su),"html.parser")
        out={}
        # A real product link often appears multiple times in one card.  Prefer title-bearing
        # anchors/containers and reject trial/bonus UI links.
        for a in soup.find_all("a",href=True):
            r=self._product_result(a["href"], a.get("title","") or a.get_text(" ",strip=True))
            if not r: continue
            # Require a plausible series/book title. Tiny UI labels and image-only links are ignored.
            if len(key(r.title)) < 4: continue
            old=out.get(r.url)
            if old is None or len(r.title)>len(old.title):
                out[r.url]=r
        self.c.logger(f"[{self.store}] Series page yielded {len(out)} product-title candidate(s): {su}")
        return list(out.values())

    def search(self,title,author=""):
        stem,wanted_vol=parse_volume(title); out={}
        # Search the series stem first. Exact volume text can cause BW to surface bonuses.
        for q in dict.fromkeys([stem,title]):
            if not q:continue
            soup=BeautifulSoup(self.c.get(f"{self.base}/search/?word={quote(q)}"),"html.parser")
            series=[]
            for a in soup.find_all("a",href=True):
                m=re.search(r"/series/(\d+)/(?:list/)?",a["href"])
                if m:
                    series.append(f"{self.base}/series/{m.group(1)}/list/")
            series=list(dict.fromkeys(series))
            self.c.logger(f"[{self.store}] Found {len(series)} series page(s) from search")
            # Rank series by their visible anchor text, then inspect a small set.
            ranked=[]
            for su in series:
                sid=re.search(r"/series/(\d+)/",su).group(1)
                texts=[space(a.get_text(" ",strip=True)) for a in soup.find_all("a",href=re.compile(rf"/series/{sid}/"))]
                besttxt=max(texts,key=len,default="")
                ranked.append((SequenceMatcher(None,key(stem),key(besttxt)).ratio(),su,besttxt))
            ranked.sort(reverse=True)
            for _,su,_ in ranked[:5]:
                for r in self._series_products(su):
                    out[r.url]=r
                # If this series contains an exact base+volume candidate, don't wander into unrelated series.
                exact=[r for r in out.values()
                       if parse_volume(r.title)[1]==wanted_vol and
                          SequenceMatcher(None,key(stem),key(parse_volume(r.title)[0])).ratio()>=.80]
                if exact:
                    self.c.logger(f"[{self.store}] Exact requested volume found on series page")
                    return exact
            # Fallback: individual product results from search, still excluding UI/bonus links.
            for a in soup.find_all("a",href=True):
                r=self._product_result(a["href"],a.get("title","") or a.get_text(" ",strip=True))
                if r: out[r.url]=r
            if out:break
        return list(out.values())

    def product(self,url):
        soup=BeautifulSoup(self.c.get(url),"html.parser")
        og=soup.select_one('meta[property="og:title"]')
        title=space(og.get("content","") if og else "")
        title=re.sub(r"\s*[-|｜]\s*BOOK.?WALKER.*$","",title,flags=re.I)
        # Exact selectors from the product-page HTML.
        price=taxex=listp=reward=None
        n=soup.select_one(".t-c-product-action-parts-price__value")
        if n: price=money(n.get_text(" ",strip=True))
        n=soup.select_one(".t-c-product-action-parts-price__tax")
        if n: taxex=money(n.get_text(" ",strip=True))
        n=soup.select_one(".t-c-product-action-parts-price__before")
        if n: listp=money(n.get_text(" ",strip=True))
        # BOOK☆WALKER shows a large first-purchase "新規限定" coin amount to
        # signed-out visitors. That is NOT the normal reward and must never be
        # recorded as if every user would receive it.
        page_html=str(soup)
        login_true=bool(re.search(r"BW_IS_LOGIN\s*=\s*true",page_html,re.I))
        login_false=bool(re.search(r"BW_IS_LOGIN\s*=\s*false",page_html,re.I))
        new_user_box=soup.select_one(".t-c-product-main-action__coin .t-c-product-action-parts-new-user-coin")
        ignored_signup_coin=None
        if new_user_box:
            em=new_user_box.select_one("em")
            if em:
                m=re.search(r"([0-9][0-9,]*)",nfkc(em.get_text(" ",strip=True)))
                if m: ignored_signup_coin=int(m.group(1).replace(",",""))

        # Only the ordinary grant-coin component is eligible. On an explicitly
        # signed-out page, leave coins unknown rather than substituting the signup
        # promotion. If a future page omits BW_IS_LOGIN but still exposes the normal
        # component, it can still be read safely.
        if not login_false:
            n=soup.select_one(".t-c-product-main-action__coin .t-c-product-action-parts-grant-coin__value")
            if n:
                m=re.search(r"([0-9][0-9,]*)",nfkc(n.get_text(" ",strip=True)))
                if m: reward=int(m.group(1).replace(",",""))

        # Conservative fallback, scoped to the main product coin area only. Never
        # search the whole page because series cards and campaign modals contain
        # unrelated coin values.
        if reward is None and not login_false and not new_user_box:
            coin_area=soup.select_one(".t-c-product-main-action__coin")
            if coin_area:
                m=re.search(r"付与コイン.{0,120}?([0-9][0-9,]*)",
                            nfkc(coin_area.get_text(" ",strip=True)))
                if m: reward=int(m.group(1).replace(",",""))

        text=soup.get_text(" ",strip=True)
        if price is None:
            m=re.search(r"([0-9][0-9,]*)\s*円\s*[（(]?税込",text)
            if m: price=int(m.group(1).replace(",",""))
        if taxex is None:
            m=re.search(r"([0-9][0-9,]*)\s*円\s*[（(]\s*\+?消費税",text)
            if m: taxex=int(m.group(1).replace(",",""))
        cover=""
        ci=soup.select_one('meta[property="og:image"]')
        if ci: cover=(ci.get("content") or "").strip()
        sid=url.rstrip("/").split("/")[-1]
        if ignored_signup_coin is not None:
            self.c.logger(f"[BOOK☆WALKER] Ignored signed-out 新規限定 signup bonus: {ignored_signup_coin} coin")
        self.c.logger(f"[BOOK☆WALKER] Product values: cash={price}, tax_ex={taxex}, coins={reward}" +
                      (" (signed in)" if login_true else " (signed out; normal coins unavailable)" if login_false else ""))
        return Result(self.store,title,url.split("?")[0],sid,price=price,list_price=listp,
                      reward_value=reward,tax_ex_price=taxex,cover_url=cover)


class DMMRegionError(RuntimeError):
    """DMM Books redirected away from book.dmm.com, typically due to region access."""
    pass


class DMM(Provider):
    store="DMM"; base="https://book.dmm.com"

    def _get(self,url):
        html=self.c.get(url)
        final=urlparse(self.c.last_url or url)
        host=(final.hostname or "").lower()
        # Outside Japan DMM Books commonly redirects search/product requests to
        # accounts.dmm.com/service/login/password instead of returning book content.
        if host=="accounts.dmm.com" and final.path.startswith("/service/login/"):
            self.c.logger("[DMM] Access redirected to DMM login/access page — Japanese IP required")
            raise DMMRegionError(
                "DMM Books is not accessible from the current network. "
                "Connect through a Japanese IP address/VPN and try again."
            )
        return html

    def _product_url(self, href):
        clean=href.split("?")[0]
        m=re.search(r"/product/(\d+)/([^/]+)/?",clean)
        if not m:return None
        content_id=m.group(2)
        # /latest/ is a moving alias, never a stable book identity.
        if content_id.lower()=="latest": return None
        return urljoin(self.base,clean),f"{m.group(1)}:{content_id}"

    def _series_candidates(self, html, series_id):
        """Extract real sibling volumes from DMM's volume-book list / embedded page state."""
        soup=BeautifulSoup(html,"html.parser"); out={}
        # Prefer schema.org records embedded by DMM. They carry permanent content URLs
        # and exact numbered titles even when a visible link uses /latest/.
        for node in soup.find_all("script",type="application/ld+json"):
            try: data=json.loads(node.string or node.get_text())
            except Exception: continue
            objs=data if isinstance(data,list) else [data]
            for obj in objs:
                if not isinstance(obj,dict): continue
                books=[]
                if obj.get("@type")=="DataFeed":
                    books=obj.get("dataFeedElement",[]) or []
                elif obj.get("@type")=="Book":
                    books=[obj]
                for b in books:
                    if not isinstance(b,dict): continue
                    u=space(b.get("url") or b.get("@id"))
                    pu=self._product_url(u)
                    if not pu: continue
                    stable,sid=pu
                    if not sid.startswith(str(series_id)+":"): continue
                    t=space(b.get("name"))
                    if parse_volume(t)[1] is None: continue
                    out[stable]=Result(self.store,t,stable,sid)
        # Current DMM pages also expose sibling volumes as product anchors. The newest
        # volume can be represented by the moving /latest/ alias; keep that alias only
        # long enough to resolve its permanent og:url from the latest product page.
        for a in soup.find_all("a",href=True):
            href=a["href"]
            pu=self._product_url(href)
            latest_m=re.search(r"/product/(\d+)/latest/?",href)
            if not pu and latest_m and latest_m.group(1)==str(series_id):
                pu=(urljoin(self.base,href.split("?")[0]),f"{series_id}:latest")
            if not pu: continue
            u,sid=pu
            if not sid.startswith(str(series_id)+":"): continue
            t=space(a.get("title","") or a.get_text(" ",strip=True))
            img=a.find("img",alt=True)
            if (not t or t in ("試し読み","購入")) and img: t=space(img.get("alt",""))
            if not t: continue
            rb,rv=parse_volume(t)
            if rv is None: continue
            old=out.get(u)
            if old is None or len(t)>len(old.title): out[u]=Result(self.store,t,u,sid)
        return list(out.values())

    def search(self,title,author=""):
        stem,wanted_vol=parse_volume(title); out={}
        # Search stem first: DMM commonly returns the series/first-volume URL even when
        # the exact numbered title exists.
        for q in dict.fromkeys([stem,title]):
            if not q: continue
            soup=BeautifulSoup(self._get(f"{self.base}/search/?searchstr={quote(q)}"),"html.parser")
            raw={}
            for a in soup.find_all("a",href=True):
                pu=self._product_url(a["href"])
                if not pu:continue
                u,sid=pu
                t=space(a.get("title","") or a.get_text(" ",strip=True))
                if not t or t=="試し読み":continue
                old=raw.get(u)
                if old is None or len(t)>len(old.title): raw[u]=Result(self.store,t,u,sid)
            self.c.logger(f"[{self.store}] Search exposed {len(raw)} unique product URL(s)")
            # Rank likely series roots before fetching. One DMM product page contains a
            # sibling-volume list, so one good family match is enough to find vol. N.
            ranked=[]
            for r in raw.values():
                rb,_=parse_volume(r.title)
                ranked.append((SequenceMatcher(None,key(stem),key(rb)).ratio(),r))
            ranked.sort(key=lambda x:x[0],reverse=True)
            for idx,(sim,r) in enumerate(ranked[:8],1):
                if sim < .60: continue
                try:
                    self.c.logger(f"[{self.store}] Inspecting series candidate {idx}/{min(8,len(ranked))}: {r.url}")
                    html=self._get(r.url)
                    sm=re.search(r"/product/(\d+)/",r.url)
                    series_id=sm.group(1) if sm else ""
                    siblings=self._series_candidates(html,series_id)
                    self.c.logger(f"[{self.store}] Series page exposed {len(siblings)} numbered volume(s)")
                    for sib in siblings:
                        sb,sv=parse_volume(sib.title)
                        base_sim=SequenceMatcher(None,key(stem),key(sb)).ratio()
                        if wanted_vol is not None and sv==wanted_vol and base_sim>=.80:
                            self.c.logger(f"[{self.store}] Exact requested volume found in series: {sib.title}")
                            return [self.product(sib.url)]
                    # The fetched URL itself can already be the requested volume.
                    full=self._parse_product_html(html,r.url)
                    fb,fv=parse_volume(full.title)
                    if wanted_vol is not None and fv==wanted_vol and SequenceMatcher(None,key(stem),key(fb)).ratio()>=.80:
                        return [full]
                    out[full.url]=full
                except Exception as e:
                    self.c.logger(f"[{self.store}] Series resolve failed: {type(e).__name__}: {e}")
            if out: break
        return list(out.values())

    def _parse_product_html(self,html,url):
        soup=BeautifulSoup(html,"html.parser")
        og=soup.select_one('meta[property="og:title"]')
        title=space(og.get("content","") if og else "")
        can=soup.select_one('link[rel="canonical"]')
        canonical=(can.get("href") if can else url).split("?")[0]
        price=listp=None; authors=[]
        # DMM deliberately canonicalizes the newest volume to /latest/, but its og:url
        # contains the permanent content-specific URL used by Share. Resolve and store it.
        if re.search(r"/product/\d+/latest/?$",canonical,re.I):
            ogurl=soup.select_one('meta[property="og:url"]')
            permanent=space(ogurl.get("content","") if ogurl else "").split("?")[0]
            pm=re.search(r"/product/(\d+)/([^/]+)/?",permanent)
            if pm and pm.group(2).lower()!="latest":
                self.c.logger(f"[{self.store}] Resolved /latest/ to permanent URL: {permanent}")
                canonical=permanent
            else:
                canonical=url.split("?")[0]
        # DMM provides clean schema.org Product/DataFeed JSON-LD. Prefer the object whose
        # URL is the canonical current product and its purchase Offer.
        for node in soup.find_all("script",type="application/ld+json"):
            try: data=json.loads(node.string or node.get_text())
            except Exception: continue
            objs=data if isinstance(data,list) else [data]
            for obj in objs:
                if not isinstance(obj,dict): continue
                if obj.get("@type")=="Product" and obj.get("url")==canonical:
                    title=space(obj.get("name") or title)
                    offers=obj.get("offers") or {}
                    if isinstance(offers,dict) and offers.get("price") is not None:
                        listp=int(float(offers["price"]))
                if obj.get("@type")=="DataFeed":
                    for b in obj.get("dataFeedElement",[]):
                        if not isinstance(b,dict) or b.get("url")!=canonical: continue
                        title=space(b.get("name") or title)
                        for a in b.get("author",[]) or []:
                            if isinstance(a,dict) and a.get("name"): authors.append(space(a["name"]))
                        for we in b.get("workExample",[]) or []:
                            pa=(we.get("potentialAction") or {}).get("expectsAcceptanceOf",[]) if isinstance(we,dict) else []
                            for off in pa or []:
                                if isinstance(off,dict) and off.get("category")=="purchase" and off.get("price") is not None:
                                    price=int(float(off["price"])); break
        # Product offers may be the ordinary/list price while DataFeed purchase offer is
        # the currently payable campaign price. If only one exists, use it as cash price.
        if price is None: price=listp
        if price is None:
            # Conservative product-page fallback; identity has already been verified.
            txt=soup.get_text(" ",strip=True)
            mprice=re.search(r"(?:価格|販売価格)[^0-9]{0,30}([0-9][0-9,]*)\s*円",txt)
            if mprice: price=int(mprice.group(1).replace(",",""))
        if listp is not None and price is not None and listp<=price: listp=None
        reward_pct=reward_value=None
        campaigns=soup.select_one('[data-testid="campaigns-container"]')
        if campaigns:
            ctxt=campaigns.get_text(" ",strip=True)
            mr=re.search(r"(\d+(?:\.\d+)?)\s*%\s*[（(]\s*([0-9][0-9,]*)\s*pt\s*[）)]\s*還元",ctxt,re.I)
            if mr:
                reward_pct=float(mr.group(1)); reward_value=int(mr.group(2).replace(",",""))
            else:
                mr=re.search(r"([0-9][0-9,]*)\s*pt\s*還元",ctxt,re.I)
                if mr: reward_value=int(mr.group(1).replace(",",""))
        cover=""
        ci=soup.select_one('meta[property="og:image"]')
        if ci: cover=(ci.get("content") or "").strip()
        m=re.search(r"/product/(\d+)/([^/]+)/?",canonical)
        sid=f"{m.group(1)}:{m.group(2)}" if m else ""
        return Result(self.store,title,canonical,sid," / ".join(dict.fromkeys(authors)),price,listp,
                      reward_pct=reward_pct,reward_value=reward_value,cover_url=cover)

    def product(self,url):
        html=self.c.get(url)
        return self._parse_product_html(html,url)

class Amazon(Provider):
    """Phase-1 Amazon support.

    Search/discovery is intentionally disabled. Only a known amazon.co.jp Kindle
    product URL from HTML import or Add from URL may be refreshed directly.
    """
    store="Amazon"; base="https://www.amazon.co.jp"

    def _embedded_asin_price(self,soup,html,asin):
        """Extract Amazon's ASIN-bound displayedPrice value.

        Amazon frequently moves the visible Kindle price around. Acquisition
        payloads are more stable: they contain name/value records such as
        items[2].action.asin=B0... and items[2].action.displayedPrice.value=396.
        Pair those fields by their shared item prefix.
        """
        target=asin.upper()

        def parse_records(raw):
            if not raw:return []
            text=str(raw)
            for _ in range(3):
                decoded=html_lib.unescape(text)
                if decoded==text:break
                text=decoded
            text=text.replace(r'\"','"')

            prefixes=set(); prices={}
            for block in re.findall(r'\{[^{}]{0,800}\}',text):
                mn=re.search(r'"name"\s*:\s*"([^"]+)"',block,re.I)
                mv=re.search(r'"value"\s*:\s*"([^"]*)"',block,re.I)
                if not mn or not mv:continue
                name=mn.group(1); value=mv.group(1)

                ma=re.match(r'(.+)\.asin$',name,re.I)
                if ma and value.upper()==target:
                    prefixes.add(ma.group(1))

                mp=re.match(r'(.+)\.displayedPrice\.value$',name,re.I)
                if mp and re.fullmatch(r'[0-9][0-9,]*',value):
                    prices[mp.group(1)]=int(value.replace(",",""))

            return [prices[p] for p in prefixes if p in prices]

        candidates=[]
        # BeautifulSoup entity-decodes attribute JSON for us.
        for tag in soup.find_all(True):
            for value in tag.attrs.values():
                values=value if isinstance(value,list) else [value]
                for raw in values:
                    if not isinstance(raw,str):continue
                    if target not in raw or "displayedPrice" not in raw:continue
                    candidates.extend(parse_records(raw))

        # Also scan the raw response near this ASIN. This covers Amazon variants
        # where the acquisition JSON is escaped in script/HTML rather than an attr.
        decoded=html
        for _ in range(3):
            nxt=html_lib.unescape(decoded)
            if nxt==decoded:break
            decoded=nxt
        pos=0
        while True:
            pos=decoded.find(target,pos)
            if pos<0:break
            candidates.extend(parse_records(decoded[max(0,pos-6000):pos+6000]))
            pos+=len(target)

        positive=[v for v in candidates if v>0]
        if positive:return min(positive),"embedded ASIN displayedPrice"
        if candidates:return 0,"embedded ASIN displayedPrice"
        return None,""

    def _kindle_swatch_price(self,soup,html):
        """Read the Amazon.co.jp Kindle price independent of page language.

        Amazon.co.jp currently offers Japanese, English and Chinese UI. All three
        keep "Kindle" in the format label and use the same slot-price /
        ebook-price-value classes; only the surrounding label and currency prefix
        vary (￥396, ¥396, JP¥396).
        """
        def price_from(container,source):
            if not container:return None
            node=container.select_one(
                ".slot-price .ebook-price-value[aria-label], "
                ".slot-price .ebook-price-value, "
                ".slot-price [aria-label]"
            )
            if node:
                raw=(node.get("aria-label") or node.get_text(" ",strip=True) or "").strip()
                value=yen_money(raw)
                if value is not None:
                    return value,source,raw
            return None

        # Best path: Amazon's language-independent Kindle swatch id.
        kindle=soup.select_one("#tmm-grid-swatch-KINDLE")
        hit=price_from(kindle,"#tmm-grid-swatch-KINDLE")
        if hit:return hit

        # Semantic fallback. Japanese, English and Chinese labels are currently:
        #   Kindle版 (電子書籍) 形式:
        #   Kindle (Digital) Format:
        #   Kindle电子书 格式：
        # Matching just "Kindle" keeps this independent of translated Format text.
        for label in soup.find_all("span",attrs={"aria-label":re.compile(r"Kindle",re.I)}):
            node=label
            for _ in range(7):
                node=getattr(node,"parent",None)
                if not node:break
                hit=price_from(node,"Kindle-labelled format row")
                if hit:return hit
                classes=set(node.get("class") or []) if hasattr(node,"get") else set()
                if "a-container" in classes:break

        # Raw HTML fallback for malformed/partially parsed Amazon markup. Locate any
        # Kindle aria-label, then require an ebook-price-value nearby. yen_money()
        # accepts ￥396, ¥396 and JP¥396.
        decoded=html_lib.unescape(html)
        for m in re.finditer(r'aria-label=["\'][^"\']*Kindle[^"\']*["\']',decoded,re.I):
            chunk=decoded[m.start():m.start()+6000]
            pm=re.search(
                r'<span[^>]*class=["\'][^"\']*ebook-price-value[^"\']*["\'][^>]*'
                r'aria-label=["\']([^"\']+)["\']',
                chunk,re.I
            )
            if not pm:
                pm=re.search(
                    r'<span[^>]*aria-label=["\']([^"\']+)["\'][^>]*'
                    r'class=["\'][^"\']*ebook-price-value[^"\']*["\']',
                    chunk,re.I
                )
            if pm:
                raw=html_lib.unescape(pm.group(1)).strip()
                value=yen_money(raw)
                if value is not None:
                    return value,"raw Kindle-labelled format row",raw

        return None,"",""

    def search(self,title,author=""):
        self.c.logger("[Amazon] Search/discovery is disabled; direct known-URL refresh only")
        return []

    def product(self,url):
        u=urlparse(url)
        host=(u.hostname or "").lower().rstrip(".")
        m=re.search(r"/dp/([A-Z0-9]{10})(?:/|$)",u.path,re.I)
        if not (host=="amazon.co.jp" or host.endswith(".amazon.co.jp")) or not m:
            raise ValueError("Amazon refresh requires an amazon.co.jp /dp/<ASIN> product URL")
        asin=m.group(1).upper()
        canonical=f"{self.base}/dp/{asin}"
        html=self.c.get(canonical)
        soup=BeautifulSoup(html,"html.parser")

        title=""
        n=soup.select_one("#productTitle") or soup.select_one("#ebooksProductTitle")
        if n:title=space(n.get_text(" ",strip=True))
        if not title:
            og=soup.select_one('meta[property="og:title"]')
            if og:title=space(og.get("content",""))
        title=re.sub(r"\s*[:|｜-]\s*Amazon\.co\.jp.*$","",title,flags=re.I)
        title=re.sub(r"\s*[（(]\s*Kindle(?:版| Edition)\s*[）)]\s*$","",title,flags=re.I)

        price,price_source,price_raw=self._kindle_swatch_price(soup,html)

        # The acquisition payload binds a displayed purchase price to the exact
        # ASIN and is more reliable than generic buy-box selectors.
        embedded_price,embedded_source=self._embedded_asin_price(soup,html,asin)
        if embedded_price is not None:
            price=embedded_price
            price_source=embedded_source
            price_raw=str(embedded_price)

        # Last-resort legacy selectors, still restricted to Kindle-specific IDs.
        if price is None:
            for sel in (
                "#kindle-price .a-offscreen","#kindle-price",
                "#tmm-grid-swatch-KINDLE .slot-price .ebook-price-value",
                "#tmm-grid-swatch-KINDLE .slot-price",
            ):
                for node in soup.select(sel):
                    raw=(node.get("aria-label") or node.get_text(" ",strip=True) or "").strip()
                    value=yen_money(raw)
                    if value is not None:
                        price=value; price_source=sel; price_raw=raw; break
                if price is not None:break

        listp=None
        for sel in ("#listPrice",".basisPrice .a-offscreen",".a-text-price .a-offscreen"):
            node=soup.select_one(sel)
            if node:
                v=yen_money(node.get_text(" ",strip=True))
                if v is not None and (price is None or v>=price):
                    listp=v; break

        reward=None
        # Only use points from the selected Kindle-format swatch. Do not search the
        # whole page because bundle/related-product points can be unrelated.
        pn=soup.select_one("#tmm-grid-swatch-KINDLE .slot-buyingPoints")
        if pn:
            mm=re.search(r"(\d[\d,]*)\s*(?:pt|ポイント)",nfkc(pn.get_text(" ",strip=True)),re.I)
            if mm:reward=int(mm.group(1).replace(",",""))
        if reward is None:
            kindle=soup.select_one("#tmm-grid-swatch-KINDLE")
            if kindle:
                mm=re.search(r"[（(]?\s*(\d[\d,]*)\s*(?:pt|ポイント)\s*[）)]?",
                             nfkc(kindle.get_text(" ",strip=True)),re.I)
                if mm:reward=int(mm.group(1).replace(",",""))

        # Kindle Unlimited/free-reading UI can expose a ¥0 element next to a normal
        # purchase price. Never let an ambiguous zero overwrite the cash price.
        if price==0 and reward and embedded_price is None:
            price=None
            price_source="ambiguous Kindle ¥0 ignored"
            price_raw=""

        cover=""
        img=soup.select_one("#landingImage") or soup.select_one("#imgBlkFront")
        if img:
            cover=(img.get("data-old-hires") or img.get("data-a-dynamic-image") or img.get("src") or "").strip()
            if cover.startswith("{"):
                try:
                    obj=json.loads(cover)
                    if obj:cover=max(obj,key=lambda x:(obj[x][0] if isinstance(obj[x],list) and obj[x] else 0))
                except Exception:cover=""
        if not cover:
            og=soup.select_one('meta[property="og:image"]')
            if og:cover=(og.get("content") or "").strip()

        self.c.logger(f"[Amazon] Direct product values: cash={price}, points={reward}, ASIN={asin}" +
                      (f", price_source={price_source}" if price_source else "") +
                      (f", raw={price_raw!r}" if price_raw else ""))
        return Result(self.store,title,canonical,asin,price=price,list_price=listp,
                      reward_value=reward,cover_url=cover)

def providers(delay=1.25,logger=None):
    c=Client(delay=delay,logger=logger)
    return {"BookLive":BookLive(c),"BOOK☆WALKER":BookWalker(c),"DMM":DMM(c),"Amazon":Amazon(c)}
