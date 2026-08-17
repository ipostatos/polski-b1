"""Бот подготовки к государственному экзамену B1 (17.10.2026).

Личный бот на одного владельца: чужим не отвечает.

Команды:
  /start      меню
  /dzis       что делать сегодня
  /gramatyka  тренировка грамматики с интервальным повторением
  /intencje   тренажёр задания I аудирования (одно прослушивание)
  /pisanie    комплект для письма, приём работы и проверка объёма
  /mowienie   комплект для устной части, 15 минут
  /blad       записать ошибку в Error Map
  /mapa       карта ошибок
  /wynik      записать результат мока
  /stan       статус по модулям и дни до экзамена
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import content  # noqa: E402
import storage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("plb1")


def wczytaj_env() -> dict[str, str]:
    env: dict[str, str] = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("BOT_TOKEN", "OWNER_ID", "WEBAPP_URL"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


ENV = wczytaj_env()
OWNER_ID = int(ENV.get("OWNER_ID") or 0)

GRAMATYKA = content.pozycje_gramatyka()
INTENCJE = content.pozycje_intencje()
WSZYSTKIE = {p.id: p for p in GRAMATYKA + INTENCJE}

# что бот сейчас ждёт от владельца: ("pisanie", zestaw_id, "a") или ("blad", kod)
OCZEKIWANIE: dict[int, tuple] = {}

dp = Dispatcher()


def swoj(msg_or_cb) -> bool:
    """Личный бот: отвечаем только владельцу."""
    uid = msg_or_cb.from_user.id
    return OWNER_ID == 0 or uid == OWNER_ID


def menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧩 Грамматика", callback_data="go:gram"),
         InlineKeyboardButton(text="🎧 Задание I", callback_data="go:int")],
        [InlineKeyboardButton(text="✍️ Письмо", callback_data="go:pis"),
         InlineKeyboardButton(text="🗣 Говорение", callback_data="go:mow")],
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="go:dzis"),
         InlineKeyboardButton(text="📊 Статус", callback_data="go:stan")],
    ])


# ------------------------------------------------------------------ старт


@dp.message(CommandStart())
async def cmd_start(m: Message) -> None:
    global OWNER_ID
    if OWNER_ID == 0:
        OWNER_ID = m.from_user.id
        _zapisz_owner(OWNER_ID)
        await m.answer(f"Владелец записан: <code>{OWNER_ID}</code>. "
                       "Больше бот никому не отвечает.", parse_mode=ParseMode.HTML)
    if not swoj(m):
        return
    dni = content.dni_do_egzaminu()
    nr, opis = content.tydzien_programu()
    await m.answer(
        f"<b>Polski B1</b> — до экзамена <b>{dni} дней</b> (17.10.2026).\n\n"
        f"Неделя {nr} программы: {opis}\n\n"
        "Порог: 50% в каждом из пяти модулей. Не в среднем — в каждом.",
        parse_mode=ParseMode.HTML, reply_markup=menu())


def _zapisz_owner(uid: int) -> None:
    f = ROOT / ".env"
    if not f.exists():
        return
    txt = f.read_text(encoding="utf-8")
    if re.search(r"^OWNER_ID=.*$", txt, re.M):
        txt = re.sub(r"^OWNER_ID=.*$", f"OWNER_ID={uid}", txt, flags=re.M)
    else:
        txt += f"\nOWNER_ID={uid}\n"
    f.write_text(txt, encoding="utf-8")


# ------------------------------------------------------------------ тренировка


def wybierz(pozycje: list[content.Pozycja], uid: int) -> content.Pozycja | None:
    """Сначала то, что пора повторить, затем новое, затем случайное."""
    do_powt = storage.do_powtorki(uid)
    widz = storage.widziane(uid)
    zapas = [p for p in pozycje if p.id in do_powt]
    if not zapas:
        zapas = [p for p in pozycje if p.id not in widz]
    if not zapas:
        zapas = list(pozycje)
    return random.choice(zapas) if zapas else None


def klawiatura(p: content.Pozycja) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=o, callback_data=f"odp:{p.id}:{i}")]
            for i, o in enumerate(p.opcje)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def pokaz(target: Message, p: content.Pozycja) -> None:
    await target.answer(
        f"<i>{p.naglowek}</i>\n\n{p.pytanie}",
        parse_mode=ParseMode.HTML, reply_markup=klawiatura(p))


@dp.message(Command("gramatyka"))
async def cmd_gramatyka(m: Message) -> None:
    if not swoj(m):
        return
    p = wybierz(GRAMATYKA, m.from_user.id)
    if p:
        await pokaz(m, p)


@dp.message(Command("intencje"))
async def cmd_intencje(m: Message) -> None:
    if not swoj(m):
        return
    p = wybierz(INTENCJE, m.from_user.id)
    if p:
        await pokaz(m, p)


@dp.callback_query(F.data.startswith("odp:"))
async def cb_odpowiedz(cb: CallbackQuery) -> None:
    if not swoj(cb):
        await cb.answer()
        return
    _, item_id, idx = cb.data.split(":", 2)
    p = WSZYSTKIE.get(item_id)
    if not p or not cb.message:
        await cb.answer("позиция не найдена")
        return
    wybor = p.opcje[int(idx)]
    ok = wybor == p.klucz
    storage.zapisz_odpowiedz(cb.from_user.id, p.id, p.kategoria, ok)

    if ok:
        tekst = f"✅ <b>{p.klucz}</b>"
    else:
        tekst = f"❌ ты выбрал <s>{wybor}</s>\n✅ правильно: <b>{p.klucz}</b>"
    if p.wyjasnienie:
        tekst += f"\n\n<i>{p.wyjasnienie}</i>"

    await cb.message.edit_text(
        f"<i>{p.naglowek}</i>\n\n{p.pytanie}\n\n{tekst}", parse_mode=ParseMode.HTML)
    await cb.answer("верно" if ok else "мимо")

    pula = GRAMATYKA if p.kategoria.startswith("GRAM") else INTENCJE
    nast = wybierz(pula, cb.from_user.id)
    if nast:
        await pokaz(cb.message, nast)


# ------------------------------------------------------------------ письмо


@dp.message(Command("pisanie"))
async def cmd_pisanie(m: Message) -> None:
    if not swoj(m):
        return
    z = random.choice(content.zestawy_pisanie())
    OCZEKIWANIE[m.from_user.id] = ("pisanie", z["id"], "a")
    await m.answer(
        f"<b>Zestaw {z['id']}</b> · 75 минут на обе работы\n\n"
        f"<b>a) {z['a']['gatunek']}</b> — {z['a']['slow']} слов\n{z['a']['polecenie']}\n\n"
        f"<b>b) {z['b']['gatunek']}</b> — {z['b']['slow']} слов\n{z['b']['polecenie']}\n\n"
        "Пиши сам, без переводчика. Пришли сначала работу <b>a</b> одним сообщением.",
        parse_mode=ParseMode.HTML)


@dp.message(Command("mowienie"))
async def cmd_mowienie(m: Message) -> None:
    if not swoj(m):
        return
    z = random.choice(content.zestawy_mowienie())
    await m.answer(
        f"<b>Zestaw {z['id']}</b> · до 15 минут на всё\n\n"
        f"<b>Zadanie 1 — opis ilustracji</b>\n{z['z1']}\n\n"
        f"<b>Zadanie 2 — monolog</b>\n{z['z2']}\n\n"
        f"<b>Zadanie 3 — sytuacja komunikacyjna</b>\n{z['z3']}\n\n"
        "Говори вслух и запиши на диктофон: без записи разбор произношения невозможен. "
        "Подготовки заранее нет — на экзамене её тоже нет.",
        parse_mode=ParseMode.HTML)


# ------------------------------------------------------------------ Error Map


@dp.message(Command("blad"))
async def cmd_blad(m: Message) -> None:
    if not swoj(m):
        return
    arg = (m.text or "").split(maxsplit=1)
    if len(arg) < 2:
        await m.answer(
            "Формат: <code>/blad КОД | как написал | как правильно | почему</code>\n\n"
            "Коды: CASE-GEN, CASE-DAT, CASE-ACC, CASE-INS, CASE-LOC, ASP, TENSE, "
            "MOOD, PREP, REKCJA, CONJ, COMP, NUM, WO, LEX, ORTH, REG, TASK",
            parse_mode=ParseMode.HTML)
        return
    czesci = [c.strip() for c in arg[1].split("|")]
    kod = czesci[0]
    zle = czesci[1] if len(czesci) > 1 else ""
    dobrze = czesci[2] if len(czesci) > 2 else ""
    kom = czesci[3] if len(czesci) > 3 else ""
    if not zle:
        await m.answer("Нужен хотя бы текст ошибки после кода.")
        return
    storage.dodaj_blad(m.from_user.id, kod, zle, dobrze, kom)
    ile = dict(storage.mapa_bledow(m.from_user.id)).get(kod.upper(), 1)
    dopisek = ""
    if ile >= 3:
        dopisek = (f"\n\n⚠️ <b>{kod.upper()} повторилась {ile} раз</b> — "
                   "категория уходит в приоритет тренировки.")
    await m.answer(f"Записано в Error Map: <b>{kod.upper()}</b>{dopisek}",
                   parse_mode=ParseMode.HTML)


@dp.message(Command("mapa"))
async def cmd_mapa(m: Message) -> None:
    if not swoj(m):
        return
    mapa = storage.mapa_bledow(m.from_user.id)
    slabe = storage.slabe_kategorie(m.from_user.id)
    if not mapa and not slabe:
        await m.answer("Error Map пока пуста. Ошибки добавляются командой /blad, "
                       "а тренировки пополняют её сами.")
        return
    lines = ["<b>Error Map</b>"]
    for kod, n in mapa:
        marker = " ⚠️" if n >= 3 else ""
        lines.append(f"{kod}: {n}{marker}")
    if slabe:
        lines.append("\n<b>Слабые места по тренировкам</b>")
        for kat, b, p in slabe:
            lines.append(f"{kat}: {b} ошибок из {p} показов")
    await m.answer("\n".join(lines), parse_mode=ParseMode.HTML)


# ------------------------------------------------------------------ результаты


@dp.message(Command("wynik"))
async def cmd_wynik(m: Message) -> None:
    if not swoj(m):
        return
    arg = (m.text or "").split()
    if len(arg) < 4:
        await m.answer(
            "Формат: <code>/wynik сессия модуль баллы</code>\n"
            "Например: <code>/wynik 2021-11 gramatyka 18</code>\n\n"
            "Модули: sluchanie, czytanie, gramatyka, pisanie, mowienie",
            parse_mode=ParseMode.HTML)
        return
    sesja, modul = arg[1], arg[2].lower()
    if modul not in content.MODULY:
        await m.answer(f"Неизвестный модуль: {modul}")
        return
    try:
        punkty = float(arg[3].replace(",", "."))
    except ValueError:
        await m.answer("Баллы должны быть числом.")
        return
    nazwa, maks, prog, cel = content.MODULY[modul]
    storage.zapisz_wynik(m.from_user.id, sesja, modul, punkty, maks)
    proc = punkty / maks * 100
    if punkty >= cel:
        status = "🟢 цель взята"
    elif punkty >= prog:
        status = "🟡 порог есть, но запаса нет"
    else:
        status = "🔴 ниже порога"
    await m.answer(
        f"<b>{nazwa}</b>\n{punkty:g} / {maks:g} = {proc:.0f}%\n"
        f"порог {prog}, цель {cel}\n\n{status}", parse_mode=ParseMode.HTML)


@dp.message(Command("stan"))
async def cmd_stan(m: Message) -> None:
    if not swoj(m):
        return
    await m.answer(tekst_stanu(m.from_user.id), parse_mode=ParseMode.HTML)


def tekst_stanu(uid: int) -> str:
    dni = content.dni_do_egzaminu()
    wyniki = storage.ostatnie_wyniki(uid)
    lines = [f"<b>До экзамена {dni} дней</b>", ""]
    for key, (nazwa, maks, prog, cel) in content.MODULY.items():
        if key in wyniki:
            p, mx, sesja = wyniki[key]
            proc = p / mx * 100
            ikona = "🟢" if p >= cel else ("🟡" if p >= prog else "🔴")
            lines.append(f"{ikona} {nazwa}: {p:g}/{mx:g} ({proc:.0f}%) · {sesja}")
        else:
            lines.append(f"⚪ {nazwa}: замера ещё не было")
    prac = storage.liczba_prac(uid)
    lines += ["", f"Работ по письму сдано: {prac}"]
    return "\n".join(lines)


@dp.message(Command("dzis"))
async def cmd_dzis(m: Message) -> None:
    if not swoj(m):
        return
    await m.answer(tekst_dzis(), parse_mode=ParseMode.HTML)


def tekst_dzis() -> str:
    from datetime import date
    nr, opis = content.tydzien_programu()
    dzien = content.DZIEN[date.today().weekday()]
    return (f"<b>Неделя {nr}</b>\n{opis}\n\n<b>Сегодня</b>\n{dzien}\n\n"
            f"До экзамена {content.dni_do_egzaminu()} дней.")


# ------------------------------------------------------------------ кнопки меню


@dp.callback_query(F.data.startswith("go:"))
async def cb_menu(cb: CallbackQuery) -> None:
    if not swoj(cb) or not cb.message:
        await cb.answer()
        return
    co = cb.data.split(":", 1)[1]
    await cb.answer()
    if co == "gram":
        p = wybierz(GRAMATYKA, cb.from_user.id)
        if p:
            await pokaz(cb.message, p)
    elif co == "int":
        p = wybierz(INTENCJE, cb.from_user.id)
        if p:
            await pokaz(cb.message, p)
    elif co == "pis":
        await cmd_pisanie(cb.message.model_copy(update={"from_user": cb.from_user}))
    elif co == "mow":
        await cmd_mowienie(cb.message.model_copy(update={"from_user": cb.from_user}))
    elif co == "dzis":
        await cb.message.answer(tekst_dzis(), parse_mode=ParseMode.HTML)
    elif co == "stan":
        await cb.message.answer(tekst_stanu(cb.from_user.id), parse_mode=ParseMode.HTML)


# ------------------------------------------------------------------ приём работ


@dp.message(F.text & ~F.text.startswith("/"))
async def przyjmij_prace(m: Message) -> None:
    if not swoj(m):
        return
    stan = OCZEKIWANIE.get(m.from_user.id)
    if not stan or stan[0] != "pisanie":
        await m.answer("Не понял. /start — меню, /dzis — план на сегодня.")
        return
    _, zestaw_id, czesc = stan
    zestawy = {z["id"]: z for z in content.zestawy_pisanie()}
    z = zestawy.get(zestaw_id)
    if not z:
        OCZEKIWANIE.pop(m.from_user.id, None)
        return
    wymagane = z[czesc]["slow"]
    slow = content.licz_slowa(m.text or "")
    ikona, komentarz = content.ocena_objetosci(slow, wymagane)
    storage.zapisz_prace(m.from_user.id, zestaw_id, czesc, slow, wymagane, m.text or "")

    if czesc == "a":
        OCZEKIWANIE[m.from_user.id] = ("pisanie", zestaw_id, "b")
        dalej = (f"\n\nТеперь работа <b>b</b>: {z['b']['gatunek']}, "
                 f"{z['b']['slow']} слов.\n{z['b']['polecenie']}")
    else:
        OCZEKIWANIE.pop(m.from_user.id, None)
        dalej = ("\n\nКомплект закрыт. Обе работы сохранены — пришли их мне в чат "
                 "на разбор по официальным критериям.")
    await m.answer(f"{ikona} <b>Objętość</b>\n{komentarz}{dalej}",
                   parse_mode=ParseMode.HTML)


# ------------------------------------------------------------------ запуск


async def main() -> None:
    token = ENV.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Нет BOT_TOKEN: заполни .env")
    storage.init()
    log.info("позиций для тренировки: грамматика %d, задание I %d",
             len(GRAMATYKA), len(INTENCJE))
    bot = Bot(token)
    me = await bot.get_me()
    log.info("бот @%s запущен, владелец %s", me.username, OWNER_ID or "ещё не задан")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
