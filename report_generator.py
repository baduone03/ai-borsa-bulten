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
    """Satır sonlarını <br>, **kalın** markdown'ını <strong> yapar (LLM markdown üretiyor)."""
    escaped = str(markupsafe.escape(value))
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
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


def _enrich_stock(s):
    """Hisse dict'ini şablon için görsel alanlarla zenginleştirir (mutasyon yok)."""
    change_1m_str, cls_1m = _change_str(s.get("change_1m"))
    change_1y_str, cls_1y = _change_str(s.get("change_1y"))
    return {
        **s,
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
