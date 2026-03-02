import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from flask import Flask, Response
from datetime import datetime
import pytz

app = Flask(__name__)
TZ = pytz.timezone('Europe/Samara')

SCHEDULE_URL = "https://timeo.mveu.ru"

@app.route('/calendar.ics')
def get_calendar():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(SCHEDULE_URL, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Явно ставим кодировку
        soup = BeautifulSoup(response.text, 'html.parser')
        cal = Calendar()
        
        # На сайте МВЕУ расписание обычно в таблице <table>
        rows = soup.find_all('tr')
        current_date = None
        
        for row in rows:
            # 1. Ищем заголовок дня (обычно это <th> или <td> с датой)
            # Дата на сайте выглядит как "02.03.2026, Понедельник"
            date_cell = row.find(['th', 'td'], class_='date-column') or row.find('th')
            if date_cell and '.' in date_cell.text:
                text = date_cell.get_text(strip=True)
                # Вытаскиваем только саму дату "02.03.2026"
                current_date = text.split(',')[0].strip()
                continue

            # 2. Ищем строки с парами
            cols = row.find_all('td')
            # В таблице МВЕУ обычно: Время | Предмет | Преподаватель/Кабинет
            if len(cols) >= 2 and current_date:
                time_text = cols[0].get_text(strip=True) # "08:30-10:00" или "08:30 - 10:00"
                
                # Если в первой колонке нет тире, это не время, пропускаем
                if '-' not in time_text:
                    continue
                
                subject = cols[1].get_text(strip=True)
                # Если есть третья колонка — там кабинет и препод
                details = cols[2].get_text(strip=True) if len(cols) > 2 else ""

                try:
                    # Чистим время от пробелов
                    times = time_text.replace(' ', '').split('-')
                    start_t = times[0]
                    end_t = times[1]
                    
                    e = Event()
                    e.name = subject
                    e.location = details
                    # Собираем дату и время в один объект
                    e.begin = TZ.localize(datetime.strptime(f"{current_date} {start_t}", "%d.%m.%Y %H:%M"))
                    e.end = TZ.localize(datetime.strptime(f"{current_date} {end_t}", "%d.%m.%Y %H:%M"))
                    cal.events.add(e)
                except Exception as ex:
                    print(f"Ошибка парсинга строки: {ex}")
                    continue
                
        return Response(str(cal), mimetype='text/calendar')
    
    except Exception as e:
        return f"Ошибка сервера: {str(e)}", 500

@app.route('/')
def index():
    return 'Сервер запущен. <a href="/calendar.ics">Скачать/Проверить .ics файл</a>'
