#!/bin/bash

BOT_URL="http://127.0.0.1:5000"
STATUS_URL="$BOT_URL/api/status"
START_URL="$BOT_URL/api/start"

while true; do
    running=$(curl -s "$STATUS_URL" | grep -o '"running":true')

    if [ "$running" != '"running":true' ]; then
        echo "$(date) — Bot is not running, starting..."
        curl -s "$START_URL" >/dev/null
    else
        echo "$(date) — Bot is running."
    fi

    sleep 300  # проверка каждые 5 минут
done
