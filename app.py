import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event
from flask import Flask, Response
from datetime import datetime
import pytz
import re

app = Flask(__name__)
TZ = pytz.timezone('Europe/Samara')
URL = "https://timeo.mveu.ru"

@app.route('/calendar.ics')
def get_calendar():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    cal = Calendar()
    cal.extra.append(re.sub(r'\s+', '', "X-PUBLISHED-TTL:PT1H"))
    
    for skip in [-1, 0, 1]:
        try:
            res = requests.get(f"{URL}&skip={skip}", headers=headers, timeout=15)
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # Ищем таблицу именно в блоке crudTable
            table = soup.find('table', class_='crud')
            if not table: continue

            rows = table.find_all('tr')
            curr_date = None
            year = datetime.now().year

            for row in rows:
                cells = row.find_all('td')
                if not cells: continue

                # Проверяем, есть ли дата в этой строке (rowspan)
                if cells[0].has_attr('rowspan'):
                    d_match = re.search(r'(\d{2}\.\d{2})', cells[0].get_text())
                    if d_match: 
                        curr_date = f"{d_match.group(1)}.{year}"
                    
                    # Когда дата ЕСТЬ, индексы: 2-время, 3-предмет, 5-препод, 6-ауд
                    idx = {"time": 2, "subj": 3, "prof": 5, "room": 6}
                else:
                    # Когда даты НЕТ, индексы: 1-время, 2-предмет, 4-препод, 5-ауд
                    idx = {"time": 1, "subj": 2, "prof": 4, "room": 5}

                # Защита: проверяем, что в строке достаточно ячеек
                needed_idx = max(idx.values())
                if len(cells) > needed_idx and curr_date:
                    try:
                        time_raw = cells[idx["time"]].get_text(strip=True).replace('—', '-').replace('–', '-')
                        subj = cells[idx["subj"]].get_text(strip=True)
                        prof = cells[idx["prof"]].get_text(strip=True)
                        room = cells[idx["room"]].get_text(strip=True)

                        if '-' in time_raw and subj:
                            st, en = [t.strip() for t in time_raw.split('-')]
                            e = Event()
                            e.name = subj
                            e.location = f"{room}, {prof}"
                            e.begin = TZ.localize(datetime.strptime(f"{curr_date} {st}", "%d.%m.%Y %H:%M"))
                            e.end = TZ.localize(datetime.strptime(f"{curr_date} {en}", "%d.%m.%Y %H:%M"))
                            cal.events.add(e)
                    except Exception:
                        continue # Если одна строка битая, идем к следующей
        except Exception:
            continue
                        
    return Response(str(cal), mimetype='text/calendar')

@app.route('/')
def home():
    return 'Бот МВЕУ работает! <a href="/calendar.ics">Ссылка</a>'

if __name__ == "__main__":
    app.run()
