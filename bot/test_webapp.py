"""Статические проверки Mini App (PR mobile-ux-polish).

Фронтенд без JS-тестовой инфраструктуры — тащить фреймворк ради десятка
инвариантов не стоит. Эти проверки читают исходники как текст и сторожат
договорённости ревью: одна кнопка «назад», честный readiness без замера,
«Дальше» только после ответа, иллюстрации говорения, выбор сессии только
из известного списка, empty state Historii с действием.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")


def test_back_jeden_nie_dwa():
    """В Telegram — только нативный BackButton; свой «‹ Назад» лишь вне него."""
    assert "${back && !W_TELEGRAMIE ?" in APP  # внутренний back только вне Telegram
    assert "!!(tg && tg.initData)" in APP      # «внутри Telegram» = по initData,
    assert "tg.BackButton.show()" in APP       # ...а не по наличию объекта WebApp
    assert "tg.BackButton.onClick" in APP


def test_readiness_bez_zameru_nie_zero():
    """0 замеренных модулей → «Нет замера» и нейтральное кольцо, а не «0%»."""
    assert "bezZamiaru" in APP
    assert "!g.zmierzone" in APP
    assert "Нет замера" in APP
    assert 'bezZamiaru ? "—"' in APP                       # вместо процента — прочерк
    assert 'bezZamiaru ? "var(--hint)"' in APP             # кольцо нейтральное, не красное


def test_dalej_tylko_po_odpowiedzi():
    """Кнопка «Дальше» рождается disabled в обоих тренажёрах и открывается кодом."""
    assert APP.count('id="next" disabled') >= 2            # widokWybor + widokOtwarte
    assert APP.count('document.getElementById("next").disabled = false') >= 2


def test_mowienie_ma_ilustracje():
    """Каждый набор говорения несёт z1_image, файл существует, грузится лениво."""
    dane = json.loads((ROOT / "data" / "zadania_mowienie.json").read_text(encoding="utf-8"))
    for z in dane["zestawy"]:
        assert z.get("z1_image"), f"{z['id']}: нет z1_image"
        plik = ROOT / "data" / "mowienie" / z["z1_image"]
        assert plik.is_file(), f"{z['id']}: нет файла {plik.name}"
    assert 'loading="lazy"' in APP
    assert "сцена пока описана словами" not in APP         # технический текст убран


def test_egzamin_tylko_znane_sesje():
    """Свободного ввода сессии нет; список в app.js равен ключам exam_map.json."""
    assert '<select id="sesja"' in APP
    assert 'input type="text" id="sesja"' not in APP
    mapa = json.loads((ROOT / "data" / "exam_map.json").read_text(encoding="utf-8"))
    lista = re.search(r"SESJE_ARKUSZY = \[(.*?)\]", APP, re.S)
    assert lista, "нет списка SESJE_ARKUSZY"
    w_app = set(re.findall(r'"(\d{4}-\d{2})"', lista.group(1)))
    assert w_app == set(mapa.keys())


def test_historia_pusta_ma_dzialanie():
    """Пустая история предлагает следующий шаг, а не мёртвый экран."""
    assert "Начать диагностику" in APP


def test_inputy_po_polsku():
    """Поля польского ввода объявляют lang=pl (Czasy/Transformacje, Pisanie, Error Map)."""
    assert APP.count('lang="pl"') >= 4
    assert 'spellcheck="true"' in APP


def test_bez_emoji_ikon():
    """Разнобойные системные emoji в плитках практики заменены на единые SVG."""
    for emoji in ("🎓", "🧩", "🎧", "⏱", "🔁", "📖", "✍", "🗣", "🗺", "📈"):
        assert emoji not in APP, f"emoji {emoji} всё ещё в app.js"
    assert "IKONY" in APP and 'stroke="currentColor"' in APP


def test_mowienie_bez_slowa_projdena():
    """Тренировку не «проходят» — её завершают; оценки не было."""
    assert "Сессия пройдена" not in APP
    assert "Завершить тренировку" in APP


def test_czytanie_nie_zaglushka():
    """Чтение — guided workflow с материалом и чек-листом, не заглушка."""
    assert "Тренажёра чтения в приложении нет" not in APP
    assert "certyfikatpolski.pl" in APP
    assert "Начать тренировку" in APP


def test_safe_area_iphone():
    css = (ROOT / "webapp" / "theme.css").read_text(encoding="utf-8")
    assert "safe-area-inset-top" in css
    assert "safe-area-inset-bottom" in css
