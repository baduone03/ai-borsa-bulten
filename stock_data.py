"""Hisse verisi katmanı: yfinance ile fiyat, 1ay/1yıl performans ve trend analizi."""

import json
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

import technical_analysis
from config import COMPANIES

NA = "N/A"
MAX_WORKERS = 8
# Rapordaki mini grafik icin: 6 aylik kapanislar bu kadar noktaya seyreltilir
SPARK_POINTS = 60
SPARK_WINDOW = 126  # ~6 ay islem gunu


def _pct_change(current, past):
    """Yüzde değişim; geçersiz girdide N/A döner."""
    if current is None or past is None or past == 0:
        return NA
    return round((current - past) / past * 100, 2)


def _spark_points(closes) -> list:
    """Rapordaki mini grafik icin son ~6 ayin kapanislarini seyrelterek dondurur."""
    recent = closes.tail(SPARK_WINDOW)
    if len(recent) < 2:
        return []
    step = max(1, len(recent) // SPARK_POINTS)
    return [round(float(v), 2) for v in recent.iloc[::step]]


def _trend(change_1m, change_1y):
    """1ay/1yıl değişimden trend notu ve sinyali üretir."""
    if change_1m == NA or change_1y == NA:
        return NA, NA

    if change_1y > 0:
        if change_1m > 0:
            return "Momentum devam ediyor", "bullish"
        if change_1m < -5:
            return "Yıllık trend yukarı ama son 1 ayda sert düzeltme", "correction"
        return "Hafif düzeltme, trend sağlam", "correction"

    # change_1y <= 0
    if change_1m > 0:
        return "Dip bölgesinden toparlanma sinyali", "recovery"
    return "Düşüş trendi devam ediyor", "bearish"


def get_stock_summary(ticker: str) -> dict:
    """Tek hisse için fiyat, performans ve trend özeti döndürür (hata halinde N/A alanlar)."""
    summary = {
        "ticker": ticker,
        "price": NA,
        "change_1m": NA,
        "change_1y": NA,
        "high_52w": NA,
        "low_52w": NA,
        "volume": NA,
        "trend_note": NA,
        "trend_signal": NA,
        "technical": {},
        "spark": [],
    }

    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
    except Exception as exc:
        print(f"[stock_data] {ticker} veri çekilemedi: {exc}")
        return summary

    if hist.empty:
        print(f"[stock_data] {ticker} için fiyat geçmişi boş")
        return summary

    closes = hist["Close"]
    current = info.get("regularMarketPrice") or info.get("currentPrice")
    if current is None:
        current = round(float(closes.iloc[-1]), 2)
    summary["price"] = round(float(current), 2)

    # 1 ay ~ 21 işlem günü
    close_1m = float(closes.iloc[-22]) if len(closes) >= 22 else None
    close_1y = float(closes.iloc[0]) if len(closes) >= 2 else None
    summary["change_1m"] = _pct_change(current, close_1m)
    summary["change_1y"] = _pct_change(current, close_1y)

    summary["high_52w"] = round(float(info.get("fiftyTwoWeekHigh", closes.max())), 2)
    summary["low_52w"] = round(float(info.get("fiftyTwoWeekLow", closes.min())), 2)
    volume = info.get("regularMarketVolume") or info.get("volume")
    if volume is None and "Volume" in hist:
        volume = int(hist["Volume"].iloc[-1])
    summary["volume"] = int(volume) if volume is not None else NA

    summary["trend_note"], summary["trend_signal"] = _trend(
        summary["change_1m"], summary["change_1y"]
    )
    summary["technical"] = technical_analysis.analyze(hist, summary["price"])
    summary["spark"] = _spark_points(closes)
    return summary


def get_all_stocks(companies: dict) -> list[dict]:
    """Tüm hisseleri paralel çeker; ad ve kategori ekler, hataları loglar. Sıra korunur."""
    tickers = list(companies)
    workers = min(MAX_WORKERS, len(tickers)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        summaries = list(pool.map(get_stock_summary, tickers))

    results = []
    for ticker, summary in zip(tickers, summaries):
        meta = companies[ticker]
        summary["name"] = meta.get("name", ticker)
        summary["category"] = meta.get("category", NA)
        if summary["price"] == NA:
            print(f"[stock_data] {ticker} eksik veriyle eklendi")
        results.append(summary)
    return results


if __name__ == "__main__":
    for tk in ["NVDA", "SMR"]:
        print(json.dumps(get_stock_summary(tk), ensure_ascii=False, indent=2))
