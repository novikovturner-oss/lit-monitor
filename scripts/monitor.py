"""
Literature Monitor — Новиков В.А.
Нейроортопедия: ДЦП (все сегменты), спастичность, селективные невротомии,
реиннервация, spina bifida, орфанные, нейромодуляция, экзоскелеты.

Источники:
  PubMed        — 26 тематических запросов
  RSS           — 6 российских + 12 зарубежных журналов
  КиберЛенинка  — 10 русскоязычных запросов

Умное расписание: журналы с известной датой выхода проверяются
только в нужный день ± 3 суток, что экономит запросы и не пропускает номера.
"""

import os, json, time, datetime, urllib.request, urllib.parse, re
import xml.etree.ElementTree as ET

# ════════════════════════════════════════════════════════════════════════
#  ПАРАМЕТРЫ
# ════════════════════════════════════════════════════════════════════════

DAYS_BACK   = 35   # период поиска: чуть больше месяца
SCHEDULE_SLACK = 3 # ±дней от даты выхода для «умного» запуска

# ── PubMed ───────────────────────────────────────────────────────────────────
PUBMED_QUERIES = [
    # ДЦП — общее
    "cerebral palsy surgery children",
    "cerebral palsy spasticity management children",
    # Верхняя конечность
    "cerebral palsy upper extremity tendon transfer children",
    "spastic hand hemiplegia surgery pediatric",
    "pronator teres rerouting forearm supination cerebral palsy",
    # Нижняя конечность
    "cerebral palsy lower extremity gait surgery",
    "cerebral palsy equinus foot surgery children",
    "crouch gait cerebral palsy surgery hamstrings",
    # Тазобедренный сустав
    "hip displacement cerebral palsy surveillance reconstruction",
    "spastic hip dislocation cerebral palsy surgery",
    # Позвоночник
    "neuromuscular scoliosis cerebral palsy spinal fusion",
    # Нейромодуляция
    "selective dorsal rhizotomy cerebral palsy outcomes",
    "botulinum toxin spasticity children cerebral palsy",
    "intrathecal baclofen cerebral palsy pump children",
    # Селективные невротомии и реиннервация
    "selective peripheral neurotomy spasticity children",
    "tibial nerve neurotomy spastic foot",
    "peripheral neurotomy spasticity upper limb",
    "nerve reinnervation reinnervation tendon transfer pediatric",
    "hyperselective neurectomy spastic upper extremity pediatric",
    # Технологии
    "exoskeleton rehabilitation cerebral palsy children",
    "robotic gait training spastic children",
    "functional electrical stimulation cerebral palsy children",
    # Spina bifida и нейромышечная патология
    "spina bifida myelomeningocele orthopedic surgery children",
    "neuromuscular disease orthopedic pediatric treatment",
    # Орфанные
    "rare genetic musculoskeletal disease pediatric surgery",
    # Нейростимуляция
    "deep brain stimulation dystonia children",
]

# ── RSS-ленты ─────────────────────────────────────────────────────────────────
# schedule: {"day": <день месяца>, "months": [список месяцев]}
# Если не указан — проверяется при каждом запуске.
# При запуске в неподходящий день лента пропускается (экономия трафика/запросов).

