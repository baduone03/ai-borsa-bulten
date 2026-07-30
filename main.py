"""Orkestrasyon: CLI argümanlarıyla (--ticker, --theme, --no-news, --no-analysis) tüm akışı yöneten ana script."""

import argparse
import os
import sys
from types import SimpleNamespace

from dotenv import load_dotenv

load_dotenv()

# Windows konsolu cp1252 olabilir; Türkçe çıktı için UTF-8'e zorla
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import config
from stock_data import get_all_stocks
from news_fetcher import fetch_all_news
from llm_analyzer import analyze_all
from report_generator import generate_report, save_report
from telegram_notifier import send_report, send_error_alert


def parse_args():
    parser = argparse.ArgumentParser(description="AI Borsa Takip Bülteni üretir.")
    parser.add_argument("--ticker", action="append", metavar="TICKER",
                        help="Sadece bu ticker (tekrarlanabilir: --ticker NVDA --ticker AMD)")
    parser.add_argument("--theme", action="append", metavar="THEME",
                        help=f"Sadece bu tema (tekrarlanabilir). Geçerli: {', '.join(config.THEMES)}")
    parser.add_argument("--no-news", action="store_true", help="Haber toplamayı atla")
    parser.add_argument("--no-analysis", action="store_true", help="LLM analizini atla")
    return parser.parse_args()


def filter_companies(tickers):
    """--ticker filtresi; bilinmeyen ticker'da hata verip çıkar."""
    if not tickers:
        return config.COMPANIES
    tickers = [t.upper() for t in tickers]
    unknown = [t for t in tickers if t not in config.COMPANIES]
    if unknown:
        sys.exit(f"Bilinmeyen ticker: {', '.join(unknown)}. "
                 f"Geçerli: {', '.join(config.COMPANIES)}")
    return {t: config.COMPANIES[t] for t in tickers}


def filter_themes(themes):
    """--theme filtresi; bilinmeyen temada hata verip çıkar."""
    if not themes:
        return config.THEMES
    unknown = [t for t in themes if t not in config.THEMES]
    if unknown:
        sys.exit(f"Bilinmeyen tema: {', '.join(unknown)}. "
                 f"Geçerli: {', '.join(config.THEMES)}")
    return {t: config.THEMES[t] for t in themes}


def main():
    args = parse_args()

    companies = filter_companies(args.ticker)
    themes = filter_themes(args.theme)

    if not args.no_analysis and not os.environ.get(config.LLM_API_KEY_ENV):
        sys.exit(f"{config.LLM_API_KEY_ENV} bulunamadı. .env dosyasına ekle "
                 f"(https://aistudio.google.com/apikey) veya --no-analysis kullan.")

    try:
        print(f"[main] {len(companies)} hisse için veri çekiliyor...")
        stock_data = get_all_stocks(companies)

        news_by_theme = {}
        if args.no_news:
            print("[main] Haber toplama atlandı (--no-news).")
        else:
            print("[main] Haberler toplanıyor (RSS + yfinance)...")
            news_config = SimpleNamespace(
                RSS_FEEDS=config.RSS_FEEDS, COMPANIES=companies, THEMES=themes,
            )
            news_by_theme = fetch_all_news(news_config)
            total = sum(len(v) for v in news_by_theme.values())
            print(f"[main] {total} haber toplandı.")

        if args.no_analysis:
            print("[main] LLM analizi atlandı (--no-analysis).")
            theme_analyses = {}
            general = "LLM analizi bu çalıştırmada atlandı (--no-analysis)."
            analysis_failed, failure_reason = False, ""
        else:
            print(f"[main] {len(themes)} tema {config.LLM_MODEL} ile tek çağrıda analiz ediliyor...")
            result = analyze_all(news_by_theme, stock_data, themes, companies)
            theme_analyses = result["theme_analyses"]
            general = result["general"]
            analysis_failed = result["failed"]
            failure_reason = result["reason"]

        print("[main] HTML rapor üretiliyor...")
        html = generate_report(stock_data, theme_analyses, general, companies, themes)
        path = save_report(html)
        print(f"[main] Rapor hazır: {path}")
    except Exception as exc:
        print(f"[main] Çalışma başarısız: {exc}")
        send_error_alert(str(exc))
        raise

    print("[main] Telegram bildirimi gönderiliyor...")
    send_report(stock_data, theme_analyses, general, themes, path,
                analysis_failed, failure_reason)


if __name__ == "__main__":
    main()
