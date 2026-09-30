"""Analiz katmanı: tüm bülteni TEK LLM çağrısıyla üretme.

Tema başına ayrı çağrı yerine 8 tema + genel değerlendirme tek istekte
üretilir ve başlık işaretleriyle ayrıştırılır. Böylece ücretsiz kotalar
zorlanmaz ve model bülteni bir bütün olarak kurgulayabilir.

Sağlayıcılar config.LLM_PROVIDERS'tan gelir (hepsi OpenAI uyumlu endpoint).
Sırayla denenir: biri kotasını doldurursa ya da hata verirse sonrakine düşülür.
"""

import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from config import LLM_PROVIDERS
from technical_analysis import format_for_prompt

load_dotenv()

MAX_RETRIES = 3
RETRY_DELAY = 65  # free tier 429'ları dakikalık pencere — pencereyi aşacak kadar bekle
REQUEST_TIMEOUT = 180  # zamanlanmış çalışmada asılı kalmayı önler
FAILURE_TEXT = "Analiz yapılamadı"

# Günlük kota tükendiğinde retry anlamsız — kota ancak ertesi gün sıfırlanır
DAILY_QUOTA_MARKERS = ("PerDay", "per day", "per-day",
                       "generate_content_free_tier_requests", "TPD", "RPD")

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

TEKNİK ANALİZ:
Her hisse için TEKNİK satırında gerçek göstergeler veriliyor:
RSI14, MACD (çizgi/sinyal/histogram), fiyatın SMA20/50/200'e göre yüzde
konumu, Bollinger %B, hacim/20 günlük ortalama oranı, ATR (% volatilite).
Bunları bir teknik analist gibi yorumla:
- RSI 70 üstü aşırı alım, 30 altı aşırı satım; ara değerlerde nötr de.
- MACD histogramı pozitiften negatife dönüyorsa momentum zayıflıyor.
- Fiyat SMA200'ün altındaysa uzun vadeli trend aşağı; üstündeyse yukarı.
- Bollinger %B 1'in üstü/0'ın altı aşırı uzama, geri çekilme riski.
- Hacim oranı 1.5x üstündeyse hareketin arkasında haber/kurumsal işlem var.
- ATR yüksekse pozisyon boyutunu küçült uyarısı yap.
Teknik tabloyla haber akışı çelişiyorsa bunu açıkça söyle — örneğin
'haber olumlu ama RSI 78 ve fiyat üst bandın dışında, giriş için kötü nokta'.
Gösterge verilmemişse (teknik veri yok) o hisse için teknik yorum yapma,
uydurma.

KURALLAR:
- Eğer bir temada gerçekten önemli haber yoksa bunu tek cümleyle açıkça
  söyle. Bülteni doldurmak için büyük haber icat etme.
- Spekülatif şirketleri (NuScale gibi henüz kâr etmeyenler) ayrı belirt.
- Hisse verilerindeki 1 aylık ve 1 yıllık performansı karşılaştırarak
  yorum yap. Örnek: '1 yıllık trend yukarı ama son 1 ayda %8 düzeltme —
  bu kâr realizasyonu mu yoksa temel tez kırılması mı?'
- Türkçe yaz, profesyonel ama anlaşılır.

LİDER GÖRÜŞLERİ:
Girdinin sonunda LİDER bölümleri var: bazı siyasi ve sektör liderlerinin
son günlerdeki AI ile ilgili haberleri. Her lider için 2-4 madde yaz:
- NE DEDİ/YAPTI: Yalnızca verilen haber başlık ve özetlerine dayan.
  Haberde geçmeyen alıntı, tarih veya rakam uydurma; doğrudan alıntıyı
  ancak haberde tırnak içinde geçiyorsa kullan. Hangi yayına dayandığını belirt.
- AI'A BAKIŞI: Mesajın yönü (regülasyon, yatırım, güvenlik, rekabet,
  ihracat kontrolü, istihdam vb.).
- PİYASA ETKİSİ: Portföydeki hangi hisse/temaları ilgilendirebilir.
Bir lider için haber verilmemişse tek cümle yaz: 'Son günlerde AI
hakkında kayda değer bir açıklaması haberlere yansımadı.' Eski
bilgilerinden açıklama üretme.

ÇIKTI FORMATI (kesinlikle uy):
Her tema için şu başlıkla bir bölüm yaz (tema_anahtarı sana verilen
anahtarın birebir aynısı olmalı):
### TEMA: tema_anahtarı
(o temanın analizi, 3-5 madde)

