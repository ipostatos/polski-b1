/* Polski B1 — Mini App. Хаб плашек + тренажёры.
   Логика повторяет бот (bot/content.py): те же данные, те же id позиций.
   Прогресс — в localStorage (и это осознанно: приложение полностью статическое). */
"use strict";

const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
if (tg) { tg.ready(); tg.expand(); }

const EGZAMIN = new Date(2026, 9, 17);          // 17.10.2026
const START = new Date(2026, 7, 17);            // 17.08.2026
const DATA = "../data/";
const app = document.getElementById("app");

const PLAN = [
  [1, "17–23.08", "ДИАГНОСТИКА. Ничего не учим. Сб — письменная часть 2021-11, вс — Mówienie."],
  [2, "24–30.08", "Грамматика: задание I (склонение) и VII (вид и наклонения). Ежедневно słuchanie и czytanie."],
  [3, "31.08–06.09", "Грамматика: IV (времена) и VI (трансформации). Старт письма: 3 работы в неделю."],
  [4, "07–13.09", "Грамматика: мелочь — II, III, V, VIII. Письмо продолжается."],
  [5, "14–20.09", "Чтение и аудирование под таймер, по одному модулю за раз."],
  [6, "21–27.09", "Полные письменные модули из архива. Говорение ежедневно."],
  [7, "28.09–04.10", "EXAM MODE. Полный мок 03.10 на сессии 2023-11."],
  [8, "05–11.10", "Стабилизация по Error Map. Мок 10.10 на 2024-02."],
  [9, "12–16.10", "Финальный мок 2024-04, дальше только короткие тренировки."],
];

/* ── хранилище прогресса ── */
const store = {
  read(key, dflt) {
    try { return JSON.parse(localStorage.getItem("b1." + key)) ?? dflt; }
    catch { return dflt; }
  },
  write(key, val) { localStorage.setItem("b1." + key, JSON.stringify(val)); },
};
function zapisz(kat, id, ok) {
  const stats = store.read("stats", {});
  const s = stats[kat] || { ok: 0, total: 0 };
  s.total += 1; if (ok) s.ok += 1;
  stats[kat] = s; store.write("stats", stats);
  const seen = store.read("seen", {});
  seen[id] = (seen[id] || 0) + 1; store.write("seen", seen);
}
function wybierz(pula) {
  const seen = store.read("seen", {});
  const nowe = pula.filter(p => !seen[p.id]);
  const zbior = nowe.length ? nowe : pula;
  return zbior[Math.floor(Math.random() * zbior.length)];
}

/* ── утилиты ── */
const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function dni() { return Math.ceil((EGZAMIN - new Date()) / 86400000); }
function tydzien() {
  const n = Math.floor((new Date() - START) / (7 * 86400000)) + 1;
  return Math.max(1, Math.min(9, n));
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

/* ── данные ── */
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
    klucz: p.klucz, dlaczego: p.wskazowka || "" }));
  src.sytuacje.pozycje.forEach((p, i) => out.push({
    id: `SYT-${String(i + 1).padStart(3, "0")}`, kat: "SYTUACJA",
    nag: "Zadanie I — miejsce wypowiedzi", tekst: p.tekst,
    pyt: "Ta wypowiedź jest typowa:", opcje: shuffle([p.klucz, ...p.dystraktory]),
    klucz: p.klucz, dlaczego: "" }));
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

/* ── каркас страниц ── */
let widok = "home";
function render(name, html, opts = {}) {
  widok = name;
  const back = name !== "home";
  if (tg) { back ? tg.BackButton.show() : tg.BackButton.hide(); }
  app.innerHTML = `
    ${back ? `<header class="top"><button class="back" id="back">‹ Назад</button></header>` : ""}
    ${html}`;
  const b = document.getElementById("back");
  if (b) b.onclick = home;
  if (opts.after) opts.after();
}
if (tg) tg.BackButton.onClick(() => { if (widok !== "home") home(); });

