"""Sunum katmanı: Jinja2 ile koyu temalı, renk kodlu, rozetli HTML rapor üretme."""

import os
import re
from datetime import datetime

import markupsafe
from jinja2 import Environment, select_autoescape

NA = "N/A"

TREND_BADGES = {
    "bullish": {"label": "Yükseliş 📈", "cls": "badge-bullish"},
    "correction": {"label": "Düzeltme ⚡", "cls": "badge-correction"},
    "bearish": {"label": "Düşüş 📉", "cls": "badge-bearish"},
    "recovery": {"label": "Toparlanma 🔄", "cls": "badge-recovery"},
}

CATEGORY_BADGES = {
    "mega-cap": {"label": "Mega-Cap", "cls": "badge-mega"},
    "speculative": {"label": "Spekülatif ⚠️", "cls": "badge-spec"},
}

TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Borsa Takip Bülteni — {{ date }}</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px; background: #0f1117; color: #e6e8ef;
  font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }
.wrap { max-width: 900px; margin: 0 auto; }
h1 { font-size: 28px; margin: 0 0 4px; }
.subtitle { color: #8b90a3; font-size: 14px; margin-bottom: 24px; }
.section { margin-bottom: 28px; }
.section h2 { font-size: 20px; border-left: 4px solid #3742fa; padding-left: 10px;
  margin-bottom: 12px; }
.analysis { background: #1a1d29; border-radius: 12px; padding: 16px 18px;
  white-space: normal; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
.card { background: #1a1d29; border-radius: 12px; padding: 16px; }
.card-head { display: flex; justify-content: space-between; align-items: flex-start;
  gap: 8px; margin-bottom: 8px; }
.name { font-weight: 600; font-size: 16px; }
.ticker { color: #8b90a3; font-size: 13px; }
.price { font-size: 26px; font-weight: 700; margin: 6px 0; }
.perf { display: flex; gap: 18px; font-size: 14px; margin-bottom: 10px; }
.perf .lbl { color: #8b90a3; font-size: 12px; display: block; }
.pos { color: #00d26a; font-weight: 600; }
.neg { color: #ff4757; font-weight: 600; }
.muted { color: #8b90a3; }
.range { margin: 10px 0 6px; }
.range-bar { position: relative; height: 6px; background: #2a2e3e; border-radius: 3px; }
.range-mark { position: absolute; top: -3px; width: 12px; height: 12px;
  background: #e6e8ef; border-radius: 50%; transform: translateX(-50%); }
.range-labels { display: flex; justify-content: space-between; font-size: 11px;
  color: #8b90a3; margin-top: 4px; }
.trend-note { font-style: italic; font-size: 12px; color: #aeb2c4; margin-top: 8px; }
.spark { margin: 10px 0 4px; }
.spark svg { display: block; width: 100%; height: 40px; }
.tech { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.tech-item { background: #23273a; border-radius: 6px; padding: 3px 8px; font-size: 11px;
  color: #aeb2c4; }
.tech-item b { color: #e6e8ef; font-weight: 600; }
.tech-hot { background: #3a2430; color: #ff8fa0; }
.tech-cold { background: #1e3040; color: #7fc4ff; }
.tech-signals { font-size: 11px; color: #ffc078; margin-top: 6px; }
.badges { display: flex; flex-direction: column; gap: 4px; align-items: flex-end; }
.badge { display: inline-block; padding: 3px 9px; border-radius: 999px;
  font-size: 11px; font-weight: 600; white-space: nowrap; }
.badge-mega { background: #3742fa; color: #fff; }
.badge-spec { background: #ff9f43; color: #1a1d29; }
.badge-bullish { background: #00d26a; color: #06281a; }
.badge-correction { background: #ffa502; color: #2a1d00; }
.badge-bearish { background: #ff4757; color: #fff; }
.badge-recovery { background: #1e90ff; color: #fff; }
.general { background: #1e2235; border-radius: 12px; padding: 20px;
  margin: 32px 0 24px; border: 1px solid #2a2e3e; }
.general h2 { margin-top: 0; }
footer { color: #6b7080; font-size: 12px; text-align: center; margin-top: 32px;
  border-top: 1px solid #2a2e3e; padding-top: 16px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>AI Borsa Takip Bülteni</h1>
  <div class="subtitle">{{ datetime_str }}</div>

  {% for theme in themes %}
  <div class="section">
    <h2>{{ theme.title }}</h2>
    <div class="analysis">{{ theme.analysis | nl2br }}</div>
  </div>
  {% endfor %}

  <div class="section">
    <h2>Şirketler</h2>
    <div class="grid">
      {% for s in stocks %}
      <div class="card">
        <div class="card-head">
          <div>
            <div class="name">{{ s.name }}</div>
            <div class="ticker">{{ s.ticker }}</div>
          </div>
          <div class="badges">
            {% if s.category_badge %}
            <span class="badge {{ s.category_badge.cls }}">{{ s.category_badge.label }}</span>
            {% endif %}
            {% if s.trend_badge %}
            <span class="badge {{ s.trend_badge.cls }}">{{ s.trend_badge.label }}</span>
            {% endif %}
          </div>
        </div>
        <div class="price">{{ s.price_str }}</div>
        <div class="perf">
          <div><span class="lbl">1 Ay</span><span class="{{ s.cls_1m }}">{{ s.change_1m_str }}</span></div>
          <div><span class="lbl">1 Yıl</span><span class="{{ s.cls_1y }}">{{ s.change_1y_str }}</span></div>
        </div>
        {% if s.range_pct is not none %}
        <div class="range">
          <div class="range-bar"><div class="range-mark" style="left: {{ s.range_pct }}%;"></div></div>
          <div class="range-labels"><span>{{ s.low_52w }}</span><span>{{ s.high_52w }}</span></div>
        </div>
        {% endif %}
        {% if s.spark_path %}
        <div class="spark">
          <svg viewBox="0 0 100 40" preserveAspectRatio="none">
            <polyline points="{{ s.spark_path }}" fill="none"
                      stroke="{{ s.spark_color }}" stroke-width="1.5"
                      vector-effect="non-scaling-stroke"/>
          </svg>
        </div>
        {% endif %}
        {% if s.tech_items %}
        <div class="tech">
          {% for t in s.tech_items %}
          <span class="tech-item {{ t.cls }}"><b>{{ t.label }}</b> {{ t.value }}</span>
          {% endfor %}
        </div>
        {% endif %}
        {% if s.tech_signals %}
        <div class="tech-signals">{{ s.tech_signals | join(' · ') }}</div>
        {% endif %}
        <div class="trend-note">{{ s.trend_note }}</div>
      </div>
      {% endfor %}
    </div>
  </div>

  <div class="general">
    <h2>Genel Değerlendirme</h2>
    <div>{{ general | nl2br }}</div>
  </div>

  <footer>
    Bu bülten yapay zeka tarafından oluşturulmuştur. Yatırım tavsiyesi niteliği taşımaz.<br>
    Oluşturulma: {{ datetime_str }}
  </footer>
</div>
</body>
</html>"""


def _nl2br(value):
    """Satır sonlarını <br>, **kalın**'ı <strong>, madde işaretlerini • yapar.

    LLM markdown üretiyor; '*   ' ve '- ' satır başları düz metinde ham
    yıldız/tire olarak görünüyordu.
    """
    escaped = str(markupsafe.escape(value))
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"^[ \t]*[*+-][ \t]+", "• ", escaped, flags=re.MULTILINE)
    return markupsafe.Markup(escaped.replace("\n", "<br>"))


def _num(value):
    return isinstance(value, (int, float))


def _change_str(value):
    if not _num(value):
        return NA, "muted"
    cls = "pos" if value >= 0 else "neg"
    return f"{value:+.2f}%", cls


def _range_pct(price, low, high):
    if not (_num(price) and _num(low) and _num(high)) or high == low:
        return None
    pct = (price - low) / (high - low) * 100
    return round(max(0, min(100, pct)), 1)


SPARK_UP, SPARK_DOWN = "#00d26a", "#ff4757"


def _spark(points):
    """Kapanış listesini 100x40 viewBox'a normalize edilmiş polyline'a çevirir."""
    if not points or len(points) < 2:
        return "", SPARK_UP
    low, high = min(points), max(points)
    span = high - low
    coords = []
    for i, value in enumerate(points):
        x = i / (len(points) - 1) * 100
        # span 0 ise (tamamen yatay) çizgiyi ortaya koy
        y = 20.0 if span == 0 else 38 - (value - low) / span * 36
        coords.append(f"{x:.1f},{y:.1f}")
    color = SPARK_UP if points[-1] >= points[0] else SPARK_DOWN
    return " ".join(coords), color


def _tech_items(ta):
    """Teknik göstergeleri rapordaki rozetlere çevirir; aşırı değerleri renklendirir."""
    if not ta:
        return []
    items = []
    rsi = ta.get("rsi")
    if rsi is not None:
        cls = "tech-hot" if rsi >= 70 else "tech-cold" if rsi <= 30 else ""
        items.append({"label": "RSI", "value": rsi, "cls": cls})
    if ta.get("macd"):
        hist = ta["macd"]["histogram"]
        items.append({"label": "MACD", "value": f"{hist:+.2f}",
                      "cls": "" if hist >= 0 else "tech-hot"})
    for period in (50, 200):
        val = ta.get(f"price_vs_sma{period}")
        if val is not None:
            items.append({"label": f"SMA{period}", "value": f"{val:+.1f}%",
                          "cls": "" if val >= 0 else "tech-hot"})
    ratio = ta.get("volume_ratio")
    if ratio is not None and ratio >= 1.5:
        items.append({"label": "Hacim", "value": f"{ratio:.1f}x", "cls": "tech-cold"})
    atr = ta.get("atr_pct")
    if atr is not None:
        items.append({"label": "ATR", "value": f"{atr}%", "cls": ""})
    return items


def _enrich_stock(s):
    """Hisse dict'ini şablon için görsel alanlarla zenginleştirir (mutasyon yok)."""
    change_1m_str, cls_1m = _change_str(s.get("change_1m"))
    change_1y_str, cls_1y = _change_str(s.get("change_1y"))
    ta = s.get("technical") or {}
    spark_path, spark_color = _spark(s.get("spark"))
    return {
        **s,
        "spark_path": spark_path,
        "spark_color": spark_color,
        "tech_items": _tech_items(ta),
        "tech_signals": ta.get("signals", []),
        "price_str": f"${s['price']:.2f}" if _num(s.get("price")) else NA,
        "change_1m_str": change_1m_str,
        "change_1y_str": change_1y_str,
        "cls_1m": cls_1m,
        "cls_1y": cls_1y,
        "range_pct": _range_pct(s.get("price"), s.get("low_52w"), s.get("high_52w")),
        "category_badge": CATEGORY_BADGES.get(s.get("category")),
        "trend_badge": TREND_BADGES.get(s.get("trend_signal")),
        "trend_note": s.get("trend_note") if s.get("trend_note") != NA else "",
    }


def generate_report(stock_data, theme_analyses, general_assessment,
                    companies_config, themes_config) -> str:
    """Hisse, tema analizleri ve genel değerlendirmeden HTML rapor üretir."""
    env = Environment(autoescape=select_autoescape(["html"]))
    env.filters["nl2br"] = _nl2br
    template = env.from_string(TEMPLATE)

    themes = [
        {"title": meta["title"], "analysis": theme_analyses[key]}
        for key, meta in themes_config.items()
        if key in theme_analyses and theme_analyses[key]
    ]
    stocks = [_enrich_stock(s) for s in stock_data]
    now = datetime.now()

    return template.render(
        date=now.strftime("%Y-%m-%d"),
        datetime_str=now.strftime("%d.%m.%Y %H:%M"),
        themes=themes,
        stocks=stocks,
        general=general_assessment,
    )


def save_report(html: str, output_dir: str = "output") -> str:
    """HTML'i output dizinine bulten_YYYY-MM-DD.html olarak kaydeder, yolu döndürür."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"bulten_{datetime.now().strftime('%Y-%m-%d')}.html"
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


if __name__ == "__main__":
    fake_stocks = [
        {"ticker": "NVDA", "name": "Nvidia", "category": "mega-cap", "price": 194.97,
         "change_1m": -8.89, "change_1y": 23.57, "low_52w": 151.49, "high_52w": 236.54,
         "trend_note": "Yıllık trend yukarı ama son 1 ayda sert düzeltme",
         "trend_signal": "correction"},
        {"ticker": "SMR", "name": "NuScale Power", "category": "speculative", "price": 10.26,
         "change_1m": -15.87, "change_1y": -74.08, "low_52w": 8.85, "high_52w": 57.42,
         "trend_note": "Düşüş trendi devam ediyor", "trend_signal": "bearish"},
    ]
    fake_themes = {
        "gpu": "ÖZET: Nvidia Blackwell sevkiyatı rekor.\nNEDEN ÖNEMLİ: Veri merkezi talebi güçlü.\nYATIRIM GÖRÜŞÜ: Momentum güçlü, pozisyonu koru.",
    }
    from config import COMPANIES, THEMES

    html = generate_report(fake_stocks, fake_themes,
                           "Piyasa AI tarafında güçlü, spekülatif isimlerde temkinli ol.",
                           COMPANIES, THEMES)
    path = save_report(html)
    print(f"Rapor kaydedildi: {path}")
