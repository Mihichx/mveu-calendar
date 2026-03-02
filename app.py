import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from flask import Flask, Response
from datetime import datetime
import pytz
import re

app = Flask(__name__)
# Часовой пояс Ижевска (UTC+4)
TZ = pytz.timezone('Europe/Samara')

# Твоя ссылка
URL = "https://timeo.mveu.ru/schedule/table?group=%D0%94%D0%98%D0%A1-242/21%D0%91"

@app.route('/calendar.ics')
def get_calendar():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    cal = Calendar()
    # Подсказка для Outlook обновляться чаще (раз в час)
    cal.extra.append(re.sub(r'\s+', '', "X-PUBLISHED-TTL:PT1H"))
    
    for skip in [-1, 0, 1]:
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

                # Определяем дату
                if cells[0].has_attr('rowspan'):
                    raw_date = cells[0].get_text(strip=True)
                    match = re.search(r'(\d{2}\.\d{2})', raw_date)
                    if match:
                        current_date_str = f"{match.group(1)}.{year}"
                    data_cells = cells[1:]
                else:
                    data_cells = cells

                # Сбор данных о паре
                try:
                    time_text = data_cells[1].get_text(strip=True).replace('—', '-').replace('–', '-')
                    subject = data_cells[2].get_text(strip=True)
                    teacher = data_cells[4].get_text(strip=True)
                    room = data_cells[5].get_text(strip=True)

                    if '-' in time_text and subject and current_date_str:
                        start_t, end_t = [t.strip() for t in time_text.split('-')]
                        
                        e = Event()
                        e.name = subject
                        e.location = f"Ауд: {room}, {teacher}"
                        
                        # Указываем местное время Ижевска, чтобы не было сдвига
                        e.begin = TZ.localize(datetime.strptime(f"{current_date_str} {start_t}", "%d.%m.%Y %H:%M"))
                        e.end = TZ.localize(datetime.strptime(f"{current_date_str} {end_t}", "%d.%m.%Y %H:%M"))
                        cal.events.add(e)
                except: continue
        except: continue
                        
    return Response(str(cal), mimetype='text/calendar')

@app.route('/')
def home():
    return 'Бот МВЕУ работает! Подключи эту ссылку: <a href="/calendar.ics">/calendar.ics</a>'

if __name__ == "__main__":
    app.run()
