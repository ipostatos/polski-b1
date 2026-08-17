#!/usr/bin/env python3
"""Собирает рабочую тетрадь B1 в PDF.

Источники содержания:
  data/exam_structure.json        — разобранный формат экзамена
  data/cwiczenia_gramatyka.json   — авторские упражнения в экзаменационном формате
  data/szablony.json              — каркасы письма и говорения

Запуск:  python workbook/build_workbook.py
Выход:   workbook/Zeszyt_B1.pdf
"""
from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "workbook" / "Zeszyt_B1.pdf"

INK = colors.HexColor("#1B1B1F")
MUTED = colors.HexColor("#6B6B75")
ACCENT = colors.HexColor("#8B1E3F")
LINE = colors.HexColor("#D8D8DE")
BAND = colors.HexColor("#F4F1F2")
GREEN = colors.HexColor("#2E6B4F")

FONTS = Path("C:/Windows/Fonts")


def register_fonts() -> tuple[str, str, str]:
    """Регистрирует шрифт с полной польской диакритикой."""
    for base, bold, italic, name in (
        ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "Calibri"),
        ("arial.ttf", "arialbd.ttf", "ariali.ttf", "Arial"),
    ):
        if (FONTS / base).exists():
            pdfmetrics.registerFont(TTFont(name, str(FONTS / base)))
            pdfmetrics.registerFont(TTFont(name + "-B", str(FONTS / bold)))
            pdfmetrics.registerFont(TTFont(name + "-I", str(FONTS / italic)))
            # без этого теги <b> и <i> внутри Paragraph молча игнорируются
            pdfmetrics.registerFontFamily(name, normal=name, bold=name + "-B",
                                          italic=name + "-I", boldItalic=name + "-B")
            return name, name + "-B", name + "-I"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


REG, BOLD, ITAL = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    s = {
        "h1": ParagraphStyle("h1", parent=ss["Normal"], fontName=BOLD, fontSize=20,
                             leading=24, textColor=INK, spaceAfter=3 * mm),
        "h2": ParagraphStyle("h2", parent=ss["Normal"], fontName=BOLD, fontSize=13,
                             leading=17, textColor=ACCENT, spaceBefore=6 * mm,
                             spaceAfter=2 * mm),
        "h3": ParagraphStyle("h3", parent=ss["Normal"], fontName=BOLD, fontSize=10.5,
                             leading=14, textColor=INK, spaceBefore=3.5 * mm,
                             spaceAfter=1.5 * mm),
        "p": ParagraphStyle("p", parent=ss["Normal"], fontName=REG, fontSize=9.5,
                            leading=14, textColor=INK, alignment=TA_JUSTIFY,
                            spaceAfter=2 * mm),
        "task": ParagraphStyle("task", parent=ss["Normal"], fontName=REG, fontSize=9.5,
                               leading=17, textColor=INK, alignment=TA_JUSTIFY,
                               spaceAfter=2 * mm),
        "note": ParagraphStyle("note", parent=ss["Normal"], fontName=ITAL, fontSize=8.5,
                               leading=12, textColor=MUTED, spaceAfter=2 * mm),
        "cell": ParagraphStyle("cell", parent=ss["Normal"], fontName=REG, fontSize=8.5,
                               leading=11.5, textColor=INK),
        "cellb": ParagraphStyle("cellb", parent=ss["Normal"], fontName=BOLD, fontSize=8.5,
                                leading=11.5, textColor=INK),
        "key": ParagraphStyle("key", parent=ss["Normal"], fontName=REG, fontSize=8.5,
                              leading=12, textColor=INK, spaceAfter=1 * mm),
        "cover": ParagraphStyle("cover", parent=ss["Normal"], fontName=BOLD, fontSize=34,
                                leading=38, textColor=INK, alignment=TA_CENTER),
        "coversub": ParagraphStyle("coversub", parent=ss["Normal"], fontName=REG,
                                   fontSize=12, leading=18, textColor=MUTED,
                                   alignment=TA_CENTER),
    }
    return s


