"""Хранилище прогресса: SQLite, одна база на владельца.

Три вещи, которые надо помнить между сессиями:
  * повторение упражнений (SRS) — что и когда показывать снова;
  * Error Map — категории ошибок и их частота;
  * результаты моков по модулям.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "moje" / "postep.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS srs (
    user_id   INTEGER NOT NULL,
    item_id   TEXT    NOT NULL,
    kategoria TEXT    NOT NULL,
    powtorki  INTEGER NOT NULL DEFAULT 0,
    bledy     INTEGER NOT NULL DEFAULT 0,
    interwal  INTEGER NOT NULL DEFAULT 0,
    nastepnie TEXT    NOT NULL,
    PRIMARY KEY (user_id, item_id)
);

CREATE TABLE IF NOT EXISTS bledy (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    kod       TEXT    NOT NULL,
    zle       TEXT    NOT NULL,
    dobrze    TEXT    NOT NULL DEFAULT '',
    komentarz TEXT    NOT NULL DEFAULT '',
    kiedy     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS wyniki (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sesja   TEXT    NOT NULL,
    modul   TEXT    NOT NULL,
    punkty  REAL    NOT NULL,
    maks    REAL    NOT NULL,
    kiedy   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS prace (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    zestaw    TEXT    NOT NULL,
    czesc     TEXT    NOT NULL,
    slow      INTEGER NOT NULL,
    wymagane  INTEGER NOT NULL,
    tekst     TEXT    NOT NULL,
    kiedy     TEXT    NOT NULL
);
"""

# интервалы повторения в днях: чем увереннее ответ, тем дальше отодвигаем
INTERWALY = [0, 1, 3, 7, 16, 35]


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _conn() as c:
        c.executescript(SCHEMA)


# ------------------------------------------------------------------ SRS


def zapisz_odpowiedz(user_id: int, item_id: str, kategoria: str, poprawnie: bool) -> None:
    """Двигает позицию по лестнице интервалов; ошибка сбрасывает в начало."""
    with _conn() as c:
        row = c.execute(
            "SELECT powtorki, bledy, interwal FROM srs WHERE user_id=? AND item_id=?",
            (user_id, item_id),
        ).fetchone()
        powtorki = (row["powtorki"] if row else 0) + 1
        bledy = (row["bledy"] if row else 0) + (0 if poprawnie else 1)
        krok = (row["interwal"] if row else 0)
        krok = min(krok + 1, len(INTERWALY) - 1) if poprawnie else 0
        nast = (date.today() + timedelta(days=INTERWALY[krok])).isoformat()
        c.execute(
            "INSERT INTO srs (user_id,item_id,kategoria,powtorki,bledy,interwal,nastepnie) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id,item_id) DO UPDATE SET "
            "powtorki=excluded.powtorki, bledy=excluded.bledy, "
            "interwal=excluded.interwal, nastepnie=excluded.nastepnie",
            (user_id, item_id, kategoria, powtorki, bledy, krok, nast),
        )


def do_powtorki(user_id: int) -> set[str]:
    """Позиции, срок которых подошёл. Незнакомые позиции сюда не входят."""
    with _conn() as c:
        rows = c.execute(
            "SELECT item_id FROM srs WHERE user_id=? AND nastepnie<=?",
            (user_id, date.today().isoformat()),
        ).fetchall()
    return {r["item_id"] for r in rows}


def widziane(user_id: int) -> set[str]:
    with _conn() as c:
        rows = c.execute("SELECT item_id FROM srs WHERE user_id=?", (user_id,)).fetchall()
    return {r["item_id"] for r in rows}


def slabe_kategorie(user_id: int, limit: int = 5) -> list[tuple[str, int, int]]:
    """Категории с наибольшим числом ошибок: (категория, ошибок, показов)."""
    with _conn() as c:
        rows = c.execute(
            "SELECT kategoria, SUM(bledy) b, SUM(powtorki) p FROM srs "
            "WHERE user_id=? GROUP BY kategoria HAVING b>0 ORDER BY b DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [(r["kategoria"], r["b"], r["p"]) for r in rows]


# ------------------------------------------------------------------ Error Map


def dodaj_blad(user_id: int, kod: str, zle: str, dobrze: str = "",
               komentarz: str = "") -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO bledy (user_id,kod,zle,dobrze,komentarz,kiedy) VALUES (?,?,?,?,?,?)",
            (user_id, kod.upper(), zle, dobrze, komentarz, datetime.now().isoformat(" ", "seconds")),
        )
        return int(cur.lastrowid or 0)


def mapa_bledow(user_id: int) -> list[tuple[str, int]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT kod, COUNT(*) n FROM bledy WHERE user_id=? GROUP BY kod ORDER BY n DESC",
            (user_id,),
        ).fetchall()
    return [(r["kod"], r["n"]) for r in rows]


def ostatnie_bledy(user_id: int, kod: str | None = None, limit: int = 10) -> list[sqlite3.Row]:
    with _conn() as c:
        if kod:
            return c.execute(
                "SELECT * FROM bledy WHERE user_id=? AND kod=? ORDER BY id DESC LIMIT ?",
                (user_id, kod.upper(), limit),
            ).fetchall()
        return c.execute(
            "SELECT * FROM bledy WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


# ------------------------------------------------------------------ результаты


def zapisz_wynik(user_id: int, sesja: str, modul: str, punkty: float, maks: float) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO wyniki (user_id,sesja,modul,punkty,maks,kiedy) VALUES (?,?,?,?,?,?)",
            (user_id, sesja, modul, punkty, maks, datetime.now().isoformat(" ", "seconds")),
        )


def ostatnie_wyniki(user_id: int) -> dict[str, tuple[float, float, str]]:
    """По одному последнему результату на модуль."""
    with _conn() as c:
        rows = c.execute(
            "SELECT modul, punkty, maks, sesja FROM wyniki WHERE user_id=? ORDER BY id",
            (user_id,),
        ).fetchall()
    out: dict[str, tuple[float, float, str]] = {}
    for r in rows:
        out[r["modul"]] = (r["punkty"], r["maks"], r["sesja"])
    return out


# ------------------------------------------------------------------ работы


def zapisz_prace(user_id: int, zestaw: str, czesc: str, slow: int, wymagane: int,
                 tekst: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO prace (user_id,zestaw,czesc,slow,wymagane,tekst,kiedy) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, zestaw, czesc, slow, wymagane, tekst,
             datetime.now().isoformat(" ", "seconds")),
        )


def liczba_prac(user_id: int) -> int:
    with _conn() as c:
        r = c.execute("SELECT COUNT(*) n FROM prace WHERE user_id=?", (user_id,)).fetchone()
    return int(r["n"])
