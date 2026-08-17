#!/usr/bin/env python3
"""Разбирает arkusze B1 на модули и задания и собирает статистику форматов.

Печатает:
  * по каждой сессии — модули, задания, баллы, тема в скобках;
  * сводку: какие типы заданий и с какой частотой встречаются;
  * сводку по грамматике: какие темы и сколько баллов они стоят.

Вход  — archive_text/*_arkusz.txt (см. tools/extract_text.py)
Выход — data/exam_map.json + человекочитаемый отчёт в stdout
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "archive_text"
OUT = ROOT / "data" / "exam_map.json"

MODULES = [
    ("sluchanie", "ROZUMIENIE ZE SŁUCHU"),
    ("czytanie", "ROZUMIENIE TEKSTÓW PISANYCH"),
    ("gramatyka", "POPRAWNOŚĆ GRAMATYCZNA"),
    ("pisanie", "PISANIE"),
    ("mowienie", "MÓWIENIE"),
]

# "III. Proszę ... (stopniowanie przymiotników i przysłówków)."
TASK_RE = re.compile(r"^\s*(?P<num>[IVX]{1,5})\.\s+(?P<body>.+)$", re.M)
# "_____ / 2,5 p. (5 x 0,5 p.)"  либо  "_____ / 2,5 (5 x 0,5 p.)" — «p.» после числа
# печатают не во всех сессиях; без необязательного p. regex промахивался и хватал
# итог модуля «/ 30 p.», отчего задание VIII получало 30 баллов в 12 сессиях из 15
PTS_RE = re.compile(r"_+\s*/\s*(?P<pts>[\d,]+)\s*(?:p\.)?\s*(?:\((?P<detail>[^)]*)\))?")

# балл одного задания не бывает больше 8: всё крупнее — это итог модуля
MAX_TASK_PTS = 8.0
# тема задания — последняя скобка в формулировке полецения
TOPIC_RE = re.compile(r"\(([^()]{4,120})\)\s*\.?\s*$")

NOISE = re.compile(r"^(POZIOM B1|\d+|===|luty|marzec|kwiecień|maj|czerwiec|listopad|styczeń)", re.I)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def split_modules(text: str) -> dict[str, str]:
    """Режет текст аркуша на пять модулей по заголовкам."""
    marks: list[tuple[int, str]] = []
    for key, title in MODULES:
        # заголовок модуля идёт отдельной строкой, берём последнее вхождение до задач
        for m in re.finditer(rf"^\s*{re.escape(title)}\s*$", text, re.M):
            marks.append((m.start(), key))
    marks.sort()
    # оставляем первое вхождение каждого модуля в порядке следования
    seen: set[str] = set()
    ordered: list[tuple[int, str]] = []
    for pos, key in marks:
        if key in seen:
            continue
        seen.add(key)
        ordered.append((pos, key))
    out: dict[str, str] = {}
    for i, (pos, key) in enumerate(ordered):
        end = ordered[i + 1][0] if i + 1 < len(ordered) else len(text)
        out[key] = text[pos:end]
    return out


def parse_tasks(chunk: str) -> list[dict]:
    """Вытаскивает задания: номер, формулировку, баллы, тему."""
    tasks: list[dict] = []
    hits = list(TASK_RE.finditer(chunk))
    for i, m in enumerate(hits):
        start = m.start()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(chunk)
        block = chunk[start:end]
        # полецение = первые строки до строки с баллами; итог модуля (30 p.) пропускаем
        head_end = None
        for cand in PTS_RE.finditer(block):
            if float(cand.group("pts").replace(",", ".")) <= MAX_TASK_PTS:
                head_end = cand
                break
        head = block[: head_end.start()] if head_end else block[:400]
        head = norm(" ".join(l for l in head.splitlines() if not NOISE.match(l.strip())))
        if len(head) < 20:
            continue
        pts = None
        detail = None
        if head_end:
            pts = head_end.group("pts").replace(",", ".")
            detail = norm(head_end.group("detail") or "") or None
        topic = None
        tm = TOPIC_RE.search(head)
        if tm:
            topic = norm(tm.group(1))
        tasks.append(
            {
                "num": m.group("num"),
                "polecenie": head[:400],
                "punkty": float(pts) if pts else None,
                "rozbicie": detail,
                "temat": topic,
            }
        )
    return tasks


def main() -> int:
    files = sorted(SRC.glob("*_arkusz.txt"))
    if not files:
        print("нет archive_text/*_arkusz.txt — сначала tools/extract_text.py", file=sys.stderr)
        return 1

    sessions: dict[str, dict] = {}
    gram_topics: Counter[str] = Counter()
    gram_points: defaultdict[str, float] = defaultdict(float)
    fmt_counter: dict[str, Counter[str]] = {k: Counter() for k, _ in MODULES}

    for f in files:
        key = f.name.split("_")[0]
        text = f.read_text(encoding="utf-8")
        mods = split_modules(text)
        sessions[key] = {}
        for mkey, _ in MODULES:
            if mkey not in mods:
                continue
            tasks = parse_tasks(mods[mkey])
            sessions[key][mkey] = tasks
            for t in tasks:
                if t["temat"]:
                    fmt_counter[mkey][t["temat"].lower()] += 1
                    if mkey == "gramatyka":
                        gram_topics[t["temat"].lower()] += 1
                        gram_points[t["temat"].lower()] += t["punkty"] or 0.0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"разобрано сессий: {len(sessions)}  ->  {OUT.relative_to(ROOT)}\n")
    for key in sorted(sessions):
        counts = {m: len(t) for m, t in sessions[key].items()}
        print(f"{key}: " + ", ".join(f"{m}={n}" for m, n in counts.items()))

    print("\n==== ГРАММАТИКА: темы заданий по всем сессиям ====")
    for topic, n in gram_topics.most_common():
        print(f"{n:3d} раз | {gram_points[topic]:5.1f} п. всего | {topic}")

    for mkey, _ in MODULES:
        if mkey == "gramatyka" or not fmt_counter[mkey]:
            continue
        print(f"\n==== {mkey.upper()}: пометки в заданиях ====")
        for topic, n in fmt_counter[mkey].most_common(15):
            print(f"{n:3d} | {topic}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