RSS_FEEDS = {
    # ══ РОССИЙСКИЕ ════════════════════════════════════════════════
    "ОТВХДВ (Турнера)": {
        "url": "https://journals.eco-vector.com/turner/gateway/plugin/WebFeedGatewayPlugin/rss2",
        "schedule": {"day": 10, "months": [3, 6, 9, 12]},   # ежеквартальный
    },
    "Вестник Приорова": {
        "url": "https://journals.eco-vector.com/0869-8678/gateway/plugin/WebFeedGatewayPlugin/rss2",
        "schedule": {"day": 15, "months": [3, 6, 9, 12]},
    },
    "Травматология и ортопедия России": {
        "url": "https://journal.rniito.org/jour/gateway/plugin/WebFeedGatewayPlugin/rss2",
        "schedule": {"day": 20, "months": [3, 6, 9, 12]},
    },
    "Хирургия позвоночника": {
        "url": "https://journal.spinaneurology.ru/spine/gateway/plugin/WebFeedGatewayPlugin/rss2",
        "schedule": {"day": 15, "months": [3, 6, 9, 12]},
    },
    "Вопросы нейрохирургии": {
        "url": "https://www.mediasphera.ru/rss/1028-6403",
        # нет жёсткого расписания → проверяется всегда
    },
    "Педиатрия им. Сперанского": {
        "url": "https://journals.eco-vector.com/pediatria/gateway/plugin/WebFeedGatewayPlugin/rss2",
        "schedule": {"day": 10, "months": [2, 4, 6, 8, 10, 12]},  # 6 раз в год
    },

    # ══ ЗАРУБЕЖНЫЕ — нейроортопедия / ДЦП ═══════════════════════
    "Dev Med Child Neurol": {
        "url": "https://onlinelibrary.wiley.com/action/showFeed?jc=14698749&type=etoc&feed=rss",
        "schedule": {"day": 1, "months": list(range(1, 13))},   # ежемесячный
    },
    "J Child Orthop": {
        "url": "https://journals.sagepub.com/action/showFeed?ui=0&mi=ehikzz&ai=2m&jc=coa&type=etoc&feed=rss",
        "schedule": {"day": 1, "months": [2, 4, 6, 8, 10, 12]},
    },
    "J Pediatr Orthop": {
        "url": "https://feeds.journals.lww.com/jpo-online/pages/default.aspx?rss=1",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },
    "J Hand Surg Am": {
        "url": "https://www.jhandsurg.org/rss/S0363-5023",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },

    # ══ ЗАРУБЕЖНЫЕ — нейрохирургия / невротомии / СДР ═══════════
    "J Neurosurg Pediatrics": {
        # JNSPG использует стандарт Atypon: action/showFeed
        "url": "https://thejns.org/action/showFeed?type=etoc&feed=rss&jc=j-neurosurg-pediatr",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },
    "Childs Nerv Syst": {
        # Springer RSS: facet-journal-id=381
        "url": "https://link.springer.com/search.rss?facet-content-type=Article&facet-journal-id=381&channel-name=Childs+Nerv+Syst",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },
    "Neurosurg Focus": {
        "url": "https://thejns.org/action/showFeed?type=etoc&feed=rss&jc=neurosurg-focus",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },

    # ══ ЗАРУБЕЖНЫЕ — реабилитация / технологии ═══════════════════
    "Eur J Paediatr Neurol": {
        "url": "https://rss.sciencedirect.com/publication/science/10903798",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },
    "Gait & Posture": {
        "url": "https://rss.sciencedirect.com/publication/science/09666362",
    },
    "Dev Neurorehabil": {
        "url": "https://www.tandfonline.com/action/showFeed?type=etoc&feed=rss&jc=ipdr20",
        "schedule": {"day": 1, "months": list(range(1, 13))},
    },
    "Disability Rehabil": {
        "url": "https://www.tandfonline.com/action/showFeed?type=etoc&feed=rss&jc=idre20",
    },
    "EFORT Open Rev": {
        # European Federation of Orthopaedic Societies — открытый доступ
        "url": "https://online.boneandjoint.org.uk/action/showFeed?type=etoc&feed=rss&jc=eor",
    },

    # ══ COCHRANE ══════════════════════════════════════════════════
    "Cochrane: CP & neuro": {
        "url": "https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858/full/xml?query=cerebral+palsy",
    },
}

# ── КиберЛенинка ─────────────────────────────────────────────────────────────
CYBERLENINKA_QUERIES = [
    "детский церебральный паралич хирургия",
    "ДЦП нижняя конечность тазобедренный сустав хирургия",
    "ДЦП позвоночник сколиоз",
    "спастичность невротомия дети",
    "селективная дорсальная ризотомия ДЦП",
    "нейромышечная патология дети ортопедия",
    "спина бифида ортопедия хирургия",
    "экзоскелет нейрореабилитация дети",
    "ботулотоксин спастичность дети",
    "орфанные заболевания скелет дети",
]

