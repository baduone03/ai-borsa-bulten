"""Liderlerin AI Görüşleri: ana bültenden BAĞIMSIZ ikinci çıktı.

Ana bülten tek LLM çağrısıyla üretiliyor; lider bölümlerini aynı çağrıya
eklemek yanıtı uzatıp token sınırına itiyordu (kesilen yanıt sağlayıcıyı
başarısız sayar → ana bülten de etkilenir). Bu yüzden liderler kendi
çağrısında, kendi HTML dosyasında ve kendi Telegram mesajında üretilir.
Buradaki her hata yutulur: bu modül ana bülteni asla düşürmez.
"""

import os
import re
from datetime import datetime

from jinja2 import Environment, select_autoescape

from llm_analyzer import FAILURE_TEXT, _chat
from report_generator import _nl2br
from telegram_notifier import (MAX_MESSAGE_LEN, _credentials, _escape_html, _redact,
                               _snippet, send_telegram_document, send_telegram_message)

# Ana bülten zinciri en kötü ~22 dk sürebiliyor; bu ek çağrı 30 dk'lık job
# sınırını aşmasın diye sağlayıcı başına tek deneme (65 sn beklemeli retry yok).
LEADER_RETRIES = 1

SYSTEM_PROMPT = """Sen AI sektörünü takip eden deneyimli bir finansal analistsin.
Görevin: aşağıda verilen liderlerin son günlerdeki AI ile ilgili haber
başlıklarını Türkçe özetlemek ve yatırımcı gözüyle yorumlamak.

Her lider için 2-3 kısa madde yaz:
- NE DEDİ/YAPTI: Yalnızca verilen haber başlıklarına dayan. Haberde
  geçmeyen alıntı, tarih veya rakam uydurma; doğrudan alıntıyı ancak
  başlıkta tırnak içinde geçiyorsa kullan.
- AI'A BAKIŞI: Mesajın yönü (regülasyon, yatırım, güvenlik, rekabet,
  ihracat kontrolü, istihdam vb.).
- PİYASA ETKİSİ: Verilen portföydeki hangi hisseleri ilgilendirebilir.

Bir lider için haber verilmemişse yalnızca şu cümleyi yaz:
'Son günlerde AI hakkında kayda değer bir açıklaması haberlere yansımadı.'
Eski bilgilerinden açıklama üretme.

ÇIKTI FORMATI (kesinlikle uy): her lider için
### LIDER: lider_anahtarı
(maddeler)
lider_anahtarı sana verilenin birebir aynısı olmalı. Bu başlıklar dışında
başlık, giriş veya kapanış metni ekleme."""


def _build_user_content(leader_news, leaders_config, companies_config):
    portfolio = ", ".join(f"{meta['name']} ({t})" for t, meta in companies_config.items())
    parts = [f"PORTFÖY: {portfolio}"]
    for key, meta in leaders_config.items():
        # Google News RSS'te summary başlığın tekrarı; yalnızca başlık gönder
        lines = [f"- [{n.get('published', '')}] {n.get('title', '')}"
                 for n in leader_news.get(key, [])]
        parts.append(f"LİDER: {key} ({meta['name']}, {meta['role']})\n"
                     f"HABERLER:\n" + ("\n".join(lines) or "(Bu dönemde haber yok.)"))
    return "\n\n".join(parts)


def parse_leaders(text, leader_keys):
    """### LIDER: x başlıklarına göre metni bölümlere ayırır."""
    matches = list(re.finditer(
        r"^#{1,4}\s*\**L[İI]DER:\s*\**([\w-]+)\**\s*$", text, re.MULTILINE
    ))
    result = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if match.group(1) in leader_keys:
            result[match.group(1)] = text[match.end():end].strip()
    return result


def analyze_leaders(leader_news, leaders_config, companies_config):
    """Lider görüşlerini ayrı LLM çağrısıyla üretir. Başarısızsa None döner."""
    user_content = _build_user_content(leader_news, leaders_config, companies_config)
    try:
        text, model = _chat(SYSTEM_PROMPT, user_content, retries=LEADER_RETRIES)
        print(f"[liderler] analiz {model} ile üretildi.")
    except Exception as exc:
        print(f"[liderler] analiz başarısız, lider bülteni atlanıyor: {exc}")
        return None
    analyses = parse_leaders(text, set(leaders_config))
    for key in leaders_config:
        if key not in analyses:
            print(f"[liderler] uyarı: model '{key}' bölümünü atladı")
            analyses[key] = FAILURE_TEXT
    return analyses


TEMPLATE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Liderlerin AI Görüşleri — {{ date }}</title>
<style>
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px; background: #0f1117; color: #e6e8ef;
  font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }
