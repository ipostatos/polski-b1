"""HTTP API дашборда Mini App. Поднимается в процессе бота на 127.0.0.1:API_PORT,
наружу выходит только через reverse proxy (Caddy, /api/*).

Авторизация: каждый запрос несёт заголовок `Authorization: tma <initData>`.
Подпись initData проверяется по алгоритму Telegram (HMAC-SHA256, ключ
"WebAppData"), затем auth_date на свежесть и user.id на совпадение с OWNER_ID.
Переданному user_id без подписи не верим никогда. SQLite наружу не смотрит —
API отдаёт только агрегаты.

Исключение — GET /api/config: статические константы экзамена (пороги, тайминг,
дата), в них нет ничего личного, а Mini App на GitHub Pages без них не соберёт
даже пустой дашборд.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import date
from urllib.parse import parse_qsl

from aiohttp import web

import content
import gotowosc
import storage

MAX_WIEK_INITDATA = 24 * 3600      # сутки: Telegram выдаёт initData при каждом открытии
DOZWOLONE_ORIGINS = {"https://ipostatos.github.io"}

# типы, которые Mini App может отметить вручную (протокольные активности);
# остальное логируется сервером само при реальных действиях
RECZNE_TYPY = {"czytanie", "mowienie", "powtorka"}


# ------------------------------------------------------------------ initData


def waliduj_init_data(init_data: str, bot_token: str,
                      teraz: float | None = None,
                      max_wiek: int = MAX_WIEK_INITDATA) -> dict | None:
    """Проверяет подпись initData. Возвращает разобранные поля или None.

    Алгоритм Telegram: data_check_string = отсортированные "k=v" без hash,
    secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token),
    hash = hex(HMAC_SHA256(key=secret_key, msg=data_check_string)).
    """
    if not init_data or not bot_token:
        return None
    try:
        pary = parse_qsl(init_data, keep_blank_values=True)
    except ValueError:
        return None
    dane = dict(pary)
    podpis = dane.pop("hash", None)
    if not podpis:
        return None
    sprawdzane = "\n".join(f"{k}={v}" for k, v in sorted(dane.items()))
    sekret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    oczekiwany = hmac.new(sekret, sprawdzane.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(oczekiwany, podpis):
        return None
    try:
        auth_date = int(dane.get("auth_date", "0"))
    except ValueError:
        return None
    if (teraz or time.time()) - auth_date > max_wiek:
        return None
    return dane


def user_id_z(dane: dict) -> int | None:
    try:
        return int(json.loads(dane.get("user", "")).get("id"))
    except (ValueError, TypeError, AttributeError):
        return None


# ------------------------------------------------------------------ приложение


def zbuduj_api(bot_token: str, owner_id: int, pula: dict[str, int]) -> web.Application:
    """`pula` — размеры пулов тренажёров: {"gramatyka": n, "sluchanie": n, "otwarte": n}."""

    def autoryzuj(request: web.Request) -> int:
        naglowek = request.headers.get("Authorization", "")
        if not naglowek.startswith("tma "):
            raise web.HTTPUnauthorized(text="brak initData")
        dane = waliduj_init_data(naglowek[4:], bot_token)
        if dane is None:
            raise web.HTTPUnauthorized(text="podpis nieprawidłowy")
        uid = user_id_z(dane)
        if uid is None:
            raise web.HTTPUnauthorized(text="brak user")
        if uid != owner_id:
            raise web.HTTPForbidden(text="bot prywatny")
        return uid

    # -------------------------------------------------- endpoints

    async def api_config(_: web.Request) -> web.Response:
        return web.json_response({
            "exam_date": content.EGZAMIN.isoformat(),
            "moduly": {k: {"nazwa": n, "maks": m, "prog": p, "cel": c}
                       for k, (n, m, p, c) in content.MODULY.items()},
            "timing": content.TIMING,
            "przerwa_min": content.PRZERWA_MIN,
            "mowienie_max_min": content.MOWIENIE_MAX_MIN,
            "plan_tygodni": [{"nr": nr, "od": od, "do": do, "opis": opis}
                             for nr, od, do, opis in content.PLAN],
        })

    async def api_dashboard(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        srs = storage.podsumowanie_srs(uid)
        historia = storage.historia_wynikow(uid)
        wyniki = storage.ostatnie_wyniki(uid)
        prace = storage.objetosc_ostatnich_prac(uid)
        mapa = storage.mapa_bledow(uid)
        got = gotowosc.gotowosc(content.MODULY, wyniki, srs["kategorie"], prace, mapa)
        tr = gotowosc.trendy(historia)
        dni_akt = storage.aktywnosc_dni(uid, 84)
        dzis = storage.aktywnosc_dzis(uid)
        plan = content.plan_dnia(date.today().weekday(), dzis)
        tydzien_nr, tydzien_opis = content.tydzien_programu()

        moduly = {}
        for k, (nazwa, maks, prog, cel) in content.MODULY.items():
            ostatni = None
            if k in wyniki:
                p, mx, sesja = wyniki[k]
                ostatni = {"punkty": p, "maks": mx, "sesja": sesja}
            moduly[k] = {"nazwa": nazwa, "maks": maks, "prog": prog, "cel": cel,
                         "ostatni": ostatni, "trend": tr.get(k)}

        return web.json_response({
            "exam": {"date": content.EGZAMIN.isoformat(),
                     "days_left": content.dni_do_egzaminu()},
            "readiness": got,
            "modules": moduly,
            "srs": {"znane": srs["znane"], "due": srs["due"],
                    "zakreplone": srs["zakreplone"], "pula": sum(pula.values())},
            "today": {"plan": plan,
                      "done": sum(1 for p in plan if p["done"]),
                      "target": len(plan)},
            "week": {"nr": tydzien_nr, "opis": tydzien_opis},
            "streak": gotowosc.seria(dni_akt, date.today()),
            "activity": dni_akt,
            "weakest": {
                "error_map": [{"kod": k, "n": n, "priorytet": n >= 3}
                              for k, n in mapa[:5]],
                "kategorie": [{"kategoria": k, "bledy": b, "pokazy": p}
                              for k, b, p in storage.slabe_kategorie(uid, 3)],
            },
        })

    async def api_odpowiedz(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        cialo = await request.json()
        item_id = str(cialo.get("item_id", ""))[:64]
        kategoria = str(cialo.get("kategoria", ""))[:32]
        ok = bool(cialo.get("ok"))
        if not item_id or not kategoria:
            raise web.HTTPBadRequest(text="item_id i kategoria wymagane")
        byla_powtorka = item_id in storage.do_powtorki(uid)
        storage.zapisz_odpowiedz(uid, item_id, kategoria, ok)
        typ = "sluchanie" if kategoria in ("INTENCJA", "SYTUACJA") else "gramatyka"
        storage.zaloguj_aktywnosc(uid, typ)
        if byla_powtorka:
            storage.zaloguj_aktywnosc(uid, "powtorka")
        return web.json_response({"zapisano": True})

    async def api_praca(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        cialo = await request.json()
        try:
            slow = int(cialo["slow"])
            wymagane = int(cialo["wymagane"])
        except (KeyError, ValueError, TypeError):
            raise web.HTTPBadRequest(text="slow i wymagane wymagane")
        storage.zapisz_prace(uid, str(cialo.get("zestaw", ""))[:16],
                             str(cialo.get("czesc", ""))[:4], slow, wymagane,
                             str(cialo.get("tekst", ""))[:20000])
        storage.zaloguj_aktywnosc(uid, "pisanie")
        return web.json_response({"zapisano": True})

    async def api_wynik(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        cialo = await request.json()
        modul = str(cialo.get("modul", "")).lower()
        if modul not in content.MODULY:
            raise web.HTTPBadRequest(text="nieznany moduł")
        try:
            punkty = float(cialo["punkty"])
        except (KeyError, ValueError, TypeError):
            raise web.HTTPBadRequest(text="punkty muszą być liczbą")
        _, maks, prog, cel = content.MODULY[modul]
        if not 0 <= punkty <= maks:
            raise web.HTTPBadRequest(text=f"punkty poza zakresem 0–{maks}")
        sesja = str(cialo.get("sesja", ""))[:32] or date.today().isoformat()
        storage.zapisz_wynik(uid, sesja, modul, punkty, maks)
        storage.zaloguj_aktywnosc(uid, "mok")
        return web.json_response({
            "zapisano": True, "prog": prog, "cel": cel,
            "status": "cel" if punkty >= cel else ("prog" if punkty >= prog else "oblany"),
        })

    async def api_blad(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        cialo = await request.json()
        kod = str(cialo.get("kod", "")).strip()[:16]
        zle = str(cialo.get("zle", "")).strip()[:500]
        if not kod or not zle:
            raise web.HTTPBadRequest(text="kod i zle wymagane")
        storage.dodaj_blad(uid, kod, zle, str(cialo.get("dobrze", ""))[:500],
                           str(cialo.get("komentarz", ""))[:500])
        storage.zaloguj_aktywnosc(uid, "blad")
        ile = dict(storage.mapa_bledow(uid)).get(kod.upper(), 1)
        return web.json_response({"zapisano": True, "razem": ile, "priorytet": ile >= 3})

    async def api_aktywnosc(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        cialo = await request.json()
        typ = str(cialo.get("typ", ""))
        if typ not in RECZNE_TYPY:
            raise web.HTTPBadRequest(text="tego typu nie można odnotować ręcznie")
        storage.zaloguj_aktywnosc(uid, typ)
        return web.json_response({"zapisano": True})

    async def api_wyniki(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        historia = storage.historia_wynikow(uid)
        sesje: dict[str, dict] = {}
        for w in historia:
            s = sesje.setdefault(w["sesja"], {"sesja": w["sesja"], "kiedy": w["kiedy"],
                                              "wyniki": {}})
            s["wyniki"][w["modul"]] = w["punkty"]
            s["kiedy"] = max(s["kiedy"], w["kiedy"])
        lista = sorted(sesje.values(), key=lambda s: s["kiedy"])
        for s in lista:
            if len(s["wyniki"]) == len(content.MODULY):
                zdany, oblane = gotowosc.egzamin_zdany(s["wyniki"], content.MODULY)
                s["zdany"], s["oblane"] = zdany, oblane
            else:
                s["zdany"], s["oblane"] = None, []   # niepełny mok — вердикта нет
        return web.json_response({"sesje": lista, "trendy": gotowosc.trendy(historia)})

    async def api_powtorki(request: web.Request) -> web.Response:
        uid = autoryzuj(request)
        return web.json_response({"due": sorted(storage.do_powtorki(uid))})

    # -------------------------------------------------- CORS (для GitHub Pages)

    @web.middleware
    async def cors(request: web.Request, handler):
        origin = request.headers.get("Origin", "")
        dozwolony = origin in DOZWOLONE_ORIGINS
        if request.method == "OPTIONS":
            odp = web.Response(status=204)
        else:
            try:
                odp = await handler(request)
            except web.HTTPException as e:
                odp = e
        if dozwolony:
            odp.headers["Access-Control-Allow-Origin"] = origin
            odp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            odp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        if isinstance(odp, web.HTTPException):
            raise odp
        return odp

    app = web.Application(middlewares=[cors])
    app.router.add_get("/api/config", api_config)
    app.router.add_get("/api/dashboard", api_dashboard)
    app.router.add_get("/api/wyniki", api_wyniki)
    app.router.add_get("/api/powtorki", api_powtorki)
    app.router.add_post("/api/odpowiedz", api_odpowiedz)
    app.router.add_post("/api/praca", api_praca)
    app.router.add_post("/api/wynik", api_wynik)
    app.router.add_post("/api/blad", api_blad)
    app.router.add_post("/api/aktywnosc", api_aktywnosc)
    # OPTIONS-префлайты обрабатывает CORS-middleware — отдельные маршруты не нужны
    return app


async def uruchom_api(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    await site.start()
    return runner
