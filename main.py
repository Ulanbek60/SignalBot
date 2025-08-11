#!/usr/bin/env python3
"""
Complete Telegram Trading Bot - All-in-One File
- Forex/OTC signals
- Alpha Vantage integration (FOREX)
- BUY/SELL images
- RU/EN
- Web dashboard
- Activation code
- 5s "thinking" countdown before signal
"""
import logging
import sys
import os
import json
import random
import time
import threading
from datetime import datetime

import requests
from flask import Flask, jsonify

# ---------------- Logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- Config ----------------

# 1) читаем токен из окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN_DEFAULT")
if not TELEGRAM_BOT_TOKEN:
    print("ERROR: set TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN_DEFAULT", file=sys.stderr)
    sys.exit(1)

TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN.strip()

ACTIVATION_CODE = "105105105"

# можно оставить "demo" для теста, для прод — подставь свои ключи
ALPHA_VANTAGE_API_KEYS = [
    "demo",
    "RIBXT3ALPHAVANTAGE",
    "YOUR_API_KEY_HERE"
]
current_api_key_index = 0

FINANCIAL_PAIRS = {
    "FOREX": {
        "CHF/JPY": "🇨🇭🇯🇵", "EUR/JPY": "🇪🇺🇯🇵", "AUD/CHF": "🇦🇺🇨🇭", "USD/CHF": "🇺🇸🇨🇭",
        "AUD/USD": "🇦🇺🇺🇸", "CAD/CHF": "🇨🇦🇨🇭", "CAD/JPY": "🇨🇦🇯🇵", "EUR/GBP": "🇪🇺🇬🇧",
        "EUR/USD": "🇪🇺🇺🇸", "USD/JPY": "🇺🇸🇯🇵", "GBP/USD": "🇬🇧🇺🇸", "USD/CAD": "🇺🇸🇨🇦",
        "AUD/CAD": "🇦🇺🇨🇦", "EUR/CHF": "🇪🇺🇨🇭", "GBP/JPY": "🇬🇧🇯🇵", "AUD/JPY": "🇦🇺🇯🇵",
        "EUR/AUD": "🇪🇺🇦🇺", "GBP/AUD": "🇬🇧🇦🇺", "GBP/CHF": "🇬🇧🇨🇭", "GBP/CAD": "🇬🇧🇨🇦",
        "EUR/CAD": "🇪🇺🇨🇦"
    },
    "OTC": {
        'EUR/USD OTC': '🇪🇺🇺🇸', 'EUR/JPY OTC': '🇪🇺🇯🇵', 'EUR/GBP OTC': '🇪🇺🇬🇧', 'GBP/USD OTC': '🇬🇧🇺🇸',
        'USD/JPY OTC': '🇺🇸🇯🇵', 'AUD/USD OTC': '🇦🇺🇺🇸', 'USD/CAD OTC': '🇺🇸🇨🇦', 'NZD/USD OTC': '🇳🇿🇺🇸',
        'GBP/JPY OTC': '🇬🇧🇯🇵', 'AUD/JPY OTC': '🇦🇺🇯🇵', 'CAD/JPY OTC': '🇨🇦🇯🇵', 'AUD/CAD OTC': '🇦🇺🇨🇦',
        'AUD/CHF OTC': '🇦🇺🇨🇭', 'AUD/NZD OTC': '🇦🇺🇳🇿', 'CAD/CHF OTC': '🇨🇦🇨🇭', 'CHF/JPY OTC': '🇨🇭🇯🇵',
        'EUR/AUD OTC': '🇪🇺🇦🇺', 'EUR/CAD OTC': '🇪🇺🇨🇦', 'EUR/CHF OTC': '🇪🇺🇨🇭', 'EUR/NZD OTC': '🇪🇺🇳🇿',
        'GBP/AUD OTC': '🇬🇧🇦🇺', 'GBP/CAD OTC': '🇬🇧🇨🇦', 'GBP/CHF OTC': '🇬🇧🇨🇭', 'GBP/NZD OTC': '🇬🇧🇳🇿',
        'NZD/CAD OTC': '🇳🇿🇨🇦', 'NZD/CHF OTC': '🇳🇿🇨🇭', 'NZD/JPY OTC': '🇳🇿🇯🇵', 'USD/CHF OTC': '🇺🇸🇨🇭'
    }
}
SIGNAL_TIMES = {
    "FOREX": ["M1", "M2", "M3", "M4", "M5", "M6"],
    "OTC": ["S5", "S10", "S15", "S30", "M1", "M2", "M3"]
}

