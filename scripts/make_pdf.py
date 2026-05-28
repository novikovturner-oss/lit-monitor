"""
PDF-генератор отчёта мониторинга литературы.
python scripts/make_pdf.py reports/data_YYYY-MM-DD.json
"""

import json, sys, os, datetime, textwrap
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, NextPageTemplate
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

W, H = A4
MARGIN = 18 * mm

# ─── Цвета ────────────────────────────────────────────────────────────────────
C_NAVY    = colors.HexColor('#0d2137')
C_TEAL    = colors.HexColor('#1a7a6e')
C_AMBER   = colors.HexColor('#b86e00')
C_DGRAY   = colors.HexColor('#3a3a3a')
C_MGRAY   = colors.HexColor('#b0bac4')
C_LGRAY   = colors.HexColor('#f0f3f6')
C_RED     = colors.HexColor('#9a0e19')
C_PURPLE  = colors.HexColor('#52005a')
C_WHITE   = colors.white
C_BLACK   = colors.HexColor('#111111')
C_ACCENT  = colors.HexColor('#1a5276')
C_HIGH_BG = colors.HexColor('#e4f4f1')
C_MED_BG  = colors.HexColor('#fdf5e0')

# Цвета обложки
C_COVER_BG    = colors.HexColor('#0a1628')   # очень тёмный синий
C_COVER_STRIP = colors.HexColor('#1a7a6e')   # бирюзовая полоса
C_COVER_WHITE = colors.HexColor('#ffffff')
C_COVER_GOLD  = colors.HexColor('#f0c040')   # золотой — хорошо читается на тёмном
C_COVER_LIGHT = colors.HexColor('#d0e8f5')   # светло-голубой для второстепенного

SOURCE_COLORS = {
    'PubMed':                           C_NAVY,
    'КиберЛенинка':                     C_RED,
    'ОТВХДВ (Турнера)':                 C_PURPLE,
    'Вестник Приорова':                 C_PURPLE,
    'Травматология и ортопедия России': C_PURPLE,
    'Хирургия позвоночника':            C_PURPLE,
    'Вопросы нейрохирургии':            C_PURPLE,
    'Педиатрия им. Сперанского':        C_PURPLE,
}

# ─── Шрифты ───────────────────────────────────────────────────────────────────
def register_fonts():
    try:
        base = '/usr/share/fonts/truetype/dejavu/'
        pdfmetrics.registerFont(TTFont('DV',     base + 'DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DV-B',   base + 'DejaVuSans-Bold.ttf'))
        pdfmetrics.registerFont(TTFont('DV-I',   base + 'DejaVuSans-Oblique.ttf'))
        pdfmetrics.registerFont(TTFont('DV-BI',  base + 'DejaVuSans-BoldOblique.ttf'))
        return 'DV', 'DV-B', 'DV-I', 'DV-BI'
    except Exception:
        return 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique', 'Helvetica-BoldOblique'

F, FB, FI, FBI = register_fonts()

# ─── Стили ────────────────────────────────────────────────────────────────────
def S(name, **kw):
    return ParagraphStyle(name, **kw)

