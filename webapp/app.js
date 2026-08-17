/* Polski B1 — Mini App: личный дашборд подготовки к госэкзамену.
   Source of truth прогресса — SQLite на сервере (API бота, /api/*).
   Авторизация: initData Telegram, подпись проверяет сервер.
   Вне Telegram приложение работает, но прогресс не сохраняется — об этом
   говорит баннер, никаких локальных «теневых» процентов не рисуем. */
"use strict";

const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (tg) { tg.ready(); tg.expand(); }

/* API: same-origin за Caddy; на GitHub Pages — кросс-доменный fallback */
const API_BASE = location.hostname.endsWith("github.io")
  ? "https://polski-b1-46-224-220-94.sslip.io" : "";
const AUTH = tg && tg.initData ? "tma " + tg.initData : null;

const DATA = "../data/";
const app = document.getElementById("app");
const S = { cfg: null, dash: null, authed: false, niezapisane: 0 };

async function api(path, body) {
  const opts = { headers: {} };
  if (AUTH) opts.headers["Authorization"] = AUTH;
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(API_BASE + path, opts);
  if (!r.ok) throw new Error(path + ": " + r.status);
  return r.json();
}

/* запись, которую не жалко потерять молча, — не бывает; считаем несохранённое */
function apiCicho(path, body) {
  return api(path, body).catch(() => { S.niezapisane += 1; });
}

