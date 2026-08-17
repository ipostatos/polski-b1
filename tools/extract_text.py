#!/usr/bin/env python3
"""Извлекает текст из скачанных arkuszy и транскрипций в archive_text/.

Результат — рабочий материал для разбора, в репозиторий не коммитится.
PyMuPDF сохраняет польскую диакритику, pdftotext её теряет.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "archive"
DST = ROOT / "archive_text"

# 4-5.02.2024 / 2023_02_5_6 / 2022.02.6-7 -> единый ключ сессии YYYY-MM
SESSION_RE = [
    re.compile(r"^(?P<d>[\d.\-]+)\.(?P<m>\d{2})\.(?P<y>\d{4})-B1"),      # 4-5.02.2024-B1
    re.compile(r"^(?P<y>\d{4})_(?P<m>\d{2})_(?P<d>[\d_]+?)_B1"),          # 2023_02_5_6_B1
    re.compile(r"^(?P<y>\d{4})\.(?P<m>\d{2})\.(?P<d>[\d\-]+)_B1"),        # 2022.02.6-7_B1
]


def session_key(name: str) -> str:
    for rx in SESSION_RE:
        m = rx.match(name)
        if m:
            return f"{m.group('y')}-{m.group('m')}"
    raise ValueError(f"не разобрал имя файла: {name}")


def kind(name: str) -> str:
    low = name.lower()
    if "arkusz" in low:
        return "arkusz"
    if "transkrypcja" in low:
        return "transkrypcja"
    return "other"


def main() -> int:
    if not SRC.is_dir():
        print(f"нет папки {SRC}; сначала tools/fetch_archive.sh", file=sys.stderr)
        return 1
    DST.mkdir(exist_ok=True)
    done = 0
    for pdf in sorted(SRC.glob("*.pdf")):
        k = kind(pdf.name)
        if k == "other":
            continue
        key = session_key(pdf.name)
        out = DST / f"{key}_{k}.txt"
        with fitz.open(pdf) as doc:
            chunks = []
            for i, page in enumerate(doc, 1):
                chunks.append(f"\n\n===== [{key} {k}] strona {i} =====\n")
                chunks.append(page.get_text("text"))
        out.write_text("".join(chunks), encoding="utf-8")
        print(f"{out.name:32s} {len(''.join(chunks)):7d} знаков  <- {pdf.name}")
        done += 1
    print(f"---- готово: {done} файлов в {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
