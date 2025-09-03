#!/bin/bash

echo "🚀 Запускаю второго Telegram-бота (клиент)..."
docker compose -f docker-compose.client.yml up -d --build
