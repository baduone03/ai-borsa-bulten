"""Teknik analiz katmanı: OHLCV geçmişinden gösterge hesaplama.

yfinance'ten zaten çekilen 1 yıllık geçmiş şimdiye kadar sadece kapanış
için kullanılıyordu. Burada aynı veriden RSI, MACD, hareketli ortalamalar,
Bollinger ve hacim göstergeleri üretilip LLM'e sayı olarak veriliyor —
grafik görüntüsü yerine, çünkü görüntü elimizdeki verinin kayıplı hali.

Dış bağımlılık yok: pandas zaten yfinance ile geliyor.
"""

import pandas as pd

NA = "N/A"

RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
BB_PERIOD, BB_STD = 20, 2
SMA_PERIODS = (20, 50, 200)
VOLUME_AVG_PERIOD = 20
ATR_PERIOD = 14

RSI_OVERBOUGHT, RSI_OVERSOLD = 70, 30
# Hacim bu katsayının üstündeyse "haber/olay kaynaklı hareket" sinyali sayılır
VOLUME_SPIKE_RATIO = 1.5


def _rsi(closes: pd.Series, period: int = RSI_PERIOD):
    """Wilder RSI. Yeterli veri yoksa None."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder yumuşatması = alpha 1/period'lu EMA
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    last_gain, last_loss = float(avg_gain.iloc[-1]), float(avg_loss.iloc[-1])
    if last_loss == 0:
        # Hic hareket yoksa RSI tanimsiz; 100 dondurmek yatay seyreden
        # (ornegin islem gormeyen) hisseye "asiri alim" sinyali takiyordu
        return None if last_gain == 0 else 100.0
    rs = last_gain / last_loss
    return round(100 - (100 / (1 + rs)), 1)


def _macd(closes: pd.Series):
    """MACD çizgisi, sinyal ve histogram. Yeterli veri yoksa None."""
    if len(closes) < MACD_SLOW + MACD_SIGNAL:
        return None
    ema_fast = closes.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = closes.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    return {
        "macd": round(float(macd_line.iloc[-1]), 2),
        "signal": round(float(signal.iloc[-1]), 2),
        "histogram": round(float(macd_line.iloc[-1] - signal.iloc[-1]), 2),
    }


def _bollinger_pct_b(closes: pd.Series):
    """Fiyatın Bollinger bandı içindeki konumu (%B). 0 alt bant, 1 üst bant."""
    if len(closes) < BB_PERIOD:
        return None
    window = closes.rolling(BB_PERIOD)
    mid = float(window.mean().iloc[-1])
    std = float(window.std().iloc[-1])
    if std == 0:
        return None
    upper, lower = mid + BB_STD * std, mid - BB_STD * std
    return round((float(closes.iloc[-1]) - lower) / (upper - lower), 2)


def _atr_pct(hist: pd.DataFrame, price: float):
    """ATR'nin fiyata oranı (% volatilite). Yeterli veri yoksa None."""
    if len(hist) < ATR_PERIOD + 1 or not price:
        return None
    high, low, prev_close = hist["High"], hist["Low"], hist["Close"].shift(1)
    true_range = pd.concat([high - low, (high - prev_close).abs(),
                            (low - prev_close).abs()], axis=1).max(axis=1)
    atr = float(true_range.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean().iloc[-1])
    return round(atr / price * 100, 2)


def _moving_averages(closes: pd.Series, price: float):
    """Her SMA için değer ve fiyatın ona göre yüzde konumu."""
    out = {}
    for period in SMA_PERIODS:
        if len(closes) < period:
            continue
        sma = float(closes.rolling(period).mean().iloc[-1])
        out[f"sma{period}"] = round(sma, 2)
        if price and sma:
            out[f"price_vs_sma{period}"] = round((price - sma) / sma * 100, 2)
    return out


def _ma_cross(closes: pd.Series):
    """SMA50/SMA200 kesişimi: son 5 günde altın/ölüm kesişimi oldu mu."""
    if len(closes) < 205:
        return None
    sma50 = closes.rolling(50).mean()
    sma200 = closes.rolling(200).mean()
    above = sma50 > sma200
    recent = above.iloc[-5:]
    if recent.iloc[-1] and not above.iloc[-6]:
        return "golden_cross"
    if not recent.iloc[-1] and above.iloc[-6]:
        return "death_cross"
    return "above" if recent.iloc[-1] else "below"


