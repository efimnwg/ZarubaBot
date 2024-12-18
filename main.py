from flask import Flask, render_template_string
import requests
import threading
import time
import schedule
from datetime import datetime

app = Flask(__name__)

PLAYER_IDS = [57943, 3403223, 225622, 2099747, 637635, 398410, 7110995, 629295]

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

leaderboard_data = []  # Глобальная переменная для хранения данных

def get_current_gameweek():
    """Получить текущую игровую неделю через API."""
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
    """Получить данные об игроке за указанную игровую неделю."""
    try:
        # Получение истории игрока
        url = f"https://fantasy.premierleague.com/api/entry/{player_id}/history/"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error fetching history for player {player_id}: {response.status_code}")
            return None

        data = response.json()
        current_week_data = next((week for week in data['current'] if week['event'] == gameweek), None)
        if not current_week_data:
            print(f"No data for current gameweek {gameweek} for player {player_id}")
            return None

        # Название команды
        team_url = f"https://fantasy.premierleague.com/api/entry/{player_id}/"
        team_response = requests.get(team_url)
        if team_response.status_code != 200:
            print(f"Error fetching team data for player {player_id}: {team_response.status_code}")
            return None
        team_name = team_response.json().get('name', 'Unknown Team')

        # Данные для таблицы
        points = current_week_data['points'] - current_week_data['event_transfers_cost']  # Учитываем штраф
        total_points = current_week_data['total_points']
        transfer_cost = -(current_week_data['event_transfers_cost'])  # Отрицательное значение
        active_chip = current_week_data.get('active_chip', 'None')

        return {
            'Team': team_name,
            'Points': points,  # С учетом штрафов за трансферы
            'Transfer Cost': transfer_cost,
            'Active Chip': active_chip,
            'Total Points': total_points,
        }
    except Exception as e:
        print(f"Error fetching data for player {player_id}: {e}")
        return None

def update_leaderboard():
    """Обновить таблицу участников."""
    global leaderboard_data
    leaderboard_data = []
    current_gameweek = get_current_gameweek()
    if not current_gameweek:
        print("Unable to fetch current gameweek. Skipping update.")
        return

    for player_id in PLAYER_IDS:
        player_data = fetch_player_data(player_id, current_gameweek)
        if player_data:
            leaderboard_data.append(player_data)

    # Сортировка по общим очкам
    leaderboard_data.sort(key=lambda x: x['Total Points'], reverse=True)
    print(f"Leaderboard updated at {datetime.now()} for gameweek {current_gameweek}")

@app.route('/')
def leaderboard():
    """Главная страница с таблицей участников."""
    if not leaderboard_data:  # Если данные отсутствуют, загружаем их
        update_leaderboard()
    return render_template_string(HTML_TEMPLATE, leaderboard=enumerate(leaderboard_data, start=1), gameweek=get_current_gameweek())

# Фоновая проверка игрового дня
def schedule_tasks():
    def check_game_day():
        tomorrow = datetime.now().date().toordinal() + 1
        is_game_day = tomorrow % 2 == 0  # Для теста: четные дни — игровые
        if not is_game_day:
            print("Next day is not a game day. Sleeping for 24 hours.")
            time.sleep(24 * 60 * 60)
        else:
            print("Game day detected. Starting updates.")
            schedule.every(5).minutes.do(update_leaderboard)

    schedule.every().day.at("23:50").do(check_game_day)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # Инициализация данных
    update_leaderboard()

    # Запуск фонового потока для расписания
    threading.Thread(target=schedule_tasks, daemon=True).start()

    # Запуск Flask
    app.run(host='0.0.0.0', port=3000, debug=True)
