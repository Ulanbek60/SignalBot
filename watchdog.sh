#!/bin/bash

# Массив ботов: URL дашборда
BOTS=("http://127.0.0.1:5000" "http://127.0.0.1:5001")

while true; do
    for BOT_URL in "${BOTS[@]}"; do
        STATUS_URL="$BOT_URL/api/status"
        START_URL="$BOT_URL/api/start"

        running=$(curl -s "$STATUS_URL" | grep -o '"running":true')

        if [ "$running" != '"running":true' ]; then
            echo "$(date) — Bot at $BOT_URL is not running, starting..."
            curl -s "$START_URL" >/dev/null
        else
            echo "$(date) — Bot at $BOT_URL is running."
        fi
    done

    sleep 300  # проверка каждые 5 минут
done
