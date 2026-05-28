"""
Сборщик статей — без API, без оплаты.

Что делает:
  1. Ищет новые статьи в PubMed (26 запросов)
  2. Забирает RSS из российских и зарубежных журналов
  3. Ищет на КиберЛенинке
  4. Сохраняет всё в один JSON-файл

Что НЕ делает: не анализирует, не переводит, не оценивает релевантность.
Анализ выполняется отдельно — вставкой JSON в Claude.ai.

Запуск:
  python scripts/collect_only.py

Требования: Python 3.8+, интернет. Ничего устанавливать не нужно.
"""

import os, json, time, datetime, urllib.request, urllib.parse, re
import xml.etree.ElementTree as ET

# ════════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ — можно редактировать
# ════════════════════════════════════════════════════════════════════════

DAYS_BACK = 35
OUTPUT_DIR = "reports"

PUBMED_QUERIES = [
    "cerebral palsy surgery children",
    "cerebral palsy spasticity management children",
    "cerebral palsy upper extremity tendon transfer children",
    "spastic hand hemiplegia surgery pediatric",
    "pronator teres rerouting forearm supination cerebral palsy",
    "cerebral palsy lower extremity gait surgery",
    "cerebral palsy equinus foot surgery children",
    "crouch gait cerebral palsy surgery hamstrings",
    "hip displacement cerebral palsy surveillance reconstruction",
    "spastic hip dislocation cerebral palsy surgery",
    "neuromuscular scoliosis cerebral palsy spinal fusion",
    "selective dorsal rhizotomy cerebral palsy outcomes",
    "botulinum toxin spasticity children cerebral palsy",
    "intrathecal baclofen cerebral palsy pump children",
    "selective peripheral neurotomy spasticity children",
    "tibial nerve neurotomy spastic foot",
    "peripheral neurotomy spasticity upper limb",
    "nerve reinnervation tendon transfer pediatric",
    "exoskeleton rehabilitation cerebral palsy children",
    "robotic gait training spastic children",
    "functional electrical stimulation cerebral palsy children",
    "spina bifida myelomeningocele orthopedic surgery children",
    "neuromuscular disease orthopedic pediatric treatment",
    "rare genetic musculoskeletal disease pediatric surgery",
    "deep brain stimulation dystonia children",
    "hyperselective neurectomy spastic upper extremity pediatric",
]

RSS_FEEDS = {
    "ОТВХДВ (Турнера)":
        "https://journals.eco-vector.com/turner/gateway/plugin/WebFeedGatewayPlugin/rss2",
    "Вестник Приорова":
        "https://journals.eco-vector.com/0869-8678/gateway/plugin/WebFeedGatewayPlugin/rss2",
    "Травматология и ортопедия России":
        "https://journal.rniito.org/jour/gateway/plugin/WebFeedGatewayPlugin/rss2",
    "Хирургия позвоночника":
        "https://journal.spinaneurology.ru/spine/gateway/plugin/WebFeedGatewayPlugin/rss2",
    "Вопросы нейрохирургии":
        "https://www.mediasphera.ru/rss/1028-6403",
    "Dev Med Child Neurol":
        "https://onlinelibrary.wiley.com/action/showFeed?jc=14698749&type=etoc&feed=rss",
    "J Child Orthop":
        "https://journals.sagepub.com/action/showFeed?ui=0&mi=ehikzz&ai=2m&jc=coa&type=etoc&feed=rss",
    "J Pediatr Orthop":
        "https://feeds.journals.lww.com/jpo-online/pages/default.aspx?rss=1",
    "J Hand Surg Am":
        "https://www.jhandsurg.org/rss/S0363-5023",
    "J Neurosurg Pediatrics":
        "https://thejns.org/action/showFeed?type=etoc&feed=rss&jc=j-neurosurg-pediatr",
    "Childs Nerv Syst":
        "https://link.springer.com/search.rss?facet-content-type=Article&facet-journal-id=381",
    "Eur J Paediatr Neurol":
        "https://rss.sciencedirect.com/publication/science/10903798",
    "Gait & Posture":
        "https://rss.sciencedirect.com/publication/science/09666362",
    "Dev Neurorehabil":
        "https://www.tandfonline.com/action/showFeed?type=etoc&feed=rss&jc=ipdr20",
    "EFORT Open Rev":
        "https://online.boneandjoint.org.uk/action/showFeed?type=etoc&feed=rss&jc=eor",
}

