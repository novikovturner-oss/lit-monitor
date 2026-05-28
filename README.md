# Мониторинг научных публикаций

Автоматический поиск и анализ новых публикаций по детской нейроортопедии и ДЦП.

**Источники:** PubMed / MEDLINE, Cochrane Library, J Hand Surg Am, J Pediatr Orthop, Dev Med Child Neurol  
**Расписание:** каждый понедельник в 10:00 МСК  
**Отчёт:** публикуется на GitHub Pages этого репозитория

---

## Первоначальная настройка (один раз)

### 1. Создать репозиторий на GitHub

Нажмите **«Use this template»** или создайте новый публичный репозиторий и загрузите эти файлы.

### 2. Добавить API-ключ Anthropic

1. Откройте `Settings` → `Secrets and variables` → `Actions`
2. Нажмите **New repository secret**
3. Имя: `ANTHROPIC_API_KEY`, значение: ваш ключ с [console.anthropic.com](https://console.anthropic.com)

### 3. Включить GitHub Pages

1. Откройте `Settings` → `Pages`
2. Source: **Deploy from a branch**
3. Branch: `main`, папка: `/reports`
4. Сохранить

Отчёт будет доступен по адресу: `https://<ваш-логин>.github.io/<имя-репо>/`

### 4. Первый запуск вручную

Перейдите на вкладку **Actions** → **Weekly Literature Monitor** → **Run workflow**.  
Первый отчёт появится через 2–3 минуты.

---

## Настройка поисковых запросов

Откройте `scripts/monitor.py` и отредактируйте список `PUBMED_QUERIES`:

```python
PUBMED_QUERIES = [
    "cerebral palsy upper extremity surgery",
    "pronator teres rerouting hemiplegia",
    "spastic hand children surgery",
    "forearm supination cerebral palsy",
    # Добавьте свои запросы:
    # "spina bifida orthopedic treatment",
    # "rare disease musculoskeletal pediatric",
]
```

Чтобы изменить период поиска — найдите строку `DAYS_BACK = 30` и замените цифру.

---

## Локальный запуск (для тестирования)

```bash
# Установить Python 3.8+, затем:
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/monitor.py
# Отчёт появится в папке reports/
```

---

## Структура проекта

```
lit-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml     # расписание GitHub Actions
├── scripts/
│   └── monitor.py          # основной скрипт
├── reports/                # отчёты (создаются автоматически)
│   ├── index.html          # последний отчёт (GitHub Pages)
│   └── report_YYYY-MM-DD.html
└── README.md
```
