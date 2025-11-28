from flask import Flask, render_template, request, redirect, url_for, session
from config import Config
from models import db, Month, Mass, Person, Availability
import calendar
import datetime
import unicodedata

# -------------------------------------------------
# Configurações gerais
# -------------------------------------------------

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
    """
    Gera automaticamente as missas do mês com base na programação fixa.
    Só funciona se year e month_number estiverem preenchidos.
    """
    if not month_obj.year or not month_obj.month_number:
        return

    year = month_obj.year
    month_num = month_obj.month_number

    _, num_days = calendar.monthrange(year, month_num)

    # Programação fixa de missas
    schedule = {
        0: [("12:00", "Santa Missa")],
        1: [("12:00", "Santa Missa")],
        2: [("12:00", "Santa Missa")],
        3: [("12:00", "Santa Missa"),
            ("19:30", "Santa Missa e Adoração ao Santíssimo")],
        4: [("12:00", "Santa Missa")],
        5: [("17:00", "Santa Missa")],
        6: [("09:00", "Santa Missa"),
            ("11:00", "Santa Missa"),
            ("16:00", "Santa Missa"),
            ("19:30", "Santa Missa")],
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
    """
    Agrupa missas por semana e dia, para o formulário de disponibilidade.
    Retorna: [(Semana 1, [(Dia, [missas...] ), ...]), ...]
    """
    weeks = {}
    for m in masses:
        d = datetime.datetime.strptime(m.date, "%Y-%m-%d").date()
        week_idx = (d.day - 1) // 7 + 1
        week_label = f"Semana {week_idx}"
        day_label = f"{WEEKDAY_LABELS[d.weekday()]} {d.day:02d}/{d.month:02d}"

        if week_label not in weeks:
            weeks[week_label] = {}
        if day_label not in weeks[week_label]:
            weeks[week_label][day_label] = []
        weeks[week_label][day_label].append(m)

    result = []
    for week_label, days_dict in weeks.items():
        day_items = []
        for day_label, masses_list in days_dict.items():
            m0 = masses_list[0]
            d = datetime.datetime.strptime(m0.date, "%Y-%m-%d").date()
            day_items.append((day_label, d, sorted(masses_list, key=lambda mm: mm.time)))
        # ordena dias dentro da semana
        day_items_sorted = sorted(day_items, key=lambda x: x[1])
        result.append((week_label, [(lbl, mlist) for (lbl, _d, mlist) in day_items_sorted]))

    # Ordena semanas 1, 2, 3...
    def week_sort(item):
        label, _ = item
        try:
            return int(label.split()[-1])
        except ValueError:
            return 99

    return sorted(result, key=week_sort)


def group_masses_by_week_for_report(masses):
    """
    Agrupa missas por semana para o relatório.
    Retorna: [(Semana 1, [(mass, day_label), ...]), ...]
    """
    weeks = {}
    for m in masses:
        d = datetime.datetime.strptime(m.date, "%Y-%m-%d").date()
        week_idx = (d.day - 1) // 7 + 1
        week_label = f"Semana {week_idx}"
        day_label = f"{WEEKDAY_LABELS[d.weekday()]} {d.day:02d}/{d.month:02d}"
        if week_label not in weeks:
            weeks[week_label] = []
        weeks[week_label].append((m, day_label, d))

    result = []
    for week_label, entries in weeks.items():
        entries_sorted = sorted(entries, key=lambda x: (x[2], x[0].time))
        result.append((week_label, [(m, day_label) for (m, day_label, _d) in entries_sorted]))

    def week_sort(item):
        label, _ = item
        try:
            return int(label.split()[-1])
        except ValueError:
            return 99

    return sorted(result, key=week_sort)


def normalize_text(text: str) -> str:
    """Remove acento e deixa minúsculo para comparação de nomes."""
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower().strip()


def format_name(name: str) -> str:
    """Coloca iniciais maiúsculas em nomes."""
    if not name:
        return ""
    return name.strip().title()


# -------------------------------------------------
# Factory da aplicação
# -------------------------------------------------

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # cria tabelas ao iniciar
    with app.app_context():
        db.create_all()

    from functools import wraps

    def admin_required(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not session.get("is_admin"):
                return redirect(url_for("admin_login"))
            return func(*args, **kwargs)
        return wrapper

    # ------------------ Rotas públicas ------------------

    @app.route("/")
    def home():
        # Se quiser depois, trocar por render_template("home.html")
        return "Sistema Pascom Trindade rodando! Use /admin/login para a coordenação."

    @app.route("/disponibilidade/<int:month_id>", methods=["GET", "POST"])
    def availability_select_person(month_id):
        month = Month.query.get_or_404(month_id)
        persons = Person.query.order_by(Person.name).all()
        error = None

        if request.method == "POST":
            name_raw = (request.form.get("name") or "").strip()
            if not name_raw:
                error = "Por favor, digite seu nome."
            else:
                norm_input = normalize_text(name_raw)
                found = None
                for p in persons:
                    if normalize_text(p.name) == norm_input:
                        found = p
                        break
                if not found:
                    new_name = format_name(name_raw)
                    found = Person(name=new_name)
                    db.session.add(found)
                    db.session.commit()
                return redirect(url_for("availability_for_person", month_id=month_id, person_id=found.id))

        # aqui você pode depois trocar por um template HTML
        # por enquanto, só um texto simples:
        if error:
            return f"Erro: {error}", 400
        return f"Seleção de nome para mês {month.name}. (Depois podemos ligar a um template.)"

    @app.route("/disponibilidade/<int:month_id>/pessoa/<int:person_id>", methods=["GET", "POST"])
    def availability_for_person(month_id, person_id):
        month = Month.query.get_or_404(month_id)
        person = Person.query.get_or_404(person_id)
        masses = Mass.query.filter_by(month_id=month_id).order_by(Mass.date, Mass.time).all()
        week_groups = group_masses_by_week_for_form(masses)

        existing = Availability.query.join(Mass).filter(
            Availability.person_id == person.id,
            Mass.month_id == month_id
        ).all()
        roles_by_mass = {a.mass_id: a.role for a in existing if a.role}

        if request.method == "POST":
            selected_roles = {}
            for m in masses:
                field_name = f"role_{m.id}"
                role = request.form.get(field_name)
                if role:
                    selected_roles[m.id] = role

            existing_by_mass = {a.mass_id: a for a in existing}

            for mass_id, role in selected_roles.items():
                if mass_id in existing_by_mass:
                    existing_by_mass[mass_id].role = role
                    existing_by_mass[mass_id].available = True
                else:
                    a = Availability(person_id=person.id, mass_id=mass_id, role=role, available=True)
                    db.session.add(a)

            db.session.commit()
            return f"Disponibilidade de {person.name} para {month.name} salva com sucesso!"

        # aqui você pode depois renderizar um template bonitinho
        return f"Formulário de disponibilidade para {person.name} no mês {month.name}."

    # ------------------ Rotas de autenticação admin ------------------

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        error = None
        if request.method == "POST":
            password = request.form.get("password")
            if password == app.config["ADMIN_PASSWORD"]:
                session["is_admin"] = True
                return redirect(url_for("admin_dashboard"))
            else:
                error = "Senha incorreta."

        # Simples por enquanto, depois pode trocar por template:
        if error:
            return f"Login coordenação – {error}", 401
        return "Tela de login da coordenação. Faça POST com 'password'."

    @app.route("/admin/logout")
    def admin_logout():
        session.pop("is_admin", None)
        return redirect(url_for("home"))

    # ------------------ Painel admin ------------------

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        months = Month.query.order_by(Month.id.desc()).all()
        # depois: render_template("admin_dashboard.html", months=months)
        names = ", ".join(m.name for m in months) or "Nenhum mês cadastrado."
        return f"Painel da coordenação. Meses cadastrados: {names}"

    @app.route("/admin/persons", methods=["GET", "POST"])
    @admin_required
    def manage_persons():
        if request.method == "POST":
            name_raw = request.form.get("name")
            if name_raw:
                name = format_name(name_raw)
                p = Person(name=name)
                db.session.add(p)
                db.session.commit()
                return redirect(url_for("manage_persons"))
        persons = Person.query.order_by(Person.name).all()
        lista = ", ".join(p.name for p in persons) or "Nenhuma pessoa cadastrada."
        return f"Pessoas cadastradas: {lista}"

    @app.route("/admin/persons/<int:person_id>/delete", methods=["POST"])
    @admin_required
    def delete_person(person_id):
        person = Person.query.get_or_404(person_id)
        Availability.query.filter_by(person_id=person.id).delete()
        db.session.delete(person)
        db.session.commit()
        return redirect(url_for("manage_persons"))

    @app.route("/admin/month/new", methods=["GET", "POST"])
    @admin_required
    def new_month():
        if request.method == "POST":
            name = request.form.get("name")
            year_raw = request.form.get("year")
            month_raw = request.form.get("month_number")

            if name:
                month_obj = Month(name=name.strip())
                if year_raw and month_raw:
                    try:
                        month_obj.year = int(year_raw)
                        month_obj.month_number = int(month_raw)
                    except ValueError:
                        pass

                db.session.add(month_obj)
                db.session.commit()

                if month_obj.year and month_obj.month_number:
                    create_default_masses_for_month(month_obj)

                return redirect(url_for("admin_dashboard"))

        return "Form de novo mês (POST com name, year, month_number)."

    @app.route("/admin/month/<int:month_id>/masses", methods=["GET", "POST"])
    @admin_required
    def manage_masses(month_id):
        month = Month.query.get_or_404(month_id)
        if request.method == "POST":
            date = request.form.get("date")
            time = request.form.get("time")
            description = request.form.get("description")
            if date and time:
                m = Mass(date=date, time=time, description=description, month=month)
                db.session.add(m)
                db.session.commit()
                return redirect(url_for("manage_masses", month_id=month_id))
        masses = Mass.query.filter_by(month_id=month_id).order_by(Mass.date, Mass.time).all()
        return f"Gerenciamento de missas para {month.name}. Total: {len(masses)}."

    @app.route("/admin/mass/<int:mass_id>/edit", methods=["GET", "POST"])
    @admin_required
    def edit_mass(mass_id):
        mass = Mass.query.get_or_404(mass_id)
        if request.method == "POST":
            mass.date = request.form.get("date")
            mass.time = request.form.get("time")
            mass.description = request.form.get("description")
            db.session.commit()
            return redirect(url_for("manage_masses", month_id=mass.month_id))
        return f"Editar missa {mass.id} (depois podemos pôr um form HTML)."

    @app.route("/admin/mass/<int:mass_id>/delete", methods=["POST"])
    @admin_required
    def delete_mass(mass_id):
        mass = Mass.query.get_or_404(mass_id)
        Availability.query.filter_by(mass_id=mass.id).delete()
        month_id = mass.month_id
        db.session.delete(mass)
        db.session.commit()
        return redirect(url_for("manage_masses", month_id=month_id))

    @app.route("/admin/month/<int:month_id>/links")
    @admin_required
    def month_links(month_id):
        month = Month.query.get_or_404(month_id)
        link = url_for("availability_select_person", month_id=month.id, _external=True)
        return f"Link único para disponibilidade de {month.name}: {link}"

    @app.route("/admin/month/<int:month_id>/relatorio")
    @admin_required
    def month_report(month_id):
        month = Month.query.get_or_404(month_id)
        masses = Mass.query.filter_by(month_id=month_id).order_by(Mass.date, Mass.time).all()
        avs = Availability.query.join(Person).join(Mass).filter(Mass.month_id == month_id).all()

        people_map = {}
        for a in avs:
            pid = a.person_id
            if pid not in people_map:
                people_map[pid] = {"person": a.person, "availability": {}}
            people_map[pid]["availability"][a.mass_id] = a.role or "✔"

        people = sorted(people_map.values(), key=lambda x: x["person"].name.lower())
        week_groups_report = group_masses_by_week_for_report(masses)

        # Versão simples em texto pra não quebrar nada no deploy
        return f"Relatório de {month.name} com {len(people)} pessoas e {len(masses)} missas."

    return app


# -------------------------------------------------
# Instância global para o Gunicorn (Railway)
# -------------------------------------------------

app = create_app()

if __name__ == "__main__":
    # Para rodar localmente
    app.run(debug=True)