.wrap { max-width: 900px; margin: 0 auto; }
h1 { font-size: 28px; margin: 0 0 4px; }
.subtitle { color: #8b90a3; font-size: 14px; margin-bottom: 24px; }
.leader { background: #1a1d29; border-radius: 12px; padding: 16px 18px;
  margin-bottom: 14px; }
.leader-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px;
  border-left: 4px solid #3742fa; padding-left: 10px; }
.leader-name { font-weight: 600; font-size: 17px; }
.leader-role { color: #8b90a3; font-size: 13px; }
.sources { margin: 12px 0 0; padding: 10px 0 0; border-top: 1px solid #2a2e3e;
  font-size: 12px; list-style: none; }
.sources li { margin-bottom: 4px; color: #8b90a3; }
.sources a { color: #7fa8ff; text-decoration: none; }
.sources a:hover { text-decoration: underline; }
footer { color: #6b7080; font-size: 12px; text-align: center; margin-top: 32px;
  border-top: 1px solid #2a2e3e; padding-top: 16px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Liderlerin AI Görüşleri</h1>
  <div class="subtitle">{{ datetime_str }} · son {{ days }} günün haberleri</div>
  {% for l in leaders %}
  <div class="leader">
    <div class="leader-head">
      <span class="leader-name">{{ l.name }}</span>
      <span class="leader-role">{{ l.role }}</span>
    </div>
    <div>{{ l.analysis | nl2br }}</div>
    {% if l.sources %}
    <ul class="sources">
      {% for n in l.sources %}
      <li>{{ n.published }} · {% if n.link %}<a href="{{ n.link }}" target="_blank" rel="noopener">{{ n.title }}</a>{% else %}{{ n.title }}{% endif %}</li>
      {% endfor %}
    </ul>
    {% endif %}
  </div>
  {% endfor %}
  <footer>
    Bu rapor yapay zeka tarafından haber başlıklarından özetlenmiştir; kaynak
    linklerinden doğrulayın. Yatırım tavsiyesi niteliği taşımaz.<br>
    Oluşturulma: {{ datetime_str }}
  </footer>
</div>
</body>
</html>"""


def _safe_link(url):
    """Yalnızca http(s) linklerine izin ver; RSS'ten gelen 'javascript:' vb. elenir."""
    return url if isinstance(url, str) and url.startswith(("http://", "https://")) else ""


def generate_html(analyses, leaders_config, leader_news, hours):
    env = Environment(autoescape=select_autoescape(["html"]))
    env.filters["nl2br"] = _nl2br
    leaders = [
        {"name": meta["name"], "role": meta["role"], "analysis": analyses[key],
         "sources": [{"title": n.get("title", ""), "published": n.get("published", ""),
                      "link": _safe_link(n.get("link"))}
                     for n in leader_news.get(key, [])]}
        for key, meta in leaders_config.items() if analyses.get(key)
    ]
    now = datetime.now()
    return env.from_string(TEMPLATE).render(
        date=now.strftime("%Y-%m-%d"), datetime_str=now.strftime("%d.%m.%Y %H:%M"),
        days=max(1, hours // 24), leaders=leaders,
    )


def save_html(html, output_dir="output"):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"liderler_{datetime.now().strftime('%Y-%m-%d')}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def build_message(analyses, leaders_config, report_date):
    lines = [f"🎙 <b>Liderlerin AI Görüşleri</b> — {_escape_html(report_date)}"]
    for key, meta in leaders_config.items():
        analysis = analyses.get(key)
        if not analysis:
            continue
        lines.append(f"\n<b>{_escape_html(meta['name'])}</b> "
                     f"<i>({_escape_html(meta['role'])})</i>\n{_snippet(analysis)}")
    lines.append("\n📎 Kaynak linkleri ekteki HTML dosyasında.")
    message = "\n".join(lines)
    if len(message) > MAX_MESSAGE_LEN:
        message = message[:MAX_MESSAGE_LEN - 1].rsplit("\n", 1)[0] + "\n…"
    return message


def run(leader_news, leaders_config, companies_config, hours):
    """Lider bültenini üretir ve Telegram'a gönderir. Hiçbir koşulda exception fırlatmaz."""
    try:
        analyses = analyze_leaders(leader_news, leaders_config, companies_config)
        if analyses is None:
            return
        path = save_html(generate_html(analyses, leaders_config, leader_news, hours))
        print(f"[liderler] Rapor hazır: {path}")

        token, chat_id = _credentials()
        if not token or not chat_id:
            print("[liderler] Telegram yapılandırılmamış, bildirim atlandı.")
            return
        try:
            report_date = datetime.now().strftime("%d.%m.%Y %H:%M")
            send_telegram_message(token, chat_id,
                                  build_message(analyses, leaders_config, report_date))
            send_telegram_document(token, chat_id, path,
                                   caption="Liderlerin AI Görüşleri — kaynaklar")
            print("[liderler] Bildirim gönderildi.")
        except Exception as exc:
            print(f"[liderler] Bildirim gönderilemedi: {_redact(exc, token)}")
    except Exception as exc:
        print(f"[liderler] beklenmeyen hata, lider bülteni atlandı: {exc}")


if __name__ == "__main__":
    sample = """### LIDER: altman
- NE DEDİ: Test.

### LİDER: **trump**
- AI'A BAKIŞI: Test."""
    parsed = parse_leaders(sample, {"altman", "trump"})
    assert parsed == {"altman": "- NE DEDİ: Test.", "trump": "- AI'A BAKIŞI: Test."}, parsed
    print("parse testi PASS")