# Бейджи-цвета источников в отчёте
SOURCE_COLORS = {
    "PubMed":                          "#1d3557",
    "КиберЛенинка":                    "#c1121f",
    "ОТВХДВ (Турнера)":                "#6a0572",
    "Вестник Приорова":                "#6a0572",
    "Травматология и ортопедия России":"#6a0572",
    "Хирургия позвоночника":           "#6a0572",
    "Вопросы нейрохирургии":           "#6a0572",
    "Педиатрия им. Сперанского":       "#6a0572",
}

# ════════════════════════════════════════════════════════════════════════
#  УМНОЕ РАСПИСАНИЕ
# ════════════════════════════════════════════════════════════════════════

def should_check_today(schedule: dict | None) -> bool:
    """
    Возвращает True если сегодня подходит для проверки журнала.
    Критерий: текущий месяц входит в список months И
    мы находимся в пределах SCHEDULE_SLACK дней от целевого дня.
    Если schedule не задан — всегда True (проверяем при каждом запуске).
    """
    if not schedule:
        return True
    today = datetime.date.today()
    if today.month not in schedule.get("months", list(range(1, 13))):
        return False
    target_day = schedule.get("day", 1)
    target = datetime.date(today.year, today.month, min(target_day, 28))
    return abs((today - target).days) <= SCHEDULE_SLACK


def schedule_summary(feeds: dict) -> str:
    today = datetime.date.today()
    active = [name for name, cfg in feeds.items() if should_check_today(cfg.get("schedule"))]
    skipped = [name for name, cfg in feeds.items() if not should_check_today(cfg.get("schedule"))]
    lines = [f"  Активных RSS сегодня ({today}): {len(active)}/{len(feeds)}"]
    if skipped:
        lines.append(f"  Пропущено по расписанию: {', '.join(skipped)}")
    return "\n".join(lines)

# ════════════════════════════════════════════════════════════════════════
#  PubMed
# ════════════════════════════════════════════════════════════════════════

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def pubmed_search(query: str) -> list:
    date_from = (datetime.date.today() - datetime.timedelta(days=DAYS_BACK)).strftime("%Y/%m/%d")
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": f'{query} AND ("{date_from}"[Date - Publication] : "3000"[Date - Publication])',
        "retmax": 25, "retmode": "json",
    })
    try:
        with urllib.request.urlopen(f"{PUBMED_BASE}/esearch.fcgi?{params}", timeout=15) as r:
            return json.loads(r.read()).get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"    [PubMed search error] {e}"); return []