S = styles()


def para(text: str, style: str = "p") -> Paragraph:
    return Paragraph(text, S[style])


def rule(space_before: float = 1.5 * mm) -> Table:
    t = Table([[""]], colWidths=[170 * mm], rowHeights=[0.6])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, LINE)]))
    return t


def band(title: str, subtitle: str = "") -> Table:
    """Плашка-заголовок раздела."""
    inner = [[para(title, "h2")]]
    if subtitle:
        inner.append([para(subtitle, "note")])
    t = Table(inner, colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
    ]))
    return t


def grid(rows: list[list], widths: list[float], header: bool = True,
         align_center: list[int] | None = None,
         row_heights: list[float] | None = None) -> Table:
    t = Table(rows, colWidths=widths, rowHeights=row_heights,
              repeatRows=1 if header else 0)
    st = [
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), BAND)]
    for c in align_center or []:
        st.append(("ALIGN", (c, 0), (c, -1), "CENTER"))
    t.setStyle(TableStyle(st))
    return t


def lines(n: int, width: float = 170 * mm, gap: float = 8 * mm) -> Table:
    """Линованное поле для письма от руки."""
    t = Table([[""]] * n, colWidths=[width], rowHeights=[gap] * n)
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def boxes(n: int, per_row: int = 10, label: str = "") -> Table:
    """Клетки для ответов бланка."""
    rows: list[list] = []
    i = 1
    while i <= n:
        nums, cells = [], []
        for j in range(per_row):
            if i + j <= n:
                nums.append(Paragraph(f"<font size=7 color='#6B6B75'>{i + j}</font>", S["cell"]))
                cells.append("")
            else:
                nums.append("")
                cells.append("")
        rows += [nums, cells]
        i += per_row
    w = 170 * mm / per_row
    t = Table(rows, colWidths=[w] * per_row,
              rowHeights=[4.5 * mm, 9 * mm] * (len(rows) // 2))
    st = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]
    for r in range(1, len(rows), 2):
        st.append(("GRID", (0, r), (-1, r), 0.5, LINE))
    t.setStyle(TableStyle(st))
    return t


# --------------------------------------------------------------------------- разделы


def cover(story: list) -> None:
    story += [
        Spacer(1, 55 * mm),
        para("ZESZYT B1", "cover"),
        Spacer(1, 4 * mm),
        para("Rabочая тетрадь к государственному экзамену<br/>"
             "z języka polskiego jako obcego", "coversub"),
        Spacer(1, 14 * mm),
    ]
    t = Table([["Poziom", "B1 — poziom progowy"],
               ["Grupa", "dorośli"],
               ["Data egzaminu", "17 października 2026"],
               ["Próg zdania", "50% z każdego z pięciu modułów"]],
              colWidths=[45 * mm, 75 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), BOLD, 9.5),
        ("FONT", (1, 0), (1, -1), REG, 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), MUTED),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [t, Spacer(1, 30 * mm),
              para("Тетрадь построена обратным способом: не «глава 1 → глава 20», "
                   "а от разбора 15 официальных сессий экзамена 2021–2024 "
                   "к точечной тренировке того, что в них повторяется.", "note"),
              PageBreak()]