/* ── главная: чистый хаб плашек ── */
const KAFELKI = [
  ["gram", "🧩", "blue", "Gramatyka", "Задания I · II · III · VII · VIII — кнопками"],
  ["intencje", "🎧", "violet", "Zadanie I — słuchanie", "Запись один раз, транскрипция после ответа"],
  ["czasy", "⏱", "cyan", "Czasy (IV)", "Форма глагола — ответ текстом"],
  ["trans", "🔁", "Transformacje (VI)", "", ""],   // заполняется ниже
  ["pisanie", "✍️", "green", "Pisanie", "Комплект a + b, счётчик объёма"],
  ["mowienie", "🗣", "amber", "Mówienie", "Комплект, таймер 15 минут, диалог задания 3"],
  ["plan", "📅", "gold", "Plan", "Неделя программы и что сегодня"],
  ["postep", "📊", "red", "Postęp", "Статистика тренировок"],
];
KAFELKI[3] = ["trans", "🔁", "violet", "Transformacje (VI)", "Перестроить предложение — ответ текстом"];

function home() {
  const d = dni(), [nr, , opis] = PLAN[tydzien() - 1];
  render("home", `
    <h1>Polski B1</h1>
    <p class="sub">Państwowy egzamin certyfikatowy · B1 dorośli</p>
    <div class="chips">
      <span class="chip">до экзамена <b>${d}</b> дн.</span>
      <span class="chip">неделя ${nr}/9</span>
      <span class="chip">порог 50% в каждом модуле</span>
    </div>
    ${KAFELKI.map(([id, ic, tone, t, dsc]) => `
      <button class="row-card" data-go="${id}">
        <span class="ic-tile ${tone}">${ic}</span>
        <span class="body"><span class="t">${t}</span><br><span class="d">${dsc}</span></span>
        <span class="chev">›</span>
      </button>`).join("")}
    <p class="foot">${esc(opis)}<br>Egzamin 17.10.2026 · 25/45/45/75 min + mówienie do 15 min</p>
  `);
  app.querySelectorAll("[data-go]").forEach(el =>
    el.onclick = () => VIEWS[el.dataset.go]());
}

