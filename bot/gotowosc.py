"""Индекс готовности к экзамену и производные дашборда.

Все функции чистые: вход — данные, выход — числа. Никакого IO, никакой
случайности: одинаковый вход всегда даёт одинаковый выход (покрыто тестами).

Готовность — УЧЕБНЫЙ ИНДЕКС, а не вероятность сдачи. Формула:

  тренировочная точность модуля (только при достатке данных):
    gramatyka  — точность SRS по категориям GRAM-* (минимум 20 показов);
    sluchanie  — точность SRS по INTENCJA и SYTUACJA (минимум 20 показов);
    pisanie    — доля последних работ с попаданием в объём 90–110%
                 (минимум 3 работы);
    czytanie, mowienie — тренажёра нет, только моки.

  готовность модуля:
    мок и тренировки → 0.6·мок% + 0.4·тренировки%;
    только мок       → мок%;
    только тренировки → min(тренировки%, 50)  — без мока выше 50 не бывает;
    ничего           → 0, модуль помечен «не замерено».

  штраф gramatyka: −3 п.п. за каждую категорию Error Map с ≥3 ошибками,
  максимум −12 (повторяющаяся ошибка — системный риск).

  итог — среднее по модулям, взвешенное их баллами (30/30/30/30/40).
"""
from __future__ import annotations

from datetime import date, timedelta

MIN_POKAZOW = 20      # меньше показов SRS — тренировочная точность не считается
MIN_PRAC = 3          # меньше работ — точность письма не считается
KARA_ZA_KATEGORIE = 3
KARA_MAX = 12

# категории SRS → модуль
KATEGORIE_MODULU = {
    "gramatyka": ("GRAM-",),
    "sluchanie": ("INTENCJA", "SYTUACJA"),
}

STATUSY = [
    (85, "Готов с запасом"),
    (70, "На хорошем пути"),
    (50, "Порог рядом"),
    (25, "База формируется"),
    (0, "Самое начало"),
]


def dokladnosc_treningu(modul: str, kategorie: dict[str, dict[str, int]],
                        prace: list[tuple[int, int]] | None = None) -> float | None:
    """Тренировочная точность модуля в процентах, None если данных мало.

    `kategorie` — {категория: {"powtorki": n, "bledy": n}} из podsumowanie_srs.
    `prace` — [(слов, требовалось)] для модуля pisanie.
    """
    if modul == "pisanie":
        prace = prace or []
        if len(prace) < MIN_PRAC:
            return None
        trafienia = sum(1 for slow, wymagane in prace
                        if wymagane > 0 and 90 <= round(slow / wymagane * 100, 6) <= 110)
        return trafienia / len(prace) * 100
    prefiksy = KATEGORIE_MODULU.get(modul)
    if not prefiksy:
        return None
    pokazy = bledy = 0
    for kat, s in kategorie.items():
        if any(kat.startswith(p) for p in prefiksy):
            pokazy += s["powtorki"]
            bledy += s["bledy"]
    if pokazy < MIN_POKAZOW:
        return None
    return (pokazy - bledy) / pokazy * 100


def gotowosc_modulu(mok_proc: float | None, trening_proc: float | None) -> tuple[int, bool]:
    """(готовность 0–100, замерен ли модуль хоть чем-то)."""
    if mok_proc is not None and trening_proc is not None:
        return round(0.6 * mok_proc + 0.4 * trening_proc), True
    if mok_proc is not None:
        return round(mok_proc), True
    if trening_proc is not None:
        return min(round(trening_proc), 50), True
    return 0, False


def kara_bledow(mapa: list[tuple[str, int]]) -> int:
    """Штраф за повторяющиеся ошибки Error Map (только gramatyka)."""
    powtarzajace = sum(1 for _, n in mapa if n >= 3)
    return min(powtarzajace * KARA_ZA_KATEGORIE, KARA_MAX)


def gotowosc(moduly: dict[str, tuple[float, float, float, float]],
             wyniki: dict[str, tuple[float, float, str]],
             kategorie: dict[str, dict[str, int]],
             prace: list[tuple[int, int]],
             mapa: list[tuple[str, int]]) -> dict:
    """Полный расчёт. `moduly` — content.MODULY без имени: {ключ: (имя, макс, порог, цель)}."""
    out: dict = {"moduly": {}, "zmierzone": 0}
    suma = wagi = 0.0
    kara = kara_bledow(mapa)
    for klucz, (_, maks, prog, cel) in moduly.items():
        mok = None
        if klucz in wyniki:
            p, mx, _ = wyniki[klucz]
            mok = p / mx * 100 if mx else None
        trening = dokladnosc_treningu(
            klucz, kategorie, prace if klucz == "pisanie" else None)
        wartosc, zmierzony = gotowosc_modulu(mok, trening)
        if klucz == "gramatyka" and zmierzony:
            wartosc = max(0, wartosc - kara)
        out["moduly"][klucz] = {
            "gotowosc": wartosc, "zmierzony": zmierzony,
            "mok": None if mok is None else round(mok),
            "trening": None if trening is None else round(trening),
        }
        if zmierzony:
            out["zmierzone"] += 1
        suma += wartosc * maks
        wagi += maks
    out["razem"] = round(suma / wagi) if wagi else 0
    out["kara_bledow"] = kara
    out["status"] = status_gotowosci(out["razem"])
    return out


def status_gotowosci(proc: int) -> str:
    for prog, nazwa in STATUSY:
        if proc >= prog:
            return nazwa
    return STATUSY[-1][1]


# ------------------------------------------------------------------ тренды


def trendy(historia: list[dict]) -> dict[str, dict]:
    """Тренд по модулям из хронологии моков: последний vs предыдущий результат.

    Возвращает {модуль: {"delta": пункты, "kierunek": "up"|"down"|"flat"}}
    только для модулей с двумя и более замерами.
    """
    po_modulach: dict[str, list[float]] = {}
    for w in historia:
        po_modulach.setdefault(w["modul"], []).append(float(w["punkty"]))
    out: dict[str, dict] = {}
    for modul, pkt in po_modulach.items():
        if len(pkt) < 2:
            continue
        delta = pkt[-1] - pkt[-2]
        out[modul] = {"delta": round(delta, 1),
                      "kierunek": "up" if delta > 0 else ("down" if delta < 0 else "flat")}
    return out


# ------------------------------------------------------------------ серия


def seria(dni_aktywnosci: dict[str, int], dzis: date) -> int:
    """Непрерывные дни с активностью, заканчивая сегодня или вчера.

    Сегодняшний день без активности серию не рвёт (день ещё идёт),
    но и не удлиняет.
    """
    aktywne = {d for d, n in dni_aktywnosci.items() if n > 0}
    start = dzis if dzis.isoformat() in aktywne else dzis - timedelta(days=1)
    n = 0
    d = start
    while d.isoformat() in aktywne:
        n += 1
        d -= timedelta(days=1)
    return n


# ------------------------------------------------------------------ вердикт


def egzamin_zdany(wyniki_sesji: dict[str, float],
                  moduly: dict[str, tuple[float, float, float, float]]) -> tuple[bool, list[str]]:
    """Zdany только когда КАЖДЫЙ модуль не ниже порога. Среднего не существует.

    Возвращает (сдан, список проваленных модулей). Отсутствующий модуль
    считается проваленным — без замера сдачи нет.
    """
    oblane = []
    for klucz, (_, _maks, prog, _cel) in moduly.items():
        p = wyniki_sesji.get(klucz)
        if p is None or p < prog:
            oblane.append(klucz)
    return (not oblane, oblane)
