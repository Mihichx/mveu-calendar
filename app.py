import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event, Alarm
from flask import Flask, Response
from datetime import datetime, timedelta
import pytz
import re
import os
from collections import defaultdict

app = Flask(__name__)
TZ = pytz.timezone('Europe/Samara')
URL = "https://timeo.mveu.ru/schedule/table?group=%D0%94%D0%98%D0%A1-242/21%D0%91"

@app.route('/')
def home():
    return 'Бот МВЕУ работает! <a href="/calendar.ics">/calendar.ics</a>'

def parse_lessons():
    headers = {'User-Agent': 'Mozilla/5.0'}
    events_by_date = defaultdict(list)
    year = datetime.now().year

    for skip in [-1, 0, 1, 2]:
        week_url = f"{URL}&skip={skip}"
        try:
            response = requests.get(week_url, headers=headers, timeout=15)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='crud')
            if not table: continue

            current_date_str = None
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if not cells or len(cells) < 4: continue 

                if cells[0].has_attr('rowspan'):
                    match = re.search(r'(\d{2}\.\d{2})', cells[0].get_text(strip=True))
                    if match: current_date_str = f"{match.group(1)}.{year}"
                    data = cells[1:]
                else:
                    data = cells

                try:
                    # Индексы как в твоем рабочем коде: 1-время, 2-предмет, 4-учитель, 5-ауд
                    time_text = data[1].get_text(strip=True).replace('—', '-').replace('–', '-')
                    subject = data[2].get_text(strip=True)
                    teacher = data[4].get_text(strip=True)
                    room = data[5].get_text(strip=True)
                    
                    # Жесткий фильтр мусора
                    if not time_text or not subject or len(subject) < 3 or "-" not in time_text:
                        continue

                    if current_date_str:
                        start_t, end_t = [t.strip() for t in time_text.split('-')]
                        dt_start = TZ.localize(datetime.strptime(f"{current_date_str} {start_t}", "%d.%m.%Y %H:%M"))
                        dt_end = TZ.localize(datetime.strptime(f"{current_date_str} {end_t}", "%d.%m.%Y %H:%M"))
                        
                        events_by_date[current_date_str].append({
                            'subject': subject,
                            'room': room,
                            'teacher': teacher,
                            'start': dt_start,
                            'end': dt_end
                        })
                except: continue
        except: continue
    return events_by_date

@app.route('/calendar.ics')
def get_calendar():
    events_by_date = parse_lessons()
    cal = Calendar()
    
    cal.add('prodid', '-//MVEU Schedule Bot//')
    cal.add('version', '2.0')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', 'Расписание МВЕУ')
    cal.add('x-wr-timezone', 'Europe/Samara')

    for date_str in sorted(events_by_date.keys(), key=lambda x: datetime.strptime(x, "%d.%m.%Y")):
        lessons = sorted(events_by_date[date_str], key=lambda x: x['start'])
        last_alarm_end_time = None

        for lesson in lessons:
            room_l = lesson['room'].lower()
            subj_l = lesson['subject'].lower()
            
            is_offline = any(char.isdigit() for char in lesson['room']) or "спортзал" in room_l
            is_online = "вебинар" in room_l or "базовый" in subj_l or "авторизируйтесь" in room_l
            is_trash = "начальный" in subj_l

            trigger_minutes = None
            if not is_trash:
                # Защита от спама (перерыв > 40 мин)
                has_break = last_alarm_end_time is None or (lesson['start'] - last_alarm_end_time) > timedelta(minutes=40)
                if is_offline and has_break:
                    trigger_minutes = 60
                elif is_online and has_break:
                    trigger_minutes = 10

            e = Event()
            e.add('summary', f"{lesson['subject']} ({lesson['room']})")
            e.add('dtstart', lesson['start'])
            e.add('dtend', lesson['end'])
            e.add('location', f"Ауд: {lesson['room']}, {lesson['teacher']}")
            e.add('uid', f"{lesson['start'].strftime('%Y%m%dT%H%M%S')}@mveu_bot")

            if trigger_minutes:
                alarm = Alarm()
                alarm.add('action', 'DISPLAY')
                alarm.add('trigger', timedelta(minutes=-trigger_minutes))
                alarm.add('description', f"Напоминание за {trigger_minutes} мин")
                e.add_component(alarm)
                last_alarm_end_time = lesson['end']
            elif last_alarm_end_time is not None and (lesson['start'] - last_alarm_end_time) <= timedelta(minutes=40):
                last_alarm_end_time = lesson['end']

            cal.add_component(e)

    # Ответ с запретом кэша
    response = Response(cal.to_ical(), mimetype='text/calendar')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
