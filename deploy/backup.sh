#!/usr/bin/env bash
# Ночной бэкап прогресса. Живой SQLite копировать файлом нельзя — только
# sqlite3 .backup. Ротация 14 дней. Крон (root): 8 3 * * * /opt/polski-b1/app/deploy/backup.sh
set -euo pipefail

TS=$(date +%F)
DST=/opt/backups/polski-b1
mkdir -p "$DST"

sqlite3 /opt/polski-b1/app/moje/postep.db ".backup '$DST/postep-$TS.db'"
install -m 600 /opt/polski-b1/app/.env "$DST/env-$TS"

find "$DST" -type f -mtime +14 -delete
