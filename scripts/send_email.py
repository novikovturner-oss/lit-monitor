"""
Email-дайджест через SendGrid.

Переменные окружения (добавить в GitHub Secrets):
  SENDGRID_API_KEY  — ключ SendGrid (sg-...)
  EMAIL_TO          — адрес получателя (ваш email)
  EMAIL_FROM        — адрес отправителя (подтверждённый в SendGrid)

Отправляет HTML-письмо только со статьями relevance >= 7.
К письму прикрепляется PDF-отчёт.
"""

import os, json, base64, urllib.request, datetime

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_TO   = os.environ.get("EMAIL_TO",   "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@litmonitor.example.com")
MIN_RELEVANCE = 7


def build_html_body(articles: list, run_date: str, stats: dict) -> str:
    high_arts = [a for a in articles if a.get("relevance", 0) >= MIN_RELEVANCE]

    source_colors = {
        "PubMed": "#1d3557", "КиберЛенинка": "#c1121f",
    }

    def badge(source):
        color = source_colors.get(source, "#6a0572")
        return (f'<span style="background:{color};color:#fff;padding:1px 7px;'
                f'border-radius:8px;font-size:11px">{source}</span>')

    def vstat(label, val, color="#1d3557"):
        return (f'<div style="background:#f4f6f8;border-left:4px solid {color};'
                f'padding:8px 14px;border-radius:3px;min-width:100px;display:inline-block;margin:4px">'
                f'<strong style="font-size:20px;color:{color};display:block">{val}</strong>'
                f'<span style="font-size:11px;color:#666">{label}</span></div>')

    stats_html = (
        vstat("всего найдено",      stats.get("total", len(articles))) +
        vstat("высокорелевантных",  stats.get("high", len(high_arts)), "#1a7a6e") +
        vstat("на русском",         stats.get("ru", 0), "#5a0060")
    )

    rows = ""
    for art in high_arts:
        rel = art.get("relevance", 0)
        bc  = "#2a9d8f" if rel >= 7 else "#e9c46a"
        tc  = "#fff"    if rel >= 7 else "#333"
        authors_str = ", ".join(art.get("authors", [])[:3])
        doi_link = (f' <a href="https://doi.org/{art["doi"]}" style="color:#457b9d">[DOI]</a>'
                    if art.get("doi") else "")
        src_link = (f' <a href="{art["url"]}" style="color:#457b9d">'
                    f'{"[PubMed]" if art.get("pmid") else "[ссылка]"}</a>'
                    if art.get("url") else "")
        rows += f"""
<tr>
  <td style="padding:14px 10px;border-bottom:1px solid #eee;vertical-align:top;width:42px">
    <span style="background:{bc};color:{tc};border-radius:50%;padding:5px 9px;
                 font-weight:700;font-size:14px">{rel}</span>
  </td>
  <td style="padding:14px 10px;border-bottom:1px solid #eee;vertical-align:top">
    <div style="font-weight:600;margin-bottom:5px">{art['title']}</div>
    <div style="color:#555;font-size:12px;margin-bottom:6px">
      {badge(art['source'])} {authors_str}
      {"&bull; " if authors_str else ""}<em>{art['journal']}</em> {art['year']}
      {doi_link}{src_link}
    </div>
    <div style="line-height:1.55;margin-bottom:5px">{art.get('summary_ru','')}</div>
    <div style="color:#1a5c8a;font-size:13px;font-style:italic">
      → {art.get('why_relevant','')}
    </div>
  </td>
</tr>"""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Georgia,serif;max-width:720px;margin:0 auto;padding:20px;color:#222;line-height:1.6">
  <div style="background:#1d3557;color:#fff;padding:24px 28px;border-radius:6px;margin-bottom:24px">
    <h1 style="margin:0 0 6px;font-size:22px">📚 Мониторинг публикаций</h1>
    <p style="margin:0;color:#a8dadc;font-size:13px">
      Нейроортопедия · ДЦП · Спастичность · {run_date}
    </p>
  </div>
  <div style="margin-bottom:20px">{stats_html}</div>
  <p style="color:#666;font-size:13px">
    Ниже — статьи с баллом <strong>7 и выше</strong>. Полный отчёт прикреплён в PDF.
  </p>
  <table style="width:100%;border-collapse:collapse">
    <tbody>{rows}</tbody>
  </table>
  <hr style="border:none;border-top:1px solid #ddd;margin:24px 0">
  <p style="color:#999;font-size:11px;text-align:center">
    Автоматический дайджест · Новиков В.А. · НМИЦ детской травматологии им. Г.И. Турнера
  </p>
</body></html>"""


def send_digest(articles: list, run_date: str, stats: dict,
                pdf_path: str = None) -> bool:
    """
    Отправляет email-дайджест через SendGrid API.
    Возвращает True при успехе.
    """
    if not SENDGRID_API_KEY:
        print("  [Email] SENDGRID_API_KEY не задан — письмо не отправлено")
        return False
    if not EMAIL_TO:
        print("  [Email] EMAIL_TO не задан — письмо не отправлено")
        return False

    high_count = sum(1 for a in articles if a.get("relevance", 0) >= MIN_RELEVANCE)
    if high_count == 0:
        print("  [Email] Нет статей с релевантностью ≥7 — письмо не отправлено")
        return False

    html_body = build_html_body(articles, run_date, stats)

    payload = {
        "personalizations": [{"to": [{"email": EMAIL_TO}]}],
        "from": {"email": EMAIL_FROM, "name": "Мониторинг литературы"},
        "subject": f"📚 {high_count} новых релевантных статей — {run_date}",
        "content": [{"type": "text/html", "value": html_body}],
    }

    # Прикрепляем PDF
    if pdf_path and os.path.exists(pdf_path):
        try:
            with open(pdf_path, "rb") as f:
                pdf_b64 = base64.b64encode(f.read()).decode()
            payload["attachments"] = [{
                "content": pdf_b64,
                "type": "application/pdf",
                "filename": os.path.basename(pdf_path),
                "disposition": "attachment",
            }]
        except Exception as e:
            print(f"  [Email] PDF не прикреплён: {e}")

    try:
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send", data=body,
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}",
                     "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.getcode()
        if code in (200, 202):
            print(f"  [Email] ✅ Отправлено на {EMAIL_TO}")
            return True
        else:
            print(f"  [Email] Неожиданный HTTP {code}")
            return False
    except Exception as e:
        print(f"  [Email] Ошибка отправки: {e}")
        return False
