import os
import logging
from flask import Flask, request, render_template_string
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import aiohttp
import asyncio
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Flask-приложение
app = Flask(__name__)

# Переменные окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not TOKEN or not WEBHOOK_URL:
    raise EnvironmentError("TELEGRAM_TOKEN или WEBHOOK_URL не установлены!")

# Идентификаторы игроков
PLAYER_IDS = [57943, 3403223, 225622, 2099747, 637635, 398410, 7110995, 629295]

# Telegram Application
application = Application.builder().token(TOKEN).build()

# Шаблон HTML
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Fantasy League Leaderboard</title>
    <style>
        table {
            width: 80%;
            margin: auto;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: center;
        }
        th {
            background-color: #f2f2f2;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f1f1f1;
        }
    </style>
</head>
<body>
    <h2 style="text-align: center;">Fantasy League Leaderboard</h2>
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Team</th>
                <th>Points (Gameweek {{ gameweek }})</th>
                <th>Transfer Cost</th>
                <th>Active Chip</th>
                <th>Total Points</th>
            </tr>
        </thead>
        <tbody>
            {% for rank, player in leaderboard %}
            <tr>
                <td>{{ rank }}</td>
                <td>{{ player['Team'] }}</td>
                <td>{{ player['Points'] }}</td>
                <td>{{ player['Transfer Cost'] }}</td>
                <td>{{ player['Active Chip'] }}</td>
                <td>{{ player['Total Points'] }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

leaderboard_data = []
is_game_day = False  # Флаг для определения игрового дня

# Функции для получения данных
async def get_current_gameweek():
    try:
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    for event in data['events']:
                        if event['is_current']:
                            return event['id']
    except Exception as e:
        logging.error(f"Error fetching current gameweek: {e}")
    return None

async def fetch_player_data(player_id, gameweek):
    # Функция аналогична изначальной
    ...

async def update_leaderboard():
    global leaderboard_data
    leaderboard_data = []
    current_gameweek = await get_current_gameweek()
    if not current_gameweek:
        logging.error("Gameweek not found")
        return

    tasks = [fetch_player_data(player_id, current_gameweek) for player_id in PLAYER_IDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    leaderboard_data = [player for player in results if player and not isinstance(player, Exception)]
    leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)

async def check_game_day():
    global is_game_day
    tomorrow = datetime.now() + timedelta(days=1)
    # Логика определения игрового дня
    is_game_day = await is_next_day_game_day(tomorrow)
    if is_game_day:
        logging.info(f"Следующий день ({tomorrow.strftime('%Y-%m-%d')}) — игровой.")
    else:
        logging.info(f"Следующий день ({tomorrow.strftime('%Y-%m-%d')}) — не игровой.")

async def is_next_day_game_day(date):
    # Реализация логики определения игрового дня
    return date.weekday() in [5, 6]  # Суббота или воскресенье

async def leaderboard_update_schedule():
    while True:
        now = datetime.now()
        if is_game_day and 10 <= now.hour < 23:
            logging.info("Обновление данных...")
            await update_leaderboard()
            await asyncio.sleep(300)  # Обновление каждые 5 минут
        else:
            logging.info("Ожидание игрового времени...")
            await asyncio.sleep(60)

async def daily_check_schedule():
    while True:
        now = datetime.now()
        if now.hour == 23 and now.minute == 50:
            await check_game_day()
        await asyncio.sleep(60)

# Основной цикл
async def main():
    await asyncio.gather(daily_check_schedule(), leaderboard_update_schedule())

if __name__ == '__main__':
    logging.info(f"TELEGRAM_TOKEN: {TOKEN}")
    logging.info(f"WEBHOOK_URL: {WEBHOOK_URL}")

    asyncio.run(main())
    app.run(host='0.0.0.0', port=3000, debug=True)
