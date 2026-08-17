#!/usr/bin/env python3
"""Смоук-проверка собранной тетради: текст реально извлекается и не искалечен.

`test -s Zeszyt_B1.pdf` ловил только пустой файл: PDF с Helvetica вместо
шрифта с диакритикой выглядел бы «зелёным», хотя кириллица и ó/ż/ę в нём
превратились бы в мусор. Здесь проверяем содержимое.

Запуск: python tools/check_pdf.py   (нужен pymupdf)
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # pymupdf

PDF = Path(__file__).resolve().parent.parent / "workbook" / "Zeszyt_B1.pdf"

# фрагменты, которые обязаны читаться из PDF дословно
WYMAGANE = [
    "Рабочая тетрадь",          # кириллица на обложке (и не «Rabочая»)
    "17 października 2026",
    "Poprawność gramatyczna",   # польская диакритика: ś, ć
    "Zadanie VII",
    "ponieważ",                 # ż
    "przyjdą",                  # ą
    "61 день",                  # план на 9 недель, не «8 недель»
    "190 минут",                # актуальный тайминг письменной части
]

ZABRONIONE = [
    "Rabочая",                  # латинско-кириллический гибрид на обложке
    "План на 8 недель",
]


def main() -> int:
    if not PDF.exists() or PDF.stat().st_size == 0:
        print(f"нет файла: {PDF}", file=sys.stderr)
        return 1
    doc = fitz.open(PDF)
    text = "\n".join(page.get_text() for page in doc)
    bledy = []
    for frag in WYMAGANE:
        if frag not in text:
            bledy.append(f"не найдено: {frag!r}")
    for frag in ZABRONIONE:
        if frag in text:
            bledy.append(f"найдено запрещённое: {frag!r}")
    if bledy:
        for b in bledy:
            print(b, file=sys.stderr)
        return 1
    print(f"PDF в порядке: {len(doc)} страниц, {len(text)} символов текста")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
