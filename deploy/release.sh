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
    # юнит из репо — source of truth: без установки правка unit-файла
    # молча не доезжала бы (systemd читает /etc/systemd/system, не \$APP)
    install -m 644 $APP/deploy/polski-b1.service /etc/systemd/system/polski-b1.service
    systemctl daemon-reload
    systemctl restart polski-b1
    sleep 3
    systemctl is-active polski-b1
    systemctl show polski-b1 -p Environment | grep -F 'TZ=Europe/Warsaw'
    # smoke: при API_PORT != 0 API дашборда ОБЯЗАН отвечать. Бот сознательно
    # переживает сбой API (graceful degradation), поэтому bind-конфликт
    # (Errno 98: порт занят соседом) не роняет службу — ловим его здесь,
    # чтобы неудачный деплой никогда не выглядел успешным.
    PORT=\$(sed -n 's/^API_PORT=//p' $APP/.env | tail -1)
    if [ -n \"\$PORT\" ] && [ \"\$PORT\" != 0 ]; then
        ok=''
        for i in 1 2 3 4 5 6 7 8 9 10; do
            if curl -fsS -o /dev/null http://127.0.0.1:\$PORT/api/config; then ok=1; break; fi
            sleep 1
        done
        [ -n \"\$ok\" ] || { echo \"smoke: API на \$PORT не отвечает — деплой ПРОВАЛЕН\" >&2; exit 1; }
        echo \"smoke: API на \$PORT отвечает\"
    fi
    journalctl -u polski-b1 -n 5 --no-pager
"

echo "выложено: $SHA"
