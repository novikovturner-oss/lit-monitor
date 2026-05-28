"""
Дедупликация между запусками.

Хранит историю найденных статей в reports/seen_articles.json
Формат: {"pmid:12345": "2026-05-01", "doi:10.xxxx": "2026-05-01", ...}

При каждом запуске:
1. Загружает историю
2. Фильтрует уже виденные статьи
3. Обновляет историю новыми
4. Очищает записи старше HISTORY_DAYS
"""

import json, os, datetime

HISTORY_DAYS = 60   # помним статью 60 дней
HISTORY_FILE = "reports/seen_articles.json"


def _article_key(art: dict) -> str:
    """Уникальный ключ статьи: PMID > DOI > URL > title+year."""
    if art.get("pmid") and not art["pmid"].startswith(("frontiers","jama","mdpi")):
        return f"pmid:{art['pmid']}"
    if art.get("doi"):
        return f"doi:{art['doi'].lower()}"
    if art.get("url"):
        return f"url:{art['url']}"
    title = art.get("title","")[:80].lower().strip()
    year  = art.get("year","")
    return f"title:{title}:{year}"


def load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history: dict):
    os.makedirs("reports", exist_ok=True)
    # Очищаем старые записи
    cutoff = (datetime.date.today() - datetime.timedelta(days=HISTORY_DAYS)).isoformat()
    clean  = {k: v for k, v in history.items() if v >= cutoff}
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def filter_new(articles: list, verbose: bool = True) -> tuple:
    """
    Разделяет статьи на новые и уже виденные.
    Возвращает (new_articles, seen_articles, history).
    """
    history  = load_history()
    today    = datetime.date.today().isoformat()
    new_arts, seen_arts = [], []

    for art in articles:
        key = _article_key(art)
        if key in history:
            art["_seen_date"] = history[key]
            seen_arts.append(art)
        else:
            new_arts.append(art)
            history[key] = today

    save_history(history)

    if verbose:
        print(f"  Дедупликация: {len(new_arts)} новых, {len(seen_arts)} уже видели")

    return new_arts, seen_arts, history
