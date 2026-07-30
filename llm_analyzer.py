"""Analiz katmanı: tüm bülteni TEK Gemini çağrısıyla üretme.

Gemini free tier günlük kotası model başına ~20 istek. Tema başına ayrı çağrı
(9 istek/gün + retry'lar) kotayı aşıyordu; bu yüzden 8 tema + genel
değerlendirme tek istekte üretilir ve başlık işaretleriyle ayrıştırılır.
"""

import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY_ENV

load_dotenv()

MAX_RETRIES = 3
RETRY_DELAY = 65  # free tier 429'ları dakikalık pencere — pencereyi aşacak kadar bekle
MAX_OUTPUT_TOKENS = 8000
FAILURE_TEXT = "Analiz yapılamadı"

SYSTEM_PROMPT = """Sen deneyimli bir finansal analistsin. AI ve teknoloji sektöründe
uzmanlaşmış bir yatırım danışmanı olarak görev yapıyorsun.
Görevin: verilen haberleri ve hisse verilerini analiz edip Türkçe
yatırım bülteni üretmek.

Her temadaki her gelişme için şu üç kısmı yaz:
1. ÖZET: Ne oldu? Tarih, rakam, detay.
2. NEDEN ÖNEMLİ: Sektörel/stratejik bağlam, 1-2 cümle.
3. YATIRIM GÖRÜŞÜ: Somut pozisyon önerisi. Şu dillerden birini kullan:
   - 'Uzun vadede yükseliş beklentisi var, dipten alım fırsatı'
   - 'Momentum güçlü, pozisyonu koru veya artır'
   - 'Düzeltme riski var, kâr realizasyonu düşün'
   - 'Belirsizlik yüksek, bekle-gör stratejisi uygula'

KURALLAR:
- Eğer bir temada gerçekten önemli haber yoksa bunu tek cümleyle açıkça
  söyle. Bülteni doldurmak için büyük haber icat etme.
- Spekülatif şirketleri (NuScale gibi henüz kâr etmeyenler) ayrı belirt.
- Hisse verilerindeki 1 aylık ve 1 yıllık performansı karşılaştırarak
  yorum yap. Örnek: '1 yıllık trend yukarı ama son 1 ayda %8 düzeltme —
  bu kâr realizasyonu mu yoksa temel tez kırılması mı?'
- Türkçe yaz, profesyonel ama anlaşılır.

ÇIKTI FORMATI (kesinlikle uy):
Her tema için şu başlıkla bir bölüm yaz (tema_anahtarı sana verilen
anahtarın birebir aynısı olmalı):
### TEMA: tema_anahtarı
(o temanın analizi, 3-5 madde)

En sona şu başlıkla günün genel değerlendirmesini ekle:
### GENEL
(piyasa yönü, riskler ve fırsatlar; spekülatif ve oturmuş şirketleri
ayrı tut; maksimum 200 kelimelik tek paragraf)

Bu başlıklar dışında başlık, giriş veya kapanış metni ekleme."""


def _get_client():
    """LLM_API_KEY_ENV'deki anahtarla OpenAI uyumlu istemci kurar."""
    api_key = os.environ.get(LLM_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"{LLM_API_KEY_ENV} environment variable set edilmemiş")
    return OpenAI(api_key=api_key, base_url=LLM_BASE_URL)


def _chat(system_prompt, user_content, max_tokens):
    """LLM chat çağrısı; 3 kez retry, başarısızlıkta exception fırlatır."""
    client = _get_client()
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_exc = exc
            print(f"[llm] deneme {attempt}/{MAX_RETRIES} başarısız: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise last_exc


def _format_news(news_list):
    lines = []
    for news in news_list:
        summary = news.get("summary", "")
        source = news.get("source", "")
        lines.append(f"- {news.get('title', '')} ({source})\n  {summary}".rstrip())
    return "\n".join(lines) if lines else "(Bu temada yeni haber yok.)"


def _format_stocks(stocks):
    lines = []
    for s in stocks:
        lines.append(
            f"- {s.get('name', s.get('ticker'))} ({s.get('ticker')}): "
            f"fiyat {s.get('price')}, 1ay {s.get('change_1m')}%, "
            f"1yıl {s.get('change_1y')}%, trend: {s.get('trend_note')}"
        )
    return "\n".join(lines) if lines else "(İlgili hisse verisi yok.)"


def _stocks_for_theme(theme_key, stock_data, companies_config):
    """O temayla ilişkili tickerların hisse verilerini filtreler."""
    tickers = {
        ticker for ticker, meta in companies_config.items()
        if theme_key in meta.get("themes", [])
    }
    return [s for s in stock_data if s.get("ticker") in tickers]


def _build_user_content(news_by_theme, stock_data, themes_config, companies_config):
    """Tüm hisse verilerini + tema tema haberleri tek prompt'ta toplar."""
    parts = [f"TÜM HİSSE VERİLERİ:\n{_format_stocks(stock_data)}"]
    for theme_key, meta in themes_config.items():
        related = _stocks_for_theme(theme_key, stock_data, companies_config)
        tickers = ", ".join(s.get("ticker", "") for s in related) or "-"
        parts.append(
            f"TEMA: {theme_key} ({meta['title']})\n"
            f"İlgili tickerlar: {tickers}\n"
            f"HABERLER:\n{_format_news(news_by_theme.get(theme_key, []))}"
        )
    return "\n\n".join(parts)


def _parse_bulletin(text, theme_keys):
    """### TEMA: x / ### GENEL başlıklarına göre metni bölümlere ayırır."""
    matches = list(re.finditer(
        r"^#{1,4}\s*(?:TEMA:\s*\**([\w-]+)\**|GENEL)\**\s*$", text, re.MULTILINE
    ))
    theme_analyses = {}
    general = ""
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        key = match.group(1)
        if key is None:
            general = body
        elif key in theme_keys:
            theme_analyses[key] = body
    return theme_analyses, general


def analyze_all(news_by_theme: dict, stock_data: list,
                themes_config: dict, companies_config: dict) -> dict:
    """Tüm temaları + genel değerlendirmeyi tek LLM çağrısıyla üretir."""
    user_content = _build_user_content(
        news_by_theme, stock_data, themes_config, companies_config
    )
    try:
        text = _chat(SYSTEM_PROMPT, user_content, max_tokens=MAX_OUTPUT_TOKENS)
    except Exception as exc:
        print(f"[llm] bülten analizi başarısız: {exc}")
        return {
            "theme_analyses": {key: FAILURE_TEXT for key in themes_config},
            "general": FAILURE_TEXT,
        }

    theme_analyses, general = _parse_bulletin(text, set(themes_config))
    for key in themes_config:
        if key not in theme_analyses:
            print(f"[llm] uyarı: model '{key}' temasını atladı")
            theme_analyses[key] = FAILURE_TEXT
    if not general:
        print("[llm] uyarı: genel değerlendirme bölümü bulunamadı")
        general = FAILURE_TEXT
    return {"theme_analyses": theme_analyses, "general": general}


if __name__ == "__main__":
    sample = """### TEMA: gpu
1. ÖZET: Test.

### GENEL
Piyasa test modunda."""
    themes, general = _parse_bulletin(sample, {"gpu", "ai"})
    assert themes == {"gpu": "1. ÖZET: Test."}, themes
    assert general == "Piyasa test modunda.", general
    print("parse testi PASS")

    if not os.environ.get(LLM_API_KEY_ENV):
        print(f"{LLM_API_KEY_ENV} set edilmemiş — canlı test atlanıyor.")
        raise SystemExit(0)
