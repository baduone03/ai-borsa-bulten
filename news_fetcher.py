"""Haber katmanı: Google News RSS + yfinance news toplama, keyword bazlı kategorize etme. AI yok."""

import calendar
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import feedparser
import yfinance as yf

from config import RSS_FEEDS, THEMES, COMPANIES

DATE_FMT = "%Y-%m-%d %H:%M"
MAX_PER_CATEGORY = 10
MAX_WORKERS = 8


def _now_utc():
    return datetime.now(timezone.utc)


def _struct_to_dt(struct):
    """feedparser struct_time (UTC) -> timezone-aware datetime."""
    return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)


def _fetch_single_feed(url: str, cutoff) -> list[dict]:
    """Tek RSS feed'ini çeker ve cutoff'tan yeni girdileri döndürür."""
    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        print(f"[news_fetcher] RSS alınamadı ({url}): {exc}")
        return []

    source = feed.feed.get("title", "RSS")
    items = []
    for entry in feed.entries:
        struct = entry.get("published_parsed")
        if not struct:
            continue
        published = _struct_to_dt(struct)
        if published < cutoff:
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:300]
        items.append({
            "title": title,
            "source": source,
            "published": published.strftime(DATE_FMT),
            "_dt": published,
            "link": entry.get("link", ""),
            "summary": summary.strip(),
        })
    return items