def pubmed_fetch(pmids: list) -> list:
    if not pmids: return []
    params = urllib.parse.urlencode({"db":"pubmed","id":",".join(pmids),"retmode":"xml"})
    try:
        with urllib.request.urlopen(f"{PUBMED_BASE}/efetch.fcgi?{params}", timeout=25) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"    [PubMed fetch error] {e}"); return []
    arts = []
    for art in root.findall(".//PubmedArticle"):
        try:
            pmid    = art.findtext(".//PMID","")
            title   = art.findtext(".//ArticleTitle","No title")
            abstract= " ".join(t.text or "" for t in art.findall(".//AbstractText"))
            authors = []
            for a in art.findall(".//Author")[:4]:
                ln=a.findtext("LastName",""); fn=a.findtext("ForeName","")
                if ln: authors.append(f"{ln} {fn}".strip())
            journal = art.findtext(".//Journal/Title","")
            year    = art.findtext(".//PubDate/Year","")
            doi     = next((x.text for x in art.findall(".//ArticleId") if x.get("IdType")=="doi"),"")
            arts.append({"source":"PubMed","pmid":pmid,"title":title,"authors":authors,
                         "journal":journal,"year":year,"doi":doi,"abstract":abstract[:1500],
                         "url":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/","lang":"en"})
        except: continue
    return arts

def collect_pubmed() -> list:
    seen, results = set(), []
    for q in PUBMED_QUERIES:
        print(f"  → {q}")
        pmids = pubmed_search(q)
        new   = [p for p in pmids if p not in seen]
        seen.update(new)
        if new: results.extend(pubmed_fetch(new))
        time.sleep(0.35)
    print(f"  PubMed итого: {len(results)}")
    return results

# ════════════════════════════════════════════════════════════════════════
#  RSS
# ════════════════════════════════════════════════════════════════════════

def fetch_rss(name: str, url: str) -> list:
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=DAYS_BACK)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
    except Exception as e:
        print(f"    [RSS error] {name}: {e}"); return []
    items = []
    try:
        root = ET.fromstring(raw)
        ns   = {"atom":"http://www.w3.org/2005/Atom"}
        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for entry in entries:
            title = (entry.findtext("title") or entry.findtext("atom:title",namespaces=ns) or "").strip()
            link  = (entry.findtext("link")  or entry.findtext("atom:id",   namespaces=ns) or "").strip()
            pub   =  entry.findtext("pubDate") or entry.findtext("atom:published",namespaces=ns) or ""
            desc  = (entry.findtext("description") or entry.findtext("atom:summary",namespaces=ns) or "")
            try:
                from email.utils import parsedate_to_datetime
                if parsedate_to_datetime(pub).replace(tzinfo=None) < cutoff: continue
            except: pass
            lang = "ru" if re.search(r'[а-яёА-ЯЁ]', title+desc) else "en"
            if title:
                items.append({"source":name,"title":title,"url":link,"abstract":desc[:900],
                              "authors":[],"journal":name,"year":pub[:4] if pub else "","pmid":"","doi":"","lang":lang})
    except Exception as e:
        print(f"    [RSS parse error] {name}: {e}")
    return items

def collect_rss() -> list:
    results = []
    for name, cfg in RSS_FEEDS.items():
        sched = cfg.get("schedule")
        if not should_check_today(sched):
            print(f"  → {name} [пропуск по расписанию]")
            continue
        print(f"  → {name}")
        items = fetch_rss(name, cfg["url"])
        print(f"     {len(items)} записей")
        results.extend(items)
        time.sleep(0.5)
    return results

# ════════════════════════════════════════════════════════════════════════
#  КиберЛенинка
# ════════════════════════════════════════════════════════════════════════

def cyberleninka_search(query: str) -> list:
    year_min = datetime.date.today().year - 1
    url = f"https://cyberleninka.ru/search?q={urllib.parse.quote(query)}&datasource=article"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent":"Mozilla/5.0 (compatible; research-bot/1.0)",
            "Accept-Language":"ru-RU,ru;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    [КиберЛенинка error] {query}: {e}"); return []
    items, seen = [], set()
    for m in re.finditer(r'href="(/article/n/([^"]+))"[^>]*>.*?<h\d[^>]*>(.*?)</h\d', html, re.DOTALL):
        slug  = m.group(2)
        title = re.sub(r'<[^>]+>','',m.group(3)).strip()
        if not title or len(title)<8 or slug in seen: continue
        seen.add(slug)
        context = html[m.start():m.start()+400]
        year_m  = re.search(r'\b(20\d{2})\b', context)
        year    = year_m.group(1) if year_m else ""
        if year and int(year) < year_min: continue
        items.append({"source":"КиберЛенинка","title":title,
                      "url":f"https://cyberleninka.ru/article/n/{slug}",
                      "abstract":"","authors":[],"journal":"КиберЛенинка","year":year,
                      "pmid":"","doi":"","lang":"ru"})
        if len(items) >= 15: break
    return items

def collect_cyberleninka() -> list:
    seen, results = set(), []
    for q in CYBERLENINKA_QUERIES:
        print(f"  → {q}")
        items = cyberleninka_search(q)
        for it in items:
            if it["url"] not in seen:
                seen.add(it["url"]); results.append(it)
        print(f"     {len(items)} записей")
        time.sleep(1.5)
    print(f"  КиберЛенинка итого: {len(results)}")
    return results

