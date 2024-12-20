from flask import Flask, request, render_template_string
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
from datetime import datetime
import threading

app = Flask(__name__)

PLAYER_IDS = [57943, 3403223, 225622, 2099747, 637635, 398410, 7110995, 629295]

# Telegram Bot Token
TOKEN = "7613814277:AAGy5ibc7a16JpBx0MpXuWlKs8giNjzzFdA"  # Укажите токен вашего Telegram-бота

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


def get_current_gameweek():
    try:
        url = "https://fantasy.premierleague.com/api/bootstrap-static/"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for event in data['events']:
                if event['is_current']:
                    return event['id']
        print("Failed to determine the current gameweek.")
    except Exception as e:
        print(f"Error fetching current gameweek: {e}")
    return None


def fetch_player_data(player_id, gameweek):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{player_id}/history/"
        response = requests.get(url)
        if response.status_code != 200:
            return None

        data = response.json()
        current_week_data = next((week for week in data['current'] if week['event'] == gameweek), None)
        if not current_week_data:
            return None

        team_url = f"https://fantasy.premierleague.com/api/entry/{player_id}/"
        team_response = requests.get(team_url)
        if team_response.status_code != 200:
            return None
        team_name = team_response.json().get('name', 'Unknown Team')

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


def update_leaderboard():
    global leaderboard_data
    leaderboard_data = []
    current_gameweek = get_current_gameweek()
    if not current_gameweek:
        return

    for player_id in PLAYER_IDS:
        player_data = fetch_player_data(player_id, current_gameweek)
        if player_data:
            leaderboard_data.append(player_data)

    leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)


@app.route('/')
def leaderboard():
    if not leaderboard_data:
        update_leaderboard()
    return render_template_string(HTML_TEMPLATE, leaderboard=enumerate(leaderboard_data, start=1), gameweek=get_current_gameweek())


# Telegram Bot Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Используй /leaderboard, чтобы увидеть таблицу лидеров.")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global leaderboard_data
    if not leaderboard_data:
        update_leaderboard()

    message = "🏆 Fantasy League Leaderboard 🏆\n\n"
    for rank, player in enumerate(leaderboard_data, start=1):
        message += f"{rank}. {player['Team']} - {player['Total Points']} очков\n"
    await update.message.reply_text(message)


# Webhook Setup
@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = f"https://your-webhook-url.com/{TOKEN}"  # Укажите публичный URL
    threading.Thread(target=application.run_webhook, args=(webhook_url,), daemon=True).start()
    return f"Webhook set to {webhook_url}"


# Add Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("leaderboard", leaderboard_command))

if __name__ == '__main__':
    update_leaderboard()
    app.run(host='0.0.0.0', port=3000, debug=True)
