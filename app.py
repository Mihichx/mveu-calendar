import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
from flask import Flask, Response
from datetime import datetime, timedelta
import pytz
import re

app = Flask(__name__)
TZ = pytz.timezone('Europe/Samara')
URL = "https://timeo.mveu.ru"

@app.route('/calendar.ics')
def get_calendar():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    cal = Calendar()
    cal.add('prodid', '-//MVEU Schedule Full//')
    cal.add('version', '2.0')
    
    # Чтобы уведомление было только на первую подходящую пару дня
    days_with_alarm = set()

    for skip in [-1, 0, 1, 2]:
        week_url = f"{URL}&skip={skip}"
        try:
            response = requests.get(week_url, headers=headers, timeout=20)
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
                    teacher = data_cells[4].get_text(strip=True)
                    room = data_cells[5].get_text(strip=True)

                    if '-' in time_text and subject and current_date_str:
                        start_t, end_t = [t.strip() for t in time_text.split('-')]
                        dt_start = TZ.localize(datetime.strptime(f"{current_date_str} {start_t}", "%d.%m.%Y %H:%M"))
                        dt_end = TZ.localize(datetime.strptime(f"{current_date_str} {end_t}", "%d.%m.%Y %H:%M"))
                        
                        e = Event()
                        e.add('summary', subject)
                        e.add('location', f"{room}, {teacher}")
                        e.add('dtstart', dt_start)
                        e.add('dtend', dt_end)

                        # ЛОГИКА УВЕДОМЛЕНИЙ
                        subject_l = subject.lower()
                        room_l = room.lower()
                        
                        # 1. Проверяем, нужно ли ВООБЩЕ уведомление для этой пары
                        # Ставим, если это НЕ "Код будущего" ИЛИ если это именно "Базовый" код будущего
                        need_alarm = ("код будущего" not in subject_l) or ("базовый" in subject_l)

                        # 2. Если нужно и это первая пара дня — настраиваем время
                        if need_alarm and current_date_str not in days_with_alarm:
                            alarm = Alarm()
                            alarm.add('action', 'DISPLAY')

                            # Оффлайн (Цифры в аудитории или Спортзал) -> 1 час
                            if any(char.isdigit() for char in room) or "спортзал" in room_l:
                                alarm.add('trigger', timedelta(hours=-1))
                                alarm.add('description', f"Через час пара: {subject}")
                                e.add_component(alarm)
                                days_with_alarm.add(current_date_str)
                            
                            # Онлайн (Вебинары или "Базовый код будущего") -> 10 минут
                            elif any(word in room_l for word in ["вебинар", "авторизируйтесь", "http"]) or "базовый" in subject_l:
                                alarm.add('trigger', timedelta(minutes=-10))
                                alarm.add('description', f"Через 10 мин: {subject}")
                                e.add_component(alarm)
                                days_with_alarm.add(current_date_str)

                        cal.add_component(e)
                except: continue
        except: continue
                        
    return Response(cal.to_ical(), mimetype='text/calendar')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
