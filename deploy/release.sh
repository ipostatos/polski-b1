#!/usr/bin/env bash
# Выкладка на VPS. Правила:
#   * только origin/main и только при зелёном CI (проверь Actions перед прогоном);
#   * код уезжает git archive → tar, git на сервере не нужен;
#   * .env и moje/ не тракаются и переживают выкладку;
#   * прогон: bash deploy/release.sh
# Разовая настройка сервера — deploy/SETUP.md.
set -euo pipefail

HOST=root@46.224.220.94
APP=/opt/polski-b1/app

cd "$(git rev-parse --show-toplevel)"
git fetch origin main
SHA=$(git rev-parse origin/main)
if [ "$(git rev-parse HEAD)" != "$SHA" ]; then
    echo "HEAD != origin/main — выкладываем только main" >&2
    exit 1
fi

git archive --format=tar origin/main | ssh "$HOST" "tar -x -C $APP"

ssh "$HOST" "
    set -e
    chown -R root:root $APP
    chown root:polskib1 $APP/.env && chmod 640 $APP/.env
    chown -R polskib1:polskib1 $APP/moje
    systemctl restart polski-b1
    sleep 3
    systemctl is-active polski-b1
    journalctl -u polski-b1 -n 5 --no-pager
"

echo "выложено: $SHA"