def _volume_ratio(hist: pd.DataFrame):
    """Son işlem hacminin 20 günlük ortalamaya oranı."""
    if "Volume" not in hist or len(hist) < VOLUME_AVG_PERIOD:
        return None
    avg = float(hist["Volume"].rolling(VOLUME_AVG_PERIOD).mean().iloc[-1])
    if not avg:
        return None
    return round(float(hist["Volume"].iloc[-1]) / avg, 2)


def _signals(rsi, macd, pct_b, cross, volume_ratio) -> list:
    """Göstergelerden okunabilir sinyal etiketleri üretir."""
    out = []
    if rsi is not None:
        if rsi >= RSI_OVERBOUGHT:
            out.append(f"RSI {rsi} — aşırı alım bölgesi")
        elif rsi <= RSI_OVERSOLD:
            out.append(f"RSI {rsi} — aşırı satım bölgesi")
    if macd:
        yon = "pozitif" if macd["histogram"] > 0 else "negatif"
        out.append(f"MACD histogramı {yon} ({macd['histogram']:+.2f})")
    if pct_b is not None:
        if pct_b > 1:
            out.append("Fiyat Bollinger üst bandının üstünde")
        elif pct_b < 0:
            out.append("Fiyat Bollinger alt bandının altında")
    if cross == "golden_cross":
        out.append("Altın kesişim: SMA50 SMA200'ü yukarı kesti")
    elif cross == "death_cross":
        out.append("Ölüm kesişimi: SMA50 SMA200'ü aşağı kesti")
    if volume_ratio and volume_ratio >= VOLUME_SPIKE_RATIO:
        out.append(f"Hacim 20 günlük ortalamanın {volume_ratio:.1f} katı")
    return out


def analyze(hist: pd.DataFrame, price) -> dict:
    """OHLCV geçmişinden teknik gösterge seti üretir.

    Veri yetersizse ilgili alanlar None kalır; çağıran tarafın N/A ile
    başa çıkması gerekir.
    """
    if hist is None or hist.empty or "Close" not in hist:
        return {}

    closes = hist["Close"].dropna()
    if closes.empty:
        return {}
    price = float(price) if isinstance(price, (int, float)) else float(closes.iloc[-1])

    rsi = _rsi(closes)
    macd = _macd(closes)
    pct_b = _bollinger_pct_b(closes)
    cross = _ma_cross(closes)
    volume_ratio = _volume_ratio(hist)

    result = {
        "rsi": rsi,
        "macd": macd,
        "bollinger_pct_b": pct_b,
        "ma_cross": cross,
        "volume_ratio": volume_ratio,
        "atr_pct": _atr_pct(hist, price),
        "signals": _signals(rsi, macd, pct_b, cross, volume_ratio),
    }
    result.update(_moving_averages(closes, price))
    return result


def format_for_prompt(ta: dict) -> str:
    """Göstergeleri LLM promptu için tek satırlık kompakt metne çevirir."""
    if not ta:
        return "teknik veri yok"
    parts = []
    if ta.get("rsi") is not None:
        parts.append(f"RSI14 {ta['rsi']}")
    if ta.get("macd"):
        parts.append(f"MACD {ta['macd']['macd']:+.2f}/sinyal {ta['macd']['signal']:+.2f}"
                     f"/hist {ta['macd']['histogram']:+.2f}")
    for period in SMA_PERIODS:
        key = f"price_vs_sma{period}"
        if ta.get(key) is not None:
            parts.append(f"SMA{period}'e göre {ta[key]:+.1f}%")
    if ta.get("bollinger_pct_b") is not None:
        parts.append(f"Bollinger %B {ta['bollinger_pct_b']}")
    if ta.get("ma_cross") in ("golden_cross", "death_cross"):
        parts.append("ALTIN KESİŞİM" if ta["ma_cross"] == "golden_cross" else "ÖLÜM KESİŞİMİ")
    if ta.get("volume_ratio") is not None:
        parts.append(f"hacim/20g ort {ta['volume_ratio']}x")
    if ta.get("atr_pct") is not None:
        parts.append(f"ATR {ta['atr_pct']}%")
    return ", ".join(parts) if parts else "teknik veri yok"


if __name__ == "__main__":
    import yfinance as yf

    for ticker in ["NVDA", "SMR"]:
        hist = yf.Ticker(ticker).history(period="1y")
        ta = analyze(hist, None)
        print(f"\n=== {ticker}")
        print(format_for_prompt(ta))
        for signal in ta.get("signals", []):
            print("  •", signal)