En sona şu başlıkla günün genel değerlendirmesini ekle:
### GENEL
(piyasa yönü, riskler ve fırsatlar; spekülatif ve oturmuş şirketleri
ayrı tut; maksimum 200 kelimelik tek paragraf)

GENEL'den sonra, girdide LİDER bölümü verilen her lider için şu başlıkla
bir bölüm yaz (lider_anahtarı verilenin birebir aynısı olmalı):
### LIDER: lider_anahtarı
(o liderin görüşleri, yukarıdaki LİDER GÖRÜŞLERİ kurallarıyla)

Bu başlıklar dışında başlık, giriş veya kapanış metni ekleme."""


class TruncatedResponseError(RuntimeError):
    """Yanıt token sınırında kesildi — bülten eksik olurdu."""


def available_providers() -> list[dict]:
    """Anahtarı .env'de tanımlı olan sağlayıcıları config sırasıyla döndürür."""
    return [p for p in LLM_PROVIDERS if os.environ.get(p["key_env"])]


def _is_daily_quota_error(exc) -> bool:
    """Günlük kota tükenmesi mi (retry fayda etmez) yoksa geçici hata mı ayırt eder."""
    text = str(exc)
    return "429" in text and any(marker in text for marker in DAILY_QUOTA_MARKERS)


def _chat_one_provider(provider, system_prompt, user_content):
    """Tek sağlayıcıda 3 kez retry; hepsi başarısızsa son exception'ı fırlatır."""
    client = OpenAI(api_key=os.environ[provider["key_env"]],
                    base_url=provider["base_url"])
    model = provider["model"]
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=provider["max_tokens"],
                temperature=0.3,
                timeout=REQUEST_TIMEOUT,
            )
            choice = response.choices[0]
            # Token bütçesi dolduysa bülten yarım kalır — kabul etmek yerine
            # sağlayıcıyı başarısız say ki zincir sonrakine düşsün
            if choice.finish_reason == "length":
                raise TruncatedResponseError(
                    f"{model} yanıtı {provider['max_tokens']} token sınırında kesildi"
                )
            return choice.message.content.strip()
        except TruncatedResponseError as exc:
            # Aynı bütçeyle tekrar denemek aynı yerde keser — doğrudan sonraki sağlayıcıya
            print(f"[llm] {exc}")
            raise
        except Exception as exc:
            last_exc = exc
            print(f"[llm] {model} deneme {attempt}/{MAX_RETRIES} başarısız: {exc}")
            if _is_daily_quota_error(exc):
                print(f"[llm] {model} günlük kotası tükenmiş — retry atlanıyor.")
                break
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise last_exc


def _chat(system_prompt, user_content):
    """Sağlayıcıları sırayla dener, ilk başarılı yanıtı (metin, model) döndürür."""
    providers = available_providers()
    if not providers:
        envs = ", ".join(p["key_env"] for p in LLM_PROVIDERS)
        raise RuntimeError(f"Hiçbir LLM anahtarı set edilmemiş (biri gerekli: {envs})")

    last_exc = None
    for provider in providers:
        try:
            text = _chat_one_provider(provider, system_prompt, user_content)
            return text, provider["model"]
        except Exception as exc:
            last_exc = exc
            print(f"[llm] {provider['model']} sağlayıcısı başarısız, sonrakine geçiliyor.")
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
            f"1yıl {s.get('change_1y')}%, trend: {s.get('trend_note')}\n"
            f"  TEKNİK: {format_for_prompt(s.get('technical'))}"
        )
    return "\n".join(lines) if lines else "(İlgili hisse verisi yok.)"


def _stocks_for_theme(theme_key, stock_data, companies_config):
    """O temayla ilişkili tickerların hisse verilerini filtreler."""
    tickers = {
        ticker for ticker, meta in companies_config.items()
        if theme_key in meta.get("themes", [])
    }
    return [s for s in stock_data if s.get("ticker") in tickers]


def _format_leader_news(news_list):
    lines = []
    for news in news_list:
        summary = news.get("summary", "")
        lines.append(f"- [{news.get('published', '')}] {news.get('title', '')} "
                     f"({news.get('source', '')})\n  {summary}".rstrip())
    return "\n".join(lines) if lines else "(Bu dönemde AI ile ilgili haber yok.)"