/* ── тренажёр с кнопками (грамматика и задание I) ── */
function widokWybor(name, pula, opts = {}) {
  const p = wybierz(pula);
  const audioSrc = opts.audio ? DATA + "audio/" + p.id + ".mp3" : null;
  render(name, `
    <div class="card">
      <p class="q-head">${esc(p.nag)}</p>
      ${audioSrc ? `
        <audio id="au" preload="auto" src="${audioSrc}"></audio>
        <button class="btn sm" id="play">🎧 Odsłuchaj — tylko jeden raz</button>
        <p class="q-text" style="margin-top:var(--sp-3)">${esc(p.pyt)}</p>`
      : `<p class="q-text">${esc(opts.audio === false && p.tekst ? `„${p.tekst}”\n\n${p.pyt}` : p.pytanie)}</p>`}
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
      app.querySelectorAll(".opt").forEach(btn => btn.onclick = () => {
        if (done) return;
        done = true;
        const wybor = p.opcje[+btn.dataset.i];
        const ok = wybor === p.klucz;
        zapisz(p.kat, p.id, ok);
        app.querySelectorAll(".opt").forEach(b2 => {
          const val = p.opcje[+b2.dataset.i];
          if (val === p.klucz) b2.classList.add("good");
          else if (b2 === btn) b2.classList.add("badly");
        });
        const ex = document.getElementById("expl");
        ex.classList.remove("hidden");
        ex.innerHTML = (ok ? "✅ " : "❌ правильно: <b>" + esc(p.klucz) + "</b><br>")
          + (audioSrc && p.tekst ? `Transkrypcja: „${esc(p.tekst)}”<br>` : "")
          + (p.dlaczego ? "<i>" + esc(p.dlaczego) + "</i>" : "");
        if (tg) tg.HapticFeedback.notificationOccurred(ok ? "success" : "error");
      });
      document.getElementById("next").onclick = () => widokWybor(name, pula, opts);
    }});
}

/* ── тренажёр с открытым ответом ── */
function widokOtwarte(name, pula) {
  const p = wybierz(pula);
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
      const check = () => {
        const warianty = [p.klucz, ...p.akceptowane].map(normalizuj);
        const ok = warianty.includes(normalizuj(inp.value || ""));
        zapisz(p.kat, p.id, ok);
        const ex = document.getElementById("expl");
        ex.classList.remove("hidden");
        ex.innerHTML = (ok ? "✅ <b>" + esc(p.klucz) + "</b>"
            : "❌ правильно: <b>" + esc(p.klucz) + "</b>"
              + (p.akceptowane.length ? "<br>также принимается: "
                 + p.akceptowane.map(esc).join(" · ") : ""))
          + (p.dlaczego ? "<br><i>" + esc(p.dlaczego) + "</i>" : "");
        document.getElementById("check").disabled = true;
        if (tg) tg.HapticFeedback.notificationOccurred(ok ? "success" : "error");
      };
      document.getElementById("check").onclick = check;
      inp.addEventListener("keydown", e => { if (e.key === "Enter") check(); });
      document.getElementById("next").onclick = () => widokOtwarte(name, pula);
    }});
}

/* ── Pisanie ── */
function widokPisanie() {
  const z = D.pisanie.zestawy[Math.floor(Math.random() * D.pisanie.zestawy.length)];
  const praca = czesc => `
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Praca ${czesc} — ${esc(z[czesc].gatunek)} · ${z[czesc].slow} słów</p>
      <p class="q-text">${esc(z[czesc].polecenie)}</p>
      <textarea id="txt-${czesc}" placeholder="Pisz po polsku, bez tłumacza…"></textarea>
      <div class="wc" id="wc-${czesc}">0 słów</div>
      <div class="meter" id="m-${czesc}"><i style="width:0%"></i></div>
    </div>`;
  render("pisanie", `
    <h1>Pisanie · ${esc(z.id)}</h1>
    <p class="sub">75 минут на обе работы. Объём ±10% — тренировочный ориентир, не официальный порог.</p>
    ${praca("a")}${praca("b")}
    <button class="btn ghost" id="next">Inny zestaw</button>`, { after: () => {
      for (const czesc of ["a", "b"]) {
        const txt = document.getElementById("txt-" + czesc);
        const wc = document.getElementById("wc-" + czesc);
        const meter = document.getElementById("m-" + czesc);
        const wymagane = z[czesc].slow;
        txt.addEventListener("input", () => {
          const n = liczSlowa(txt.value);
          const proc = Math.round(n / wymagane * 100);
          wc.textContent = `${n} / ${wymagane} słów (${proc}%)`;
          meter.className = "meter " +
            (proc >= 90 && proc <= 110 ? "ok" : (proc < 90 ? "bad" : "warn"));
          meter.firstElementChild.style.width = Math.min(100, proc) + "%";
        });
      }
      document.getElementById("next").onclick = widokPisanie;
    }});
}

/* ── Mówienie ── */
function widokMowienie() {
  const z = D.mowienie.zestawy[Math.floor(Math.random() * D.mowienie.zestawy.length)];
  render("mowienie", `
    <h1>Mówienie · ${esc(z.id)}</h1>
    <p class="sub">До 15 минут. Составь короткий план монолога — официальный сборник это прямо рекомендует.</p>
    <div class="timer" id="timer">15:00</div>
    <button class="btn sm ghost" id="start" style="margin-bottom:var(--sp-4)">▶️ Старт таймера</button>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Zadanie 1 — opis ilustracji</p>
      <p class="q-text">${esc(z.z1)}</p>
      <p class="muted" style="font-size:var(--fs-xs)">На экзамене здесь настоящая фотография — сцена пока описана словами.</p>
    </div>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Zadanie 2 — monolog</p>
      <p class="q-text">${esc(z.z2)}</p>
    </div>
    <div class="card" style="margin-bottom:var(--sp-3)">
      <p class="q-head">Zadanie 3 — sytuacja komunikacyjna (dialog!)</p>
      <p class="q-text">${esc(z.z3)}</p>
      <div id="dialog"></div>
      <button class="btn sm" id="dlg">▶️ Реплика собеседника</button>
    </div>
    <button class="btn ghost" id="next">Inny zestaw</button>`, { after: () => {
      let sek = 15 * 60, iv = null;
      const t = document.getElementById("timer");
      document.getElementById("start").onclick = function () {
        if (iv) return;
        this.disabled = true;
        iv = setInterval(() => {
          sek--;
          t.textContent = `${String(Math.floor(sek / 60)).padStart(2, "0")}:${String(sek % 60).padStart(2, "0")}`;
          if (sek <= 0) { clearInterval(iv); t.textContent = "KONIEC"; }
        }, 1000);
      };
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
      document.getElementById("next").onclick = widokMowienie;
    }});
}

/* ── Plan ── */
function widokPlan() {
  const now = tydzien();
  render("plan", `
    <h1>Plan</h1>
    <p class="sub">17.08 → 17.10.2026 · 61 день, 9 недель</p>
    <div class="card">
      ${PLAN.map(([nr, d, opis]) => `
        <div class="plan-week ${nr === now ? "now" : ""}">
          <span class="nr">${nr}</span>
          <span><b>${d}</b><br>${esc(opis)}</span>
        </div>`).join("")}
    </div>
    <p class="foot">Экзамен 2026: słuchanie 25 · czytanie 45 · gramatyka 45 · pisanie 75 (razem 190 мин),
    перерывы ≥10 мин, mówienie до 15 мин.</p>`);
}

/* ── Postęp ── */
function widokPostep() {
  const stats = store.read("stats", {});
  const rows = Object.entries(stats).sort();
  const suma = rows.reduce((a, [, s]) => a + s.total, 0);
  const dobre = rows.reduce((a, [, s]) => a + s.ok, 0);
  const proc = suma ? Math.round(dobre / suma * 100) : 0;
  render("postep", `
    <h1>Postęp</h1>
    <p class="sub">Тренировки в Mini App (бот считает свою статистику отдельно)</p>
    <div class="card" style="display:flex; gap:var(--sp-4); align-items:center; margin-bottom:var(--sp-3)">
      <div class="ring" style="--p:${proc}; --ring-color:${proc >= 70 ? "var(--ok)" : proc >= 50 ? "var(--warn)" : "var(--bad)"}">
        <div class="ring-val"><span class="ring-num">${proc}%</span><span class="ring-cap">верных</span></div>
      </div>
      <div><b>${dobre}</b> из <b>${suma}</b> ответов верны.<br>
        <span class="muted" style="font-size:var(--fs-sm)">До экзамена ${dni()} дн.</span></div>
    </div>
    ${rows.length ? `<div class="card"><div class="statgrid">
      ${rows.map(([k, s]) => `<span>${esc(k)}</span><span><b>${s.ok}</b>/${s.total}</span>`).join("")}
    </div></div>` : `<div class="state">Ещё нет ответов — начни с грамматики.</div>`}`);
}

/* ── маршруты ── */
const VIEWS = {
  gram: () => widokWybor("gram", D.gram),
  intencje: () => widokWybor("intencje", D.int, { audio: true }),
  czasy: () => widokOtwarte("czasy", D.czasy),
  trans: () => widokOtwarte("trans", D.trans),
  pisanie: widokPisanie,
  mowienie: widokMowienie,
  plan: widokPlan,
  postep: widokPostep,
};

loadData().then(home).catch(e => {
  app.innerHTML = `<div class="state">Не удалось загрузить данные:<br>${esc(e.message)}</div>`;
});
