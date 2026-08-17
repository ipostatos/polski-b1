"""Тесты содержания и логики. Сеть не трогают, бот не запускают."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import content  # noqa: E402
import storage  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


# ------------------------------------------------------------------ содержание


def test_wszystkie_pliki_danych_sa_poprawnym_json():
    for f in DATA.glob("*.json"):
        json.loads(f.read_text(encoding="utf-8"))


def test_klucz_zawsze_jest_wsrod_opcji():
    """Если ключа нет среди вариантов, вопрос нерешаемый."""
    for p in content.pozycje_gramatyka() + content.pozycje_intencje():
        assert p.klucz in p.opcje, f"{p.id}: ключ {p.klucz!r} не среди {p.opcje}"


def test_opcje_sie_nie_powtarzaja():
    for p in content.pozycje_gramatyka() + content.pozycje_intencje():
        assert len(p.opcje) == len(set(p.opcje)), f"{p.id}: повторяющиеся варианты"


def test_identyfikatory_sa_unikalne():
    """id — ключ прогресса; дубль означал бы перемешивание истории."""
    poz = content.pozycje_gramatyka() + content.pozycje_intencje()
    ids = [p.id for p in poz]
    assert len(ids) == len(set(ids))


def test_kazde_pytanie_ma_co_najmniej_dwie_opcje():
    for p in content.pozycje_gramatyka() + content.pozycje_intencje():
        assert len(p.opcje) >= 2, f"{p.id}: вариантов меньше двух"


def test_kontekst_zawiera_znacznik_luki():
    cw = json.loads((DATA / "cwiczenia_gramatyka.json").read_text(encoding="utf-8"))
    zestaw = cw["zadania"][0]["zestawy"][0]
    frag = content._kontekst(zestaw["tekst"], 3)
    assert "▁▁▁▁▁" in frag
    assert "{3}" not in frag


def test_suma_punktow_gramatyki_wynosi_30():
    """Скелет модуля: 5+2,5+2,5+5+2,5+5+5+2,5 = 30."""
    cw = json.loads((DATA / "cwiczenia_gramatyka.json").read_text(encoding="utf-8"))
    assert sum(z["punkty"] for z in cw["zadania"]) == pytest.approx(30.0)


def test_struktura_egzaminu_zgadza_sie_z_moduami():
    s = json.loads((DATA / "exam_structure.json").read_text(encoding="utf-8"))
    assert len(s["sesje_przeanalizowane"]) == 15
    assert len(s["moduly"]["gramatyka"]["zadania"]) == 8
    assert s["moduly"]["sluchanie"]["zadania"][0]["odtworzenia"] == {"jeden raz": 15}
    for z in s["moduly"]["sluchanie"]["zadania"][1:]:
        assert z["odtworzenia"] == {"dwa razy": 15}


def test_zestawy_pisania_maja_obie_prace():
    for z in content.zestawy_pisanie():
        assert z["a"]["slow"] <= 40, f"{z['id']}: короткая работа слишком длинная"
        assert 160 <= z["b"]["slow"] <= 180, f"{z['id']}: длинная работа вне нормы"


def test_zestawy_mowienia_maja_trzy_zadania():
    for z in content.zestawy_mowienie():
        assert z["z1"] and z["z2"] and z["z3"]


# ------------------------------------------------------------------ подсчёт слов


@pytest.mark.parametrize("tekst,ile", [
    ("", 0),
    ("Dzień dobry", 2),
    ("  Dzień   dobry  ", 2),
    ("Sprzedam rower, stan bardzo dobry.", 5),
    ("A: — ...", 1),
])
def test_licz_slowa(tekst, ile):
    assert content.licz_slowa(tekst) == ile


def test_ocena_objetosci_trafienie():
    ikona, _ = content.ocena_objetosci(30, 30)
    assert ikona == "✅"


def test_ocena_objetosci_za_krotko():
    ikona, kom = content.ocena_objetosci(20, 30)
    assert ikona == "❌"
    assert "10" in kom


def test_ocena_objetosci_za_dlugo():
    ikona, _ = content.ocena_objetosci(200, 170)
    assert ikona == "⚠️"


def test_granice_tolerancji_objetosci():
    """Экзамен считает объём в процентах, допуск ±10%."""
    assert content.ocena_objetosci(153, 170)[0] == "✅"   # 90%
    assert content.ocena_objetosci(152, 170)[0] == "❌"   # 89%
    assert content.ocena_objetosci(187, 170)[0] == "✅"   # 110%
    assert content.ocena_objetosci(188, 170)[0] == "⚠️"  # 111%


# ------------------------------------------------------------------ календарь


def test_dni_do_egzaminu():
    assert content.dni_do_egzaminu(date(2026, 10, 16)) == 1
    assert content.dni_do_egzaminu(date(2026, 8, 17)) == 61


def test_tydzien_programu():
    assert content.tydzien_programu(date(2026, 8, 17))[0] == 1
    assert content.tydzien_programu(date(2026, 8, 24))[0] == 2
    assert content.tydzien_programu(date(2026, 10, 12))[0] == 9
    # за пределами программы не уезжаем
    assert content.tydzien_programu(date(2026, 12, 1))[0] == 9
    assert content.tydzien_programu(date(2026, 1, 1))[0] == 1


# ------------------------------------------------------------------ хранилище


@pytest.fixture()
def baza(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "test.db")
    storage.init()
    return tmp_path


def test_srs_poprawna_odpowiedz_odsuwa_powtorke(baza):
    storage.zapisz_odpowiedz(1, "X-1", "GRAM-I", True)
    assert "X-1" not in storage.do_powtorki(1)
    assert "X-1" in storage.widziane(1)


def test_srs_blad_wraca_na_dzis(baza):
    storage.zapisz_odpowiedz(1, "X-1", "GRAM-I", True)
    storage.zapisz_odpowiedz(1, "X-1", "GRAM-I", False)
    assert "X-1" in storage.do_powtorki(1)


def test_srs_liczy_bledy_po_kategoriach(baza):
    for _ in range(3):
        storage.zapisz_odpowiedz(1, "A-1", "GRAM-VII", False)
    storage.zapisz_odpowiedz(1, "B-1", "GRAM-II", True)
    slabe = storage.slabe_kategorie(1)
    assert slabe[0][0] == "GRAM-VII"
    assert slabe[0][1] == 3


def test_uzytkownicy_nie_mieszaja_sie(baza):
    storage.zapisz_odpowiedz(1, "X-1", "GRAM-I", False)
    assert storage.widziane(2) == set()


def test_error_map_zlicza_kody(baza):
    storage.dodaj_blad(1, "asp", "robiłem", "zrobiłem", "результат")
    storage.dodaj_blad(1, "ASP", "kupowałem", "kupiłem")
    storage.dodaj_blad(1, "ORTH", "rzeka/żeka")
    mapa = dict(storage.mapa_bledow(1))
    assert mapa["ASP"] == 2  # регистр кода не должен плодить категории
    assert mapa["ORTH"] == 1


def test_wyniki_pamietaja_ostatni_pomiar(baza):
    storage.zapisz_wynik(1, "2021-11", "gramatyka", 14, 30)
    storage.zapisz_wynik(1, "2023-11", "gramatyka", 22, 30)
    ost = storage.ostatnie_wyniki(1)
    assert ost["gramatyka"] == (22, 30, "2023-11")


def test_prace_sa_liczone(baza):
    assert storage.liczba_prac(1) == 0
    storage.zapisz_prace(1, "P-01", "a", 31, 30, "tekst")
    assert storage.liczba_prac(1) == 1
