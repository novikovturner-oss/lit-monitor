"""
Верификатор статей — проверка реального существования.

Логика:
1. PubMed-статьи (есть PMID) — проверяем через efetch, смотрим совпадение заголовка
2. DOI-статьи — делаем HEAD-запрос на doi.org, смотрим HTTP 200/301
3. КиберЛенинка/RSS без PMID и DOI — Claude проверяет через web_search
   (задаёт запрос: автор + ключевые слова + год)

Статусы верификации:
  "verified"     — существование подтверждено
  "not_found"    — статья не найдена, вероятная галлюцинация
  "mismatch"     — найдена, но данные не совпадают (другое название/год)
  "unverifiable" — нет достаточных данных для проверки
  "skipped"      — КиберЛенинка/RSS без абстракта (проверка нецелесообразна)
"""

import os, json, time, re, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ── 1. Проверка PubMed по PMID ────────────────────────────────────────────

def verify_by_pmid(article: dict) -> dict:
    """Подтягивает реальный заголовок из PubMed и сравнивает."""
    pmid = article.get("pmid", "")
    if not pmid:
        return {"status": "unverifiable", "note": "нет PMID"}
    params = urllib.parse.urlencode({"db": "pubmed", "id": pmid, "retmode": "xml"})
    try:
        with urllib.request.urlopen(f"{PUBMED_BASE}/efetch.fcgi?{params}", timeout=12) as r:
            root = ET.fromstring(r.read())
        real_title = root.findtext(".//ArticleTitle", "").strip().lower()
        real_year  = root.findtext(".//PubDate/Year", "")
        real_journal = root.findtext(".//Journal/Title", "").strip()
        if not real_title:
            return {"status": "not_found", "note": f"PMID {pmid} не найден в PubMed"}

        our_title = article.get("title", "").strip().lower()
        # Нечёткое сравнение: достаточно совпадения первых 6 слов
        def first_words(s, n=6):
            return " ".join(re.sub(r'[^\w\s]', '', s).split()[:n])
        match = first_words(real_title) == first_words(our_title)

        # Год
        year_ok = (not real_year) or (real_year == article.get("year", ""))

        if match and year_ok:
            return {"status": "verified",
                    "note": f"PMID подтверждён: {real_journal} {real_year}",
                    "real_title": real_title,
                    "real_year": real_year,
                    "real_journal": real_journal}
        elif match and not year_ok:
            return {"status": "mismatch",
                    "note": f"Заголовок совпадает, год расходится: реальный {real_year}, указан {article.get('year')}",
                    "real_title": real_title,
                    "real_year": real_year,
                    "real_journal": real_journal}
        else:
            return {"status": "mismatch",
                    "note": f"PMID {pmid} ведёт на другую статью: «{real_title[:80]}»",
                    "real_title": real_title,
                    "real_year": real_year}
    except Exception as e:
        return {"status": "unverifiable", "note": f"Ошибка PubMed: {e}"}


# ── 2. Проверка DOI ───────────────────────────────────────────────────────

def verify_by_doi(doi: str) -> dict:
    """HEAD-запрос на doi.org — подтверждает физическое существование DOI."""
    if not doi:
        return {"status": "unverifiable", "note": "нет DOI"}
    url = f"https://doi.org/{doi}"
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.getcode()
        if code in (200, 301, 302, 303):
            return {"status": "verified", "note": f"DOI разрешается: HTTP {code}"}
        else:
            return {"status": "not_found", "note": f"DOI вернул HTTP {code}"}
    except Exception as e:
        err = str(e)
        if "404" in err or "Not Found" in err:
            return {"status": "not_found", "note": "DOI не существует (404)"}
        return {"status": "unverifiable", "note": f"Ошибка DOI: {err[:80]}"}


# ── 3. Проверка через Claude + web_search ────────────────────────────────

VERIFY_SYSTEM = """Ты — ассистент для верификации научных публикаций.
Твоя задача: определить, реально ли существует статья.
Используй инструмент web_search для поиска.
Отвечай строго в JSON без текста вне JSON."""