def make_styles():
    base = dict(fontName=F, fontSize=10, textColor=C_BLACK, leading=14)
    return {
        # Секции
        'sec':      S('sec',  fontName=FB, fontSize=13, textColor=C_NAVY,
                       leading=18, spaceBefore=14, spaceAfter=4),
        # Карточка — заголовок статьи
        'title':    S('title', fontName=FB, fontSize=11.5, textColor=C_BLACK,
                       leading=16),
        # Мета (авторы, журнал, год)
        'meta':     S('meta',  fontName=FI, fontSize=9, textColor=C_DGRAY,
                       leading=13),
        # Резюме Claude (2–3 предложения)
        'summary':  S('sum',   fontName=F,  fontSize=10.5, textColor=C_BLACK,
                       leading=15, spaceBefore=2),
        # Почему релевантно
        'why':      S('why',   fontName=FBI, fontSize=9.5, textColor=C_ACCENT,
                       leading=13),
        # Перевод абстракта — основной текст
        'abstract': S('abs',   fontName=F,  fontSize=9.5, textColor=C_DGRAY,
                       leading=14, spaceBefore=2),
        # Заголовок блока "Абстракт"
        'abs_head': S('absh',  fontName=FB, fontSize=8.5,
                       textColor=colors.HexColor('#666666'),
                       leading=11, spaceBefore=4),
        # Тезисы (буллеты)
        'bullet':   S('bul',   fontName=F,  fontSize=10, textColor=C_BLACK,
                       leading=14, leftIndent=8, firstLineIndent=-6),
        # Bullet-заголовок
        'bul_head': S('bulh',  fontName=FB, fontSize=9,
                       textColor=C_ACCENT, leading=12, spaceBefore=5),
        # Колонтитул
        'footer':   S('ftr',   fontName=F,  fontSize=7.5, textColor=C_MGRAY,
                       leading=10, alignment=TA_CENTER),
        # Статистика — число
        'stat_n':   S('stn',   fontName=FB, fontSize=24, textColor=C_NAVY,
                       leading=28, alignment=TA_CENTER),
        'stat_l':   S('stl',   fontName=F,  fontSize=8.5, textColor=C_DGRAY,
                       leading=11, alignment=TA_CENTER),
    }

# ─── Шаблон страниц ───────────────────────────────────────────────────────────
def _draw_cover(canvas, doc):
    """Рисует обложку через canvas — полный контроль над фоном."""
    canvas.saveState()
    # Тёмный фон
    canvas.setFillColor(C_COVER_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)

    # Бирюзовая вертикальная полоса слева
    canvas.setFillColor(C_COVER_STRIP)
    canvas.rect(0, 0, 8*mm, H, fill=1, stroke=0)

    # Горизонтальная золотая линия под заголовком (рисуется после текста)
    canvas.setStrokeColor(C_COVER_GOLD)
    canvas.setLineWidth(1.5)
    canvas.line(18*mm, H - 95*mm, W - 18*mm, H - 95*mm)

    # Нижняя бирюзовая полоса
    canvas.setFillColor(C_COVER_STRIP)
    canvas.rect(0, 0, W, 22*mm, fill=1, stroke=0)

    # Текст нижней полосы
    canvas.setFillColor(C_WHITE)
    canvas.setFont(FB, 8.5)
    canvas.drawString(18*mm, 8*mm,
        'НМИЦ детской травматологии и ортопедии им. Г.И. Турнера · Новиков В.А.')

    canvas.restoreState()


def _draw_content_page(canvas, doc):
    """Колонтитул на страницах контента."""
    canvas.saveState()
    # Тонкая линия вверху
    canvas.setStrokeColor(C_MGRAY)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN, H - 12*mm, W - MARGIN, H - 12*mm)
    canvas.setFont(F, 7.5)
    canvas.setFillColor(C_MGRAY)
    canvas.drawString(MARGIN, H - 10*mm, 'Мониторинг научных публикаций · Нейроортопедия · ДЦП')
    canvas.drawRightString(W - MARGIN, H - 10*mm, doc.run_date)
    # Линия внизу
    canvas.line(MARGIN, 14*mm, W - MARGIN, 14*mm)
    canvas.drawCentredString(W / 2, 9*mm, f'— {doc.page - 1} —')
    canvas.restoreState()


class ReportDoc(BaseDocTemplate):
    def __init__(self, path, run_date, **kw):
        super().__init__(path, **kw)
        self.run_date = run_date
        cover_frame   = Frame(0, 0, W, H, leftPadding=0, rightPadding=0,
                               topPadding=0, bottomPadding=0)
        content_frame = Frame(MARGIN, 20*mm, W - 2*MARGIN, H - 34*mm)
        self.addPageTemplates([
            PageTemplate(id='Cover',   frames=[cover_frame],
                         onPage=_draw_cover),
            PageTemplate(id='Content', frames=[content_frame],
                         onPage=_draw_content_page),
        ])


