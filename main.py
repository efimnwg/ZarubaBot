from flask import Flask, request, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import aiohttp
from datetime import datetime
import asyncio

app = Flask(__name__)

# Проверка наличия переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    raise EnvironmentError("TELEGRAM_TOKEN или WEBHOOK_URL не установлены!")

PLAYER_IDS = [57943, 3403223, 225622, 2099747, 637635, 398410, 7110995, 629295]

# Telegram Application
application = Application.builder().token(TOKEN).build()

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
        print(f"Error fetching current gameweek: {e}")
    return None


async def fetch_player_data(player_id, gameweek):
    try:
        async with aiohttp.ClientSession() as session:
            history_url = f"https://fantasy.premierleague.com/api/entry/{player_id}/history/"
            team_url = f"https://fantasy.premierleague.com/api/entry/{player_id}/"

            async with session.get(history_url) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                current_week_data = next((week for week in data['current'] if week['event'] == gameweek), None)
                if not current_week_data:
                    return None

            async with session.get(team_url) as response:
                if response.status != 200:
                    return None
                team_name = (await response.json()).get('name', 'Unknown Team')

            points = current_week_data['points'] - current_week_data['event_transfers_cost']
            total_points = current_week_data['total_points']
            transfer_cost = -(current_week_data['event_transfers_cost'])
            active_chip = current_week_data.get('active_chip', 'None')

            return {
                'Team': team_name,
                'Points': points,
                'Transfer Cost': transfer_cost,
                'Active Chip': active_chip,
                'Total Points': total_points,
            }
    except Exception as e:
        print(f"Error fetching data for player {player_id}: {e}")
        return None


async def update_leaderboard():
    global leaderboard_data
    leaderboard_data = []
    current_gameweek = await get_current_gameweek()
    if not current_gameweek:
        print("Gameweek not found")
        return

    tasks = [fetch_player_data(player_id, current_gameweek) for player_id in PLAYER_IDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    leaderboard_data = [player for player in results if player and not isinstance(player, Exception)]
    leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)


@app.route('/')
async def leaderboard():
    if not leaderboard_data:
        await update_leaderboard()
    return render_template_string(HTML_TEMPLATE, leaderboard=enumerate(leaderboard_data, start=1), gameweek=await get_current_gameweek())


# Telegram Bot Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Используй /leaderboard, чтобы увидеть таблицу лидеров.")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global leaderboard_data
    if not leaderboard_data:
        await update_leaderboard()

    message = "🏆 Fantasy League Leaderboard 🏆\n\n"
    for rank, player in enumerate(leaderboard_data, start=1):
        message += f"{rank}. {player['Team']} - {player['Total Points']} очков\n"
    await update.message.reply_text(message)


# Webhook Setup
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    application.run_webhook(url_path=f"/{TOKEN}", webhook_url=WEBHOOK_URL)
    return f"Webhook set to {WEBHOOK_URL}"


# Add Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("leaderboard", leaderboard_command))

if __name__ == '__main__':
    # Вывод значений переменных окружения для отладки
    print(f"TELEGRAM_TOKEN: {TOKEN}")
    print(f"WEBHOOK_URL: {WEBHOOK_URL}")

    # Инициализация обновления таблицы и запуска приложения
    asyncio.run(update_leaderboard())
    app.run(host='0.0.0.0', port=3000, debug=True)

