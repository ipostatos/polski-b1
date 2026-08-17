#!/usr/bin/env bash
# Выкачивает официальный архив B1 (dorośli) с certyfikatpolski.pl.
# Материалы НЕ коммитятся в репозиторий — только локальная рабочая копия.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DST="$ROOT/archive"
IDX="$ROOT/tools/b1_adult_urls.txt"
mkdir -p "$DST"

n=0; ok=0; fail=0
while read -r url; do
  [ -z "$url" ] && continue
  n=$((n+1))
  name="$(basename "$url")"
  out="$DST/$name"
  if [ -s "$out" ]; then ok=$((ok+1)); echo "skip  $name"; continue; fi
  if curl -sfL --retry 3 --retry-delay 2 -o "$out.part" "$url"; then
    mv "$out.part" "$out"; ok=$((ok+1)); echo "ok    $name ($(stat -c%s "$out") b)"
  else
    rm -f "$out.part"; fail=$((fail+1)); echo "FAIL  $url"
  fi
done < "$IDX"
echo "---- total=$n ok=$ok fail=$fail"
