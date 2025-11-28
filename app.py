
from flask import Flask, render_template, request, redirect, url_for, session
from config import Config
from models import db, Month, Mass, Person, Availability
import calendar
import datetime
import unicodedata

WEEKDAY_LABELS = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}

ROLE_OPTIONS = ["Fotos", "Transmissão", "Projeção"]

def create_default_masses_for_month(month_obj):
    if not month_obj.year or not month_obj.month_number:
        return

    year = month_obj.year
    month_num = month_obj.month_number
    _, num_days = calendar.monthrange(year, month_num)

    schedule = {
        0: [("12:00", "Santa Missa")],
        1: [("12:00", "Santa Missa")],
        2: [("12:00", "Santa Missa")],
        3: [("12:00", "Santa Missa"), ("19:30", "Santa Missa e Adoração ao Santíssimo")],
        4: [("12:00", "Santa Missa")],
        5: [("17:00", "Santa Missa")],
        6: [("09:00", "Santa Missa"), ("11:00", "Santa Missa"),
            ("16:00", "Santa Missa"), ("19:30", "Santa Missa")],
    }

    for day in range(1, num_days + 1):
        d = datetime.date(year, month_num, day)
        weekday = d.weekday()
        if weekday not in schedule:
            continue

        date_str = d.strftime("%Y-%m-%d")
        for time_str, desc in schedule[weekday]:
            m = Mass(date=date_str, time=time_str, description=desc, month=month_obj)
            db.session.add(m)

    db.session.commit()


def group_masses_by_week_for_form(masses):
    weeks = {}
    for m in masses:
        d = datetime.datetime.strptime(m.date, "%Y-%m-%d").date()
        week_idx = (d.day - 1)//7 + 1
        week_label = f"Semana {week_idx}"
        day_label = f"{WEEKDAY_LABELS[d.weekday()]} {d.day:02d}/{d.month:02d}"

        weeks.setdefault(week_label, {}).setdefault(day_label, []).append(m)

    final = []
    for week_label, days in weeks.items():
        ordered_days = []
        for lbl, lst in days.items():
            d0 = datetime.datetime.strptime(lst[0].date, "%Y-%m-%d").date()
            ordered_days.append((lbl, d0, sorted(lst, key=lambda x: x.time)))
        ordered_days.sort(key=lambda x: x[1])
        final.append((week_label, [(lbl, masses_list) for lbl, _, masses_list in ordered_days]))
    final.sort(key=lambda x: int(x[0].split()[1]))
    return final


def group_masses_by_week_for_report(masses):
    weeks = {}
    for m in masses:
        d = datetime.datetime.strptime(m.date, "%Y-%m-%d").date()
        week_idx = (d.day - 1)//7 + 1
        week_label = f"Semana {week_idx}"
        day_label = f"{WEEKDAY_LABELS[d.weekday()]} {d.day:02d}/{d.month:02d}"
        weeks.setdefault(week_label, []).append((m, day_label, d))

    final = []
    for week_label, items in weeks.items():
        items.sort(key=lambda x: (x[2], x[0].time))
        final.append((week_label, [(m, day_label) for (m, day_label, _) in items]))
    final.sort(key=lambda x: int(x[0].split()[1]))
    return final


def normalize_text(text):
    if not text: return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


def format_name(name): return name.strip().title()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context(): db.create_all()

    from functools import wraps
    def admin_required(f):
        @wraps(f)
        def w(*a, **k):
            if not session.get("is_admin"):
                return redirect(url_for("admin_login"))
            return f(*a, **k)
        return w

    @app.route("/")
    def home():
        return "Pascom Escala - Sistema ativo!"

    @app.route("/admin/login", methods=["GET","POST"])
    def admin_login():
        if request.method=="POST":
            if request.form.get("password")==app.config["ADMIN_PASSWORD"]:
                session["is_admin"]=True
                return "Logado!"
            return "Senha incorreta"
        return "Tela de login"

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
