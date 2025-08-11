FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# полезно иметь curl и свежие корневые сертификаты для HTTPS-запросов к Telegram
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# копируем код и картинки
COPY . /app/

EXPOSE 5000

# запускаем твой файл
CMD ["python", "main.py"]