# ─── Элементы карточки ────────────────────────────────────────────────────────
def rel_badge(rel: int) -> Table:
    if rel >= 7:   bg, fg = C_TEAL,  C_WHITE
    elif rel >= 4: bg, fg = C_AMBER, C_WHITE
    else:          bg, fg = C_MGRAY, C_DGRAY
    s = S('rb', fontName=FB, fontSize=14, textColor=fg,
           alignment=TA_CENTER, leading=17)
    t = Table([[Paragraph(str(rel), s)]], colWidths=[12*mm], rowHeights=[12*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,0), bg),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0),(-1,-1), 0),
        ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    return t


def src_badge(source: str) -> Table:
    color = SOURCE_COLORS.get(source, C_ACCENT)
    s = S('sb', fontName=FB, fontSize=7.5, textColor=C_WHITE,
           alignment=TA_CENTER, leading=9)
    t = Table([[Paragraph(source[:18], s)]], colWidths=[32*mm], rowHeights=[7*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,0), color),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LEFTPADDING',   (0,0),(-1,-1), 4),
        ('RIGHTPADDING',  (0,0),(-1,-1), 4),
        ('TOPPADDING',    (0,0),(-1,-1), 0),
        ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    return t


def build_card(art: dict, styles: dict, pw: float) -> list:
    rel     = art.get('relevance', 0)
    title   = art.get('title',    '')[:220]
    authors = ', '.join(art.get('authors', [])[:4])
    if len(art.get('authors', [])) > 4: authors += ' et al.'
    journal = art.get('journal', '')
    year    = art.get('year', '')
    doi     = art.get('doi', '')
    url     = art.get('url', '')
    summary = art.get('summary_ru', '')
    why     = art.get('why_relevant', '')
    source  = art.get('source', '')
    abstract_ru = art.get('abstract_ru', '')   # переведённый абстракт
    bullets     = art.get('key_points', [])    # тезисы

    # Мета-строка
    meta_parts = []
    if authors: meta_parts.append(authors)
    if journal: meta_parts.append(f'<i>{journal}</i>')
    if year:    meta_parts.append(year)
    if doi:     meta_parts.append(f'DOI: {doi[:40]}')
    meta_str = '  ·  '.join(meta_parts)

    link_para = Paragraph(
        f'<link href="{url}"><font color="#1a5276">{"[PubMed]" if art.get("pmid") else "[ссылка]"}</font></link>',
        styles['meta']) if url else Paragraph('', styles['meta'])

    # Контент карточки
    items = [
        Paragraph(title, styles['title']),
        Spacer(1, 2*mm),
        Table([[src_badge(source), Spacer(4*mm, 1), link_para]],
              colWidths=[34*mm, 4*mm, None],
              style=[('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                     ('LEFTPADDING',(0,0),(-1,-1),0),
                     ('RIGHTPADDING',(0,0),(-1,-1),0),
                     ('TOPPADDING',(0,0),(-1,-1),0),
                     ('BOTTOMPADDING',(0,0),(-1,-1),0)]),
        Spacer(1, 1.5*mm),
        Paragraph(meta_str, styles['meta']),
    ]

    # Резюме Claude (всегда)
    if summary:
        items += [Spacer(1, 3*mm), Paragraph(summary, styles['summary'])]

    # Почему релевантно
    if why:
        items += [Spacer(1, 2*mm), Paragraph(f'▶ {why}', styles['why'])]

    # Тезисы — на что обратить внимание
    if bullets:
        items += [Spacer(1, 3*mm), Paragraph('На что обратить внимание:', styles['bul_head'])]
        for b in bullets[:5]:
            items.append(Paragraph(f'• {b}', styles['bullet']))

    # Перевод абстракта (если есть)
    if abstract_ru:
        items += [
            Spacer(1, 3*mm),
            HRFlowable(width=pw - 16*mm, thickness=0.4, color=C_MGRAY),
            Spacer(1, 2*mm),
            Paragraph('Аннотация:', styles['abs_head']),
            Paragraph(abstract_ru, styles['abstract']),
        ]

    row_bg = C_HIGH_BG if rel >= 7 else (C_MED_BG if rel >= 4 else C_WHITE)

    card = Table([[rel_badge(rel), items]],
                 colWidths=[14*mm, pw - 14*mm])
    card.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), row_bg),
        ('VALIGN',        (0,0),(0,0),   'TOP'),
        ('VALIGN',        (1,0),(1,0),   'TOP'),
        ('TOPPADDING',    (0,0),(-1,-1), 7),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LEFTPADDING',   (0,0),(0,0),   3),
        ('RIGHTPADDING',  (1,0),(1,0),   6),
        ('LINEBELOW',     (0,0),(-1,-1), 0.5, C_MGRAY),
    ]))
    return [KeepTogether([card])]