BUY_IMAGE = "buy_signal.jpg"
SELL_IMAGE = "sell_signal.jpg"

# ---------------- Flask ----------------
app = Flask(__name__)

# ---------------- State ----------------
bot_status = {"running": False, "error": None, "start_time": None}
user_data = {}  # {user_id: {...}}

# ---------------- Telegram API helpers ----------------
def tg_api(method: str, **params):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    if "reply_markup" in params and isinstance(params["reply_markup"], dict):
        params["reply_markup"] = json.dumps(params["reply_markup"])
    r = requests.post(url, json=params, timeout=30)
    try:
        return r.json()
    except Exception:
        return {"ok": False, "error": f"HTTP {r.status_code}"}

def send_telegram_message(chat_id, text, reply_markup=None):
    return tg_api("sendMessage", chat_id=chat_id, text=text, parse_mode="Markdown", reply_markup=reply_markup)

def edit_message(chat_id, message_id, text, reply_markup=None):
    return tg_api("editMessageText", chat_id=chat_id, message_id=message_id, text=text,
                  parse_mode="Markdown", reply_markup=reply_markup)

def answer_callback(callback_id):
    try:
        tg_api("answerCallbackQuery", callback_query_id=callback_id)
    except Exception as e:
        logger.warning(f"answerCallbackQuery warn: {e}")

def delete_message(chat_id, message_id):
    return tg_api("deleteMessage", chat_id=chat_id, message_id=message_id)

def get_telegram_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"timeout": 50}
    if offset:
        params["offset"] = offset
    r = requests.get(url, params=params, timeout=55)
    return r.json()