/* ── утилиты ── */
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function dniDoEgzaminu() {
  const d = S.cfg ? new Date(S.cfg.exam_date + "T00:00:00") : new Date(2026, 9, 17);
  return Math.ceil((d - new Date()) / 86400000);
}
function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function normalizuj(t) {
  return t.toLowerCase().replace(/[,.!?…;:„”"'—–()]/g, " ").replace(/\s+/g, " ").trim();
}
function liczSlowa(t) {
  return t.split(/\s+/).filter(w => /[\p{L}\p{N}]/u.test(w)).length;
}
function kontekst(tekst, nr, okno = 130) {
  const marker = "{" + nr + "}";
  const i = tekst.indexOf(marker);
  if (i < 0) return tekst.slice(0, okno);
  const start = Math.max(0, i - okno), end = Math.min(tekst.length, i + marker.length + okno);
  let frag = tekst.slice(start, end);
  for (let m = 1; m < 20; m++)
    frag = frag.split("{" + m + "}").join(m === nr ? "▁▁▁▁▁" : "……");
  return (start ? "… " : "") + frag.trim() + (end < tekst.length ? " …" : "");
}
const MMSS = s => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
/* локальная ISO-дата: toISOString даёт UTC и вечером «уезжает» на вчера */
const isoLokalne = dt => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;

/* логотип: мини-«karta odpowiedzi» с красной отметкой — мотив hero из README */
const MARK = `<svg class="mark" viewBox="0 0 30 30" aria-hidden="true">
  <rect x="1.5" y="1.5" width="27" height="27" rx="7" fill="#16202F" stroke="#5B9BD9" stroke-width="1.6"/>
  <rect x="7" y="8" width="6" height="6" rx="1.5" fill="none" stroke="#8B98AC" stroke-width="1.4"/>
  <rect x="7" y="17" width="6" height="6" rx="1.5" fill="#C7495B"/>
  <path d="M16 11h7M16 20h7" stroke="#8B98AC" stroke-width="1.6" stroke-linecap="round"/>
</svg>`;

/* ── учебные данные (те же id позиций, что в боте) ── */
let D = null;
async function loadData() {
  const [cw, intencje, pisanie, mowienie] = await Promise.all(
    ["cwiczenia_gramatyka.json", "intencje.json", "zadania_pisanie.json",
     "zadania_mowienie.json"].map(f => fetch(DATA + f).then(r => {
       if (!r.ok) throw new Error(f + ": " + r.status);
       return r.json();
     })));
  D = { cw, intencje, pisanie, mowienie };
  D.gram = pozycjeGram(cw);
  D.int = pozycjeInt(intencje);
  D.czasy = pozycjeOtwarte(cw, "IV");
  D.trans = pozycjeOtwarte(cw, "VI");
  D.wszystkie = new Map([...D.gram, ...D.int].map(p => [p.id, p]));
  D.otwarte = new Map([...D.czasy, ...D.trans].map(p => [p.id, p]));
}
function pozycjeGram(cw) {
  const out = [];
  for (const z of cw.zadania) {
    const kat = "GRAM-" + z.nr, nag = `Zadanie ${z.nr} — ${z.sprawdza}`;
    for (const zestaw of z.zestawy) {
      for (const luka of (zestaw.luki || [])) {
        if (!luka.opcje) continue;
        out.push({ id: `${zestaw.id}-${luka.nr}`, kat, nag,
          pytanie: kontekst(zestaw.tekst, luka.nr),
          opcje: luka.opcje.slice(), klucz: luka.klucz, dlaczego: luka.dlaczego || "" });
      }
      if (zestaw.ramka) {
        for (const zd of zestaw.zdania) {
          const inne = shuffle(zestaw.ramka.filter(
            w => w.toLowerCase() !== zd.klucz.toLowerCase())).slice(0, 3);
          out.push({ id: `${zestaw.id}-${zd.nr}`, kat, nag,
            pytanie: zd.tekst, opcje: shuffle([zd.klucz, ...inne]),
            klucz: zd.klucz, dlaczego: zd.dlaczego || "" });
        }
      }
    }
  }
  return out;
}
function pozycjeInt(src) {
  const out = [];
  src.pozycje.forEach((p, i) => out.push({
    id: `INT-${String(i + 1).padStart(3, "0")}`, kat: "INTENCJA",
    nag: "Zadanie I — intencja wypowiedzi", tekst: p.tekst,
    pyt: "Ta wypowiedź to:", opcje: shuffle([p.klucz, ...p.dystraktory]),
    klucz: p.klucz, dlaczego: p.wskazowka || "", audio: true }));
  src.sytuacje.pozycje.forEach((p, i) => out.push({
    id: `SYT-${String(i + 1).padStart(3, "0")}`, kat: "SYTUACJA",
    nag: "Zadanie I — miejsce wypowiedzi", tekst: p.tekst,
    pyt: "Ta wypowiedź jest typowa:", opcje: shuffle([p.klucz, ...p.dystraktory]),
    klucz: p.klucz, dlaczego: "", audio: true }));
  return out;
}
function pozycjeOtwarte(cw, nr) {
  const out = [];
  for (const z of cw.zadania) {
    if (z.nr !== nr) continue;
    const nag = `Zadanie ${z.nr} — ${z.sprawdza}`;
    for (const zestaw of z.zestawy) {
      for (const luka of (zestaw.luki || []))
        out.push({ id: `${zestaw.id}-${luka.nr}`, kat: "GRAM-" + nr, nag,
          pytanie: kontekst(zestaw.tekst, luka.nr), hint: `(${luka.podstawa})`,
          klucz: luka.klucz, akceptowane: luka.akceptowane || [],
          dlaczego: luka.dlaczego || "" });
      for (const zd of (zestaw.zdania || []))
        out.push({ id: `${zestaw.id}-${zd.nr}`, kat: "GRAM-" + nr, nag,
          pytanie: zd.zdanie, hint: `użyj: ${zd.wyraz}`,
          klucz: zd.klucz, akceptowane: zd.akceptowane || [],
          dlaczego: zd.dlaczego || "" });
    }
  }
  return out;
}

/* Запись ответа: истину о результате определяет СЕРВЕР по content —
   клиент шлёт только id позиции и сам ответ. Возвращает {ok, klucz,
   akceptowane, zapisano}; при недоступном API — локальная проверка
   (прогресс не записан, счётчик niezapisane растёт). */
async function sprawdzOdpowiedz(p, odpowiedz) {
  if (S.authed) {
    try {
      const r = await api("/api/odpowiedz", { item_id: p.id, odpowiedz });
      return { ok: r.ok, klucz: r.klucz, akceptowane: r.akceptowane || [], zapisano: true };
    } catch (e) { S.niezapisane += 1; }
  }
  const warianty = [p.klucz, ...(p.akceptowane || [])].map(normalizuj);
  return { ok: warianty.includes(normalizuj(odpowiedz)), klucz: p.klucz,
           akceptowane: p.akceptowane || [], zapisano: false };
}

/* выбор позиции: очередь due (если знаем) → новое → случайное */
function wybierz(pula, dueSet) {
  if (dueSet && dueSet.size) {
    const due = pula.filter(p => dueSet.has(p.id));
    if (due.length) return due[Math.floor(Math.random() * due.length)];
  }
  return pula[Math.floor(Math.random() * pula.length)];
}

/* ── каркас ── */
let widok = "home";
let aktywnyTimer = null;
/* один живой таймер на экран: смена экрана гасит предыдущий */
function timerEkranu(fn, ms) {
  if (aktywnyTimer) clearInterval(aktywnyTimer);
  aktywnyTimer = setInterval(fn, ms);
  return aktywnyTimer;
}
function render(name, html, opts = {}) {
  widok = name;
  if (aktywnyTimer) { clearInterval(aktywnyTimer); aktywnyTimer = null; }
  const back = name !== "home";
  if (tg) { back ? tg.BackButton.show() : tg.BackButton.hide(); }
  app.innerHTML = `
    ${back ? `<header class="top"><button class="back" id="back">‹ Назад</button></header>` : ""}
    ${html}`;
  const b = document.getElementById("back");
  if (b) b.onclick = przeladujHome;
  if (opts.after) opts.after();
  window.scrollTo(0, 0);
}
if (tg) tg.BackButton.onClick(() => { if (widok !== "home") przeladujHome(); });

async function przeladujHome() {
  if (S.authed) { try { S.dash = await api("/api/dashboard"); } catch (e) { /* оставляем прежний */ } }
  home();
}

/* ═══════════════════════════ ДАШБОРД ═══════════════════════════ */

function home() {
  const d = S.dash;
  const cfg = S.cfg;
  const czesci = [];

  czesci.push(`
    <div class="hero">${MARK}<h1>Polski B1</h1></div>
    <p class="sub">Подготовка к государственному экзамену · B1 dorośli</p>`);

  if (!S.authed) czesci.push(`
    <div class="banner">Открыто вне Telegram — прогресс <b>не сохраняется</b>
    и дашборд не считается. Открой через @Pl_B1_bot.</div>`);
  if (S.niezapisane > 0) czesci.push(`
    <div class="banner">⚠ ${S.niezapisane} ответ(а) не дошли до сервера — проверь связь.</div>`);

  if (d) {
    /* ── пора повторить ── */
    const srs = d.srs;
    czesci.push(`
      <div class="next">
        <div class="label">Пора повторить</div>
        <div class="big">↻ ${srs.due} к повторению</div>
        <div class="hintline">Интервальное повторение · закреплено ${srs.zakreplone}
          из ${srs.znane} изученных · всего в пуле ${srs.pula}</div>
        <div class="actions">
          <button class="btn" data-go="powtorki" ${srs.due ? "" : "disabled"}>Повторить</button>
          <button class="btn ghost" data-go="plan">План</button>
        </div>
      </div>`);

    /* ── готовность ── */
    const g = d.readiness;
    const kolor = g.razem >= 70 ? "var(--ok)" : g.razem >= 50 ? "var(--warn)" : "var(--red)";
    const slabe = [...d.weakest.kategorie.map(k => ({ label: nazwaKategorii(k.kategoria), go: goDlaKategorii(k.kategoria) })),
                   ...d.weakest.error_map.filter(e => e.priorytet).map(e => ({ label: e.kod, go: "mapa" }))]
      .slice(0, 3);
    czesci.push(`
      <div class="card" style="margin-bottom:var(--sp-3)">
        <div style="display:flex; gap:var(--sp-4); align-items:center">
          <div class="ring" style="--p:${g.razem}; --ring-color:${kolor}">
            <div class="ring-val"><span class="ring-num num">${g.razem}%</span>
            <span class="ring-cap">B1</span></div>
          </div>
          <div style="flex:1; min-width:0">
            <div class="h2" style="margin:0 0 2px">Готовность · B1</div>
            <div style="font-size:var(--fs-sm)">${esc(g.status)}</div>
            <div class="muted" style="font-size:var(--fs-xs); margin-top:4px">
              замерено ${g.zmierzone} из 5 модулей ·
              <span data-go="oGotowosci" style="text-decoration:underline; cursor:pointer">как считается?</span>
            </div>
          </div>
        </div>
        <div class="stats" style="margin-top:var(--sp-3)">
          <div><div class="k">Сегодня</div><div class="v num">${d.today.done}/${d.today.target}</div></div>
          <div><div class="k">Серия</div><div class="v num">${d.streak} дн</div></div>
          <div><div class="k">До экзамена</div><div class="v num">${d.exam.days_left}</div></div>
        </div>
        ${slabe.length ? `<div class="muted" style="font-size:var(--fs-sm); margin-top:var(--sp-3)">
          Слабее всего (${d.weakest.okno_dni ?? 30} дн): ${slabe.map(s =>
            `<span class="chip tap" data-go="${s.go}">${esc(s.label)}</span>`).join(" ")}
        </div>` : ""}
      </div>`);

    /* ── пять модулей ── */
    const ob = d.pisanie_objetosc;
    czesci.push(`<div class="card" style="margin-bottom:var(--sp-3)">
      ${Object.entries(d.modules).map(([k, m]) => wierszModulu(k, m)).join("")}
      ${ob && ob.prace ? `<div class="muted num" style="font-size:var(--fs-xs); margin-top:var(--sp-2)">
        Objętość (дисциплина формата, не входит в готовность):
        ${ob.trafienia}/${ob.prace} работ в допуске</div>` : ""}
      <div class="muted" style="font-size:var(--fs-xs); margin-top:var(--sp-2)">
        <span style="color:var(--red)">|</span> порог (50%) ·
        <span style="color:var(--hint)">|</span> цель · результат — последний мок</div>
    </div>`);

    /* ── сегодня ── */
    czesci.push(`
      <div class="card" style="margin-bottom:var(--sp-3)">
        <div class="h2">Сегодня · неделя ${d.week.nr}</div>
        ${d.today.plan.map(p => `
          <div class="todo ${p.done ? "done" : ""}">
            <span class="st">${p.done ? "✓" : "○"}</span>
            <span class="lbl">${esc(p.label)}
              ${p.zrobione ? `<span class="muted num">· ${p.zrobione}</span>` : ""}</span>
            <span class="min num">${esc(String(p.minut))} мин</span>
          </div>`).join("")}
      </div>`);

    /* ── активность ── */
    czesci.push(`
      <div class="card" style="margin-bottom:var(--sp-3)">
        <div class="h2">Активность</div>
        ${heatmapHTML(d.activity)}
        <div class="muted" style="font-size:var(--fs-xs); margin-top:var(--sp-2)">
          12 недель · закрашиваются только реальные учебные действия</div>
      </div>`);
  } else if (S.authed) {
    czesci.push(`<div class="state">Дашборд не загрузился — проверь связь и потяни вниз.</div>`);
  }

  /* ── практика ── */
  czesci.push(`
    <div class="section-title">Практика</div>
    <button class="cell wide" data-go="egzamin" style="margin-bottom:var(--sp-2)">
      <span class="ic-tile red">🎓</span>
      <span class="body"><span class="t">Реальный экзамен</span><br>
        <span class="d">Таймер · 4 письменных модуля · перерывы · результат</span></span>
      <span class="chev">›</span>
    </button>
    <div class="grid">
      ${[["gram", "🧩", "blue", "Грамматика", "8 типов заданий"],
         ["intencje", "🎧", "violet", "Аудирование", "Intencje · audio · один проход"],
         ["czasy", "⏱", "cyan", "Czasy (IV)", "Формы глагола текстом"],
         ["trans", "🔁", "violet", "Transformacje (VI)", "Перестроить предложение"],
         ["czytanie", "📖", "gold", "Чтение", "Форматы реального B1 · таймер"],
         ["pisanie", "✍️", "green", "Письмо", "2 работы · счётчик объёма"],
         ["mowienie", "🗣", "amber", "Говорение", "3 задания · симуляция"],
         ["mapa", "🗺", "red", "Error Map", "Мои повторяющиеся ошибки"]]
        .map(([id, ic, tone, t, dsc]) => `
        <button class="cell" data-go="${id}">
          <span class="ic-tile ${tone}">${ic}</span>
          <span class="t">${t}</span><span class="d">${dsc}</span>
        </button>`).join("")}
    </div>
    <button class="cell wide" data-go="wyniki" style="margin-top:var(--sp-2)">
      <span class="ic-tile cyan">📈</span>
      <span class="body"><span class="t">Historia egzaminów próbnych</span><br>
        <span class="d">Моки, тренды по модулям, вердикты</span></span>
      <span class="chev">›</span>
    </button>
    <p class="foot">Egzamin 17.10.2026 · 25/45/45/75 min + mówienie do 15 min<br>
      Порог: 50% в каждом из пяти модулей, среднего не существует.</p>`);

  render("home", czesci.join(""));
  app.querySelectorAll("[data-go]").forEach(el =>
    el.onclick = () => VIEWS[el.dataset.go] && VIEWS[el.dataset.go]());
}

function wierszModulu(klucz, m) {
  const ost = m.ostatni;
  const proc = ost ? Math.round(ost.punkty / ost.maks * 100) : null;
  const ton = proc === null ? "" : (ost.punkty >= m.cel ? "ok" : (ost.punkty >= m.prog ? "warn" : "bad"));
  const t = m.trend;
  const strzalka = !t ? "" : t.kierunek === "up"
    ? `<span class="trend-up num">↑ +${t.delta}</span>`
    : t.kierunek === "down" ? `<span class="trend-down num">↓ ${t.delta}</span>`
    : `<span class="trend-flat">→</span>`;
  return `
    <div class="mod">
      <div class="name">
        <div class="t">${esc(m.nazwa)} ${strzalka}</div>
        <div class="meter ${ton}">
          <i style="width:${proc ?? 0}%"></i>
          <span class="tick prog" style="left:${m.prog / m.maks * 100}%"></span>
          <span class="tick cel" style="left:${m.cel / m.maks * 100}%"></span>
        </div>
      </div>
      <div class="score">
        <div class="v num">${ost ? `${ost.punkty}/${m.maks}` : "—"}</div>
        <div class="s num">${proc !== null ? proc + "% · " + esc(ost.sesja) : "нет замера"}</div>
      </div>
    </div>`;
}

function nazwaKategorii(k) {
  const mapa = { "INTENCJA": "Intencje", "SYTUACJA": "Sytuacje", "GRAM-IV": "Czasy",
                 "GRAM-VI": "Transformacje" };
  return mapa[k] || k.replace("GRAM-", "Zadanie ");
}
function goDlaKategorii(k) {
  if (k === "INTENCJA" || k === "SYTUACJA") return "intencje";
  if (k === "GRAM-IV") return "czasy";
  if (k === "GRAM-VI") return "trans";
  return "gram";
}

function heatmapHTML(dni) {
  /* 12 недель, колонки — недели (понедельник сверху), уровни фиксированные:
     1–2 действия, 3–5, 6–9, 10+ — детерминированно и объяснимо */
  const dzisiaj = new Date();
  const dow = (dzisiaj.getDay() + 6) % 7;             // 0 = понедельник
  const start = new Date(dzisiaj);
  start.setDate(dzisiaj.getDate() - dow - 77);        // 11 полных недель назад + текущая
  const kom = [];
  for (let i = 0; i < 84; i++) {
    const dt = new Date(start);
    dt.setDate(start.getDate() + i);
    if (dt > dzisiaj) { kom.push(`<i style="opacity:.25"></i>`); continue; }
    const iso = isoLokalne(dt);
    const n = dni[iso] || 0;
    const kl = n >= 10 ? "a4" : n >= 6 ? "a3" : n >= 3 ? "a2" : n >= 1 ? "a1" : "";
    kom.push(`<i class="${kl}" title="${iso}: ${n}"></i>`);
  }
  return `<div class="heatmap">${kom.join("")}</div>`;
}

/* ── как считается готовность ── */
function widokOGotowosci() {
  render("oGotowosci", `
    <h1>Как считается готовность</h1>
    <p class="sub">Учебный индекс, а не вероятность сдачи</p>
    <div class="card" style="font-size:var(--fs-sm); line-height:1.6">
      <p style="margin-top:0">По каждому модулю:</p>
      <p>• есть мок и тренировки → <b>0.6 · мок% + 0.4 · тренировки%</b><br>
      • только мок → его процент<br>
      • только тренировки → не выше <b>50%</b> (без мока запас не подтверждён)<br>
      • данных нет → <b>0</b>, модуль «не замерено»</p>
      <p>Тренировочная точность: gramatyka и słuchanie — из SRS (минимум
      20 показов). Pisanie, czytanie и mówienie замеряются только моками:
      попадание в объём — дисциплина формата, а не умение писать, оно
      показывается отдельной строкой и в готовность не входит.</p>
      <p>Штраф: −3 п.п. gramatyce за каждую категорию Error Map с ≥3 ошибками
      за последние 30 дней (до −12) — закрытая старая категория не штрафует.</p>
      <p style="margin-bottom:0">Итог — среднее по модулям, взвешенное их баллами
      (30/30/30/30/40). Формула детерминированная и покрыта тестами
      (bot/gotowosc.py).</p>
    </div>`);
}

/* ═══════════════════════════ ТРЕНАЖЁРЫ ═══════════════════════════ */

function widokWybor(name, pula, opts = {}) {
  const p = opts.nastepna || wybierz(pula);
  if (!p) { przeladujHome(); return; }
  const audioSrc = p.audio ? DATA + "audio/" + p.id + ".mp3" : null;
  render(name, `
    <div class="card">
      <p class="q-head">${esc(p.nag)}</p>
      ${audioSrc ? `
        <audio id="au" preload="auto" src="${audioSrc}"></audio>
        <button class="btn sm" id="play">🎧 Odsłuchaj — tylko jeden raz</button>
        <p class="q-text" style="margin-top:var(--sp-3)">${esc(p.pyt)}</p>`
      : `<p class="q-text">${esc(p.pytanie)}</p>`}
      <div class="opts">${p.opcje.map((o, i) =>
        `<button class="btn opt" data-i="${i}">${esc(o)}</button>`).join("")}</div>
      <div class="expl hidden" id="expl"></div>
    </div>
    <div class="split" style="margin-top:var(--sp-3)">
      <button class="btn ghost" id="next">Dalej →</button>
    </div>`, { after: () => {
      const play = document.getElementById("play");
      if (play) {
        const au = document.getElementById("au");
        play.onclick = () => { au.play(); play.disabled = true;
          play.textContent = "🎧 Odtworzone (1/1)"; };
      }
      let done = false;
      app.querySelectorAll(".opt").forEach(btn => btn.onclick = async () => {
        if (done) return;
        done = true;
        const wybor = p.opcje[+btn.dataset.i];
        const w = await sprawdzOdpowiedz(p, wybor);
        app.querySelectorAll(".opt").forEach(b2 => {
          const val = p.opcje[+b2.dataset.i];
          if (val === w.klucz) b2.classList.add("good");
          else if (b2 === btn) b2.classList.add("badly");
        });
        const ex = document.getElementById("expl");
        ex.classList.remove("hidden");
        ex.innerHTML = (w.ok ? "✅ " : "❌ правильно: <b>" + esc(w.klucz) + "</b><br>")
          + (audioSrc && p.tekst ? `Transkrypcja: „${esc(p.tekst)}”<br>` : "")
          + (p.dlaczego ? "<i>" + esc(p.dlaczego) + "</i>" : "")
          + (w.zapisano ? "" : "<br><i>⚠ не сохранено</i>");
        if (tg) tg.HapticFeedback.notificationOccurred(w.ok ? "success" : "error");
        if (opts.poOdpowiedzi) opts.poOdpowiedzi(w.ok);
      });
      document.getElementById("next").onclick =
        () => (opts.dalej ? opts.dalej() : widokWybor(name, pula, opts));
    }});
}

function widokOtwarte(name, pula, opts = {}) {
  const p = opts.nastepna || wybierz(pula);
  if (!p) { przeladujHome(); return; }
  render(name, `
    <div class="card">
      <p class="q-head">${esc(p.nag)}</p>
      <p class="q-text">${esc(p.pytanie)}</p>
      <p class="muted" style="font-size:var(--fs-sm)">${esc(p.hint)}</p>
      <div class="stack">
        <input type="text" id="odp" autocomplete="off" autocapitalize="off"
               placeholder="Twoja odpowiedź…">
        <button class="btn" id="check">Sprawdź</button>
      </div>
      <div class="expl hidden" id="expl"></div>
    </div>
    <div class="split" style="margin-top:var(--sp-3)">
      <button class="btn ghost" id="next">Dalej →</button>
    </div>`, { after: () => {
      const inp = document.getElementById("odp");
      inp.focus();
      let done = false;
      const check = async () => {
        if (done) return;
        done = true;
        const w = await sprawdzOdpowiedz(p, inp.value || "");
        const ex = document.getElementById("expl");
        ex.classList.remove("hidden");
        ex.innerHTML = (w.ok ? "✅ <b>" + esc(w.klucz) + "</b>"
            : "❌ правильно: <b>" + esc(w.klucz) + "</b>"
              + (w.akceptowane.length ? "<br>также принимается: "
                 + w.akceptowane.map(esc).join(" · ") : ""))
          + (p.dlaczego ? "<br><i>" + esc(p.dlaczego) + "</i>" : "")
          + (w.zapisano ? "" : "<br><i>⚠ не сохранено</i>");
        document.getElementById("check").disabled = true;
        if (tg) tg.HapticFeedback.notificationOccurred(w.ok ? "success" : "error");
        if (opts.poOdpowiedzi) opts.poOdpowiedzi(w.ok);
      };
      document.getElementById("check").onclick = check;
      inp.addEventListener("keydown", e => { if (e.key === "Enter") check(); });
      document.getElementById("next").onclick =
        () => (opts.dalej ? opts.dalej() : widokOtwarte(name, pula, opts));
    }});
}

/* ── очередь повторения: только due-позиции с сервера ── */
async function widokPowtorki() {
  let due;
  try { due = (await api("/api/powtorki")).due; }
  catch (e) { render("powtorki", `<div class="state">Очередь не загрузилась: ${esc(e.message)}</div>`); return; }
  const kolejka = shuffle(due.slice());
  let zrobione = 0;
  let biezacy = null;

  /* неверный ответ по правилам SRS остаётся due сегодня — возвращаем позицию
     в очередь через несколько вопросов, а не выбрасываем до завтра */
  const poOdpowiedzi = ok => {
    zrobione += 1;
    if (!ok && biezacy) kolejka.splice(Math.min(3, kolejka.length), 0, biezacy);
  };

  const nastepny = () => {
    const id = kolejka.shift();
    if (!id) {
      render("powtorki", `
        <h1>Повторение</h1>
        <div class="state">Очередь пуста — на сегодня всё повторено
          (${zrobione} ответов). ✓</div>
        <button class="btn" id="dom">На дашборд</button>`,
        { after: () => document.getElementById("dom").onclick = przeladujHome });
      return;
    }
    biezacy = id;
    const zwykla = D.wszystkie.get(id);
    if (zwykla) { widokWybor("powtorki", [], { nastepna: zwykla, dalej: nastepny, poOdpowiedzi }); return; }
    const otwarta = D.otwarte.get(id);
    if (otwarta) { widokOtwarte("powtorki", [], { nastepna: otwarta, dalej: nastepny, poOdpowiedzi }); return; }
    nastepny();   // позиция ушла из пула контента — пропускаем
  };
  nastepny();
}

/* ── чтение: честный протокол (тренажёра нет, есть режим занятия) ── */
function widokCzytanie() {
  render("czytanie", `
    <h1>Czytanie</h1>
    <p class="sub">Тренажёра чтения в приложении нет — и это честно: модуль
      тренируется на полных текстах.</p>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-text" style="margin-bottom:var(--sp-2)">Возьми модуль чтения из
      сборника <b>6_B1_RT</b> (ключи официальные) или из архивной сессии по
      программе. 5 заданий, лимит как на экзамене.</p>
      <div class="timer" id="t">45:00</div>
      <button class="btn" id="start">▶ 45 минут</button>
    </div>
    <button class="btn ghost" id="done">Отметить занятие чтением ✓</button>
    <p class="foot">Отметка попадает в активность и план дня. Результат полного
      модуля вноси через «Реальный экзамен» или Historia.</p>`, { after: () => {
      timerNaPrzycisku("start", "t", 45 * 60);
      document.getElementById("done").onclick = async function () {
        this.disabled = true;
        if (S.authed) await apiCicho("/api/aktywnosc", { typ: "czytanie" });
        this.textContent = "Записано ✓";
      };
    }});
}

function timerNaPrzycisku(btnId, timerId, sekund) {
  const t = document.getElementById(timerId);
  document.getElementById(btnId).onclick = function () {
    this.disabled = true;
    const koniec = Date.now() + sekund * 1000;
    const iv = timerEkranu(() => {
      const s = Math.max(0, Math.round((koniec - Date.now()) / 1000));
      t.textContent = s ? MMSS(s) : "KONIEC";
      if (!s) clearInterval(iv);
    }, 500);
  };
}

/* ── письмо ── */
function widokPisanie() {
  const z = D.pisanie.zestawy[Math.floor(Math.random() * D.pisanie.zestawy.length)];
  const praca = czesc => `
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Praca ${czesc} — ${esc(z[czesc].gatunek)} · ${z[czesc].slow} słów</p>
      <p class="q-text">${esc(z[czesc].polecenie)}</p>
      <textarea id="txt-${czesc}" placeholder="Pisz po polsku, bez tłumacza…"></textarea>
      <div class="wc num" id="wc-${czesc}">0 słów</div>
      <div class="meter" id="m-${czesc}"><i style="width:0%"></i></div>
      <button class="btn sm" id="zap-${czesc}" style="margin-top:var(--sp-3)" disabled>
        Записать работу ${czesc}</button>
    </div>`;
  render("pisanie", `
    <h1>Pisanie · ${esc(z.id)}</h1>
    <p class="sub">75 минут на обе работы. Объём ±10% — тренировочный ориентир,
      не официальный порог.</p>
    <div class="timer mini" id="t">75:00</div>
    <button class="btn sm ghost" id="start" style="margin-bottom:var(--sp-3)">▶ Старт 75 мин</button>
    ${praca("a")}${praca("b")}
    <button class="btn ghost" id="next">Inny zestaw</button>`, { after: () => {
      timerNaPrzycisku("start", "t", 75 * 60);
      for (const czesc of ["a", "b"]) {
        const txt = document.getElementById("txt-" + czesc);
        const wc = document.getElementById("wc-" + czesc);
        const meter = document.getElementById("m-" + czesc);
        const zap = document.getElementById("zap-" + czesc);
        const wymagane = z[czesc].slow;
        txt.addEventListener("input", () => {
          const n = liczSlowa(txt.value);
          const proc = Math.round(n / wymagane * 100);
          wc.textContent = `${n} / ${wymagane} słów (${proc}%)`;
          meter.className = "meter " +
            (proc >= 90 && proc <= 110 ? "ok" : (proc < 90 ? "bad" : "warn"));
          meter.firstElementChild.style.width = Math.min(100, proc) + "%";
          zap.disabled = n === 0;
        });
        zap.onclick = async () => {
          zap.disabled = true;
          if (S.authed) {
            await apiCicho("/api/praca", { zestaw: z.id, czesc,
              slow: liczSlowa(txt.value), wymagane, tekst: txt.value });
            zap.textContent = `Работа ${czesc} записана ✓`;
          } else zap.textContent = "Вне Telegram не сохраняется";
        };
      }
      document.getElementById("next").onclick = widokPisanie;
    }});
}

/* ── говорение ── */
function widokMowienie() {
  const z = D.mowienie.zestawy[Math.floor(Math.random() * D.mowienie.zestawy.length)];
  render("mowienie", `
    <h1>Mówienie · ${esc(z.id)}</h1>
    <p class="sub">До 15 минут. Составь короткий план монолога — официальный
      сборник это прямо рекомендует. Говори вслух, пиши на диктофон.</p>
    <div class="timer mini" id="t">15:00</div>
    <button class="btn sm ghost" id="start" style="margin-bottom:var(--sp-4)">▶ Старт таймера</button>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Zadanie 1 — opis ilustracji</p>
      <p class="q-text">${esc(z.z1)}</p>
      <p class="muted" style="font-size:var(--fs-xs)">На экзамене здесь настоящая
        фотография — сцена пока описана словами.</p>
    </div>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Zadanie 2 — monolog</p>
      <p class="q-text">${esc(z.z2)}</p>
    </div>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Zadanie 3 — sytuacja komunikacyjna (dialog!)</p>
      <p class="q-text">${esc(z.z3)}</p>
      <div id="dialog"></div>
      <button class="btn sm" id="dlg">▶ Реплика собеседника</button>
    </div>
    <div class="split">
      <button class="btn ghost" id="next">Inny zestaw</button>
      <button class="btn" id="done">Сессия пройдена ✓</button>
    </div>`, { after: () => {
      timerNaPrzycisku("start", "t", 15 * 60);
      let krok = 0;
      const dlg = document.getElementById("dialog");
      document.getElementById("dlg").onclick = function () {
        const linie = z.z3_dialog || [];
        if (krok < linie.length) {
          dlg.insertAdjacentHTML("beforeend",
            `<div class="dialog-line">🗣 ${esc(linie[krok])}</div>
             <div class="dialog-line me muted">…твой ответ вслух…</div>`);
          krok++;
          if (krok >= linie.length) { this.disabled = true; this.textContent = "Rozmowa zakończona"; }
        }
      };
      document.getElementById("done").onclick = async function () {
        this.disabled = true;
        if (S.authed) await apiCicho("/api/aktywnosc", { typ: "mowienie" });
        this.textContent = "Записано ✓";
      };
      document.getElementById("next").onclick = widokMowienie;
    }});
}

/* ═══════════════════════════ REAL EXAM ═══════════════════════════ */

const EXAM_KOLEJNOSC = ["sluchanie", "czytanie", "gramatyka", "pisanie"];
const EXAM_KLUCZ_SS = "b1.egzamin";
const EXAM_MAX_WIEK_MS = 6 * 3600 * 1000;

/* чекпоинт текущего экзамена: НЕ учебная статистика, а страховка от
   выгрузки WebView — SQLite остаётся единственным источником прогресса */
function egzaminStan() {
  try {
    const s = JSON.parse(sessionStorage.getItem(EXAM_KLUCZ_SS));
    if (s && Date.now() - s.start < EXAM_MAX_WIEK_MS) return s;
  } catch (e) { /* повреждённый чекпоинт игнорируем */ }
  sessionStorage.removeItem(EXAM_KLUCZ_SS);
  return null;
}
function egzaminZapisz(stan) {
  sessionStorage.setItem(EXAM_KLUCZ_SS, JSON.stringify(stan));
}
/* id попытки: сервер по нему отличает retry от новой попытки, когда ответ
   на POST /api/mok потерялся в сети уже после записи */
function idProby() {
  return crypto.randomUUID ? crypto.randomUUID()
    : Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}
function egzaminWyczysc() {
  sessionStorage.removeItem(EXAM_KLUCZ_SS);
  if (tg) tg.disableClosingConfirmation();
}

/* восстановление после reload: фаза выводится из абсолютных времён */
function egzaminWznow() {
  const stan = egzaminStan();
  if (!stan || !S.cfg) return false;
  if (stan.faza === "wynik") { egzaminWynik(stan); return true; }
  if (tg) tg.enableClosingConfirmation();
  if (stan.faza === "modul") {
    if (Date.now() < stan.koniec) egzaminModul(stan);
    else egzaminPoModule(stan);       // время модуля вышло, пока нас не было
    return true;
  }
  if (stan.faza === "przerwa") { egzaminPrzerwa(stan); return true; }
  return false;
}

function widokEgzamin() {
  const cfg = S.cfg;
  if (!cfg) { render("egzamin", `<div class="state">Конфиг экзамена не загрузился.</div>`); return; }
  if (egzaminStan()) { egzaminWznow(); return; }
  const t = cfg.timing;
  render("egzamin", `
    <h1>Realny tryb egzaminu</h1>
    <p class="sub">B1 · dorośli · протокол честного мока</p>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <table class="exam-table">
        ${EXAM_KOLEJNOSC.map(k => `<tr><td>${esc(cfg.moduly[k].nazwa)}</td>
          <td class="num">${t[k]} min</td></tr>`).join("")}
        <tr><td>Razem</td><td class="num">${EXAM_KOLEJNOSC.reduce((a, k) => a + t[k], 0)} min</td></tr>
      </table>
      <div class="warnbox">
        <b>Без словаря. Без переводчика. Без AI. Без паузы.</b><br>
        Аудио — ровно столько раз, сколько в задании. Пустых клеток не оставлять:
        штрафа за неверный ответ нет. Материал модуля — архивный аркуш по
        программе (в приложение он не встроен: чужие авторские материалы).
        Следующий модуль начинается по расписанию, даже если работа сдана
        раньше, — как на настоящем экзамене.
      </div>
      <label class="muted" style="font-size:var(--fs-sm)">Сессия аркуша
        <input type="text" id="sesja" placeholder="например 2021-11"
               style="margin-top:6px"></label>
    </div>
    <button class="btn danger" id="start">Rozpocznij egzamin</button>
    <p class="foot">Между модулями перерыв не меньше ${cfg.przerwa_min} минут.
      Mówienie (до ${cfg.mowienie_max_min} мин) проводится отдельно и вносится
      в результат вручную.</p>`, { after: () => {
      document.getElementById("start").onclick = () => {
        const sesja = document.getElementById("sesja").value.trim()
          || isoLokalne(new Date());
        if (tg) tg.enableClosingConfirmation();
        const stan = { sesja, proba: idProby(),
                       idx: 0, faza: "modul", start: Date.now(),
                       koniec: Date.now() + S.cfg.timing[EXAM_KOLEJNOSC[0]] * 60000,
                       oddany: false };
        egzaminZapisz(stan);
        egzaminModul(stan);
      };
    }});
}

function egzaminModul(stan) {
  const cfg = S.cfg;
  const klucz = EXAM_KOLEJNOSC[stan.idx];
  const m = cfg.moduly[klucz];
  render("egzamin", `
    <h1>${stan.idx + 1}/4 · ${esc(m.nazwa)}</h1>
    <p class="sub">${m.maks} p. · próg ${m.prog} · cel ${m.cel}</p>
    <div class="timer" id="t">--:--</div>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-text" style="margin:0" id="opis">${stan.oddany
        ? opisOddanego(klucz)
        : `Работай в аркуше сессии <b>${esc(stan.sesja)}</b>. Когда время выйдет —
           модуль закрыт, листы откладываются и больше не трогаются.`}</p>
    </div>
    <button class="btn ghost" id="oddaj" ${stan.oddany ? "disabled" : ""}>
      Oddaj pracę wcześniej</button>
    <button class="btn ghost" id="przerwij"
      style="margin-top:var(--sp-2); color:var(--red)">Przerwij egzamin</button>`,
    { after: () => {
      const t = document.getElementById("t");
      const tick = () => {
        const s = Math.max(0, Math.round((stan.koniec - Date.now()) / 1000));
        t.textContent = MMSS(s);
        return s;
      };
      tick();
      timerEkranu(() => { if (tick() <= 0) egzaminPoModule(stan); }, 500);
      /* досрочная сдача НЕ ускоряет расписание: лист закрыт, время модуля идёт */
      document.getElementById("oddaj").onclick = function () {
        stan.oddany = true;
        egzaminZapisz(stan);
        this.disabled = true;
        document.getElementById("opis").innerHTML = opisOddanego(klucz);
      };
      przyciskPrzerwania(document.getElementById("przerwij"));
    }});
  window.scrollTo(0, 0);
}

function opisOddanego(klucz) {
  return `Лист сдан. Следующий модуль начнётся по расписанию — после конца
    времени <b>${esc(S.cfg.moduly[klucz].nazwa)}</b> и перерыва. Досиди:
    на экзамене выйти из зала можно, а ускорить день — нет.`;
}

/* «Przerwij egzamin» — двойное подтверждение без диалогов (они вешают WebView) */
function przyciskPrzerwania(btn) {
  btn.onclick = () => {
    if (btn.dataset.raz) {
      egzaminWyczysc();
      przeladujHome();
      return;
    }
    btn.dataset.raz = "1";
    btn.textContent = "Точно прервать? Мок пропадёт";
    setTimeout(() => {
      if (document.body.contains(btn)) {
        delete btn.dataset.raz;
        btn.textContent = "Przerwij egzamin";
      }
    }, 4000);
  };
}

function egzaminPoModule(stan) {
  if (stan.idx + 1 < EXAM_KOLEJNOSC.length) {
    const nowy = { ...stan, idx: stan.idx + 1, faza: "przerwa", oddany: false,
                   koniec: Date.now() + S.cfg.przerwa_min * 60000 };
    egzaminZapisz(nowy);
    egzaminPrzerwa(nowy);
  } else {
    const nowy = { ...stan, faza: "wynik" };
    egzaminZapisz(nowy);
    egzaminWynik(nowy);
  }
}

function egzaminPrzerwa(stan) {
  const cfg = S.cfg;
  render("egzamin", `
    <h1>Przerwa</h1>
    <p class="sub">Минимум ${cfg.przerwa_min} минут. Следующий модуль:
      ${esc(cfg.moduly[EXAM_KOLEJNOSC[stan.idx]].nazwa)}</p>
    <div class="timer" id="t">--:--</div>
    <button class="btn" id="dalej" disabled>Rozpocznij następny moduł</button>
    <button class="btn ghost" id="przerwij"
      style="margin-top:var(--sp-2); color:var(--red)">Przerwij egzamin</button>
    <p class="foot">Кнопка откроется, когда перерыв пройдёт целиком —
      как на настоящем экзамене.</p>`, { after: () => {
      const t = document.getElementById("t");
      const btn = document.getElementById("dalej");
      const tick = () => {
        const s = Math.max(0, Math.round((stan.koniec - Date.now()) / 1000));
        t.textContent = MMSS(s);
        if (s <= 0) btn.disabled = false;
        return s;
      };
      if (tick() > 0) timerEkranu(tick, 500);
      btn.onclick = () => {
        const nowy = { ...stan, faza: "modul",
                       koniec: Date.now() + S.cfg.timing[EXAM_KOLEJNOSC[stan.idx]] * 60000 };
        egzaminZapisz(nowy);
        egzaminModul(nowy);
      };
      przyciskPrzerwania(document.getElementById("przerwij"));
    }});
}

function egzaminWynik(stan) {
  const cfg = S.cfg;
  const sesja = stan.sesja;
  /* чекпоинт, созданный до появления id попытки, дополняем на месте */
  if (!stan.proba) { stan.proba = idProby(); egzaminZapisz(stan); }
  const pola = Object.entries(cfg.moduly).map(([k, m]) => `
    <label style="display:block; margin-bottom:var(--sp-3); font-size:var(--fs-sm)">
      ${esc(m.nazwa)} <span class="muted">/ ${m.maks}${k === "mowienie" ? " · опционально" : ""}</span>
      <input type="number" id="w-${k}" min="0" max="${m.maks}" step="0.5"
             inputmode="decimal" style="margin-top:4px">
    </label>`).join("");
  render("egzamin", `
    <h1>Wynik · ${esc(sesja)}</h1>
    <p class="sub">Проверь по ключу (klucze/) и внеси баллы. Mówienie можно
      внести позже отдельно.</p>
    <div class="card" style="margin-bottom:var(--sp-3)">${pola}</div>
    <button class="btn" id="zapisz">Zapisz wynik</button>
    <div id="werdykt" style="margin-top:var(--sp-3)"></div>`, { after: () => {
      document.getElementById("zapisz").onclick = async function () {
        this.disabled = true;
        const wpisane = {};
        for (const k of Object.keys(cfg.moduly)) {
          const v = document.getElementById("w-" + k).value;
          if (v !== "") wpisane[k] = parseFloat(v);
        }
        if (!Object.keys(wpisane).length) { this.disabled = false; return; }
        const w = document.getElementById("werdykt");
        if (S.authed) {
          /* мок пишется атомарно; штамп — ТОЛЬКО из ответа сервера;
             attempt_id делает повторное нажатие после обрыва сети безопасным */
          try {
            const r = await api("/api/mok",
              { sesja, attempt_id: stan.proba, wyniki: wpisane });
            egzaminWyczysc();
            pokazWerdykt(r);
          } catch (e) {
            this.disabled = false;
            w.innerHTML = `<div class="banner">⚠ Мок НЕ записан (${esc(e.message)}).
              Ничего не потеряно — исправь связь или значения и нажми ещё раз.</div>`;
          }
          return;
        }
        /* вне Telegram: сохранить некуда — честно считаем локально */
        egzaminWyczysc();
        const statusy = {};
        for (const [k, m] of Object.entries(cfg.moduly))
          if (wpisane[k] !== undefined)
            statusy[k] = { punkty: wpisane[k], maks: m.maks, prog: m.prog,
                           zdal: wpisane[k] >= m.prog };
        const pelny = Object.keys(cfg.moduly).every(k => wpisane[k] !== undefined);
        pokazWerdykt({ statusy,
          zdany: pelny ? Object.values(statusy).every(s => s.zdal) : null },
          "⚠ Вне Telegram — результат НЕ сохранён.");
      };
    }});
}

function pokazWerdykt(r, dopisek) {
  const cfg = S.cfg;
  const wiersze = Object.entries(cfg.moduly).map(([k, m]) => {
    const s = r.statusy[k];
    if (!s)
      return `<div class="todo"><span class="st">·</span><span class="lbl muted">${esc(m.nazwa)}</span><span class="min">не внесено</span></div>`;
    return `<div class="todo"><span class="st">${s.zdal ? "✓" : "✗"}</span>
      <span class="lbl">${esc(m.nazwa)}</span>
      <span class="min num" style="color:${s.zdal ? "var(--ok)" : "var(--bad)"}">
        ${s.punkty}/${s.maks}</span></div>`;
  }).join("");
  const stamp = r.zdany === null || r.zdany === undefined
    ? `<p class="muted" style="font-size:var(--fs-sm)">Вердикта нет — мок неполный.
       Внеси недостающие модули позже, вердикт появится в Historia.</p>`
    : `<p style="text-align:center; margin:var(--sp-4) 0">
       <span class="stamp ${r.zdany ? "ok" : ""}">${r.zdany ? "EGZAMIN ZDANY" : "EGZAMIN NIEZDANY"}</span></p>`;
  const w = document.getElementById("werdykt");
  w.innerHTML = `${dopisek ? `<div class="banner">${dopisek}</div>` : ""}
    <div class="card">${wiersze}</div>${stamp}
    <button class="btn ghost" id="dom" style="margin-top:var(--sp-3)">На дашборд</button>`;
  document.getElementById("dom").onclick = przeladujHome;
}

/* ═══════════════════════════ ИСТОРИЯ И ERROR MAP ═══════════════════════════ */

async function widokWyniki() {
  let dane;
  try { dane = await api("/api/wyniki"); }
  catch (e) { render("wyniki", `<div class="state">История не загрузилась: ${esc(e.message)}</div>`); return; }
  const cfg = S.cfg;
  const sesje = dane.sesje.slice().reverse();
  const trendy = {};
  for (const s of dane.sesje)
    for (const [m, p] of Object.entries(s.wyniki))
      (trendy[m] = trendy[m] || []).push(p);
  render("wyniki", `
    <h1>Historia egzaminów próbnych</h1>
    <p class="sub">Вердикт — только по полным мокам: каждый модуль ≥ порога</p>
    ${sesje.length ? `<div class="card" style="margin-bottom:var(--sp-3)">
      ${sesje.map(s => `
        <div class="wyn-row">
          <div class="wyn-head"><b>${esc(s.sesja)}</b>
            ${s.zdany === true ? `<span class="stamp ok" style="font-size:var(--fs-xs)">ZDANY</span>`
              : s.zdany === false ? `<span class="stamp" style="font-size:var(--fs-xs)">NIEZDANY</span>` : ""}
            <span class="d">${esc(s.kiedy.slice(0, 10))}</span></div>
          <div class="wyn-mods">${Object.entries(s.wyniki).map(([m, p]) => {
            const md = cfg.moduly[m];
            const kolor = p >= md.cel ? "var(--ok)" : p >= md.prog ? "var(--warn)" : "var(--bad)";
            return `<span class="chip num"><span class="dot" style="background:${kolor}"></span>
              ${m.slice(0, 2).toUpperCase()} ${p}/${md.maks}</span>`;
          }).join("")}</div>
        </div>`).join("")}
    </div>
    <div class="card">
      <div class="h2">Trend</div>
      ${Object.entries(trendy).filter(([, v]) => v.length >= 2).map(([m, v]) => `
        <div class="todo"><span class="lbl">${esc(cfg.moduly[m].nazwa)}</span>
          <span class="trendline">${v.join(" → ")}</span></div>`).join("")
        || `<p class="muted" style="font-size:var(--fs-sm)">Тренд появится после второго мока.</p>`}
    </div>` : `<div class="state">Моков ещё не было. Первый — диагностика по
      «Реальный экзамен».</div>`}`);
}

const KODY_BLEDOW = ["CASE-GEN", "CASE-DAT", "CASE-ACC", "CASE-INS", "CASE-LOC",
  "ASP", "TENSE", "MOOD", "PREP", "REKCJA", "CONJ", "COMP", "NUM", "WO",
  "LEX", "ORTH", "REG", "TASK"];

function widokMapa() {
  const d = S.dash;
  const em = d ? d.weakest.error_map : [];
  const kat = d ? d.weakest.kategorie : [];
  render("mapa", `
    <h1>Error Map</h1>
    <p class="sub">Повторяющиеся ошибки за ${d && d.weakest.okno_dni || 30} дней —
      приоритет тренировки</p>
    ${em.length ? `<div class="card" style="margin-bottom:var(--sp-3)">
      ${em.map(e => `<div class="todo">
        <span class="st">${e.priorytet ? "⚠" : "·"}</span>
        <span class="lbl">${esc(e.kod)}</span>
        <span class="min num">${e.n}×</span></div>`).join("")}
    </div>` : `<div class="state">Ошибок пока не записано.</div>`}
    ${kat.length ? `<div class="card" style="margin-bottom:var(--sp-3)">
      <div class="h2">Слабые места по тренировкам</div>
      ${kat.map(k => `<div class="todo">
        <span class="lbl">${esc(nazwaKategorii(k.kategoria))}</span>
        <span class="min num">${k.bledy} из ${k.pokazy}</span></div>`).join("")}
    </div>` : ""}
    <div class="card">
      <div class="h2">Записать ошибку</div>
      <div class="stack">
        <select id="kod">${KODY_BLEDOW.map(k => `<option>${k}</option>`).join("")}</select>
        <input type="text" id="zle" placeholder="как написал / сказал">
        <input type="text" id="dobrze" placeholder="как правильно (опционально)">
        <button class="btn" id="zapisz">Записать</button>
        <div id="wynik-bledu" class="muted" style="font-size:var(--fs-sm)"></div>
      </div>
    </div>`, { after: () => {
      document.getElementById("zapisz").onclick = async () => {
        const zle = document.getElementById("zle").value.trim();
        if (!zle || !S.authed) return;
        const r = await api("/api/blad", {
          kod: document.getElementById("kod").value, zle,
          dobrze: document.getElementById("dobrze").value.trim() });
        document.getElementById("zle").value = "";
        document.getElementById("dobrze").value = "";
        document.getElementById("wynik-bledu").textContent =
          `Записано (${r.razem}×)` + (r.priorytet ? " — категория в приоритете ⚠" : "");
      };
    }});
}

/* ── план ── */
function widokPlan() {
  const cfg = S.cfg;
  const tygodnie = cfg ? cfg.plan_tygodni : [];
  const nrTeraz = S.dash ? S.dash.week.nr : 0;
  render("plan", `
    <h1>Plan</h1>
    <p class="sub">17.08 → 17.10.2026 · 9 недель</p>
    ${S.dash ? `<div class="card" style="margin-bottom:var(--sp-3)">
      <div class="h2">Сегодня</div>
      ${S.dash.today.plan.map(p => `
        <div class="todo ${p.done ? "done" : ""}">
          <span class="st">${p.done ? "✓" : "○"}</span>
          <span class="lbl">${esc(p.label)}</span>
          <span class="min num">${esc(String(p.minut))} мин</span>
        </div>`).join("")}
    </div>` : ""}
    <div class="card">
      ${tygodnie.map(t => `
        <div class="plan-week ${t.nr === nrTeraz ? "now" : ""}">
          <span class="nr">${t.nr}</span>
          <span><b>${esc(t.od)}–${esc(t.do)}</b><br>${esc(t.opis)}</span>
        </div>`).join("")}
    </div>`);
}

/* ── маршруты ── */
const VIEWS = {
  gram: () => widokWybor("gram", D.gram),
  intencje: () => widokWybor("intencje", D.int),
  czasy: () => widokOtwarte("czasy", D.czasy),
  trans: () => widokOtwarte("trans", D.trans),
  czytanie: widokCzytanie,
  pisanie: widokPisanie,
  mowienie: widokMowienie,
  egzamin: widokEgzamin,
  wyniki: widokWyniki,
  mapa: widokMapa,
  plan: widokPlan,
  powtorki: widokPowtorki,
  oGotowosci: widokOGotowosci,
};

/* ── старт ── */
(async () => {
  try { await loadData(); }
  catch (e) {
    app.innerHTML = `<div class="state">Не удалось загрузить данные:<br>${esc(e.message)}</div>`;
    return;
  }
  try { S.cfg = await api("/api/config"); } catch (e) { /* Pages без API: без конфига */ }
  if (AUTH) {
    try { S.dash = await api("/api/dashboard"); S.authed = true; }
    catch (e) { S.authed = false; }
  }
  /* незавершённый экзамен переживает reload/выгрузку WebView */
  if (!egzaminWznow()) home();
})();