def fetch_rss_news(feed_urls: list, hours: int = 24) -> list[dict]:
    """RSS feed'lerini paralel çeker, son {hours} saati filtreler, dedupe eder, yeniden eskiye sıralar."""
    cutoff = _now_utc() - timedelta(hours=hours)
    workers = min(MAX_WORKERS, len(feed_urls)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_feed = pool.map(lambda url: _fetch_single_feed(url, cutoff), feed_urls)

    items = _dedupe([item for feed_items in per_feed for item in feed_items])
    items.sort(key=lambda x: x["_dt"], reverse=True)
    return items


def _yf_entry_fields(entry):
    """Eski ve yeni yfinance news şemalarından (title, link, published_dt) çıkarır."""
    content = entry.get("content", entry)
    title = content.get("title", "")
    link = ""
    if isinstance(content.get("clickThroughUrl"), dict):
        link = content["clickThroughUrl"].get("url", "")
    elif isinstance(content.get("canonicalUrl"), dict):
        link = content["canonicalUrl"].get("url", "")
    link = link or entry.get("link", "")

    published_dt = None
    pub_date = content.get("pubDate") or content.get("displayTime")
    if pub_date:
        try:
            published_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        except ValueError:
            published_dt = None
    elif entry.get("providerPublishTime"):
        published_dt = datetime.fromtimestamp(entry["providerPublishTime"], tz=timezone.utc)

    return title, link, published_dt


def _fetch_ticker_news(ticker: str, cutoff) -> list[dict]:
    """Tek ticker için yfinance haberlerini çeker ve cutoff'tan yenilerini döndürür."""
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception as exc:
        print(f"[news_fetcher] {ticker} yfinance haberi alınamadı: {exc}")
        return []

    items = []
    for entry in raw:
        title, link, published_dt = _yf_entry_fields(entry)
        if not title or published_dt is None or published_dt < cutoff:
            continue
        items.append({
            "title": title.strip(),
            "source": "Yahoo Finance",
            "published": published_dt.strftime(DATE_FMT),
            "_dt": published_dt,
            "link": link,
            "summary": "",
            "related_ticker": ticker,
        })
    return items


def fetch_yfinance_news(tickers: list) -> list[dict]:
    """Ticker'ların yfinance haberlerini paralel çeker, son 24 saati filtreler, related_ticker ekler."""
    cutoff = _now_utc() - timedelta(hours=24)
    workers = min(MAX_WORKERS, len(tickers)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        per_ticker = pool.map(lambda t: _fetch_ticker_news(t, cutoff), tickers)

    items = [item for ticker_items in per_ticker for item in ticker_items]
    items.sort(key=lambda x: x["_dt"], reverse=True)
    return items


def _matches(text: str, terms) -> bool:
    """Terimlerden herhangi biri metinde kelime sınırıyla geçiyor mu.

    Çoğul eki opsiyonel: düz \b eşleşmesi "data centers", "GPUs", "reactors"
    gibi başlıkları kaçırıyordu (başlıklarda çoğul hali tekilden yaygın).
    """
    return any(re.search(rf"\b{re.escape(term.lower())}(?:e?s)?\b", text)
               for term in terms)


def _company_terms(ticker: str, meta: dict) -> list:
    """Bir şirketi metinde aramak için ticker + ad varyantları ('Alphabet/Google' -> ikisi de)."""
    return [ticker] + [part.strip() for part in meta.get("name", "").split("/") if part.strip()]


def _mentioned_tickers(text: str, companies: dict) -> list:
    return [t for t, meta in companies.items() if _matches(text, _company_terms(t, meta))]


def categorize_news(news_list: list, themes: dict, companies: dict = None) -> dict:
    """Haberleri temalara dağıtır: önce keyword, hiçbiri tutmazsa adı geçen
    portföy şirketinin temaları. İkisi de tutmazsa 'other'.

    Şirket eşleşmesi yalnızca fallback olarak kullanılıyor: her habere uygulanınca
    Nvidia gibi her yerde geçen isimler tüm temaları aynı haberlerle dolduruyor.
    """
    companies = companies if companies is not None else COMPANIES
    buckets = {theme: [] for theme in themes}
    buckets["other"] = []

    for news in news_list:
        text = f"{news.get('title', '')} {news.get('summary', '')}".lower()
        matched = [t for t, meta in themes.items() if _matches(text, meta["keywords"])]
        if not matched:
            for ticker in _mentioned_tickers(text, companies):
                matched += [t for t in companies[ticker].get("themes", []) if t in themes]
            matched = list(dict.fromkeys(matched))

        for theme in matched:
            buckets[theme].append(news)
        if not matched:
            buckets["other"].append(news)

    return buckets


def _rank_for_theme(news_list: list, theme: str, companies: dict, keywords: list) -> list:
    """Tema kotasına girecek haberleri seçmeden önce ilgiye göre sıralar.

    Sıra: (1) temanın konusuna VE hissesine değen haber, (2) sadece konuya değen,
    (3) yalnızca şirket adı üzerinden bu temaya düşmüş haber. Son kademe olmasa
    Tesla'nın robotaksi haberi 'enerji' temasının başına geçiyor.
    Kademe içinde yeniden eskiye.
    """
    theme_tickers = {t: meta for t, meta in companies.items()
                     if theme in meta.get("themes", [])}
    # company_news gibi hiçbir şirketin listelemediği temalarda ilgi sıralaması
    # tamamen devre dışı kalıyordu; orada tüm portföyü ilgili say.
    theme_tickers = theme_tickers or companies

    def relevance(news):
        text = f"{news.get('title', '')} {news.get('summary', '')}".lower()
        on_topic = _matches(text, keywords) if keywords else False
        related = news.get("related_ticker") in theme_tickers or any(
            _matches(text, _company_terms(t, meta)) for t, meta in theme_tickers.items()
        )
        tier = 0 if (on_topic and related) else 1 if on_topic else 2
        return (tier, -news["_dt"].timestamp())

    return sorted(news_list, key=relevance)


def _normalize_title(title: str) -> str:
    """Aynı haber farklı yayıncılarda '... - Yahoo Finance' gibi eklerle geliyor;
    dedupe anahtarı için sondaki kaynak ekini ve noktalamayı atar."""
    stripped = re.sub(r"\s+[-–|]\s+[^-–|]{2,40}$", "", title).strip().lower()
    return re.sub(r"[^\w\s]", "", stripped)


def _dedupe(news_list):
    seen = set()
    result = []
    for news in news_list:
        key = _normalize_title(news["title"])
        if key in seen:
            continue
        seen.add(key)
        result.append(news)
    return result


def fetch_all_news(config) -> dict:
    """RSS + yfinance haberlerini toplar, dedupe + kategorize eder, kategori başı max 10 tutar."""
    rss = fetch_rss_news(config.RSS_FEEDS)
    yf_news = fetch_yfinance_news(list(config.COMPANIES.keys()))
    combined = _dedupe(rss + yf_news)
    combined.sort(key=lambda x: x["_dt"], reverse=True)

    categorized = categorize_news(combined, config.THEMES, config.COMPANIES)
    return {
        theme: _rank_for_theme(
            items, theme, config.COMPANIES,
            config.THEMES.get(theme, {}).get("keywords", []),
        )[:MAX_PER_CATEGORY]
        for theme, items in categorized.items()
    }


if __name__ == "__main__":
    import config

    rss_items = fetch_rss_news(RSS_FEEDS)
    print(f"RSS haber sayısı: {len(rss_items)}")

    categorized = fetch_all_news(config)
    total = sum(len(v) for v in categorized.values())
    print(f"Kategorize toplam (max 10/kategori): {total}")
    for theme, items in categorized.items():
        title = THEMES[theme]["title"] if theme in THEMES else "Diğer"
        print(f"  {theme} ({title}): {len(items)}")