# ─── Обложка ──────────────────────────────────────────────────────────────────
def make_cover_story(styles, run_date, stats):
    """Текстовые элементы обложки поверх canvas-фона."""
    # Заголовок и подзаголовок — через canvas в _draw_cover,
    # но ReportLab не даёт рисовать произвольный текст в FlowTemplate напрямую.
    # Решение: Paragraph в прозрачном фрейме поверх canvas.
    story = []
    story.append(Spacer(1, 38*mm))

    # Главный заголовок — белый, крупный
    story.append(Paragraph(
        'Мониторинг научных публикаций',
        S('ct', fontName=FB, fontSize=34, textColor=C_COVER_WHITE,
          leading=42, alignment=TA_LEFT, leftIndent=10*mm)
    ))
    story.append(Spacer(1, 5*mm))

    # Подзаголовок — золотой, хорошо читается на тёмном
    story.append(Paragraph(
        'Нейроортопедия  ·  ДЦП  ·  Спастичность  ·  Новые технологии',
        S('cs', fontName=FBI, fontSize=14, textColor=C_COVER_GOLD,
          leading=20, alignment=TA_LEFT, leftIndent=10*mm)
    ))
    story.append(Spacer(1, 18*mm))  # место для золотой линии

    # Блок с датой и статистикой
    story.append(Paragraph(
        f'Дата отчёта:',
        S('cl', fontName=F, fontSize=10, textColor=C_COVER_LIGHT,
          leading=14, leftIndent=10*mm)
    ))
    story.append(Paragraph(
        run_date,
        S('cd', fontName=FB, fontSize=22, textColor=C_COVER_WHITE,
          leading=28, leftIndent=10*mm)
    ))
    story.append(Spacer(1, 8*mm))

    # Плашки со статистикой — горизонтальная таблица
    def cov_stat(label, val, color):
        sn = S('csn', fontName=FB, fontSize=28, textColor=color,
                leading=34, alignment=TA_CENTER)
        sl = S('csl', fontName=F,  fontSize=9,  textColor=C_COVER_LIGHT,
                leading=12, alignment=TA_CENTER)
        return [Paragraph(str(val), sn), Paragraph(label, sl)]

    stat_data = [[
        cov_stat('статей найдено',      stats['total'],   C_COVER_WHITE),
        cov_stat('высокорелевантных',   stats['high'],    C_COVER_GOLD),
        cov_stat('на русском языке',    stats['ru'],      colors.HexColor('#b0d4f1')),
    ]]
    cw = (W - 2*MARGIN - 20*mm) / 3
    stat_t = Table(stat_data, colWidths=[cw]*3, rowHeights=[30*mm])
    stat_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), colors.HexColor('#142035')),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('LINEAFTER',     (0,0),(1,-1),  0.5, colors.HexColor('#2a4a6a')),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
        ('RIGHTPADDING',  (0,0),(-1,-1), 0),
    ]))
    story.append(Table([[Spacer(10*mm, 1), stat_t]],
                       colWidths=[10*mm, W - 2*MARGIN - 10*mm],
                       style=[('LEFTPADDING',(0,0),(-1,-1),0),
                               ('RIGHTPADDING',(0,0),(-1,-1),0),
                               ('TOPPADDING',(0,0),(-1,-1),0),
                               ('BOTTOMPADDING',(0,0),(-1,-1),0)]))

    story.append(Spacer(1, 10*mm))

    # Источники
    story.append(Paragraph(
        f'Источники: PubMed ({stats.get("pm_queries","26")} запросов)  ·  '
        f'Российские журналы ({stats.get("rss_active","5")})  ·  КиберЛенинка',
        S('ci', fontName=FI, fontSize=9.5, textColor=C_COVER_LIGHT,
          leading=13, leftIndent=10*mm)
    ))
    story.append(PageBreak())
    return story


