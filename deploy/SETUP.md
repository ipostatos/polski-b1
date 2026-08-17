# Разовая настройка VPS (выполнена 17.08.2026)

Сервер `root@46.224.220.94`, схема — как у соседних ботов флота
(своя учётка, systemd с изоляцией, ночной бэкап SQLite).

```bash
# учётка и каталоги
useradd --system --home /opt/polski-b1 --shell /usr/sbin/nologin polskib1
mkdir -p /opt/polski-b1/app/moje

# venv (код приедет release.sh)
python3 -m venv /opt/polski-b1/venv
/opt/polski-b1/venv/bin/pip install aiogram==3.29.0

# секреты: скопировать локальный .env, вписать WEBAPP_URL, права root:polskib1 640
# база прогресса: scp moje/postep.db на сервер в app/moje/ (владелец polskib1)

# служба
cp /opt/polski-b1/app/deploy/polski-b1.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now polski-b1

# бэкап (root-крон)
( crontab -l; echo '8 3 * * * /opt/polski-b1/app/deploy/backup.sh >> /var/log/polski-b1-backup.log 2>&1' ) | crontab -
```

⚠️ Бот поллит Telegram: два экземпляра одновременно (сервер + локальный
`python bot/bot.py`) будут драться за getUpdates. После переезда на VPS
локально бот не запускать.
