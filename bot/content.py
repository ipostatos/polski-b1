"""Загрузка учебного содержания и разворачивание его в отдельные позиции.

Одна позиция = один вопрос, который бот может задать. У каждой стабильный id,
по которому хранится прогресс, поэтому порядок в JSON менять безопасно,
а id — нет.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
AUDIO = DATA / "audio"
OBRAZKI = DATA / "obrazki"

EGZAMIN = date(2026, 10, 17)

MODULY = {
    "sluchanie": ("Rozumienie ze słuchu", 30, 15, 22),
    "czytanie": ("Rozumienie tekstów pisanych", 30, 15, 23),
    "gramatyka": ("Poprawność gramatyczna", 30, 15, 22),
    "pisanie": ("Pisanie", 30, 15, 21),
    "mowienie": ("Mówienie", 40, 20, 28),
}


@dataclass
class Pozycja:
    """Один вопрос с вариантами."""

    id: str
    kategoria: str
    pytanie: str
    opcje: list[str]
    klucz: str
    wyjasnienie: str = ""
    naglowek: str = ""
    opcje_pelne: list[str] = field(default_factory=list)
    # для задания I аудирования: транскрипция реплики и путь к записи (если есть)
    transkrypcja: str = ""
    audio: Path | None = None
    pytanie_audio: str = ""

    @property
    def indeks_klucza(self) -> int:
        return self.opcje.index(self.klucz)


@dataclass
class Otwarte:
    """Вопрос с открытым ответом (задания IV и VI): ответ набирается текстом."""

    id: str
    kategoria: str
    pytanie: str
    klucz: str
    akceptowane: list[str] = field(default_factory=list)
    wyjasnienie: str = ""
    naglowek: str = ""

    def poprawna(self, odpowiedz: str) -> bool:
        warianty = [self.klucz, *self.akceptowane]
        return normalizuj(odpowiedz) in {normalizuj(w) for w in warianty}


def normalizuj(tekst: str) -> str:
    """Сравнение ответов без чувствительности к регистру, пунктуации и пробелам."""
    out = tekst.lower()
    for ch in ",.!?…;:„”\"'—–()":
        out = out.replace(ch, " ")
    return " ".join(out.split())


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def dni_do_egzaminu(today: date | None = None) -> int:
    return (EGZAMIN - (today or date.today())).days


# ------------------------------------------------------------------ грамматика


def pozycje_gramatyka() -> list[Pozycja]:
    """Разворачивает упражнения в отдельные вопросы с вариантами.

    Берутся только задания с готовыми вариантами (подчеркнуть верную форму
    и вставить из рамки). Задания с открытым ответом (IV, V, VI) в боте
    не тренируются кнопками — они идут в тетради и в разборе.
    """
    cw = _load("cwiczenia_gramatyka.json")
    out: list[Pozycja] = []
    for z in cw["zadania"]:
        kat = f"GRAM-{z['nr']}"
        for zestaw in z["zestawy"]:
            for luka in zestaw.get("luki", []):
                if "opcje" not in luka:
                    continue
                out.append(Pozycja(
                    id=f"{zestaw['id']}-{luka['nr']}",
                    kategoria=kat,
                    pytanie=_kontekst(zestaw["tekst"], luka["nr"]),
                    opcje=list(luka["opcje"]),
                    klucz=luka["klucz"],
                    wyjasnienie=luka.get("dlaczego", ""),
                    naglowek=f"Zadanie {z['nr']} — {z['sprawdza']}",
                ))
            if "ramka" in zestaw:
                for zd in zestaw["zdania"]:
                    opcje = _opcje_z_ramki(zestaw["ramka"], zd["klucz"])
                    out.append(Pozycja(
                        id=f"{zestaw['id']}-{zd['nr']}",
                        kategoria=kat,
                        pytanie=zd["tekst"],
                        opcje=opcje,
                        klucz=zd["klucz"],
                        wyjasnienie=zd.get("dlaczego", ""),
                        naglowek=f"Zadanie {z['nr']} — {z['sprawdza']}",
                    ))
    return out


def _kontekst(tekst: str, nr: int, okno: int = 130) -> str:
    """Вырезает фрагмент вокруг пропуска, чтобы вопрос помещался в сообщение."""
    marker = "{%d}" % nr
    i = tekst.find(marker)
    if i < 0:
        return tekst[:okno]
    start = max(0, i - okno)
    end = min(len(tekst), i + len(marker) + okno)
    frag = tekst[start:end]
    for m in range(1, 20):
        frag = frag.replace("{%d}" % m, "……" if m != nr else "▁▁▁▁▁")
    return ("… " if start else "") + frag.strip() + (" …" if end < len(tekst) else "")


def _opcje_z_ramki(ramka: list[str], klucz: str, ile: int = 4) -> list[str]:
    """Ключ плюс несколько соседей из рамки — иначе кнопок было бы семь."""
    inne = [w for w in ramka if w.lower() != klucz.lower()]
    rng = random.Random(klucz)
    wybrane = rng.sample(inne, min(ile - 1, len(inne)))
    opcje = [klucz] + wybrane
    rng.shuffle(opcje)
    return opcje


# ------------------------------------------------------------------ интенции


def pozycje_intencje() -> list[Pozycja]:
    """Тренажёр задания I аудирования.

    Если для позиции есть запись в data/audio/, бот отправляет её голосом и
    показывает вопрос БЕЗ транскрипции — только так тренируется rozumienie ze
    słuchu. Без записи позиция работает в текстовом режиме (fallback), но это
    тренировка чтения интенций, а не аудирования. Записи генерируются скриптом
    tools/make_audio.py.
    """
    src = _load("intencje.json")
    out: list[Pozycja] = []
    for i, p in enumerate(src["pozycje"], 1):
        opcje = [p["klucz"], *p["dystraktory"]]
        random.Random(p["tekst"]).shuffle(opcje)
        iid = f"INT-{i:03d}"
        out.append(Pozycja(
            id=iid,
            kategoria="INTENCJA",
            pytanie=f"„{p['tekst']}”\n\nTa wypowiedź to:",
            opcje=opcje,
            klucz=p["klucz"],
            wyjasnienie=p.get("wskazowka", ""),
            naglowek="Zadanie I — intencja wypowiedzi",
            transkrypcja=p["tekst"],
            audio=_audio_dla(iid),
            pytanie_audio="Ta wypowiedź to:",
        ))
    for i, p in enumerate(src["sytuacje"]["pozycje"], 1):
        opcje = [p["klucz"], *p["dystraktory"]]
        random.Random(p["tekst"]).shuffle(opcje)
        iid = f"SYT-{i:03d}"
        out.append(Pozycja(
            id=iid,
            kategoria="SYTUACJA",
            pytanie=f"„{p['tekst']}”\n\nTa wypowiedź jest typowa:",
            opcje=opcje,
            klucz=p["klucz"],
            naglowek="Zadanie I — miejsce wypowiedzi",
            transkrypcja=p["tekst"],
            audio=_audio_dla(iid),
            pytanie_audio="Ta wypowiedź jest typowa:",
        ))
    return out


def _audio_dla(iid: str) -> Path | None:
    f = AUDIO / f"{iid}.mp3"
    return f if f.exists() else None


def obrazek_dla(zestaw_id: str) -> Path | None:
    """Фотография для Zadanie 1 устной части, если она подготовлена."""
    for ext in ("jpg", "png", "webp"):
        f = OBRAZKI / f"{zestaw_id}.{ext}"
        if f.exists():
            return f
    return None


# ------------------------------------------------------------------ открытые ответы


def pozycje_czasy() -> list[Otwarte]:
    """Задание IV (времена): форма глагола вписывается текстом."""
    cw = _load("cwiczenia_gramatyka.json")
    out: list[Otwarte] = []
    for z in cw["zadania"]:
        if z["nr"] != "IV":
            continue
        for zestaw in z["zestawy"]:
            for luka in zestaw["luki"]:
                out.append(Otwarte(
                    id=f"{zestaw['id']}-{luka['nr']}",
                    kategoria="GRAM-IV",
                    pytanie=(_kontekst(zestaw["tekst"], luka["nr"])
                             + f"\n\nWpisz formę: <b>({luka['podstawa']})</b>"),
                    klucz=luka["klucz"],
                    akceptowane=list(luka.get("akceptowane", [])),
                    wyjasnienie=luka.get("dlaczego", ""),
                    naglowek=f"Zadanie {z['nr']} — {z['sprawdza']}",
                ))
    return out


def pozycje_transformacje() -> list[Otwarte]:
    """Задание VI (трансформации): предложение перестраивается целиком."""
    cw = _load("cwiczenia_gramatyka.json")
    out: list[Otwarte] = []
    for z in cw["zadania"]:
        if z["nr"] != "VI":
            continue
        for zestaw in z["zestawy"]:
            for zd in zestaw["zdania"]:
                out.append(Otwarte(
                    id=f"{zestaw['id']}-{zd['nr']}",
                    kategoria="GRAM-VI",
                    pytanie=(f"{zd['zdanie']}\n\nPrzekształć, używając: "
                             f"<b>{zd['wyraz']}</b>"),
                    klucz=zd["klucz"],
                    akceptowane=list(zd.get("akceptowane", [])),
                    wyjasnienie=zd.get("dlaczego", ""),
                    naglowek=f"Zadanie {z['nr']} — {z['sprawdza']}",
                ))
    return out


# ------------------------------------------------------------------ письмо и речь


def zestawy_pisanie() -> list[dict]:
    return _load("zadania_pisanie.json")["zestawy"]


def zestawy_mowienie() -> list[dict]:
    return _load("zadania_mowienie.json")["zestawy"]


def licz_slowa(tekst: str) -> int:
    """Считает слова по пробелам, без пустых токенов.

    Официального алгоритма подсчёта комиссия не публикует — это наш способ
    держать объём под контролем на тренировках, а не «так считает экзаменатор».
    """
    return len([w for w in tekst.split() if any(ch.isalnum() for ch in w)])


def ocena_objetosci(slow: int, wymagane: int) -> tuple[str, str]:
    """Возвращает (статус, комментарий) по подкритерию objętość.

    Допуск ±10% — тренировочная эвристика: в аркуше напечатано требуемое число
    слов, но официально объявленного процента допуска не существует. Оцениваем
    строже, чтобы на экзамене был запас.
    """
    # округляем: без этого 187/170 даёт 110.00000000000001 и выпадает из допуска
    proc = round(slow / wymagane * 100, 6)
    if 90 <= proc <= 110:
        return "✅", f"{slow} слов при требуемых {wymagane} — попадание ({proc:.0f}%)"
    if proc < 90:
        return "❌", (f"{slow} слов при требуемых {wymagane} ({proc:.0f}%) — коротко. "
                     f"Не хватает {wymagane - slow} слов: объём — отдельный подкритерий "
                     "оценки, короткий текст рискует его потерять.")
    return "⚠️", (f"{slow} слов при требуемых {wymagane} ({proc:.0f}%) — длинно. "
                  "Лишний объём съедает время и тоже рискует подкритерием objętość. "
                  "±10% — наш тренировочный ориентир, не официальный порог.")


# ------------------------------------------------------------------ план дня

PLAN = [
    (1, "17.08", "23.08", "ДИАГНОСТИКА. Ничего не учим. Сб — письменная часть 2021-11, вс — Mówienie."),
    (2, "24.08", "30.08", "Грамматика: задание I (склонение) и VII (вид и наклонения). Ежедневно słuchanie и czytanie."),
    (3, "31.08", "06.09", "Грамматика: IV (времена) и VI (трансформации). Старт письма: 3 работы в неделю."),
    (4, "07.09", "13.09", "Грамматика: мелочь — II, III, V, VIII. Письмо продолжается."),
    (5, "14.09", "20.09", "Чтение и аудирование под таймер, по одному модулю за раз."),
    (6, "21.09", "27.09", "Полные письменные модули из архива. Говорение ежедневно."),
    (7, "28.09", "04.10", "EXAM MODE. Полный мок 03.10 на сессии 2023-11."),
    (8, "05.10", "11.10", "Стабилизация по Error Map. Мок 10.10 на 2024-02."),
    (9, "12.10", "16.10", "Финальный мок 2024-04, дальше только короткие тренировки."),
]

DZIEN = {
    0: "Понедельник: gramatyka 20 · słuchanie 15 · czytanie 15 · mówienie 10",
    1: "Вторник: gramatyka 20 · pisanie (работа целиком) · słuchanie 15",
    2: "Среда: gramatyka 20 · słuchanie 15 · czytanie 15 · mówienie 10",
    3: "Четверг: gramatyka 20 · pisanie (работа целиком) · czytanie 15",
    4: "Пятница: gramatyka 20 · słuchanie 15 · czytanie 15 · mówienie 15",
    5: "Суббота: экзаменационная практика, 90–190 минут",
    6: "Воскресенье: разбор ошибок + лёгкий польский без напряжения",
}


def tydzien_programu(today: date | None = None) -> tuple[int, str]:
    d = today or date.today()
    start = date(2026, 8, 17)
    nr = max(1, min(9, (d - start).days // 7 + 1))
    for w, _, _, opis in PLAN:
        if w == nr:
            return nr, opis
    return nr, ""