CYBERLENINKA_QUERIES = [
    "детский церебральный паралич хирургия",
    "ДЦП нижняя конечность тазобедренный сустав",
    "спастичность невротомия дети",
    "ДЦП позвоночник сколиоз",
    "нейромышечная патология дети ортопедия",
    "спина бифида ортопедия",
    "экзоскелет реабилитация дети",
    "ботулотоксин спастичность дети",
]

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# ════════════════════════════════════════════════════════════════════════
#  СБОР
# ════════════════════════════════════════════════════════════════════════

def pubmed_search(query):
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
        print(f"    [!] {e}"); return []

def pubmed_fetch(pmids):
    if not pmids: return []
    params = urllib.parse.urlencode({"db":"pubmed","id":",".join(pmids),"retmode":"xml"})
    try:
        with urllib.request.urlopen(f"{PUBMED_BASE}/efetch.fcgi?{params}", timeout=25) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"    [!] {e}"); return []
    arts = []
    for art in root.findall(".//PubmedArticle"):
        try:
            pmid     = art.findtext(".//PMID", "")
            title    = art.findtext(".//ArticleTitle", "")
            abstract = " ".join(t.text or "" for t in art.findall(".//AbstractText"))
            authors  = []
            for a in art.findall(".//Author")[:4]:
                ln = a.findtext("LastName",""); fn = a.findtext("ForeName","")
                if ln: authors.append(f"{ln} {fn}".strip())
            journal  = art.findtext(".//Journal/Title","")
            year     = art.findtext(".//PubDate/Year","")
            doi      = next((x.text for x in art.findall(".//ArticleId") if x.get("IdType")=="doi"),"")
            if title:
                arts.append({"source":"PubMed","pmid":pmid,"title":title,"authors":authors,
                             "journal":journal,"year":year,"doi":doi,"abstract":abstract,
                             "url":f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/","lang":"en"})
        except: continue
    return arts

def collect_pubmed():
    seen, results = set(), []
    for q in PUBMED_QUERIES:
        print(f"  PubMed: {q[:55]}...")
        pmids = pubmed_search(q)
        new   = [p for p in pmids if p not in seen]
        seen.update(new)
        if new: results.extend(pubmed_fetch(new))
        time.sleep(0.35)
    return results

def fetch_rss(name, url):
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=DAYS_BACK)
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
    except Exception as e:
        print(f"    [!] {name}: {e}"); return []
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
                items.append({"source":name,"pmid":"","title":title,"authors":[],
                              "journal":name,"year":pub[:4] if pub else "","doi":"",
                              "abstract": re.sub(r'<[^>]+>','',desc)[:800],
                              "url":link,"lang":lang})
    except Exception as e:
        print(f"    [!] RSS parse {name}: {e}")
    return items

def collect_rss():
    results = []
    for name, url in RSS_FEEDS.items():
        print(f"  RSS: {name}")
        items = fetch_rss(name, url)
        print(f"       {len(items)} записей")
        results.extend(items)
        time.sleep(0.5)
    return results

def cyberleninka_search(query):
    year_min = datetime.date.today().year - 1
    url = f"https://cyberleninka.ru/search?q={urllib.parse.quote(query)}&datasource=article"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent":"Mozilla/5.0","Accept-Language":"ru-RU,ru;q=0.9"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    [!] КиберЛенинка: {e}"); return []
    items, seen = [], set()
    for m in re.finditer(r'href="(/article/n/([^"]+))"[^>]*>.*?<h\d[^>]*>(.*?)</h\d',
                         html, re.DOTALL):
        slug  = m.group(2)
        title = re.sub(r'<[^>]+>','',m.group(3)).strip()
        if not title or len(title)<8 or slug in seen: continue
        seen.add(slug)
        ctx   = html[m.start():m.start()+400]
        ym    = re.search(r'\b(20\d{2})\b', ctx)
        year  = ym.group(1) if ym else ""
        if year and int(year) < year_min: continue
        items.append({"source":"КиберЛенинка","pmid":"","title":title,"authors":[],
                      "journal":"КиберЛенинка","year":year,"doi":"","abstract":"",
                      "url":f"https://cyberleninka.ru/article/n/{slug}","lang":"ru"})
        if len(items) >= 12: break
    return items