def mapa_egzaminu(story: list, struct: dict) -> None:
    story += [band("Карта экзамена", "Одна страница, которую надо знать наизусть")]
    rows = [[para("Модуль", "cellb"), para("Время", "cellb"), para("Заданий", "cellb"),
             para("Баллов", "cellb"), para("Порог", "cellb"), para("Цель", "cellb")]]
    for name, key, zad, pts, prog, cel in (
        ("Rozumienie ze słuchu", "sluchanie", "5", "30", "15", "22"),
        ("Rozumienie tekstów pisanych", "czytanie", "5", "30", "15", "23"),
        ("Poprawność gramatyczna", "gramatyka", "8", "30", "15", "22"),
        ("Pisanie", "pisanie", "1 zestaw = 2 prace", "30", "15", "21"),
        ("Mówienie", "mowienie", "3", "40", "20", "28"),
    ):
        czas = struct["moduly"][key]["czas"]
        rows.append([para(name, "cell"), para(czas, "cell"), para(zad, "cell"),
                     para(pts, "cell"), para(prog, "cell"),
                     Paragraph(f"<font color='#2E6B4F'><b>{cel}</b></font>", S["cell"])])
    story += [grid(rows, [52 * mm, 25 * mm, 30 * mm, 20 * mm, 18 * mm, 18 * mm],
                   align_center=[2, 3, 4, 5]), Spacer(1, 4 * mm)]

    story += [para("<b>Порога «в среднем» не существует.</b> Пять независимых порогов: "
                   "49% в одном модуле — экзамен не сдан, даже если остальные на 90%.", "p")]

    story += [para("Три вещи, которые решают больше всего", "h3")]
    for txt in (
        "<b>Аудирование, задание I звучит ОДИН раз.</b> Это 14 микровысказываний и "
        "7 баллов из 30. Остальные четыре задания — дважды. Проверено во всех 15 сессиях.",
        "<b>Грамматика предсказуема полностью.</b> С 2021 года те же 8 заданий, в том же "
        "порядке, с теми же баллами. Четыре из них дают 20 баллов из 30.",
        "<b>В письме объём — это балл.</b> Попадание в 30 и 170 слов оценивается отдельным "
        "подкритерием: 2 балла из 30 модуля просто за длину.",
    ):
        story += [para("• " + txt, "p")]

    story += [para("Порядок и тайминг письменной части", "h3"),
              grid([[para("Модуль", "cellb"), para("Лимит", "cellb"),
                     para("Сколько на задание", "cellb")],
                    [para("Rozumienie ze słuchu", "cell"), para("do 30 minut", "cell"),
                     para("темп задаёт запись", "cell")],
                    [para("Rozumienie tekstów", "cell"), para("45 minut", "cell"),
                     para("≈ 9 минут на задание", "cell")],
                    [para("Poprawność gramatyczna", "cell"), para("45 minut", "cell"),
                     para("≈ 5 минут на задание", "cell")],
                    [para("Pisanie", "cell"), para("75 minut", "cell"),
                     para("15 мин короткая + 50 длинная + 10 проверка", "cell")]],
                   [50 * mm, 30 * mm, 90 * mm]),
              PageBreak()]


def gramatyka_mapa(story: list) -> None:
    story += [band("Модуль грамматики: скелет из восьми заданий",
                   "Не менялся ни разу с 2021 по 2024 — проверено по 15 сессиям")]
    rows = [[para("№", "cellb"), para("Что делать", "cellb"),
             para("Что проверяют", "cellb"), para("Баллов", "cellb"),
             para("Приоритет", "cellb")]]
    data = [
        ("I", "подчеркнуть верную форму", "склонение существительных, прилагательных, местоимений", "5,0", "1"),
        ("II", "вставить из рамки", "союзы", "2,5", "6"),
        ("III", "подчеркнуть верную форму", "степени сравнения", "2,5", "7"),
        ("IV", "вписать форму", "времена", "5,0", "3"),
        ("V", "задать вопрос", "вопросительные слова и падеж", "2,5", "5"),
        ("VI", "перестроить предложение", "трансформации", "5,0", "4"),
        ("VII", "подчеркнуть верную форму", "вид и наклонения", "5,0", "2"),
        ("VIII", "вставить из рамки", "предлоги", "2,5", "8"),
    ]
    for nr, co, spr, pts, prio in data:
        strong = pts == "5,0"
        st = "cellb" if strong else "cell"
        rows.append([para(nr, "cellb"), para(co, "cell"), para(spr, "cell"),
                     para(pts, st), para(prio, "cell")])
    story += [grid(rows, [12 * mm, 42 * mm, 66 * mm, 18 * mm, 20 * mm],
                   align_center=[0, 3, 4]),
              Spacer(1, 3 * mm),
              para("Задания <b>I, IV, VI, VII</b> дают <b>20 баллов из 30</b>. Порог модуля — 15. "
                   "Значит, закрыв склонение, времена, трансформации и вид, порог берётся "
                   "даже при нуле за союзы, степени, вопросы и предлоги. Отсюда порядок "
                   "тренировки: I → VII → IV → VI, остальное вторым слоем.", "p"),
              para("Задание VI — единственное, где ошибка стоит целый балл, а не половину. "
                   "Самое дорогое задание модуля в пересчёте на пункт.", "note"),
              PageBreak()]


