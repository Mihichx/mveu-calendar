import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
from flask import Flask, Response
from datetime import datetime, timedelta
import pytz
import re
import os

app = Flask(__name__)
TZ = pytz.timezone('Europe/Samara')
# ОБЯЗАТЕЛЬНО используем полную ссылку с группой
URL = "https://timeo.mveu.ru/schedule/table?group=%D0%94%D0%98%D0%A1-242/21%D0%91"

@app.route('/')
def home():
    return 'Бот МВЕУ работает! Ссылка: <a href="/calendar.ics">/calendar.ics</a>'

@app.route('/calendar.ics')
def get_calendar():
    headers = {'User-Agent': 'Mozilla/5.0'}
    cal = Calendar()
    cal.add('prodid', '-//MVEU Schedule//')
    cal.add('version', '2.0')
    
    days_with_alarm = set()

    for skip in [-1, 0, 1, 2]:
        week_url = f"{URL}&skip={skip}"
        try:
            response = requests.get(week_url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='crud')
            if not table: continue

            rows = table.find_all('tr')
            current_date_str = None
            year = datetime.now().year

            for row in rows:
                cells = row.find_all('td')
                if not cells: continue 

                if cells[0].has_attr('rowspan'):
                    raw_date = cells[0].get_text(strip=True)
                    match = re.search(r'(\d{2}\.\d{2})', raw_date)
                    if match:
                        current_date_str = f"{match.group(1)}.{year}"
                    data_cells = cells[1:]
                else:
                    data_cells = cells

                try:
                    time_text = data_cells[1].get_text(strip=True).replace('—', '-').replace('–', '-')
                    subject = data_cells[2].get_text(strip=True)
                    room = data_cells[5].get_text(strip=True)
                    
                    if '-' in time_text and subject and current_date_str:
                        start_t, end_t = [t.strip() for t in time_text.split('-')]
                        dt_start = TZ.localize(datetime.strptime(f"{current_date_str} {start_t}", "%d.%m.%Y %H:%M"))
                        dt_end = TZ.localize(datetime.strptime(f"{current_date_str} {end_t}", "%d.%m.%Y %H:%M"))
                        
                        e = Event()
                        e.add('summary', f"{subject} ({room})")
                        e.add('dtstart', dt_start)
                        e.add('dtend', dt_end)
                        e.add('location', room)

                        # Логика уведомлений
                        room_l = room.lower()
                        if current_date_str not in days_with_alarm:
                            alarm = Alarm()
                            alarm.add('action', 'DISPLAY')
                            
                            # Если кабинет с цифрами или спортзал — за час
                            if any(char.isdigit() for char in room) or "спортзал" in room_l:
                                alarm.add('trigger', timedelta(hours=-1))
                                alarm.add('description', f"Пара в {room}")
                                e.add_component(alarm)
                                days_with_alarm.add(current_date_str)
                            # Если вебинар — за 10 минут
                            elif "вебинар" in room_l or "авторизируйтесь" in room_l:
                                alarm.add('trigger', timedelta(minutes=-10))
                                alarm.add('description', "Скоро вебинар")
                                e.add_component(alarm)
                                days_with_alarm.add(current_date_str)

                        cal.add_component(e)
                except Exception as ex:
                    print(f"Ошибка парсинга строки: {ex}")
                    continue
        except Exception as ex:
            print(f"Ошибка запроса: {ex}")
            continue
                        
    return Response(cal.to_ical(), mimetype='text/calendar')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