def verify_by_claude_search(article: dict) -> dict:
    """Просит Claude найти статью через web_search и сообщить о результате."""
    if not ANTHROPIC_API_KEY:
        return {"status": "unverifiable", "note": "нет API-ключа"}

    title   = article.get("title", "")[:120]
    authors = ", ".join(article.get("authors", [])[:2])
    year    = article.get("year", "")
    journal = article.get("journal", "")

    # Формируем поисковый запрос
    query = f'"{title[:60]}" {authors} {year}'

    prompt = f"""Проверь, реально ли существует эта научная статья:

Название: {title}
Авторы: {authors or '(неизвестны)'}
Журнал: {journal}
Год: {year}

Поисковый запрос для проверки: {query}

Используй web_search чтобы найти эту статью. Затем верни JSON:
{{
  "status": "verified" | "not_found" | "mismatch" | "unverifiable",
  "note": "<что нашёл или не нашёл — 1-2 предложения>",
  "real_title": "<реальное название если нашёл, иначе null>",
  "real_year": "<реальный год если нашёл, иначе null>"
}}

Критерии:
- "verified": нашёл именно эту статью с совпадающим названием и годом
- "not_found": статьи с таким названием/авторами не существует
- "mismatch": нашёл похожую статью, но данные не совпадают
- "unverifiable": недостаточно данных для проверки"""

    try:
        body = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "system": VERIFY_SYSTEM,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"Content-Type": "application/json",
                     "x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=40) as r:
            resp = json.loads(r.read())

        # Извлекаем последний text-блок
        text = ""
        for block in resp.get("content", []):
            if block.get("type") == "text":
                text = block.get("text", "")
        if not text:
            return {"status": "unverifiable", "note": "Claude не вернул текст"}

        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        result = json.loads(raw)
        return result

    except Exception as e:
        return {"status": "unverifiable", "note": f"Ошибка верификации: {str(e)[:80]}"}


# ── 4. Главная функция верификации ────────────────────────────────────────

def verify_article(article: dict) -> dict:
    """
    Выбирает оптимальный метод верификации в зависимости от доступных данных.
    Приоритет: PMID → DOI → Claude search → skip
    """
    source = article.get("source", "")
    pmid   = article.get("pmid", "")
    doi    = article.get("doi", "")
    lang   = article.get("lang", "en")

    # КиберЛенинка без абстракта — невозможно проверить содержательно
    if source == "КиберЛенинка" and not article.get("abstract"):
        return {"status": "skipped",
                "note": "КиберЛенинка без абстракта — проверка нецелесообразна"}

    # 1. PubMed — самый надёжный
    if pmid and not pmid.startswith("frontiers") and not pmid.startswith("jama") \
             and not pmid.startswith("mdpi"):
        return verify_by_pmid(article)

    # 2. DOI есть — проверяем физическое существование
    if doi:
        doi_result = verify_by_doi(doi)
        # Если DOI подтверждён — достаточно
        if doi_result["status"] == "verified":
            return doi_result
        # Если DOI не найден — это уже сигнал
        if doi_result["status"] == "not_found":
            return doi_result

    # 3. Русскоязычные статьи без PMID — проверяем через Claude+search
    if lang == "ru" and article.get("title"):
        return verify_by_claude_search(article)

    # 4. Английские статьи из RSS без PMID/DOI — проверяем если есть данные
    if article.get("title") and article.get("authors"):
        return verify_by_claude_search(article)

    return {"status": "unverifiable", "note": "недостаточно данных"}


# ── 5. Пакетная верификация ───────────────────────────────────────────────

def verify_all(articles: list, verbose: bool = True) -> tuple:
    """
    Верифицирует все статьи.
    Статьи со статусом not_found и mismatch — удаляются (не сохраняются и не показываются).
    Возвращает (clean_articles, counts).
    """
    def priority(art):
        if art.get("lang") == "ru": return 0   # русские — первыми
        if not art.get("pmid"):     return 1
        return 2

    articles_sorted = sorted(articles, key=priority)
    total = len(articles_sorted)

    counts   = {"verified": 0, "not_found": 0, "mismatch": 0,
                "unverifiable": 0, "skipped": 0}
    clean    = []   # статьи, которые прошли проверку
    removed  = []   # удалённые галлюцинации (для лога)

    for i, art in enumerate(articles_sorted):
        if verbose:
            print(f"  [{i+1}/{total}] {art['source']} — {art['title'][:55]}...")

        result = verify_article(art)
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1

        if verbose:
            icon = {"verified":"✅","not_found":"❌","mismatch":"⚠️",
                    "unverifiable":"❓","skipped":"—"}.get(status, "?")
            print(f"     {icon} {status}: {result.get('note','')[:80]}")

        if status in ("not_found", "mismatch"):
            # Галлюцинация или несоответствие — удаляем молча, только в лог
            removed.append({
                "title":  art.get("title","")[:80],
                "source": art.get("source",""),
                "reason": result.get("note",""),
                "status": status,
            })
        else:
            # verified / unverifiable / skipped — оставляем
            # поле verification не нужно снаружи, не добавляем
            clean.append(art)

        if art.get("pmid"):
            time.sleep(0.35)
        else:
            time.sleep(1.0)

    if verbose:
        print(f"\n  Верификация завершена:")
        print(f"    ✅ подтверждены:          {counts['verified']}")
        print(f"    ❌ удалено галлюцинаций:  {counts['not_found']}")
        print(f"    ⚠️  удалено (несоответствие): {counts['mismatch']}")
        print(f"    ❓ не удалось проверить:  {counts['unverifiable']}")
        print(f"    —  пропущены (нет данных): {counts['skipped']}")
        if removed:
            print(f"\n  Удалённые статьи:")
            for r in removed:
                print(f"    [{r['status']}] {r['source']} — {r['title']}")
                print(f"      Причина: {r['reason']}")

    return clean, counts