# ════════════════════════════════════════════════════════════════════════
#  Claude API — анализ
# ════════════════════════════════════════════════════════════════════════

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY","")

SYSTEM_PROMPT = """Ты — ассистент детского нейроортопеда. Специализация:
• ДЦП: хирургия руки, ноги, тазобедренного сустава, позвоночника
• Нейромодуляция: ботулотоксин, ИТБ, СДР; селективные периферические невротомии
• Реиннервация, гиперселективная нейрэктомия при спастичности
• Spina bifida, нейромышечный сколиоз, орфанные заболевания ОДА у детей
• Экзоскелеты, роботизированная реабилитация, ФЭС, нейростимуляция

Русскоязычные статьи (из российских журналов и КиберЛенинки) особенно ценны.
Отвечай строго в JSON без текста вне JSON-объекта."""

def analyze_batch(articles: list) -> list:
    if not ANTHROPIC_API_KEY:
        print("  [!] ANTHROPIC_API_KEY не задан — анализ Claude пропущен.")
        print("      Всем статьям проставлен нейтральный балл 5 без резюме и перевода.")
        print("      Чтобы включить анализ, задайте ключ и запустите снова:")
        print('        export ANTHROPIC_API_KEY="sk-ant-..."   (macOS/Linux)')
        print('        setx ANTHROPIC_API_KEY "sk-ant-..."      (Windows, затем новый терминал)')
        for a in articles:
            a.update({"relevance":5,"summary_ru":"(нет API-ключа — анализ не выполнялся)",
                      "why_relevant":"","read_full":True,"abstract_ru":"","key_points":[]})
        return articles
    batch_size = 5
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]
        batch_text = ""
        for j, art in enumerate(batch):
            flag = "(русскоязычная)" if art.get("lang")=="ru" else ""
            batch_text += f"""
[{j+1}] {flag}
Название: {art['title']}
Журнал: {art['journal']} {art['year']}
Аннотация: {art.get('abstract','')[:600] or '(нет)'}
---"""
        prompt = f"""Оцени релевантность для детского нейроортопеда
(ДЦП, спастичность, невротомии, реиннервация, нейроортопедия, экзоскелеты).

{batch_text}

Верни JSON:
{{
  "items": [
    {{
      "index": 1,
      "relevance": <1–10>,
      "summary_ru": "<2–3 предложения на русском: что изучали и главный вывод>",
      "why_relevant": "<1 предложение: зачем это данному специалисту, или «Вне профиля»>",
      "read_full": <true если relevance ≥ 7>,
      "abstract_ru": "<перевод аннотации на русский язык — полный, 5–10 предложений; если аннотации нет — пустая строка>",
      "key_points": [
        "<тезис 1: конкретный факт или вывод, на который стоит обратить внимание>",
        "<тезис 2>",
        "<тезис 3>"
      ]
    }}
  ]
}}

Требования к key_points: 2–4 тезиса, конкретные цифры и факты где есть,
формулировки — с точки зрения практикующего хирурга («показание», «осложнение», «размер эффекта»)."""
        try:
            body = json.dumps({
                "model":"claude-sonnet-4-20250514","max_tokens":1000,
                "system":SYSTEM_PROMPT,"messages":[{"role":"user","content":prompt}]
            }).encode()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages", data=body,
                headers={"Content-Type":"application/json",
                         "x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as r:
                resp = json.loads(r.read())
            raw = resp["content"][0]["text"].strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"): raw=raw[4:]
            result = json.loads(raw)
            for item in result.get("items",[]):
                idx = item["index"]-1
                if 0<=idx<len(batch):
                    batch[idx].update({
                        "relevance":   item.get("relevance",5),
                        "summary_ru":  item.get("summary_ru",""),
                        "why_relevant":item.get("why_relevant",""),
                        "read_full":   item.get("read_full",False),
                        "abstract_ru": item.get("abstract_ru",""),
                        "key_points":  item.get("key_points",[]),
                    })
        except Exception as e:
            print(f"  [Claude error] batch {i//batch_size+1}: {e}")
            for art in batch:
                art.setdefault("relevance",5)
                art.setdefault("summary_ru",art.get("abstract","")[:300] or "(нет аннотации)")
                art.setdefault("why_relevant","Ошибка анализа")
                art.setdefault("read_full",True)
        time.sleep(1)
    return articles

# ════════════════════════════════════════════════════════════════════════
#  HTML-отчёт
# ════════════════════════════════════════════════════════════════════════

def source_badge(source: str) -> str:
    color = SOURCE_COLORS.get(source,"#457b9d")
    return (f'<span style="background:{color};color:#fff;padding:1px 7px;'
            f'border-radius:9px;font-size:11px;margin-right:5px">{source}</span>')

def make_rows(arts: list) -> str:
    rows = ""
    for art in arts:
        rel  = art.get("relevance",0)
        bc   = "#2a9d8f" if rel>=7 else ("#e9c46a" if rel>=4 else "#bbb")
        tc   = "#fff"    if rel>=7 else ("#333"    if rel>=4 else "#555")
        read_badge = (
            '<span style="background:#2a9d8f;color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;margin-left:6px">читать полностью</span>'
            if art.get("read_full") else ""
        )
        authors_str = ", ".join(art["authors"][:3]) + (" et al." if len(art["authors"])>3 else "")
        doi_link  = (f'<a href="https://doi.org/{art["doi"]}" target="_blank" style="color:#457b9d">[DOI]</a> '
                     if art.get("doi") else "")
        src_link  = (f'<a href="{art["url"]}" target="_blank" style="color:#457b9d">'
                     f'{"[PubMed]" if art.get("pmid") else "[ссылка]"}</a>'
                     if art.get("url") else "")
        veri_html = ""

    rows += f"""
<tr>
  <td style="padding:12px 8px;border-bottom:1px solid #eee;text-align:center;vertical-align:top;width:42px">
    <span style="background:{bc};color:{tc};border-radius:50%;padding:5px 8px;font-weight:700">{rel}</span>
  </td>
  <td style="padding:12px 10px;border-bottom:1px solid #eee;vertical-align:top">
    <div style="font-weight:600;margin-bottom:4px">{art['title']}</div>
    <div style="color:#555;font-size:12px;margin-bottom:6px">
      {source_badge(art['source'])}{authors_str}{"&bull; " if authors_str else ""}
      <em>{art['journal']}</em> {art['year']}&nbsp;{doi_link}{src_link}
    </div>
    <div style="line-height:1.55;margin-bottom:5px">{art.get('summary_ru','')}</div>
    <div style="color:#457b9d;font-size:13px">{art.get('why_relevant','')}{read_badge}</div>
  </td>
</tr>"""
    return rows

def render_html(articles: list, run_date: str, skipped_feeds: list,
                verify_counts: dict = None) -> str:
    articles = sorted(articles, key=lambda a: -a.get("relevance",0))
    high = sum(1 for a in articles if a.get("relevance",0)>=7)
    med  = sum(1 for a in articles if 4<=a.get("relevance",0)<7)
    low  = sum(1 for a in articles if a.get("relevance",0)<4)
    ru   = sum(1 for a in articles if a.get("lang")=="ru")
    en   = len(articles)-ru

    sections = [
        ("🔬 Высокая релевантность (7–10)", [a for a in articles if a.get("relevance",0)>=7]),
        ("📋 Средняя (4–6)",                [a for a in articles if 4<=a.get("relevance",0)<7]),
        ("📎 Низкая (1–3)",                 [a for a in articles if a.get("relevance",0)<4]),
    ]
    body_html = ""
    for title, arts in sections:
        if not arts: continue
        body_html += f"""
<h2 style="color:#1d3557;margin-top:30px;border-bottom:2px solid #a8dadc;padding-bottom:5px">
  {title} <span style="font-size:13px;color:#888;font-weight:normal">({len(arts)})</span>
</h2>
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#1d3557;color:#fff">
    <th style="padding:8px;width:42px">Балл</th>
    <th style="padding:8px;text-align:left">Статья</th>
  </tr></thead>
  <tbody>{make_rows(arts)}</tbody>
</table>"""

    skipped_note = ""
    if skipped_feeds:
        skipped_note = (f'<p style="color:#888;font-size:12px;margin-top:8px">'
                        f'Пропущено по расписанию: {", ".join(skipped_feeds)}</p>')

    active_feeds = len(RSS_FEEDS) - len(skipped_feeds)
    vc = verify_counts or {}

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Мониторинг — {run_date}</title>
<style>
body{{font-family:Georgia,serif;max-width:980px;margin:36px auto;padding:0 20px;color:#222;line-height:1.6}}
h1{{color:#1d3557;border-bottom:3px solid #457b9d;padding-bottom:8px}}
.meta{{color:#666;font-size:13px;margin-bottom:16px}}
.stats{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.stat{{background:#f1faee;border-left:4px solid #457b9d;padding:9px 15px;border-radius:4px;min-width:110px}}
.stat strong{{display:block;font-size:22px;color:#1d3557}}
.stat span{{font-size:12px;color:#555}}
tr:hover td{{background:#f8f9fa}}
</style>
</head>
<body>
<h1>📚 Мониторинг научных публикаций</h1>
<div class="meta">
  Дата: <strong>{run_date}</strong> &nbsp;|&nbsp; Период: {DAYS_BACK} дней &nbsp;|&nbsp;
  PubMed ({len(PUBMED_QUERIES)} запросов) · RSS ({active_feeds}/{len(RSS_FEEDS)} журналов) · КиберЛенинка
</div>
{skipped_note}
<div class="stats">
  <div class="stat"><strong>{len(articles)}</strong><span>всего</span></div>
  <div class="stat"><strong style="color:#2a9d8f">{high}</strong><span>высокая релевантность</span></div>
  <div class="stat"><strong style="color:#e9a429">{med}</strong><span>средняя</span></div>
  <div class="stat"><strong style="color:#999">{low}</strong><span>низкая</span></div>
  <div class="stat"><strong style="color:#6a0572">{ru}</strong><span>на русском</span></div>
  <div class="stat"><strong style="color:#1d3557">{en}</strong><span>на английском</span></div>
</div>
{body_html}
</body></html>"""

# ════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════

def _load_module(name: str):
    """Загружает модуль из той же папки, что и monitor.py."""
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(name, os.path.join(here, f"{name}.py"))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def preflight():
    """Проверяет окружение перед запуском и печатает понятные подсказки.
    Ничего не прерывает: скрипт работает и без ключа/reportlab, просто
    с урезанным результатом. Возвращает словарь с флагами доступности."""
    import sys
    print("── Проверка окружения ──────────────────────────────────────")

    # Python 3.8+
    py_ok = sys.version_info >= (3, 8)
    print(f"  Python {sys.version.split()[0]}: " + ("ок" if py_ok else "нужен 3.8+"))

    # reportlab (нужен только для PDF)
    try:
        import reportlab  # noqa: F401
        pdf_ok = True
        print("  reportlab: установлен (PDF будет сгенерирован)")
    except ImportError:
        pdf_ok = False
        print("  reportlab: НЕ установлен — PDF будет пропущен.")
        print("      Установите:  pip install reportlab   (или pip3)")

    # API-ключ (нужен для анализа Claude)
    key_ok = bool(ANTHROPIC_API_KEY)
    if key_ok:
        print("  ANTHROPIC_API_KEY: задан (анализ Claude включён)")
    else:
        print("  ANTHROPIC_API_KEY: НЕ задан — статьи соберутся, но без анализа/перевода.")
        print('      Задайте:  export ANTHROPIC_API_KEY="sk-ant-..."  (macOS/Linux)')

    print("────────────────────────────────────────────────────────────\n")
    return {"pdf": pdf_ok, "key": key_ok}


def main():
    run_date = datetime.date.today().isoformat()
    print(f"=== Мониторинг литературы {run_date} ===")
    preflight()
    print(schedule_summary(RSS_FEEDS))

    print("\n[1/5] PubMed...")
    pm = collect_pubmed()

    print("\n[2/5] RSS-ленты...")
    skipped = [n for n, cfg in RSS_FEEDS.items() if not should_check_today(cfg.get("schedule"))]
    rss = collect_rss()

    print("\n[3/5] КиберЛенинка...")
    cl = collect_cyberleninka()

    raw_arts = pm + rss + cl

    # ── Дедупликация ─────────────────────────────────────────────────────
    print(f"\n[4/5] Дедупликация (всего собрано: {len(raw_arts)})...")
    try:
        dedup   = _load_module("dedup")
        new_arts, seen_arts, _ = dedup.filter_new(raw_arts)
    except Exception as e:
        print(f"  [dedup] Пропущена: {e}")
        new_arts = raw_arts

    print(f"\n[5/5] Анализ {len(new_arts)} новых статей через Claude API...")
    new_arts = analyze_batch(new_arts)

    # ── Верификация ───────────────────────────────────────────────────────
    print(f"\n[+] Верификация статей (проверка галлюцинаций)...")
    verify_counts = {}
    try:
        verify = _load_module("verify")
        new_arts, verify_counts = verify.verify_all(new_arts)
    except Exception as e:
        print(f"  [verify] Пропущена: {e}")
        for a in new_arts:
            a.setdefault("verification", {"status": "unverifiable", "note": "модуль недоступен"})

    # ── HTML-отчёт ────────────────────────────────────────────────────────
    print("\nГенерация отчёта...")
    html = render_html(new_arts, run_date, skipped, verify_counts)
    os.makedirs("reports", exist_ok=True)
    for path in [f"reports/report_{run_date}.html", "reports/index.html"]:
        with open(path, "w", encoding="utf-8") as f: f.write(html)
    with open(f"reports/data_{run_date}.json", "w", encoding="utf-8") as f:
        json.dump(new_arts, f, ensure_ascii=False, indent=2)

    # ── PDF ───────────────────────────────────────────────────────────────
    pdf_path = f"reports/report_{run_date}.pdf"
    try:
        make_pdf = _load_module("make_pdf")
        make_pdf.generate_pdf(new_arts, run_date, pdf_path)
    except ImportError:
        print("  [PDF] Пропущен: не установлен reportlab. Установите: pip install reportlab")
        pdf_path = None
    except Exception as e:
        print(f"  [PDF] Пропущен: {e}")
        pdf_path = None

    # ── Email-дайджест ────────────────────────────────────────────────────
    high = sum(1 for a in new_arts if a.get("relevance", 0) >= 7)
    ru   = sum(1 for a in new_arts if a.get("lang") == "ru")
    stats = {
        "total":     len(new_arts),
        "high":      high,
        "ru":        ru,
        "not_found": verify_counts.get("not_found", 0),
        "mismatch":  verify_counts.get("mismatch", 0),
    }
    try:
        email_mod = _load_module("send_email")
        email_mod.send_digest(new_arts, run_date, stats, pdf_path)
    except Exception as e:
        print(f"  [Email] Пропущен: {e}")

    # ── Итог ──────────────────────────────────────────────────────────────
    not_found = verify_counts.get("not_found", 0)
    mismatch  = verify_counts.get("mismatch",  0)
    print(f"\n{'='*55}")
    print(f"✓ Новых статей:          {len(new_arts)}")
    print(f"  Высокорелевантных:     {high}")
    print(f"  На русском:            {ru}")
    print(f"  ✅ Верифицированы:     {verify_counts.get('verified', 0)}")
    if not_found:
        print(f"  ❌ НЕ НАЙДЕНЫ (возм. галлюцинации): {not_found}")
    if mismatch:
        print(f"  ⚠️  Несоответствие данных: {mismatch}")
    print(f"  Пропущено по расписанию RSS: {len(skipped)}")
    print(f"  Отчёт: reports/index.html")

if __name__ == "__main__":
    main()