def _build_user_content(news_by_theme, stock_data, themes_config, companies_config,
                        leader_news=None, leaders_config=None):
    """Tüm hisse verilerini + tema tema haberleri + lider haberlerini tek prompt'ta toplar."""
    parts = [f"TÜM HİSSE VERİLERİ:\n{_format_stocks(stock_data)}"]
    for theme_key, meta in themes_config.items():
        related = _stocks_for_theme(theme_key, stock_data, companies_config)
        tickers = ", ".join(s.get("ticker", "") for s in related) or "-"
        parts.append(
            f"TEMA: {theme_key} ({meta['title']})\n"
            f"İlgili tickerlar: {tickers}\n"
            f"HABERLER:\n{_format_news(news_by_theme.get(theme_key, []))}"
        )
    for key, meta in (leaders_config or {}).items():
        parts.append(
            f"LİDER: {key} ({meta['name']}, {meta['role']})\n"
            f"HABERLER:\n{_format_leader_news((leader_news or {}).get(key, []))}"
        )
    return "\n\n".join(parts)


def _parse_bulletin(text, theme_keys, leader_keys=()):
    """### TEMA: x / ### LIDER: x / ### GENEL başlıklarına göre metni bölümlere ayırır."""
    matches = list(re.finditer(
        r"^#{1,4}\s*\**(?:(TEMA|L[İI]DER):\s*\**([\w-]+)\**|GENEL)\**\s*$",
        text, re.MULTILINE,
    ))
    theme_analyses = {}
    leader_analyses = {}
    general = ""
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        kind, key = match.group(1), match.group(2)
        if kind is None:
            general = body
        elif kind == "TEMA" and key in theme_keys:
            theme_analyses[key] = body
        elif kind != "TEMA" and key in leader_keys:
            leader_analyses[key] = body
    return theme_analyses, general, leader_analyses


def analyze_all(news_by_theme: dict, stock_data: list,
                themes_config: dict, companies_config: dict,
                leader_news: dict = None, leaders_config: dict = None) -> dict:
    """Tüm temaları + genel değerlendirmeyi + lider görüşlerini tek LLM çağrısıyla üretir."""
    leaders_config = leaders_config or {}
    user_content = _build_user_content(
        news_by_theme, stock_data, themes_config, companies_config,
        leader_news, leaders_config,
    )
    try:
        text, model = _chat(SYSTEM_PROMPT, user_content)
        print(f"[llm] analiz {model} ile üretildi.")
    except Exception as exc:
        print(f"[llm] bülten analizi başarısız: {exc}")
        tried = ", ".join(p["model"] for p in available_providers()) or "-"
        reason = (f"Tüm sağlayıcıların ({tried}) günlük ücretsiz kotası tükendi."
                  if _is_daily_quota_error(exc) else f"LLM hatası: {exc}")
        return {
            "theme_analyses": {key: FAILURE_TEXT for key in themes_config},
            "general": FAILURE_TEXT,
            "leader_analyses": {key: FAILURE_TEXT for key in leaders_config},
            "failed": True,
            "reason": reason,
        }

    theme_analyses, general, leader_analyses = _parse_bulletin(
        text, set(themes_config), set(leaders_config)
    )
    for key in themes_config:
        if key not in theme_analyses:
            print(f"[llm] uyarı: model '{key}' temasını atladı")
            theme_analyses[key] = FAILURE_TEXT
    if not general:
        print("[llm] uyarı: genel değerlendirme bölümü bulunamadı")
        general = FAILURE_TEXT
    for key in leaders_config:
        if key not in leader_analyses:
            print(f"[llm] uyarı: model '{key}' lider bölümünü atladı")
            leader_analyses[key] = FAILURE_TEXT
    return {"theme_analyses": theme_analyses, "general": general,
            "leader_analyses": leader_analyses, "failed": False, "reason": ""}


if __name__ == "__main__":
    sample = """### TEMA: gpu
1. ÖZET: Test.

### GENEL
Piyasa test modunda.

### LIDER: altman
- NE DEDİ: Test.

### LİDER: **trump**
- AI'A BAKIŞI: Test."""
    themes, general, leaders = _parse_bulletin(sample, {"gpu", "ai"}, {"altman", "trump"})
    assert themes == {"gpu": "1. ÖZET: Test."}, themes
    assert general == "Piyasa test modunda.", general
    assert leaders == {"altman": "- NE DEDİ: Test.", "trump": "- AI'A BAKIŞI: Test."}, leaders
    print("parse testi PASS")

    active = available_providers()
    print("aktif sağlayıcılar:", ", ".join(p["model"] for p in active) or "(yok)")
