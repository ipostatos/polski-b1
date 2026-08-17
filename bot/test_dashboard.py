"""Тесты дашборда: формула готовности, вердикты, серия, initData, API.

Запуск: python -m pytest bot/test_dashboard.py -q
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import api
import content
import gotowosc
import storage

MODULY = content.MODULY


# ------------------------------------------------------------------ готовность


def test_dni_do_egzaminu():
    assert content.dni_do_egzaminu(date(2026, 10, 16)) == 1
    assert content.dni_do_egzaminu(date(2026, 10, 17)) == 0
    assert content.dni_do_egzaminu(date(2026, 8, 17)) == 61


def test_trening_gramatyka_liczy_tylko_gram():
    kategorie = {
        "GRAM-I": {"powtorki": 30, "bledy": 6},
        "INTENCJA": {"powtorki": 100, "bledy": 100},  # не должна влиять
    }
    assert gotowosc.dokladnosc_treningu("gramatyka", kategorie) == 80.0


def test_trening_malo_danych_nie_liczy_sie():
    kategorie = {"GRAM-I": {"powtorki": 19, "bledy": 0}}
    assert gotowosc.dokladnosc_treningu("gramatyka", kategorie) is None


def test_trening_pisanie_po_objetosci():
    prace = [(170, 170), (30, 30), (100, 170)]     # 2 попадания из 3
    assert gotowosc.dokladnosc_treningu("pisanie", {}, prace) == pytest.approx(66.67, abs=0.01)
    assert gotowosc.dokladnosc_treningu("pisanie", {}, [(170, 170)]) is None


def test_czytanie_bez_treningu():
    assert gotowosc.dokladnosc_treningu("czytanie", {"GRAM-I": {"powtorki": 99, "bledy": 0}}) is None


def test_gotowosc_modulu_kombinacje():
    assert gotowosc.gotowosc_modulu(60.0, 80.0) == (68, True)     # 0.6*60+0.4*80
    assert gotowosc.gotowosc_modulu(60.0, None) == (60, True)
    assert gotowosc.gotowosc_modulu(None, 90.0) == (50, True)     # только тренировки ≤ 50
    assert gotowosc.gotowosc_modulu(None, 30.0) == (30, True)
    assert gotowosc.gotowosc_modulu(None, None) == (0, False)


def test_kara_bledow():
    assert gotowosc.kara_bledow([]) == 0
    assert gotowosc.kara_bledow([("ASP", 3), ("ORTH", 2)]) == 3
    assert gotowosc.kara_bledow([("A", 3), ("B", 4), ("C", 5), ("D", 3), ("E", 9)]) == 12


def test_gotowosc_deterministyczna_i_wazona():
    wyniki = {"gramatyka": (18.0, 30.0, "2021-11"), "mowienie": (28.0, 40.0, "2021-11")}
    kategorie = {"GRAM-I": {"powtorki": 40, "bledy": 4}}
    r1 = gotowosc.gotowosc(MODULY, wyniki, kategorie, [], [])
    r2 = gotowosc.gotowosc(MODULY, wyniki, kategorie, [], [])
    assert r1 == r2
    # gramatyka: 0.6*60 + 0.4*90 = 72; mowienie: 70; остальные 0
    assert r1["moduly"]["gramatyka"]["gotowosc"] == 72
    assert r1["moduly"]["mowienie"]["gotowosc"] == 70
    assert r1["moduly"]["czytanie"] == {"gotowosc": 0, "zmierzony": False,
                                        "mok": None, "trening": None}
    assert r1["zmierzone"] == 2
    # взвешивание: (72*30 + 70*40) / 160
    assert r1["razem"] == round((72 * 30 + 70 * 40) / 160)


def test_gotowosc_kara_tylko_gramatyka():
    wyniki = {"gramatyka": (20.0, 30.0, "x"), "pisanie": (20.0, 30.0, "x")}
    mapa = [("ASP", 5), ("REKCJA", 3)]
    r = gotowosc.gotowosc(MODULY, wyniki, {}, [], mapa)
    assert r["kara_bledow"] == 6
    assert r["moduly"]["gramatyka"]["gotowosc"] == round(20 / 30 * 100) - 6
    assert r["moduly"]["pisanie"]["gotowosc"] == round(20 / 30 * 100)


def test_statusy_progow():
    assert gotowosc.status_gotowosci(0) == "Самое начало"
    assert gotowosc.status_gotowosci(43) == "База формируется"
    assert gotowosc.status_gotowosci(50) == "Порог рядом"
    assert gotowosc.status_gotowosci(71) == "На хорошем пути"
    assert gotowosc.status_gotowosci(85) == "Готов с запасом"


# ------------------------------------------------------------------ тренды


def test_trendy():
    historia = [
        {"modul": "gramatyka", "punkty": 14.0}, {"modul": "gramatyka", "punkty": 17.0},
        {"modul": "pisanie", "punkty": 20.0},
        {"modul": "czytanie", "punkty": 21.0}, {"modul": "czytanie", "punkty": 21.0},
    ]
    t = gotowosc.trendy(historia)
    assert t["gramatyka"] == {"delta": 3.0, "kierunek": "up"}
    assert t["czytanie"]["kierunek"] == "flat"
    assert "pisanie" not in t     # один замер — тренда нет


# ------------------------------------------------------------------ серия


def test_seria_liczy_do_dzis():
    dzis = date(2026, 8, 20)
    dni = {"2026-08-20": 3, "2026-08-19": 1, "2026-08-18": 5}
    assert gotowosc.seria(dni, dzis) == 3


def test_seria_dzis_pusty_nie_rwie():
    dzis = date(2026, 8, 20)
    dni = {"2026-08-19": 1, "2026-08-18": 5}
    assert gotowosc.seria(dni, dzis) == 2


def test_seria_przerwa_zeruje():
    dzis = date(2026, 8, 20)
    dni = {"2026-08-17": 9}
    assert gotowosc.seria(dni, dzis) == 0


# ------------------------------------------------------------------ вердикт


def test_egzamin_oblany_gdy_jeden_modul_ponizej():
    wyniki = {"sluchanie": 15, "czytanie": 15, "gramatyka": 14.5,
              "pisanie": 15, "mowienie": 20}
    zdany, oblane = gotowosc.egzamin_zdany(wyniki, MODULY)
    assert not zdany and oblane == ["gramatyka"]


def test_egzamin_zdany_tylko_gdy_wszystkie():
    wyniki = {"sluchanie": 15, "czytanie": 15, "gramatyka": 15,
              "pisanie": 15, "mowienie": 20}
    zdany, oblane = gotowosc.egzamin_zdany(wyniki, MODULY)
    assert zdany and not oblane


def test_egzamin_brakujacy_modul_to_oblany():
    wyniki = {"sluchanie": 30, "czytanie": 30, "gramatyka": 30, "pisanie": 30}
    zdany, oblane = gotowosc.egzamin_zdany(wyniki, MODULY)
    assert not zdany and oblane == ["mowienie"]


# ------------------------------------------------------------------ план дня


def test_plan_dnia_done_po_progu():
    plan = content.plan_dnia(0, {"gramatyka": 15, "sluchanie": 7})
    stany = {p["typ"]: p["done"] for p in plan}
    assert stany["gramatyka"] is True
    assert stany["sluchanie"] is False       # 7 < 8
    assert stany["czytanie"] is False


def test_dzien_tekst_z_planu():
    assert "Gramatyka 20" in content.DZIEN[0]
    assert "Экзаменационная практика" in content.DZIEN[5]


# ------------------------------------------------------------------ storage


@pytest.fixture()
def baza(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "postep.db")
    storage.init()
    return 7


def test_aktywnosc_i_due(baza):
    uid = baza
    storage.zaloguj_aktywnosc(uid, "gramatyka", 3)
    storage.zaloguj_aktywnosc(uid, "gramatyka", 2)
    storage.zaloguj_aktywnosc(uid, "nieznany-typ")      # молча игнорируется
    assert storage.aktywnosc_dzis(uid) == {"gramatyka": 5}
    # ошибка кладёт позицию на сегодня → сразу due
    storage.zapisz_odpowiedz(uid, "X-1", "GRAM-I", False)
    storage.zapisz_odpowiedz(uid, "X-2", "GRAM-I", True)
    assert storage.do_powtorki(uid) == {"X-1"}
    s = storage.podsumowanie_srs(uid)
    assert s["znane"] == 2 and s["due"] == 1 and s["zakreplone"] == 0


# ------------------------------------------------------------------ initData


TOKEN = "12345:testtoken"


def podpisz(dane: dict, token: str = TOKEN) -> str:
    czysta = "\n".join(f"{k}={v}" for k, v in sorted(dane.items()))
    sekret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    podpis = hmac.new(sekret, czysta.encode(), hashlib.sha256).hexdigest()
    return urlencode({**dane, "hash": podpis})


def init_data_dla(uid: int, auth_date: int | None = None) -> str:
    return podpisz({
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAF",
        "user": json.dumps({"id": uid, "first_name": "T"}),
    })


def test_initdata_poprawna():
    dane = api.waliduj_init_data(init_data_dla(42), TOKEN)
    assert dane is not None and api.user_id_z(dane) == 42


def test_initdata_zmanipulowana():
    zla = init_data_dla(42).replace("42", "43", 1)
    assert api.waliduj_init_data(zla, TOKEN) is None


def test_initdata_zly_token():
    assert api.waliduj_init_data(init_data_dla(42), "inny:token") is None


def test_initdata_przeterminowana():
    stara = init_data_dla(42, auth_date=int(time.time()) - api.MAX_WIEK_INITDATA - 5)
    assert api.waliduj_init_data(stara, TOKEN) is None


def test_initdata_pusta_i_bez_hash():
    assert api.waliduj_init_data("", TOKEN) is None
    assert api.waliduj_init_data("auth_date=1&user=x", TOKEN) is None


# ------------------------------------------------------------------ API


OWNER = 42


def klient(test):
    """Гоняет асинхронный сценарий против собранного API."""
    from aiohttp.test_utils import TestClient, TestServer

    async def run():
        app = api.zbuduj_api(TOKEN, OWNER, {"gramatyka": 50, "sluchanie": 36, "otwarte": 15})
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            await test(client)
        finally:
            await client.close()
    asyncio.run(run())


def test_api_bez_auth_401(baza):
    async def scenariusz(cl):
        for sciezka in ("/api/dashboard", "/api/wyniki", "/api/powtorki"):
            r = await cl.get(sciezka)
            assert r.status == 401, sciezka
        r = await cl.post("/api/odpowiedz", json={"item_id": "x", "kategoria": "GRAM-I", "ok": True})
        assert r.status == 401
    klient(scenariusz)


def test_api_cudzy_user_403(baza):
    async def scenariusz(cl):
        r = await cl.get("/api/dashboard",
                         headers={"Authorization": "tma " + init_data_dla(OWNER + 1)})
        assert r.status == 403
    klient(scenariusz)


def test_api_config_publiczny(baza):
    async def scenariusz(cl):
        r = await cl.get("/api/config")
        assert r.status == 200
        cfg = await r.json()
        assert cfg["exam_date"] == "2026-10-17"
        assert cfg["moduly"]["mowienie"]["prog"] == 20
        assert cfg["timing"]["pisanie"] == 75
    klient(scenariusz)


def test_api_dashboard_i_zapisy(baza):
    naglowki = {"Authorization": "tma " + init_data_dla(OWNER)}

    async def scenariusz(cl):
        # ответ тренажёра пишется и попадает в агрегаты
        r = await cl.post("/api/odpowiedz", headers=naglowki,
                          json={"item_id": "G1-1", "kategoria": "GRAM-I", "ok": False})
        assert r.status == 200
        r = await cl.post("/api/wynik", headers=naglowki,
                          json={"sesja": "2021-11", "modul": "gramatyka", "punkty": 18})
        assert r.status == 200
        assert (await r.json())["status"] == "prog"
        r = await cl.post("/api/wynik", headers=naglowki,
                          json={"sesja": "x", "modul": "gramatyka", "punkty": 99})
        assert r.status == 400          # за пределами максимума
        r = await cl.get("/api/dashboard", headers=naglowki)
        assert r.status == 200
        d = await r.json()
        assert d["exam"]["date"] == "2026-10-17"
        assert d["srs"]["znane"] == 1 and d["srs"]["due"] == 1
        assert d["modules"]["gramatyka"]["ostatni"]["punkty"] == 18
        assert d["readiness"]["moduly"]["gramatyka"]["zmierzony"] is True
        assert d["today"]["target"] == len(content.PLAN_DNIA[date.today().weekday()])
        r = await cl.get("/api/powtorki", headers=naglowki)
        assert (await r.json())["due"] == ["G1-1"]
    klient(scenariusz)


def test_api_aktywnosc_tylko_reczne_typy(baza):
    naglowki = {"Authorization": "tma " + init_data_dla(OWNER)}

    async def scenariusz(cl):
        r = await cl.post("/api/aktywnosc", headers=naglowki, json={"typ": "czytanie"})
        assert r.status == 200
        r = await cl.post("/api/aktywnosc", headers=naglowki, json={"typ": "mok"})
        assert r.status == 400          # мок руками не отмечается — только через /api/wynik
    klient(scenariusz)


def test_api_cors_tylko_dozwolony_origin(baza):
    async def scenariusz(cl):
        r = await cl.options("/api/dashboard",
                             headers={"Origin": "https://ipostatos.github.io"})
        assert r.headers.get("Access-Control-Allow-Origin") == "https://ipostatos.github.io"
        r = await cl.options("/api/dashboard", headers={"Origin": "https://evil.example"})
        assert "Access-Control-Allow-Origin" not in r.headers
    klient(scenariusz)


# ------------------------------------------------------------------ legacy


def test_brak_zeglarskiego_slownictwa():
    """В текстовых исходниках нет следов чужих учебных проектов."""
    zakazane = re.compile(
        r"\b(" + "|".join([
            "IS" + "SA", "sk" + "ipper", "in" + "shore", "ya" + "cht", "ja" + "cht",
            "sail" + "ing", "żeg" + "l", "V" + "HF", "mar" + "ina",
            "anch" + "or", "kotw" + "ic",
        ]) + r")", re.IGNORECASE)
    root = Path(__file__).resolve().parent.parent
    # сам тест и CI-сторож содержат список запрещённых слов по определению
    wyjatki = {Path(__file__).resolve(), root / ".github" / "workflows" / "ci.yml"}
    for wzor in ("bot/*.py", "webapp/*", "data/*.json", "docs/*.md", "*.md",
                 "deploy/*", "tools/*.py", ".github/workflows/*.yml"):
        for f in root.glob(wzor):
            if f in wyjatki or not f.is_file() or f.suffix in (".mp3", ".pdf", ".png", ".jpg"):
                continue
            tekst = f.read_text(encoding="utf-8", errors="ignore")
            m = zakazane.search(tekst)
            assert not m, f"{f}: найдено «{m.group(0) if m else ''}»"
