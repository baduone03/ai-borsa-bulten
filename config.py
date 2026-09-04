"""Merkezi yapılandırma: şirketler, temalar, DeepSeek ayarları, RSS kaynakları."""

COMPANIES = {
    "NVDA": {"name": "Nvidia", "category": "mega-cap", "themes": ["gpu", "ai", "data_center"]},
    "TSLA": {"name": "Tesla", "category": "mega-cap", "themes": ["ai", "energy"]},
    "GOOGL": {"name": "Alphabet/Google", "category": "mega-cap", "themes": ["ai", "cloud", "data_center"]},
    "AMZN": {"name": "Amazon", "category": "mega-cap", "themes": ["cloud", "data_center", "ai"]},
    "AMD": {"name": "AMD", "category": "mega-cap", "themes": ["gpu", "ai"]},
    "MRVL": {"name": "Marvell", "category": "mega-cap", "themes": ["gpu", "data_center"]},
    "LRCX": {"name": "Lam Research", "category": "mega-cap", "themes": ["gpu"]},
    "PLTR": {"name": "Palantir", "category": "mega-cap", "themes": ["ai"]},
    "EQIX": {"name": "Equinix", "category": "mega-cap", "themes": ["data_center"]},
    "DLR": {"name": "Digital Realty", "category": "mega-cap", "themes": ["data_center"]},
    "SNDK": {"name": "SanDisk", "category": "mega-cap", "themes": ["gpu"]},
    "VRT": {"name": "Vertiv", "category": "mega-cap", "themes": ["cooling", "data_center"]},
    "CEG": {"name": "Constellation Energy", "category": "mega-cap", "themes": ["nuclear", "energy"]},
    "VST": {"name": "Vistra", "category": "mega-cap", "themes": ["energy"]},
    "SMR": {"name": "NuScale Power", "category": "speculative", "themes": ["nuclear", "energy"]},
    "TSM": {"name": "TSMC", "category": "mega-cap", "themes": ["gpu"]},
}

# Keyword'ler kelime sınırıyla (\b) eşleştirilir, substring olarak değil.
# Bu yüzden "AI", "chip", "SMR" gibi kısa terimler güvenle kullanılabilir;
# uzun tam-ifadeler ("energy consumption AI") pratikte hiçbir başlığa uymuyordu.
THEMES = {
    "ai": {
        "title": "Yapay Zeka Gelişmeleri",
        "keywords": ["AI", "artificial intelligence", "AI model", "LLM", "machine learning",
                     "chatbot", "OpenAI", "Anthropic", "AI regulation"],
    },
    "data_center": {
        "title": "Veri Merkezi İnşaatı ve Kapasitesi",
        "keywords": ["data center", "data centre", "hyperscale", "hyperscaler",
                     "colocation", "rack"],
    },
    "energy": {
        "title": "Enerji Tüketimi ve Güç Altyapısı",
        "keywords": ["power grid", "electricity", "power demand", "energy demand",
                     "megawatt", "gigawatt", "utility", "utilities", "power generation",
                     "PPA", "behind the meter", "power infrastructure"],
    },
    "gpu": {
        "title": "GPU ve Özel AI Çipleri",
        "keywords": ["GPU", "chip", "chips", "semiconductor", "ASIC", "HBM",
                     "accelerator", "foundry", "wafer"],
    },
    "cooling": {
        "title": "Soğutma Teknolojileri",
        "keywords": ["cooling", "thermal", "immersion"],
    },
    "nuclear": {
        "title": "Nükleer ve Yenilenebilir Enerji",
        "keywords": ["nuclear", "SMR", "reactor", "uranium", "renewable", "solar", "wind"],
    },
    "cloud": {
        "title": "Bulut Altyapı Yatırımları",
        "keywords": ["cloud", "AWS", "Azure", "capex"],
    },
    "company_news": {
        "title": "Şirket Haberleri ve Yatırımcı Sunumları",
        "keywords": ["earnings", "guidance", "revenue", "quarterly",
                     "SEC filing", "investor presentation"],
    },
}

SPECULATIVE_TICKERS = ["SMR"]

# LLM sağlayıcıları: sırayla denenir, biri patlarsa (kota/hata) sonrakine düşülür.
# Hepsi OpenAI uyumlu endpoint olduğu için tek istemci kodu yeter.
# Anahtarı .env'de olmayan sağlayıcı sessizce atlanır.
# Sıra: Gemini analiz derinliği daha iyi ama günlük 20 istek kotası var;
# kota dolunca Groq devralıyor (limiti çok daha yüksek).
LLM_PROVIDERS = [
    {
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        # Düşünme modeli: reasoning token'ları da bu bütçeden harcanıyor,
        # 8000'de bülten bitmeden kesiliyordu. Model tavanı 65535.
        "max_tokens": 32000,
    },
    {
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "max_tokens": 8000,
    },
]

# Bildirim: Telegram bot (0 maliyet)
TELEGRAM_BOT_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV = "TELEGRAM_CHAT_ID"

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence+stocks&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=data+center+construction&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=nvidia+AMD+GPU&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=nuclear+energy+SMR&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=cloud+infrastructure+AWS+Azure&hl=en-US&gl=US&ceid=US:en",
    # energy ve cooling temaları kaynaksız kalıyordu (günlük 0 haber), bu iki feed onları besliyor
    "https://news.google.com/rss/search?q=data+center+power+grid+electricity+demand&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=data+center+liquid+cooling&hl=en-US&gl=US&ceid=US:en",
]
