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

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


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


def test_skelet_gramatyki_w_strukturze():
    """Каждое задание грамматики стоит одинаково во всех 15 сессиях, сумма 30.

    Ловит регресс парсера: раньше regex промахивался мимо строки баллов
    задания VIII и записывал ему итог модуля (30 p.) в 12 сессиях из 15.
    """
    s = json.loads((DATA / "exam_structure.json").read_text(encoding="utf-8"))
    oczekiwane = {"I": "5.0", "II": "2.5", "III": "2.5", "IV": "5.0",
                  "V": "2.5", "VI": "5.0", "VII": "5.0", "VIII": "2.5"}
    for z in s["moduly"]["gramatyka"]["zadania"]:
        assert z["punkty_rozklad"] == {oczekiwane[z["nr"]]: 15}, \
            f"zadanie {z['nr']}: {z['punkty_rozklad']}"
    assert sum(float(k) for z in s["moduly"]["gramatyka"]["zadania"]
               for k in z["punkty_rozklad"]) == pytest.approx(30.0)


def test_tajming_egzaminu_2026():
    """Актуальная письменная часть: 25 + 45 + 45 + 75 = 190 минут."""
    s = json.loads((DATA / "exam_structure.json").read_text(encoding="utf-8"))
    e = s["egzamin_2026"]
    assert e["sluchanie"] + e["czytanie"] + e["gramatyka"] + e["pisanie"] == 190
    assert e["razem_pisemna"] == 190


def test_ramka_ma_dokladnie_jeden_zbedny_wyraz():
    """Если polecenie обещает «jeden wyraz zbędny», лишним должно быть ровно одно слово."""
    cw = json.loads((DATA / "cwiczenia_gramatyka.json").read_text(encoding="utf-8"))
    for z in cw["zadania"]:
        if "jeden wyraz zbędny" not in z.get("format", ""):
            continue
        for zestaw in z["zestawy"]:
            ramka = [w.lower() for w in zestaw["ramka"]]
            klucze = [zd["klucz"].lower() for zd in zestaw["zdania"]]
            assert len(ramka) == len(klucze) + 1, \
                f"{zestaw['id']}: {len(ramka)} слов в рамке при {len(klucze)} пропусках"
            for k in klucze:
                assert k in ramka, f"{zestaw['id']}: ключ {k!r} не в рамке"
            zbedne = set(ramka) - set(klucze)
            assert len(zbedne) == 1, f"{zestaw['id']}: лишние {zbedne}"
            assert zestaw["zbedny"].lower() in zbedne


def test_otwarte_pozycje_sa_kompletne():
    czasy = content.pozycje_czasy()
    trans = content.pozycje_transformacje()
    assert len(czasy) == 10 and len(trans) == 5
    for o in czasy + trans:
        assert o.klucz
        assert o.poprawna(o.klucz), f"{o.id}: собственный ключ не принимается"
        for wariant in o.akceptowane:
            assert o.poprawna(wariant), f"{o.id}: вариант {wariant!r} не принимается"


def test_normalizuj_ignoruje_wielkosc_i_interpunkcje():
    assert content.normalizuj("  Warto, przeczytać tę książkę! ") == \
        content.normalizuj("warto przeczytać tę książkę")
    assert content.normalizuj("A") != content.normalizuj("B")


def test_intencje_maja_transkrypcje_i_pytanie_audio():
    for p in content.pozycje_intencje():
        assert p.transkrypcja
        assert p.pytanie_audio
        # если аудио сгенерировано — файл существует и не пуст
        if p.audio is not None:
            assert p.audio.exists() and p.audio.stat().st_size > 0


def test_zestawy_mowienia_maja_dialog_zadania_3():
    for z in content.zestawy_mowienie():
        assert len(z.get("z3_dialog", [])) >= 3, f"{z['id']}: нет диалога задания 3"


# ------------------------------------------------------------------ документация


def _sciezki_z_dokumentow() -> list[tuple[str, str]]:
    """Все упоминания путей репозитория в docs/*.md и README."""
    import re
    wynik = []
    for md in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]:
        text = md.read_text(encoding="utf-8")
        # markdown-ссылки [x](path) и пути в `backticks`
        for m in re.finditer(r"\]\(([^)#\s]+)\)|`((?:docs|data|tools|bot|workbook|webapp)/[^`\s]+)`", text):
            path = m.group(1) or m.group(2)
            if path and not path.startswith(("http", "mailto")):
                wynik.append((md.name, path))
    return wynik


def test_dokumentacja_nie_ma_martwych_sciezek():
    """Каждый упомянутый в документации файл репозитория обязан существовать.

    Исключение — то, что по правилам живёт только локально (архив, ключи,
    личный прогресс): его в CI нет и не должно быть.
    """
    lokalne = ("archive", "archive_text", "klucze", "moje", "data/exam_map.json",
               "data/audio", "data/obrazki")
    for zrodlo, path in _sciezki_z_dokumentow():
        if path.startswith(lokalne):
            continue
        assert (ROOT / path).exists(), f"{zrodlo}: битая ссылка {path}"


def test_dokumentacja_bez_ustawy_2016_jako_aktualnej():
    """Акт 2016 года можно упоминать только как исторический/утративший силу."""
    for md in sorted((ROOT / "docs").glob("*.md")):
        text = md.read_text(encoding="utf-8")
        if "2016 poz. 405" in text or "poz. 405" in text:
            assert "утрат" in text or "историч" in text, \
                f"{md.name}: ссылка на отменённый акт 2016 без оговорки"


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