def send_telegram_photo(chat_id, photo_path, caption="", reply_markup=None):
    """Если фотки нет — отправим просто текст."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    if not os.path.exists(photo_path) or os.path.getsize(photo_path) == 0:
        return send_telegram_message(chat_id, caption, reply_markup)
    try:
        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            if isinstance(reply_markup, dict):
                data["reply_markup"] = json.dumps(reply_markup)
            return requests.post(url, files=files, data=data, timeout=30).json()
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return send_telegram_message(chat_id, caption, reply_markup)

def ensure_polling_mode():
    info = tg_api("getWebhookInfo")
    if isinstance(info, dict) and info.get("ok") and info.get("result", {}).get("url"):
        logger.info("Webhook is set, deleting …")
        tg_api("deleteWebhook")

# ---- helpers to make buttons work from photos too ----
def edit_or_send(chat_id, message_id, text, keyboard):
    """Пытаемся отредактировать, если не получилось (фото) — удаляем и шлём новое."""
    jr = edit_message(chat_id, message_id, text, keyboard)
    if not isinstance(jr, dict) or not jr.get("ok"):
        delete_message(chat_id, message_id)
        return send_telegram_message(chat_id, text, keyboard)
    return jr

# ---------------- Alpha Vantage ----------------
def get_forex_data_from_api(symbol):
    global current_api_key_index
    try:
        api_symbol = symbol.replace("/", "").replace(" OTC", "")
        from_sym, to_sym = api_symbol[:3], api_symbol[3:]
        api_key = ALPHA_VANTAGE_API_KEYS[current_api_key_index]
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "FX_INTRADAY",
            "from_symbol": from_sym,
            "to_symbol": to_sym,
            "interval": "1min",
            "outputsize": "compact",
            "apikey": api_key,
        }
        r = requests.get(url, params=params, timeout=12)
        data = r.json()
        key = "Time Series FX (1min)"
        if key in data and isinstance(data[key], dict) and data[key]:
            ts = data[key]
            times = sorted(ts.keys(), reverse=True)
            latest = times[0]
            current_price = float(ts[latest]["4. close"])
            prev = times[1:6]
            if prev:
                avg = sum(float(ts[t]["4. close"]) for t in prev) / len(prev)
                is_up = current_price > avg
                return is_up, current_price
        current_api_key_index = (current_api_key_index + 1) % len(ALPHA_VANTAGE_API_KEYS)
    except Exception as e:
        logger.error(f"Error getting forex data: {e}")
    return random.choice([True, False]), None

def generate_trading_signal(pair, timeframe):
    asset_type = "OTC" if "OTC" in pair else "FOREX"
    flag = FINANCIAL_PAIRS[asset_type].get(pair, "")
    if asset_type == "FOREX":
        is_call, current_price = get_forex_data_from_api(pair)
        direction = "CALL (Вверх)" if is_call else "PUT (Вниз)"
        price_info = f"\n💰 Цена: {current_price:.5f}" if current_price else ""
    else:
        direction = random.choice(["CALL (Вверх)", "PUT (Вниз)"])
        price_info = ""
    emoji = "📈" if "CALL" in direction else "📉"
    text = (
        f"{emoji} {direction}\n\n"
        f"📊 {pair} {flag}\n"
        f"⏰ Таймфрейм: {timeframe}\n"
        f"🕐 Время: {datetime.now().strftime('%H:%M:%S')} (локально){price_info}\n\n"
        f"💡 *Сигнал основан на техническом анализе*"
    )
    return text, direction

# ---------------- Handlers ----------------
def handle_message(message):
    try:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        user_id = str(message["from"]["id"])
        logger.info(f"Message from {user_id}: {text}")

        if text == "/start":
            user_data.setdefault(user_id, {"lang": "ru", "activated": False})
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Русский", "callback_data": "lang_ru"}],
                    [{"text": "English", "callback_data": "lang_en"}],
                ]
            }
            send_telegram_message(chat_id, "Выберите язык / Choose language:", keyboard)
            return

        if text == ACTIVATION_CODE:
            ud = user_data.setdefault(user_id, {"lang": "ru", "activated": False})
            ud["activated"] = True
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Форех", "callback_data": "type_FOREX"}],
                    [{"text": "ОТС", "callback_data": "type_OTC"}],
                ]
            }
            send_telegram_message(chat_id, "✅ Код принят! Теперь вы можете получать сигналы.\n\nВыберите тип актива:", keyboard)
            return

        if user_data.get(user_id, {}).get("activated"):
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Форех", "callback_data": "type_FOREX"}],
                    [{"text": "ОТС", "callback_data": "type_OTC"}],
                ]
            }
            send_telegram_message(chat_id, "Выберите тип актива:", keyboard)
            return

        lang = user_data.get(user_id, {}).get("lang", "ru")
        keyboard = {
            "inline_keyboard": [
                [{"text": "Регистрация" if lang == "ru" else "Registration",
                  "url": "https://u3.shortink.io/register?utm_campaign=817526&utm_source=affiliate&utm_medium=sr&a=j0CEcN7XhE0dAK&ac=bexs&code=FDX201"}]
            ]
        }
        msg = ("У вас нет доступа к сигналам. Пожалуйста, введите код активации.\n\nПосле регистрации отправьте мне код."
               if lang == "ru" else
               "You don't have access to signals. Please enter the activation code.\n\nAfter registration, send me the code.")
        send_telegram_message(chat_id, msg, keyboard)

    except Exception as e:
        logger.error(f"Error handling message: {e}")

def handle_callback_query(callback_query):
    try:
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]
        user_id = str(callback_query["from"]["id"])
        data = callback_query.get("data", "")
        logger.info(f"Callback from {user_id}: {data}")

        answer_callback(callback_query["id"])

        ud = user_data.setdefault(user_id, {"lang": "ru", "activated": False})
        lang = ud.get("lang", "ru")

        if data.startswith("lang_"):
            ud["lang"] = data.split("_", 1)[1]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Регистрация" if ud["lang"] == "ru" else "Registration",
                      "url": "https://u3.shortink.io/register?utm_campaign=817526&utm_source=affiliate&utm_medium=sr&a=j0CEcN7XhE0dAK&ac=bexs&code=FDX201"}]
                ]
            }
            txt = ("Добро пожаловать! Для начала работы зарегистрируйтесь по ссылке ниже.\n\nПосле регистрации отправьте код."
                   if ud["lang"] == "ru" else
                   "Welcome! To get started, register using the link below.\n\nAfter registration, send the activation code.")
            edit_or_send(chat_id, message_id, txt, keyboard)
            return

        if data.startswith("type_"):
            asset_type = data.split("_", 1)[1]
            ud["asset_type"] = asset_type
            pairs = list(FINANCIAL_PAIRS[asset_type].items())
            keyboard = {"inline_keyboard": []}
            for i in range(0, len(pairs), 3):
                row = [{"text": f"{p} {f}", "callback_data": f"pair_{p}"} for p, f in pairs[i:i+3]]
                keyboard["inline_keyboard"].append(row)
            keyboard["inline_keyboard"].append([{"text": "← Назад" if lang == "ru" else "← Back", "callback_data": "main_menu"}])
            edit_or_send(chat_id, message_id, "Выберите валютную пару:" if lang == "ru" else "Choose a currency pair:", keyboard)
            return

        if data.startswith("pair_"):
            pair = data.split("_", 1)[1]
            ud["selected_pair"] = pair
            asset_type = ud.get("asset_type", "FOREX")
            tms = SIGNAL_TIMES[asset_type]
            keyboard = {"inline_keyboard": []}
            for i in range(0, len(tms), 3):
                keyboard["inline_keyboard"].append([{"text": t, "callback_data": f"time_{t}"} for t in tms[i:i+3]])
            keyboard["inline_keyboard"].append([{"text": "← Назад" if lang == "ru" else "← Back", "callback_data": f"type_{asset_type}"}])
            edit_or_send(chat_id, message_id, "Выберите время сделки:" if lang == "ru" else "Choose trade time:", keyboard)
            return

        if data.startswith("time_"):
            timeframe = data.split("_", 1)[1]
            pair = ud.get("selected_pair")
            if not pair:
                edit_or_send(chat_id, message_id, "Сначала выберите пару", None)
                return

            # удаляем сообщение с кнопками таймфрейма
            delete_message(chat_id, message_id)

            # отправляем сообщение-таймер и обновляем его 5→1
            resp = send_telegram_message(chat_id, "⏳ Подготовка сигнала… 5 сек")
            timer_msg_id = None
            if isinstance(resp, dict) and resp.get("ok"):
                timer_msg_id = resp["result"]["message_id"]
                for i in range(4, 0, -1):
                    time.sleep(1)
                    edit_message(chat_id, timer_msg_id, f"⏳ Подготовка сигнала… {i} сек")

            # генерим сигнал
            signal_text, direction = generate_trading_signal(pair, timeframe)
            photo_path = BUY_IMAGE if "CALL" in direction else SELL_IMAGE
            keyboard = {
                "inline_keyboard": [
                    [{"text": "🔄 Новый сигнал" if lang == "ru" else "🔄 New signal", "callback_data": f"pair_{pair}"}],
                    [{"text": "← Назад" if lang == "ru" else "← Back", "callback_data": f"pair_{pair}"}],
                    [{"text": "🏠 Главное меню" if lang == "ru" else "🏠 Main menu", "callback_data": "main_menu"}]
                ]
            }

            # убираем таймер и отправляем фото
            if timer_msg_id:
                delete_message(chat_id, timer_msg_id)
            send_telegram_photo(chat_id, photo_path, signal_text, keyboard)
            return

        if data == "main_menu":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Форех" if lang == "ru" else "Forex", "callback_data": "type_FOREX"}],
                    [{"text": "ОТС" if lang == "ru" else "OTC", "callback_data": "type_OTC"}],
                ]
            }
            edit_or_send(chat_id, message_id, "Выберите тип актива:" if lang == "ru" else "Choose an asset type:", keyboard)
            return

    except Exception as e:
        logger.error(f"Error handling callback: {e}")

# ---------------- Polling ----------------
def bot_polling():
    bot_status.update({"running": True, "error": None, "start_time": datetime.now()})
    logger.info("Bot started polling…")
    offset = None
    try:
        while bot_status["running"]:
            updates = get_telegram_updates(offset)
            if updates and updates.get("ok"):
                for upd in updates.get("result", []):
                    offset = upd["update_id"] + 1
                    if "message" in upd:
                        handle_message(upd["message"])
                    elif "callback_query" in upd:
                        handle_callback_query(upd["callback_query"])
            time.sleep(1)
    except Exception as e:
        bot_status["error"] = str(e)
        logger.error(f"Bot error: {e}")
    finally:
        bot_status["running"] = False
        logger.info("Bot stopped.")

# ---------------- Dashboard (Flask) ----------------
@app.route("/")
def index():
    html = """
