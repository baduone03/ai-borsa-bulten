"""Haber katmanı: Google News RSS + yfinance news toplama, keyword bazlı kategorize etme. AI yok."""

import calendar
import re
from datetime import datetime, timedelta, timezone

import feedparser
import yfinance as yf

from config import RSS_FEEDS, THEMES, COMPANIES

DATE_FMT = "%Y-%m-%d %H:%M"
MAX_PER_CATEGORY = 10


def _now_utc():
    return datetime.now(timezone.utc)


def _struct_to_dt(struct):
    """feedparser struct_time (UTC) -> timezone-aware datetime."""
    return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)


def fetch_rss_news(feed_urls: list, hours: int = 24) -> list[dict]:
    """RSS feed'lerini çeker, son {hours} saati filtreler, dedupe eder, yeniden eskiye sıralar."""
    cutoff = _now_utc() - timedelta(hours=hours)
    seen_titles = set()
    items = []

    for url in feed_urls:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", "RSS")
        for entry in feed.entries:
            struct = entry.get("published_parsed")
            if not struct:
                continue
            published = _struct_to_dt(struct)
            if published < cutoff:
                continue

            title = entry.get("title", "").strip()
            key = title.lower()
            if not title or key in seen_titles:
                continue
            seen_titles.add(key)

            summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))[:300]
            items.append({
                "title": title,
                "source": source,
                "published": published.strftime(DATE_FMT),
                "_dt": published,
                "link": entry.get("link", ""),
                "summary": summary.strip(),
            })

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


def fetch_yfinance_news(tickers: list) -> list[dict]:
    """Her ticker için yfinance haberlerini çeker, son 24 saati filtreler, related_ticker ekler."""
    cutoff = _now_utc() - timedelta(hours=24)
    items = []

    for ticker in tickers:
        try:
            raw = yf.Ticker(ticker).news or []
        except Exception as exc:
            print(f"[news_fetcher] {ticker} yfinance haberi alınamadı: {exc}")
            continue

        for entry in raw:
            title, link, published_dt = _yf_entry_fields(entry)
            if not title or published_dt is None:
                continue
            if published_dt < cutoff:
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

    items.sort(key=lambda x: x["_dt"], reverse=True)
    return items


def categorize_news(news_list: list, themes: dict) -> dict:
    """Haberleri title+summary keyword'lerine göre temalara dağıtır; uymayanlar 'other'."""
    buckets = {theme: [] for theme in themes}
    buckets["other"] = []

    for news in news_list:
        text = f"{news.get('title', '')} {news.get('summary', '')}".lower()
        matched = False
        for theme, meta in themes.items():
            if any(kw.lower() in text for kw in meta["keywords"]):
                buckets[theme].append(news)
                matched = True
        if not matched:
            buckets["other"].append(news)

    return buckets


def _dedupe(news_list):
    seen = set()
    result = []
    for news in news_list:
        key = news["title"].lower()
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

    categorized = categorize_news(combined, config.THEMES)
    return {theme: items[:MAX_PER_CATEGORY] for theme, items in categorized.items()}


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