def cwiczenia(story: list, cw: dict) -> None:
    """Упражнения по восьми типам заданий."""
    story += [band("Ćwiczenia", "Формат экзаменационный, тексты авторские. Ключи — в конце тетради.")]
    for z in cw["zadania"]:
        for zestaw in z["zestawy"]:
            head = (f"Zadanie {z['nr']} · {zestaw['id']} "
                    f"<font color='#6B6B75'>— {z['sprawdza']} · {str(z['punkty']).replace('.', ',')} p.</font>")
            block: list = [para(head, "h3"), para(z["polecenie"], "note")]

            if "tekst" in zestaw:
                txt = zestaw["tekst"]
                for luka in zestaw["luki"]:
                    n = luka["nr"]
                    if "opcje" in luka:
                        opts = ", ".join(luka["opcje"])
                        repl = f"<b>(</b>{opts}<b>)</b><super>{n}</super>"
                    else:
                        repl = ("……………………<super>%d</super> <i>(%s)</i>"
                                % (n, luka["podstawa"]))
                    txt = txt.replace("{%d}" % n, repl)
                block.append(para(txt, "task"))

            elif "zdania" in zestaw and "ramka" in zestaw:
                ramka = Table([[Paragraph(
                    "&nbsp;&nbsp;&nbsp;".join(f"<b>{w}</b>" for w in zestaw["ramka"]),
                    S["cell"])]], colWidths=[170 * mm])
                ramka.setStyle(TableStyle([
                    ("BOX", (0, 0), (-1, -1), 0.8, MUTED),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                block += [ramka, Spacer(1, 2 * mm)]
                for zd in zestaw["zdania"]:
                    block.append(para(f"{zd['nr']}. {zd['tekst']}", "task"))

            elif "zdania" in zestaw and z["nr"] == "V":
                for zd in zestaw["zdania"]:
                    zdanie = zd["zdanie"].replace(
                        zd["podkreslone"], f"<u>{zd['podkreslone']}</u>")
                    block.append(para(f"{zd['nr']}. {zdanie}", "task"))
                    block.append(lines(1, 170 * mm, 7 * mm))
                    block.append(Spacer(1, 1.5 * mm))

            elif "zdania" in zestaw:
                for zd in zestaw["zdania"]:
                    block.append(para(
                        f"{zd['nr']}. {zd['zdanie']} <b>({zd['wyraz']})</b>", "task"))
                    block.append(lines(1, 170 * mm, 7 * mm))
                    block.append(Spacer(1, 1.5 * mm))

            block.append(Spacer(1, 4 * mm))
            story.append(KeepTogether(block))
    story.append(PageBreak())


def klucz(story: list, cw: dict) -> None:
    story += [band("Klucz", "Ответы к упражнениям с объяснением, почему именно так")]
    for z in cw["zadania"]:
        for zestaw in z["zestawy"]:
            rows = [[para("№", "cellb"), para("Odpowiedź", "cellb"),
                     para("Dlaczego", "cellb")]]
            if "luki" in zestaw:
                for l in zestaw["luki"]:
                    rows.append([para(str(l["nr"]), "cell"),
                                 para(f"<b>{l['klucz']}</b>", "cell"),
                                 para(l["dlaczego"], "cell")])
            elif "zdania" in zestaw:
                for zd in zestaw["zdania"]:
                    rows.append([para(str(zd["nr"]), "cell"),
                                 para(f"<b>{zd['klucz']}</b>", "cell"),
                                 para(zd.get("dlaczego", ""), "cell")])
            blk = [para(f"Zadanie {z['nr']} · {zestaw['id']}", "h3"),
                   grid(rows, [10 * mm, 55 * mm, 105 * mm], align_center=[0])]
            if "zbedny" in zestaw:
                blk.append(para(f"Niepotrzebny wyraz w ramce: <b>{zestaw['zbedny']}</b>",
                                "note"))
            blk.append(Spacer(1, 3 * mm))
            story.append(KeepTogether(blk))
    story.append(PageBreak())


def pisanie(story: list, sz: dict) -> None:
    p = sz["pisanie"]
    story += [band("Pisanie", "Обе работы оцениваются вместе. Каркасы, а не готовые сочинения.")]

    story += [para("Как считают баллы", "h3")]
    rows = [[para("Критерий", "cellb"), para("Из чего складывается", "cellb"),
             para("У каждого<br/>экзаменатора", "cellb")],
            [para("1. Wykonanie zadania", "cell"),
             para("treść 2,5 + forma 1,5 + <b>objętość 1,0</b>", "cell"), para("5", "cell")],
            [para("2. Środki językowe", "cell"),
             para("leksyka 2 + składnia 2 + styl 1", "cell"), para("5", "cell")],
            [para("3. Poprawność językowa", "cell"),
             para("<b>gramatyka 3,5</b> + ortografia i interpunkcja 1,5", "cell"),
             para("5", "cell")],
            [para("<b>RAZEM</b>", "cellb"),
             para("два экзаменатора, баллы суммируются", "cell"),
             para("<b>15 + 15 = 30</b>", "cellb")]]
    story += [grid(rows, [42 * mm, 98 * mm, 30 * mm], align_center=[2]),
              Spacer(1, 3 * mm),
              para(f"<b>Объём.</b> {p['kontrola_objetosci']['zasada']} "
                   f"{p['kontrola_objetosci']['metoda']} "
                   f"Ориентир: {p['kontrola_objetosci']['orientacyjnie']} "
                   f"{p['kontrola_objetosci']['uwaga']}", "p")]

    for tytul, lista in (("Короткая работа (a)", p["krotkie"]),
                         ("Длинная работа (b)", p["dlugie"])):
        story += [para(tytul, "h2")]
        for g in lista:
            rows = [[para(f"<b>{g['gatunek']}</b> <font color='#6B6B75'>· {g['slow']} слов · "
                          f"{g['kiedy']}</font>", "cell")],
                    [para("<b>Каркас:</b> " + " → ".join(g["szkielet"]), "cell")],
                    [para("<b>Конструкции:</b><br/>" +
                          "<br/>".join("• " + z for z in g["zwroty"]), "cell")],
                    [para(f"<font color='#8B1E3F'><b>Ловушка:</b> {g['pulapka']}</font>",
                          "cell")]]
            t = Table(rows, colWidths=[170 * mm])
            t.setStyle(TableStyle([
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), BAND),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(KeepTogether([t, Spacer(1, 3 * mm)]))
    story.append(PageBreak())


def mowienie(story: list, sz: dict) -> None:
    m = sz["mowienie"]
    story += [band("Mówienie", "Материалы устной части не публикуются — каркасы собраны "
                               "по официальному сборнику 6_B1_M")]
    for key in ("zadanie1_opis", "zadanie2_monolog", "zadanie3_sytuacja"):
        z = m[key]
        rows = [[para(f"<b>{z['nazwa']}</b>", "cell")],
                [para("<b>Каркас:</b> " + " → ".join(z["szkielet"]), "cell")],
                [para("<b>Конструкции:</b><br/>" +
                      "<br/>".join("• " + w for w in z["zwroty"]), "cell")],
                [para(f"<font color='#8B1E3F'><b>Чего не делать:</b> {z['czego_unikac']}</font>",
                      "cell")]]
        t = Table(rows, colWidths=[170 * mm])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(KeepTogether([t, Spacer(1, 3 * mm)]))

    story += [para("Спасательные фразы", "h3"),
              para(m["ratunkowe"]["opis"], "note")]
    story += [para("&nbsp;&nbsp;• " + w, "task") for w in m["ratunkowe"]["zwroty"]]

    story += [para("Произношение: пары, которые проверяют", "h3"),
              para(m["wymowa"]["opis"], "note")]
    rows = [[para("Оппозиция", "cellb"), para("Пример", "cellb")]]
    for a, b in m["wymowa"]["pary"]:
        rows.append([para(f"<b>{a}</b>", "cell"), para(b, "cell")])
    story += [grid(rows, [40 * mm, 130 * mm]), Spacer(1, 2 * mm),
              para(m["wymowa"]["akcent"], "p"), PageBreak()]


def karta_odpowiedzi(story: list) -> None:
    story += [band("Karta odpowiedzi", "Бланк для мока. Печатать по одному на каждую сессию.")]
    story += [grid([[para("Sesja", "cellb"), para("Data", "cellb"), para("Czas startu", "cellb")],
                    [para("", "cell"), para("", "cell"), para("", "cell")]],
                   [70 * mm, 50 * mm, 50 * mm]), Spacer(1, 5 * mm)]

    for tytul, zad in (("Rozumienie ze słuchu — 30 p.",
                        [("I", 14), ("II", 8), ("III", 8), ("IV", 6), ("V", 6)]),
                       ("Rozumienie tekstów pisanych — 30 p.",
                        [("I", 6), ("II", 7), ("III", 8), ("IV", 7), ("V", 5)])):
        story += [para(tytul, "h3")]
        for nr, n in zad:
            story += [para(f"Zadanie {nr}", "note"), boxes(n), Spacer(1, 2 * mm)]
        story.append(Spacer(1, 3 * mm))

    story.append(PageBreak())
    story += [para("Poprawność gramatyczna — 30 p.", "h3")]
    for nr, n in (("I", 10), ("II", 5), ("III", 5), ("IV", 10), ("VII", 10), ("VIII", 5)):
        story += [para(f"Zadanie {nr}", "note"), boxes(n), Spacer(1, 2 * mm)]
    story += [para("Zadanie V (pytania) i VI (transformacje) — на линованном поле", "note"),
              lines(10), Spacer(1, 4 * mm)]

    story += [para("Wynik", "h3"),
              grid([[para("Moduł", "cellb"), para("Punkty", "cellb"),
                     para("%", "cellb"), para("Status", "cellb")]] +
                   [[para(n, "cell"), para(f"____ / {p}", "cell"), para("____", "cell"),
                     para("", "cell")]
                    for n, p in (("Słuchanie", 30), ("Czytanie", 30), ("Gramatyka", 30),
                                 ("Pisanie", 30), ("Mówienie", 40))],
                   [60 * mm, 40 * mm, 30 * mm, 40 * mm], align_center=[1, 2, 3]),
              PageBreak()]


def karta_pisania(story: list) -> None:
    story += [band("Karta oceny pisania", "Официальная сетка из экзаменационного аркуша")]
    rows = [[para("", "cellb"), para("Oceniane są", "cellb"),
             para("Egz. A", "cellb"), para("Egz. B", "cellb"), para("Razem", "cellb")],
            [para("1.", "cell"),
             para("wykonanie zadania<br/>treść ___/2,5 &nbsp; forma ___/1,5 &nbsp; objętość ___/1",
                  "cell"), para("___ / 5", "cell"), para("___ / 5", "cell"),
             para("___ / 10", "cell")],
            [para("2.", "cell"),
             para("środki językowe<br/>leksyka ___/2 &nbsp; składnia ___/2 &nbsp; styl ___/1",
                  "cell"), para("___ / 5", "cell"), para("___ / 5", "cell"),
             para("___ / 10", "cell")],
            [para("3.", "cell"),
             para("poprawność językowa<br/>gramatyka ___/3,5 &nbsp; ortografia i interpunkcja ___/1,5",
                  "cell"), para("___ / 5", "cell"), para("___ / 5", "cell"),
             para("___ / 10", "cell")],
            [para("", "cell"), para("<b>RAZEM</b>", "cellb"), para("___ / 15", "cellb"),
             para("___ / 15", "cellb"), para("<b>___ / 30</b>", "cellb")]]
    story += [grid(rows, [10 * mm, 92 * mm, 22 * mm, 22 * mm, 24 * mm],
                   align_center=[2, 3, 4]), Spacer(1, 4 * mm)]

    story += [para("Liczba błędów", "h3"),
              grid([[para("gramatyczne", "cellb"), para("leksykalne", "cellb"),
                     para("stylistyczne", "cellb"),
                     para("ortograficzne + interpunkcyjne", "cellb")],
                    [para("", "cell")] * 4],
                   [40 * mm, 40 * mm, 40 * mm, 50 * mm]), Spacer(1, 4 * mm)]

    story += [para("Objętość prac", "h3"),
              grid([[para("", "cellb"), para("napisano", "cellb"), para("wymagane", "cellb"),
                     para("%", "cellb")],
                    [para("praca a)", "cell"), para("", "cell"), para("", "cell"), para("", "cell")],
                    [para("praca b)", "cell"), para("", "cell"), para("", "cell"), para("", "cell")]],
                   [40 * mm, 45 * mm, 45 * mm, 40 * mm]), Spacer(1, 4 * mm)]

    story += [para("Recenzja", "h3"), lines(8), PageBreak()]


def error_map(story: list) -> None:
    story += [band("Error Map", "Журнал ошибок. Категория, повторившаяся трижды, "
                                "получает больше упражнений.")]
    kody = [("CASE-GEN", "dopełniacz"), ("CASE-DAT", "celownik"), ("CASE-ACC", "biernik"),
            ("CASE-INS", "narzędnik"), ("CASE-LOC", "miejscownik"), ("ASP", "aspekt"),
            ("TENSE", "czasy"), ("MOOD", "tryby"), ("PREP", "przyimki"),
            ("REKCJA", "управление глагола"), ("CONJ", "spójniki"),
            ("COMP", "stopniowanie"), ("NUM", "liczebniki"), ("WO", "szyk zdania"),
            ("LEX", "leksyka"), ("ORTH", "ortografia i interpunkcja"),
            ("REG", "rejestr / styl"), ("TASK", "не выполнено условие задания")]
    rows, buf = [], []
    for i, (k, v) in enumerate(kody, 1):
        buf += [para(f"<b>{k}</b>", "cell"), para(v, "cell")]
        if i % 3 == 0:
            rows.append(buf)
            buf = []
    if buf:
        buf += [para("", "cell")] * (6 - len(buf))
        rows.append(buf)
    story += [grid(rows, [22 * mm, 34 * mm] * 3, header=False), Spacer(1, 5 * mm)]

    for _ in range(2):
        rows = [[para("Kod", "cellb"), para("❌ Как написал", "cellb"),
                 para("✅ Как правильно", "cellb"), para("Почему", "cellb")]]
        rows += [[para("", "cell")] * 4 for _ in range(11)]
        t = grid(rows, [22 * mm, 50 * mm, 50 * mm, 48 * mm],
                 row_heights=[7 * mm] + [13 * mm] * (len(rows) - 1))
        story += [t, PageBreak()]


def plan(story: list) -> None:
    story += [band("План на 8 недель", "17.08 → 17.10.2026")]
    rows = [[para("Неделя", "cellb"), para("Даты", "cellb"), para("Фокус", "cellb"),
             para("Экзамен из архива", "cellb"), para("✓", "cellb")]]
    for w, d, f, e in (
        ("1", "17–23.08", "ДИАГНОСТИКА, ничего не учим", "2021-11 (сжигаем)"),
        ("2", "24–30.08", "грамматика: задания I и VII", "2021-01 по частям"),
        ("3", "31.08–06.09", "грамматика: IV и VI, старт письма", "2021-05, 2021-06"),
        ("4", "07–13.09", "грамматика: мелочь II, III, V, VIII", "2022-02, 2022-03"),
        ("5", "14–20.09", "чтение и аудирование под таймер", "2022-06, 2022-11"),
        ("6", "21–27.09", "полные письменные модули", "2023-02, 2023-04, 2023-06"),
        ("7", "28.09–04.10", "EXAM MODE, полный мок 03.10", "2023-11"),
        ("8", "05–11.10", "стабилизация, мок 10.10", "2024-02"),
        ("9", "12–16.10", "финальный мок и снятие нагрузки", "2024-04"),
    ):
        rows.append([para(w, "cell"), para(d, "cell"), para(f, "cell"), para(e, "cell"),
                     para("", "cell")])
    story += [grid(rows, [16 * mm, 26 * mm, 68 * mm, 44 * mm, 12 * mm],
                   align_center=[0, 4]), Spacer(1, 4 * mm),
              para("Резерв 2024-06 не трогаем ни при каких условиях: это единственный "
                   "нетронутый комплект на случай, если что-то пойдёт не так.", "note"),
              Spacer(1, 4 * mm)]

    story += [para("Ежедневный режим", "h3"),
              grid([[para("День", "cellb"), para("Что", "cellb"), para("Сколько", "cellb")],
                    [para("Пн–Пт", "cell"),
                     para("gramatyka 20 · słuchanie 15 · czytanie 15 · mówienie 10–15; "
                          "через день часть блока заменяется на pisanie", "cell"),
                     para("60–75 мин", "cell")],
                    [para("Суббота", "cell"), para("экзаменационная практика", "cell"),
                     para("90–190 мин", "cell")],
                    [para("Воскресенье", "cell"),
                     para("разбор ошибок + лёгкий польский без напряжения", "cell"),
                     para("40 мин", "cell")]],
                   [26 * mm, 114 * mm, 30 * mm])]


# --------------------------------------------------------------------------- сборка


def on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont(REG, 7.5)
    canvas.setFillColor(MUTED)
    if doc.page > 1:
        canvas.drawString(20 * mm, 12 * mm, "Zeszyt B1 · egzamin 17.10.2026")
        canvas.drawRightString(190 * mm, 12 * mm, str(doc.page))
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.restoreState()


def main() -> int:
    struct = json.loads((DATA / "exam_structure.json").read_text(encoding="utf-8"))
    cw = json.loads((DATA / "cwiczenia_gramatyka.json").read_text(encoding="utf-8"))
    sz = json.loads((DATA / "szablony.json").read_text(encoding="utf-8"))

    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="Zeszyt B1", author="podręcznik własny")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=on_page)])

    story: list = []
    cover(story)
    mapa_egzaminu(story, struct)
    gramatyka_mapa(story)
    cwiczenia(story, cw)
    klucz(story, cw)
    pisanie(story, sz)
    mowienie(story, sz)
    karta_odpowiedzi(story)
    karta_pisania(story)
    error_map(story)
    plan(story)

    doc.build(story)
    print(f"готово: {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} КБ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
