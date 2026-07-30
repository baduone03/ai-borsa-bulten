# AI Borsa Takip Bülteni

AI ve teknoloji sektöründeki gelişmeleri takip eden, günlük otomatik yatırım bülteni üreten Python sistemi. Hisse verisi + haber toplar, tek Gemini çağrısıyla Türkçe analiz üretir, HTML rapor kaydeder ve Telegram'a gönderir.

**Maliyet: $0** — yfinance, Google News RSS, Gemini free tier ve Telegram Bot API'nin tamamı ücretsiz.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` dosyasını doldur:

| Değişken | Nereden alınır |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (ücretsiz) |
| `TELEGRAM_BOT_TOKEN` | Telegram'da [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_CHAT_ID` | Telegram'da [@userinfobot](https://t.me/userinfobot) |

## Kullanım

```bash
py -3 main.py                                  # tam bülten + Telegram bildirimi
py -3 main.py --no-analysis                    # LLM'siz (kota harcamaz)
py -3 main.py --ticker NVDA --ticker AMD       # sadece belirli hisseler
py -3 main.py --theme gpu --theme nuclear      # sadece belirli temalar
py -3 main.py --no-news                        # haber toplamayı atla
```

Çıktı: `output/bulten_YYYY-MM-DD.html`

## Mimari

| Katman | Dosya | İş |
|---|---|---|
| Veri | `stock_data.py` | yfinance ile fiyat, 1ay/1yıl performans, trend sinyali |
| Veri | `news_fetcher.py` | Google News RSS + yfinance news, keyword bazlı kategorize |
| Analiz | `llm_analyzer.py` | 8 tema + genel değerlendirme, **tek** Gemini çağrısı |
| Sunum | `report_generator.py` | Jinja2 ile koyu temalı, rozetli HTML |
| Bildirim | `telegram_notifier.py` | Zengin özet mesajı + HTML dosya eki |
| Orkestrasyon | `main.py` | CLI, akış yönetimi, hata bildirimi |

Yapılandırma (`config.py`): 16 şirket, 8 tema, 5 RSS kaynağı.

## Neden tek LLM çağrısı

Gemini free tier günlük kotası model başına ~20 istek. Tema başına ayrı çağrı (9 istek + retry'lar) kotayı tüketiyordu. Bülten tek istekte üretilip `### TEMA: x` / `### GENEL` başlıklarıyla ayrıştırılıyor.

## Notlar

- `gemini-2.0-flash` free tier'dan kaldırıldı (limit 0) — `gemini-2.5-flash` kullanılıyor
- Windows'ta `python` yerine `py -3` gerekebilir
- `.env` asla commit edilmez (`.gitignore`'da)

Bu bülten yapay zeka tarafından oluşturulur, yatırım tavsiyesi niteliği taşımaz.