# ─── Статистический блок (стр. 2) ────────────────────────────────────────────
def make_stats_page(articles, styles, pw):
    high = sum(1 for a in articles if a.get('relevance', 0) >= 7)
    med  = sum(1 for a in articles if 4 <= a.get('relevance', 0) < 7)
    low  = sum(1 for a in articles if a.get('relevance', 0) < 4)
    ru   = sum(1 for a in articles if a.get('lang') == 'ru')
    en   = len(articles) - ru

    def cell(label, val, color):
        return [
            Paragraph(str(val), S('sv', fontName=FB, fontSize=24, textColor=color,
                                   alignment=TA_CENTER, leading=29)),
            Paragraph(label,    S('sl', fontName=F,  fontSize=8.5, textColor=C_DGRAY,
                                   alignment=TA_CENTER, leading=11)),
        ]

    cw = (pw - 2*mm) / 3
    data = [
        [cell('всего найдено',   len(articles), C_NAVY),
         cell('высокорелевантных', high,         C_TEAL),
         cell('средняя',         med,            C_AMBER)],
        [cell('низкая',          low,            C_MGRAY),
         cell('на русском',      ru,             C_PURPLE),
         cell('на английском',   en,             C_ACCENT)],
    ]
    t = Table(data, colWidths=[cw]*3, rowHeights=[26*mm]*2)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), C_LGRAY),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('GRID',          (0,0),(-1,-1), 0.5, C_WHITE),
        ('TOPPADDING',    (0,0),(-1,-1), 5),
        ('BOTTOMPADDING', (0,0),(-1,-1), 5),
    ]))
    return t


# ─── Главная функция ──────────────────────────────────────────────────────────
def generate_pdf(articles: list, run_date: str, output_path: str):
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    pw      = W - 2*MARGIN
    styles  = make_styles()
    sorted_arts = sorted(articles, key=lambda a: -a.get('relevance', 0))

    high = sum(1 for a in articles if a.get('relevance', 0) >= 7)
    ru   = sum(1 for a in articles if a.get('lang') == 'ru')

    doc = ReportDoc(
        output_path, run_date,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=14*mm,   bottomMargin=20*mm,
        title=f'Мониторинг литературы {run_date}',
        author='Новиков В.А.',
    )

    story = [NextPageTemplate('Cover')]

    # Обложка
    story += make_cover_story(styles, run_date, {
        'total': len(articles), 'high': high, 'ru': ru,
        'pm_queries': '26', 'rss_active': '5',
    })

    # Контент
    story.append(NextPageTemplate('Content'))

    # Статистика
    story.append(Paragraph('Сводная статистика', styles['sec']))
    story.append(make_stats_page(articles, styles, pw))
    story.append(Spacer(1, 10*mm))

    # Секции
    sections = [
        ('🔬 Высокая релевантность (7–10)',
         [a for a in sorted_arts if a.get('relevance', 0) >= 7]),
        ('📋 Средняя релевантность (4–6)',
         [a for a in sorted_arts if 4 <= a.get('relevance', 0) < 7]),
        ('📎 Низкая релевантность (1–3)',
         [a for a in sorted_arts if a.get('relevance', 0) < 4]),
    ]

    for sec_title, arts in sections:
        if not arts:
            continue
        story.append(HRFlowable(width=pw, thickness=2, color=C_NAVY, spaceAfter=4))
        story.append(Paragraph(
            f'{sec_title}  <font size="11" color="#666666">({len(arts)} статей)</font>',
            styles['sec']))
        story.append(Spacer(1, 3*mm))
        for art in arts:
            story += build_card(art, styles, pw)
        story.append(Spacer(1, 6*mm))

    doc.build(story)
    print(f'PDF сохранён: {output_path}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Использование: python scripts/make_pdf.py reports/data_YYYY-MM-DD.json')
        sys.exit(1)
    with open(sys.argv[1], encoding='utf-8') as f:
        arts = json.load(f)
    run_date = datetime.date.today().isoformat()
    out = sys.argv[1].replace('data_', 'report_').replace('.json', '.pdf')
    generate_pdf(arts, run_date, out)
