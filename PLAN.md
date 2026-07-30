# AI Borsa Takip Bülteni — Proje Planı

## Amaç
AI ve teknoloji sektöründeki gelişmeleri takip eden, günlük otomatik yatırım bülteni üreten bir Python sistemi.

## Mimari
Sistem 4 katmandan oluşuyor:

1. **Veri Katmanı** (ücretsiz, API maliyeti yok)
   - `stock_data.py` → yfinance ile hisse fiyatları, 1ay/1yıl performans, trend analizi
   - `news_fetcher.py` → Google News RSS + yfinance news ile haber toplama, keyword bazlı kategorize etme

2. **Analiz Katmanı** (Google Gemini free tier — $0/gün)
   - `llm_analyzer.py` → Tüm bülten (8 tema + genel değerlendirme) TEK Gemini çağrısıyla üretilir, çıktı `### TEMA: x` / `### GENEL` başlıklarıyla ayrıştırılır
   - Neden tek çağrı: free tier günlük kota model başına sadece 20 istek; tema başına ayrı çağrı (9 istek + retry) kotayı aşıyor
   - OpenAI uyumlu SDK (openai paketi, base_url değiştirilerek)
   - Model: gemini-2.5-flash (gemini-2.0-flash free tier'dan kaldırıldı, limit 0)
   - API key: GEMINI_API_KEY env variable (ücretsiz: https://aistudio.google.com/apikey)

3. **Sunum Katmanı**
   - `report_generator.py` → Jinja2 ile koyu temalı, renk kodlu, rozetli HTML rapor

4. **Orkestrasyon**
   - `main.py` → CLI argümanlarıyla (--ticker, --theme, --no-news, --no-analysis) tüm akışı yöneten ana script

## Takip Edilen Şirketler (16 adet)
| Ticker | Şirket | Kategori |
|--------|--------|----------|
| NVDA | Nvidia | mega-cap |
| TSLA | Tesla | mega-cap |
| GOOGL | Alphabet/Google | mega-cap |
| AMZN | Amazon | mega-cap |
| AMD | AMD | mega-cap |
| MRVL | Marvell | mega-cap |
| LRCX | Lam Research | mega-cap |
| PLTR | Palantir | mega-cap |
| EQIX | Equinix | mega-cap |
| DLR | Digital Realty | mega-cap |
| SNDK | SanDisk | mega-cap |
| VRT | Vertiv | mega-cap |
| CEG | Constellation Energy | mega-cap |
| VST | Vistra | mega-cap |
| SMR | NuScale Power | speculative |
| TSM | TSMC | mega-cap |

## Takip Edilen Temalar (8 adet)
1. Yapay zeka (model lansmanları, regülasyon)
2. Veri merkezi inşaatı ve kapasitesi
3. Enerji tüketimi ve güç altyapısı
4. GPU ve özel AI çipleri (Nvidia, AMD, ASIC, HBM)
5. Soğutma teknolojileri
6. Nükleer ve yenilenebilir enerji
7. Bulut şirketleri altyapı yatırımları (AWS, Azure, GCP)
8. Şirket haberleri ve yatırımcı sunumları

## Bülten Formatı
Her tema altında 3-5 madde, her madde üç kısım:
1. **Gelişmenin özeti** — ne oldu, tarih, rakamlar
2. **Neden önemli** — sektörel/stratejik bağlam
3. **Yatırım görüşü** — somut pozisyon önerisi, net dil

## Rozet Sistemi
- Şirket kategorisi: "Mega-Cap" (mavi) / "Spekülatif ⚠️" (turuncu)
- Trend durumu: "Yükseliş 📈" (yeşil) / "Düzeltme ⚡" (sarı) / "Düşüş 📉" (kırmızı) / "Toparlanma 🔄" (mavi)

## Önemli Kurallar
- Spekülatif şirketleri (SMR gibi) ayrı rozetle işaretle
- Gerçekten önemli haber yoksa bunu açıkça söyle, haber icat etme
- 1 aylık ve 1 yıllık performansı karşılaştırarak yorum yap
- Raporun sonunda "Genel Değerlendirme" paragrafı olsun
- Footer'da "Yatırım tavsiyesi niteliği taşımaz" uyarısı

## Teknoloji Stack
- Python 3.10+
- yfinance (hisse verisi)
- feedparser (RSS parse)
- openai SDK (Gemini OpenAI-uyumlu endpoint erişimi)
- jinja2 (HTML template)

## Dosya Yapısı
```
ai-borsa-bulten/
├── PLAN.md
├── config.py
├── stock_data.py
├── news_fetcher.py
├── llm_analyzer.py
├── report_generator.py
├── main.py
├── requirements.txt
└── output/
```
