#!/usr/bin/env python3
"""Строит data/exam_structure.json — чистую сводку формата экзамена.

Из подробного разбора (data/exam_map.json, локальный, не коммитится) остаются только
наши выводы: тип задания, баллы, сколько раз звучит запись. Дословных фрагментов
экзаменационных текстов в результат не попадает.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "data" / "exam_map.json"
TXT = ROOT / "archive_text"
OUT = ROOT / "data" / "exam_structure.json"

# распознаём тип задания по формулировке, наружу отдаём только ярлык
TYPES = [
    ("wybor_wielokrotny", r"zaznaczyć właściwe odpowiedzi|zaznaczyć właściwą odpowiedź"),
    ("prawda_falsz_bi", r"TAK\s*–|zaznaczyć:\s*TAK"),
    ("dopasowanie", r"dopasować|połączyć"),
    ("uzupelnianie_ramka", r"uzupełnić.*wyrazami z ramki"),
    ("uzupelnianie_formy", r"uzupełnić.*poprawnymi formami"),
    ("podkreslanie_formy", r"podkreślić poprawn"),
    ("podkreslanie_leksyka", r"podkreślić najlepszą"),
    ("pytanie_do_czesci", r"zapytać o podkreśloną"),
    ("transformacja", r"przekształcić zdanie"),
]

GRAM_SKELETON = {
    "I": "odmiana rzeczowników, przymiotników i zaimków",
    "II": "spójniki / wskaźniki zespolenia",
    "III": "stopniowanie przymiotników i przysłówków",
    "IV": "czasy (teraźniejszy + przeszły albo przyszły)",
    "V": "pytanie o podkreśloną część zdania",
    "VI": "transformacja zdania",
    "VII": "aspekt i tryby",
    "VIII": "przyimki",
}

# ожидаемые баллы заданий грамматики — если хоть одна сессия разобрана иначе,
# это ошибка парсера, а не «экзамен поменялся»: сборка падает и требует разбора
GRAM_POINTS = {"I": 5.0, "II": 2.5, "III": 2.5, "IV": 5.0,
               "V": 2.5, "VI": 5.0, "VII": 5.0, "VIII": 2.5}

# актуальная структура экзамена (certyfikatpolski.pl, B1 dorośli, 2026):
# у архивных аркушей 2021–2024 тайминг может отличаться (например, słuchanie
# «do 30 minut» на самом аркуше) — при прогонах архива верить напечатанному
EGZAMIN_2026 = {
    "sluchanie": 25,
    "czytanie": 45,
    "gramatyka": 45,
    "pisanie": 75,
    "razem_pisemna": 190,
    "mowienie": "do 15 minut",
    "przerwy": "między modułami części pisemnej co najmniej 10 minut",
}


def classify(polecenie: str) -> str:
    for name, rx in TYPES:
        if re.search(rx, polecenie, re.I):
            return name
    return "inne"


def main() -> int:
    data = json.loads(MAP.read_text(encoding="utf-8"))
    plays: dict[str, list[str]] = {}
    for f in sorted(TXT.glob("*_arkusz.txt")):
        t = f.read_text(encoding="utf-8")
        a, b = t.find("ROZUMIENIE ZE SŁUCHU"), t.find("ROZUMIENIE TEKSTÓW")
        seq = re.findall(r"odtworzone (?:tylko )?(jeden raz|dwa razy)", t[a:b])
        plays[f.name.split("_")[0]] = seq[:5]

    out: dict = {
        "poziom": "B1",
        "grupa": "dorośli",
        "sesje_przeanalizowane": sorted(data),
        "egzamin_2026": EGZAMIN_2026,
        "moduly": {},
    }

    for mod, limit, total in (
        ("sluchanie", "do 30 minut (na arkuszach 2021–2024; egzamin 2026: 25 minut)", 30),
        ("czytanie", "45 minut", 30),
        ("gramatyka", "45 minut", 30),
    ):
        tasks = []
        for pos in range(8 if mod == "gramatyka" else 5):
            types: Counter[str] = Counter()
            pts: Counter[float] = Counter()
            rzym = None
            for s in sorted(data):
                lst = data[s].get(mod, [])
                if len(lst) > pos:
                    t = lst[pos]
                    rzym = rzym or t["num"]
                    types[classify(t["polecenie"])] += 1
                    if t["punkty"]:
                        pts[t["punkty"]] += 1
            entry = {
                "nr": rzym,
                "typ": types.most_common(1)[0][0] if types else None,
                "punkty_rozklad": {str(k): v for k, v in sorted(pts.items())},
            }
            if mod == "gramatyka":
                entry["sprawdza"] = GRAM_SKELETON.get(rzym or "")
                oczekiwane = GRAM_POINTS.get(rzym or "")
                zle = [p for p in pts if p != oczekiwane]
                if zle:
                    raise SystemExit(
                        f"gramatyka {rzym}: ожидалось {oczekiwane} p., парсер увидел "
                        f"{dict(pts)} — ошибка разбора, разберись перед пересборкой")
            if mod == "sluchanie":
                cnt = Counter(p[pos] for p in plays.values() if len(p) > pos)
                entry["odtworzenia"] = dict(cnt)
            tasks.append(entry)
        out["moduly"][mod] = {"czas": limit, "punkty": total, "zadania": tasks}

    out["moduly"]["pisanie"] = {
        "czas": "75 minut",
        "punkty": 30,
        "uklad": "3 zestawy do wyboru, w wybranym wykonać obie prace (a i b)",
        "praca_a_slow": "30–35",
        "praca_b_slow": "165–170",
        "ocena": {
            "oceniajacy": ["A", "B"],
            "max_na_oceniajacego": 15,
            "kryteria": {
                "wykonanie_zadania": {"tresc": 2.5, "forma": 1.5, "objetosc": 1.0},
                "srodki_jezykowe": {"leksyka": 2.0, "skladnia": 2.0, "styl": 1.0},
                "poprawnosc": {"gramatyka": 3.5, "ortografia_interpunkcja": 1.5},
            },
        },
    }
    out["moduly"]["mowienie"] = {
        "czas": "do 15 minut",
        "punkty": 40,
        "zadania": [
            {"nr": 1, "typ": "opis_ilustracji"},
            {"nr": 2, "typ": "monolog"},
            {"nr": 3, "typ": "sytuacja_komunikacyjna"},
        ],
        "uwaga": "materiały części ustnej nie są publikowane; źródło — zbiór 6_B1_M",
    }
    out["prog_zdania"] = "co najmniej 50% z każdego modułu części pisemnej oraz z części ustnej"

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"готово: {OUT.relative_to(ROOT)} ({OUT.stat().st_size} b)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