def collect_cyberleninka():
    seen, results = set(), []
    for q in CYBERLENINKA_QUERIES:
        print(f"  КиберЛенинка: {q}")
        items = cyberleninka_search(q)
        for it in items:
            if it["url"] not in seen:
                seen.add(it["url"]); results.append(it)
        time.sleep(1.5)
    return results

# ════════════════════════════════════════════════════════════════════════
#  ИСТОРИЯ (дедупликация между запусками)
# ════════════════════════════════════════════════════════════════════════

HISTORY_FILE = os.path.join(OUTPUT_DIR, "seen_articles.json")
HISTORY_DAYS = 60

def load_history():
    if not os.path.exists(HISTORY_FILE): return {}
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_history(h):
    cutoff = (datetime.date.today() - datetime.timedelta(days=HISTORY_DAYS)).isoformat()
    clean  = {k:v for k,v in h.items() if v >= cutoff}
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

def art_key(a):
    if a.get("pmid"): return f"pmid:{a['pmid']}"
    if a.get("doi"):  return f"doi:{a['doi'].lower()}"
    if a.get("url"):  return f"url:{a['url']}"
    return f"title:{a.get('title','')[:60].lower()}"

def dedup(articles):
    history = load_history()
    today   = datetime.date.today().isoformat()
    new = []
    for a in articles:
        k = art_key(a)
        if k not in history:
            new.append(a)
            history[k] = today
    save_history(history)
    print(f"  Дедупликация: {len(new)} новых из {len(articles)}")
    return new

# ════════════════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ
# ════════════════════════════════════════════════════════════════════════

def save(articles, run_date):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"collected_{run_date}.json")
    # Сохраняем только нужные поля — компактно для вставки в Claude
    slim = []
    for a in articles:
        slim.append({
            "title":    a.get("title",""),
            "authors":  a.get("authors",[]),
            "journal":  a.get("journal",""),
            "year":     a.get("year",""),
            "source":   a.get("source",""),
            "lang":     a.get("lang","en"),
            "pmid":     a.get("pmid",""),
            "doi":      a.get("doi",""),
            "url":      a.get("url",""),
            "abstract": a.get("abstract","")[:1200],
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    return path

# ════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════

def main():
    run_date = datetime.date.today().isoformat()
    print(f"\n{'='*55}")
    print(f"  Сбор статей — {run_date}")
    print(f"{'='*55}\n")

    print("[1/3] PubMed...")
    pm = collect_pubmed()
    print(f"  → {len(pm)} статей\n")

    print("[2/3] RSS-ленты...")
    rss = collect_rss()
    print(f"  → {len(rss)} записей\n")

    print("[3/3] КиберЛенинка...")
    cl = collect_cyberleninka()
    print(f"  → {len(cl)} статей\n")

    all_arts = pm + rss + cl
    print("Дедупликация...")
    new_arts = dedup(all_arts)

    print("\nСохранение...")
    path = save(new_arts, run_date)

    print(f"\n{'='*55}")
    print(f"  Готово!")
    print(f"  Найдено новых статей: {len(new_arts)}")
    print(f"  Файл: {path}")
    print(f"{'='*55}")
    print(f"""
Следующий шаг:
  Откройте файл {path}
  Скопируйте содержимое
  Вставьте в Claude.ai со словами:
  "Проанализируй эти статьи и сделай PDF-отчёт"
""")

if __name__ == "__main__":
    main()
