# AI Borsa Takip Bülteni

AI ve teknoloji sektöründeki gelişmeleri takip eden, günlük otomatik yatırım bülteni üreten Python sistemi. Hisse verisi + haber toplar, tek LLM çağrısıyla Türkçe analiz üretir, HTML rapor kaydeder ve Telegram'a gönderir.

**Maliyet: $0** — yfinance, Google News RSS, Groq free tier, Telegram Bot API ve GitHub Actions'ın tamamı ücretsiz.

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` dosyasını doldur:

| Değişken | Nereden alınır |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com/keys (ücretsiz) |
| `TELEGRAM_BOT_TOKEN` | Telegram'da [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_CHAT_ID` | Telegram'da [@userinfobot](https://t.me/userinfobot) |

> Bot sana mesaj gönderebilmesi için önce Telegram'dan bota **Start** demen gerekir. Aksi halde `chat not found` hatası alınır.

## Otomatik günlük çalıştırma

`.github/workflows/daily-bulletin.yml` her gün 06:00 UTC'de (09:00 TR) GitHub'ın sunucusunda çalışır — bilgisayarın kapalı olsa bile. Kurulum:

1. Repo → **Settings → Secrets and variables → Actions → New repository secret**
2. Üç secret ekle: `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. **Actions** sekmesinden `Gunluk Bulten` → `Run workflow` ile elle de tetiklenebilir

Üretilen HTML, çalışma artifact'i olarak 30 gün saklanır.

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
| Analiz | `llm_analyzer.py` | 8 tema + genel değerlendirme, **tek** LLM çağrısı |
| Sunum | `report_generator.py` | Jinja2 ile koyu temalı, rozetli HTML |
| Bildirim | `telegram_notifier.py` | Zengin özet mesajı + HTML dosya eki |
| Orkestrasyon | `main.py` | CLI, akış yönetimi, hata bildirimi |

Yapılandırma (`config.py`): 16 şirket, 8 tema, 5 RSS kaynağı.

## Neden tek LLM çağrısı

Tema başına ayrı çağrı ücretsiz kotaları hızla tüketiyordu (Gemini'de günlük 20 istek sınırına takıldık). Bülten tek istekte üretilip `### TEMA: x` / `### GENEL` başlıklarıyla ayrıştırılıyor. Ek fayda: model bülteni bir bütün olarak kurguluyor.

## Sağlayıcı değiştirme

`config.py`'deki üç satır yeterli — kodun geri kalanı OpenAI uyumlu SDK kullandığı için değişmez:

```python
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_BASE_URL = "https://api.groq.com/openai/v1"
LLM_API_KEY_ENV = "GROQ_API_KEY"
```

Gemini'ye dönmek için: `gemini-2.5-flash` / `https://generativelanguage.googleapis.com/v1beta/openai/` / `GEMINI_API_KEY`.

## Notlar

- LLM analizi başarısız olursa bülten yine gönderilir; hisse verileri geçerli olduğu için korunur, analiz bölümleri yerine açık bir uyarı konur
- Veri toplama paralelleştirildi: 29s → 8s
- Windows'ta `python` yerine `py -3` gerekebilir
- `.env` asla commit edilmez (`.gitignore`'da)

Bu bülten yapay zeka tarafından oluşturulur, yatırım tavsiyesi niteliği taşımaz.
