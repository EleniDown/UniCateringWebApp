import requests
import sqlite3
import time
from fastapi.responses import HTMLResponse
from bs4 import BeautifulSoup

from typing import Union

from fastapi import FastAPI

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
def read_root():
    html = """
    <!doctype html>
    <html>
    <head>
    <title>Our Restaurant</title>
    <meta name="description" content="Our uni restaurants">
    <meta name="keywords" content="uni restaurant menu">
    </head>
    <body>
    Καλώς ήρθατε στο μενού του εστιατορίου του 
    <a href="/uni/auth">
    Αριστοτέλειου Πανεπιστημίου Θεσσαλονίκης
    </a>
    <ul>
    <li><a href="/uni/auth?menu_time=ΠΡΩ">
    Πρωινό
    </a></li>
    <li><a href="/uni/auth?menu_time=ΜΕΣ">
    Μεσημεριανό
    </a></li>
    <li><a href="/uni/auth?menu_time=ΒΡΑΔ">
    Βραδινό
    </a></li>
    </ul>
    </body>
    </html>
"""
    return html

@app.get("/uni/pamak", response_class=HTMLResponse)
def menu_pamak():
    r = requests.get("https://my.uom.gr/restaurant")
    return r.text

@app.get("/uni/auth")
def menu_auth(filter:str="", menu_time:str=""):
    con = connect_database()
    dishes = get_dishes(con)
    filtered_dishes = [dish for dish in dishes if filter.upper() in str(dish).upper()]
    dish_objs = [dishrow_toobject(dish) for dish in filtered_dishes]
    filtered_objs = [dish for dish in dish_objs if menu_time.upper() in dish['menu_time'].upper()]
    return filtered_objs 
    
@app.get("/refreshdatabase")
def refresh_database():
    con = connect_database()
    r = requests.get("https://www.auth.gr/weekly-menu/")
    html_doc = r.text
    soup = BeautifulSoup(html_doc, 'html.parser')
    x = "wp-block-kadence-pane"
    days = soup.find_all("div", class_=x)
    weekdays = ['ΔΕΥΤΕΡΑ', 'ΤΡΙΤΗ', 'ΤΕΤΑΡΤΗ', 'ΠΕΜΠΤΗ', 'ΠΑΡΑΣΚΕΥΗ', 'ΣΑΒΒΑΤΟ', 'ΚΥΡΙΑΚΗ']
    t = time.time()
    for i, day in enumerate(days): 
        weekday = weekdays[i]
        breakfast, lunch, dinner = parse_day(day)
        insert_dish(con, breakfast, weekday, 'ΠΡΩΙΝΟ', '', t)

        lunch_firsts, lunch_mains = lunch
        for f in lunch_firsts:
            insert_dish(con, f, weekday, 'ΜΕΣΗΜΕΡΙΑΝΟ', 'ΠΡΩΤΟ', t)
        for m in lunch_mains:
            insert_dish(con, m, weekday, 'ΜΕΣΗΜΕΡΙΑΝΟ', 'ΚΥΡΙΩΣ', t)

        dinner_firsts, dinner_mains = dinner
        for f in dinner_firsts:
            insert_dish(con, f, weekday, 'ΒΡΑΔΙΝΟ', 'ΠΡΩΤΟ', t)
        for m in dinner_mains:
            insert_dish(con, m, weekday, 'ΒΡΑΔΙΝΟ', 'ΚΥΡΙΩΣ', t)
    return 'success'

@app.get("/cleardatabase")
def clear_database():
    clear_dishes()
    return 'success'

def parse_day(day_div):
    BREAKFAST = "Πρωινό (Ωράριο Διανομής : 08:30 – 10:30)"
    LUNCH = "Μεσημεριανό (Ωράριο Διανομής : 12:00 – 16:00)"
    DINNER = "Βραδινό (Ωράριο Διανομής : 18:00 – 21:00)"
    all_elements = day_div.find_all()
    breakfast = ""
    lunch_options = []
    dinner_options = []
    lunch_appeared = None
    dinner_appeared = None
    for i, el in enumerate(all_elements):
        el_text = el.get_text(" ", strip=True)
        if BREAKFAST == el_text:
            breakfast = all_elements[i+3].get_text(" ", strip=True)
        elif LUNCH == el_text:
            lunch_appeared = i
        elif DINNER == el_text:
            dinner_appeared = i
    if lunch_appeared is not None and dinner_appeared is not None:
        lunch_options = [el.get_text(" ", strip=True) for el in all_elements[lunch_appeared:dinner_appeared]]
        dinner_options = [el.get_text(" ", strip=True) for el in all_elements[dinner_appeared:]]
    return breakfast, parse_lunch_dinner(lunch_options), parse_lunch_dinner(dinner_options)

def parse_lunch_dinner(options):
    first_dish = []
    main_dish = []
    first_dish_appeared = None
    main_dish_appeared = None
    salad_appeared = None
    for i, option in enumerate(options):
        if option == "ΠΡΩΤΟ ΠΙΑΤΟ":
            first_dish_appeared = i
        elif option == "ΚΥΡΙΩΣ ΠΙΑΤΑ":
            main_dish_appeared = i
        elif option == "ΣΑΛΑΤΑ":
            salad_appeared = i
    if first_dish_appeared is not None and main_dish_appeared is not None and salad_appeared is not None:
        first_dish = [option for option in options[first_dish_appeared+2:main_dish_appeared-1]]
        main_dish = [option for option in options[main_dish_appeared+2:salad_appeared-1]]

    return cleanup_authmenulist(first_dish), cleanup_authmenulist(main_dish)

def cleanup_authmenulist(original_list):
    previous = ''
    final_list = []
    for el in original_list:
        final_list.append(el)
        if el in previous:
            final_list.remove(previous)
        previous = el

    return final_list
    
def connect_database():
    con = sqlite3.connect("restaurant.db")
    cur = con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS dish(dish_name, menu_day, menu_time, dish_type, retrieval_ts)")
    return con

def insert_dish(con, dish_name, menu_day, menu_time, dish_type, ts):
    if con is None: 
        con = sqlite3.connect("restaurant.db")
    cur = con.cursor()
    cur.execute(f"""
    INSERT INTO dish VALUES
        ('{dish_name}', '{menu_day}', '{menu_time}', '{dish_type}', '{ts}')
    """)
    con.commit()

def get_dishes(con):
    if con is None: 
        con = sqlite3.connect("restaurant.db")
    cur = con.cursor()
    res = cur.execute('SELECT * FROM dish')
    return res.fetchall()

def clear_dishes(con=None):
    if con is None: 
        con = sqlite3.connect("restaurant.db")
    cur = con.cursor()
    res = cur.execute('DELETE FROM dish')
    con.commit()

def dishrow_toobject(dishrow):
    dish_name, menu_day, menu_time, dish_type, ts = dishrow
    return dict(dish_name=dish_name, menu_day=menu_day, menu_time=menu_time, dish_type=dish_type, ts=ts)