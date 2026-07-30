"""Bildirim katmanı: bülteni Telegram'a zengin formatlı özet + tam HTML eki olarak gönderir."""

import os

import requests

from config import TELEGRAM_BOT_TOKEN_ENV, TELEGRAM_CHAT_ID_ENV

API_BASE = "https://api.telegram.org/bot{token}/{method}"
MAX_MESSAGE_LEN = 4096
THEME_SNIPPET_LEN = 220
MOVERS_COUNT = 3


def _escape_html(text) -> str:
    """Telegram HTML parse_mode için özel karakterleri kaçırır."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _num(value):
    return isinstance(value, (int, float))


def _format_movers(stock_data: list) -> str:
    """1 aylık değişime göre en çok yükselen/düşen hisseleri tek satırda özetler."""
    valid = [s for s in stock_data if _num(s.get("change_1m"))]
    if not valid:
        return "(hisse verisi yok)"
    ranked = sorted(valid, key=lambda s: s["change_1m"], reverse=True)
    gainers = ranked[:MOVERS_COUNT]
    losers = [s for s in ranked[-MOVERS_COUNT:] if s["change_1m"] < 0][::-1]

    lines = []
    for s in gainers:
        if s["change_1m"] <= 0:
            break
        lines.append(f"🟢 {_escape_html(s['ticker'])} {s['change_1m']:+.2f}% (1A)")
    for s in losers:
        lines.append(f"🔴 {_escape_html(s['ticker'])} {s['change_1m']:+.2f}% (1A)")
    return "\n".join(lines) if lines else "(belirgin hareket yok)"


def _snippet(text: str, limit: int = THEME_SNIPPET_LEN) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return _escape_html(text)
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{_escape_html(cut)}…"


def build_summary_message(stock_data, theme_analyses, general,
                          themes_config, report_date: str) -> str:
    """Zengin, HTML formatlı Telegram özet mesajı üretir (tema başlıkları + kısa özet)."""
    parts = [f"📊 <b>AI Borsa Takip Bülteni</b> — {_escape_html(report_date)}"]

    movers = _format_movers(stock_data)
    parts.append(f"\n<b>📈 Öne Çıkan Hareketler (1 Ay)</b>\n{movers}")

    if general:
        parts.append(f"\n<b>🧠 Genel Değerlendirme</b>\n{_snippet(general, 600)}")

    theme_lines = ["\n<b>🗂 Tema Özetleri</b>"]
    for key, meta in themes_config.items():
        analysis = theme_analyses.get(key)
        if not analysis:
            continue
        theme_lines.append(f"\n<b>{_escape_html(meta['title'])}</b>\n{_snippet(analysis)}")
    parts.append("\n".join(theme_lines))

    parts.append("\n📎 Tam rapor ekteki HTML dosyasında.")
    parts.append("⚠️ Yatırım tavsiyesi niteliği taşımaz.")

    message = "\n".join(parts)
    if len(message) > MAX_MESSAGE_LEN:
        message = message[:MAX_MESSAGE_LEN - 1].rsplit("\n", 1)[0] + "\n…"
    return message


def _credentials():
    token = os.environ.get(TELEGRAM_BOT_TOKEN_ENV)
    chat_id = os.environ.get(TELEGRAM_CHAT_ID_ENV)
    return token, chat_id


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    url = API_BASE.format(token=token, method="sendMessage")
    resp = requests.post(url, data={
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=30)
    resp.raise_for_status()


def send_telegram_document(token: str, chat_id: str, file_path: str, caption: str = "") -> None:
    url = API_BASE.format(token=token, method="sendDocument")
    with open(file_path, "rb") as f:
        resp = requests.post(url, data={"chat_id": chat_id, "caption": caption},
                             files={"document": f}, timeout=60)
    resp.raise_for_status()


def send_error_alert(error_text: str) -> None:
    """Pipeline çöktüğünde en azından kısa bir hata bildirimi göndermeyi dener (best-effort)."""
    token, chat_id = _credentials()
    if not token or not chat_id:
        return
    try:
        send_telegram_message(token, chat_id, f"🚨 <b>AI Borsa Bülteni çalışması BAŞARISIZ</b>\n{_escape_html(error_text)}")
    except Exception as exc:
        print(f"[telegram] Hata bildirimi de gönderilemedi: {exc}")


def send_report(stock_data, theme_analyses, general, themes_config, report_path: str) -> bool:
    """Bülten özetini + HTML ekini Telegram'a gönderir. Hata durumunda False döner, exception fırlatmaz."""
    token, chat_id = _credentials()
    if not token or not chat_id:
        print(f"[telegram] {TELEGRAM_BOT_TOKEN_ENV}/{TELEGRAM_CHAT_ID_ENV} eksik, bildirim atlandı.")
        return False

    from datetime import datetime
    report_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    try:
        message = build_summary_message(stock_data, theme_analyses, general,
                                        themes_config, report_date)
        send_telegram_message(token, chat_id, message)
        send_telegram_document(token, chat_id, report_path,
                               caption="AI Borsa Takip Bülteni — tam rapor")
        print("[telegram] Bildirim gönderildi.")
        return True
    except Exception as exc:
        print(f"[telegram] Bildirim gönderilemedi: {exc}")
        return False


if __name__ == "__main__":
    fake_stocks = [
        {"ticker": "NVDA", "change_1m": 5.23}, {"ticker": "SMR", "change_1m": -12.4},
        {"ticker": "AMD", "change_1m": 2.1},
    ]
    fake_themes_cfg = {"gpu": {"title": "GPU ve Özel AI Çipleri"}}
    fake_analyses = {"gpu": "ÖZET: Nvidia Blackwell sevkiyatı rekor kırdı. " * 5}
    msg = build_summary_message(fake_stocks, fake_analyses,
                                "Piyasa AI tarafında güçlü, spekülatif isimlerde temkinli ol.",
                                fake_themes_cfg, "31.07.2026 14:32")
    assert "<b>AI Borsa" in msg and len(msg) <= MAX_MESSAGE_LEN
    print("mesaj testi PASS")
    print(msg)