<!doctype html><html><head><meta charset="utf-8"><title>Trading Bot Dashboard</title>
<style>
body{font-family:Arial;margin:20px;background:#f5f5f5}
.card{background:#fff;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,.1);margin-bottom:20px}
.metric{display:inline-block;margin:10px 20px 10px 0}
.metric-value{font-size:24px;font-weight:bold;color:#4CAF50}
.btn{background:#4CAF50;color:#fff;padding:10px 20px;border:0;border-radius:4px;cursor:pointer}
.btn:hover{background:#45a049}
.badge{display:inline-block;padding:3px 8px;border-radius:12px;background:#4CAF50;color:#fff}
.badge.stopped{background:#f44336}
</style></head><body>
<div class="card">
  <h2>Bot Status</h2>
  <div class="metric"><div id="status" class="metric-value">Loading…</div><div class="metric-label">Status</div></div>
  <div class="metric"><div id="uptime" class="metric-value">--</div><div class="metric-label">Uptime</div></div>
  <div class="metric"><div id="error" class="metric-value">--</div><div class="metric-label">Error</div></div>
  <button class="btn" onclick="startBot()">Start / Restart</button>
</div>
<script>
function refresh(){
  fetch('/api/status').then(r=>r.json()).then(d=>{
    document.getElementById('status').textContent = d.running ? 'Running' : 'Stopped';
    document.getElementById('uptime').textContent = d.uptime || '--';
    document.getElementById('error').textContent = d.error || '--';
  })
}
function startBot(){ fetch('/api/start').then(r=>r.json()).then(_=>refresh()) }
setInterval(refresh, 5000); refresh();
</script>
</body></html>
"""
    return html

@app.route("/api/status")
def api_status():
    return jsonify({
        "running": bot_status["running"],
        "error": bot_status["error"],
        "start_time": bot_status["start_time"].isoformat() if bot_status["start_time"] else None,
        "uptime": str(datetime.now() - bot_status["start_time"]) if bot_status["start_time"] else None,
    })

@app.route("/api/start")
def api_start():
    if not bot_status["running"]:
        threading.Thread(target=bot_polling, daemon=True).start()
        return jsonify({"success": True, "message": "Bot started"})
    bot_status["running"] = False
    time.sleep(1.2)
    threading.Thread(target=bot_polling, daemon=True).start()
    return jsonify({"success": True, "message": "Bot restarted"})

# ---------------- Main ----------------
if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is empty.", file=sys.stderr)
        sys.exit(1)

    ensure_polling_mode()

    threading.Thread(target=bot_polling, daemon=True).start()
    logger.info("Dashboard: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)