#!/usr/bin/env python3
"""Генерирует записи для тренажёра задания I (data/audio/*.mp3).

Реплики — наши авторские (data/intencje.json), поэтому сгенерированное аудио
можно хранить в репозитории. Голоса чередуются, чтобы ухо не привыкало
к одному диктору — на экзамене дикторы разные.

Запуск:  pip install edge-tts && python tools/make_audio.py
Повторный запуск перегенерирует только отсутствующие файлы;
--force перегенерирует всё.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "intencje.json"
OUT = ROOT / "data" / "audio"

GLOSY = ["pl-PL-ZofiaNeural", "pl-PL-MarekNeural"]


def pozycje() -> list[tuple[str, str]]:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    out = [(f"INT-{i:03d}", p["tekst"]) for i, p in enumerate(src["pozycje"], 1)]
    out += [(f"SYT-{i:03d}", p["tekst"])
            for i, p in enumerate(src["sytuacje"]["pozycje"], 1)]
    return out


async def main() -> int:
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    zrobione = 0
    for n, (iid, tekst) in enumerate(pozycje()):
        f = OUT / f"{iid}.mp3"
        if f.exists() and not force:
            continue
        glos = GLOSY[n % len(GLOSY)]
        await edge_tts.Communicate(tekst, voice=glos, rate="-5%").save(str(f))
        zrobione += 1
        print(f"{iid}  {glos}  {f.stat().st_size // 1024} КБ")
    print(f"готово: {zrobione} новых, всего {len(list(OUT.glob('*.mp3')))} файлов")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
