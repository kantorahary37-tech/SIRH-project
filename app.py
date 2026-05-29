import logging
import os
from datetime import date, datetime
from functools import wraps

import pandas as pd
from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import extract, func
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from models import db
from models.agents import Agent
from models.mouvements import Mouvement, enregistrer_mouvement
from models.sanctions import Sanction
from models.users import User

logger = logging.getLogger(__name__)

LISTE_CORPS = [
    "Inspecteur de trésor",
    "Percepteur Principal des Finances",
    "Percepteur des Finances",
    "Controleur du Trésor",
    "Comptable du Trésor",
    "Planificateur principal",
    "Magistrat",
    "Concepteur",
    "Planificateur",
    "Fonctionnaire de la catégorie VII",
    "Attaché de planification",
    "Réalisateur",
    "Réalisateur adjoint",
    "Technicien supérieur",
    "Encadreur",
    "Opérateur",
    "Sous opérateur",
    "Contractuel",
    "ELD",
    "ECD",
    "Autre",
    "Agent de police",
    "Agent détaché"
]

AGENT_FIELDS = [
    "agent",
    "matricule",
    "telephone",
    "genre",
    "date_naissance",
    "statut",
    "corps",
    "poste_type",
    "poste_comptable",
    "date_premiere_prise_service",
    "historique_formations",
    "epoux_epouse_nom_poste",
    "promotion_corps",
]

AGENT_INACTIVITY_FIELDS = [
    "motif_inactivite",
    "date_inactivite",
    "commentaire_inactivite",
]

USER_ROLES = ["admin", "gestionnaire", "lecteur"]
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

DATE_FIELDS = {
    "date_naissance",
    "date_premiere_prise_service",
    "date_inactivite",
}

IMPORT_RENAME_MAP = {
    "agents": "agent",
    "postes comptables": "poste_comptable",
    "date de naissance": "date_naissance",
    "poste type": "poste_type",
    "date de premiere prise de service": "date_premiere_prise_service",
    "historique formations": "historique_formations",
    "historique des formations": "historique_formations",
    "epoux ou epouse": "epoux_epouse_nom_poste",
    "promotion corps": "promotion_corps",
    "numero telephone": "telephone",
    "im": "matricule",
}

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "sirh_secret_key"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "mysql+pymysql://root@localhost/sirh"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    UPLOAD_FOLDER=UPLOAD_FOLDER,
)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user.role != "admin":
            flash("Accès réservé à l'administrateur.", "danger")
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapped_view


def normalize_value(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass

    if isinstance(value, str):
        value = value.strip()
        return value or None

    return value


def parse_optional_date(value):
    value = normalize_value(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def normalize_genre(value):
    value = normalize_value(value)
    if value is None:
        return None

    normalized = str(value).upper()
    if normalized in {"M", "MALE", "H", "MASCULIN", "HOMME"}:
        return "Homme"
    if normalized in {"F", "FEMALE", "FEMININ", "FEMME"}:
        return "Femme"
    return str(value)


def normalize_matricule(value):
    value = normalize_value(value)
    if value is None:
        return None
    return str(value).replace(".0", "").strip() or None


def normalize_agent_value(field, value):
    if field == "matricule":
        return normalize_matricule(value)
    if field == "genre":
        return normalize_genre(value)
    if field in DATE_FIELDS:
        return parse_optional_date(value)

    value = normalize_value(value)
    if value is None:
        return None

    return str(value) if isinstance(value, (int, float)) else value


def build_agent_payload(source, fields, defaults=None):
    payload = {
        field: normalize_agent_value(field, source.get(field))
        for field in fields
    }

    for field, value in (defaults or {}).items():
        if payload.get(field) is None:
            payload[field] = value

    return payload


def build_merged_agent_payload(agent, source, fields, defaults=None):
    merged_source = {
        field: source.get(field, getattr(agent, field))
        for field in fields
    }
    return build_agent_payload(merged_source, fields, defaults=defaults)


def apply_agent_payload(agent, payload, keep_existing=False):
    for field, value in payload.items():
        if keep_existing and value is None:
            continue
        setattr(agent, field, value)


def serialize_for_compare(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return "" if value is None else str(value)


def calculate_age(value, today=None):
    target_date = parse_optional_date(value)
    if target_date is None:
        return None

    today = today or date.today()
    return today.year - target_date.year - (
        (today.month, today.day) < (target_date.month, target_date.day)
    )


def serialize_agent(agent):
    return {
        "id": agent.id,
        "matricule": agent.matricule,
        "agent": agent.agent,
        "telephone": agent.telephone,
        "genre": agent.genre,
        "date_naissance": agent.date_naissance.isoformat() if agent.date_naissance else None,
        "statut": agent.statut,
        "corps": agent.corps,
        "poste_type": agent.poste_type,
        "poste_comptable": agent.poste_comptable,
        "date_premiere_prise_service": (
            agent.date_premiere_prise_service.isoformat()
            if agent.date_premiere_prise_service else None
        ),
        "historique_formations": agent.historique_formations,
        "epoux_epouse_nom_poste": agent.epoux_epouse_nom_poste,
        "promotion_corps": agent.promotion_corps,
        "motif_inactivite": agent.motif_inactivite,
        "date_inactivite": agent.date_inactivite.isoformat() if agent.date_inactivite else None,
        "commentaire_inactivite": agent.commentaire_inactivite,
    }


def collect_original_values(agent, fields):
    return {field: getattr(agent, field) for field in fields}


def record_agent_movements(agent_id, original_values, new_values, auteur):
    for field, ancienne_valeur in original_values.items():
        nouvelle_valeur = new_values.get(field)
        if serialize_for_compare(ancienne_valeur) == serialize_for_compare(nouvelle_valeur):
            continue

        type_mouvement = "modification"
        if field == "statut" and ancienne_valeur == "Inactif" and nouvelle_valeur == "Actif":
            type_mouvement = "reactivation"
        elif field == "statut" and ancienne_valeur == "Actif" and nouvelle_valeur == "Inactif":
            type_mouvement = "inactivation"

        enregistrer_mouvement(
            agents_id=agent_id,
            champ=field,
            ancienne_valeur=serialize_for_compare(ancienne_valeur),
            nouvelle_valeur=serialize_for_compare(nouvelle_valeur),
            auteur=auteur,
            type_mouvement=type_mouvement,
        )


def normalize_import_columns(df):
    df.columns = df.columns.str.strip().str.lower()

    for old_name, new_name in IMPORT_RENAME_MAP.items():
        matching_columns = [col for col in df.columns if old_name in col]
        for column in matching_columns:
            df.rename(columns={column: new_name}, inplace=True)

    if "agent" not in df.columns:
        for column in df.columns:
            if any(token in column for token in ["nom", "prenom", "full", "employe"]):
                df.rename(columns={column: "agent"}, inplace=True)
                break

    return df


def get_existing_agents_by_matricule(matricules):
    if not matricules:
        return {}

    existing_agents = Agent.query.filter(Agent.matricule.in_(matricules)).all()
    return {agent.matricule: agent for agent in existing_agents}


def create_user_account(username, password, role="gestionnaire"):
    username = normalize_value(username)
    role = normalize_value(role) or "gestionnaire"

    if not username:
        raise ValueError("Le nom d'utilisateur est obligatoire.")
    if not password or len(password) < 6:
        raise ValueError("Le mot de passe doit faire au moins 6 caractères.")
    if role not in USER_ROLES:
        raise ValueError("Le rôle sélectionné est invalide.")
    if User.query.filter_by(username=username).first():
        raise ValueError("Ce nom d'utilisateur existe déjà.")

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    return user

# === ROUTES PRINCIPALES ===
@app.route('/')
@app.route("/dashboard")
@login_required
def dashboard():
    today = date.today()

    total_actifs = Agent.query.filter_by(statut="Actif").count()
    total_inactifs = Agent.query.filter_by(statut="Inactif").count()

    nouveaux_agents = Agent.query.filter(
        extract("month", Agent.date_premiere_prise_service) == today.month,
        extract("year", Agent.date_premiere_prise_service) == today.year
    ).count()

    dates_naissance = db.session.query(Agent.date_naissance).filter(
        Agent.date_naissance.isnot(None)
    ).all()

    proches_retraite = sum(
        1
        for (date_naissance,) in dates_naissance
        if (age := calculate_age(date_naissance, today)) is not None and 55 <= age < 60
    )

    derniers_agents = Agent.query.filter(
        extract("month", Agent.date_premiere_prise_service) == today.month,
        extract("year", Agent.date_premiere_prise_service) == today.year
    ).order_by(
        Agent.date_premiere_prise_service.desc()
    ).limit(5).all()

    total_agents = Agent.query.count()
    total_sanctions = Sanction.query.count()

    return render_template(
        "dashboard.html",
        page="dashboard",
        total_actifs=total_actifs,
        total_inactifs=total_inactifs,
        total_agents=total_agents,
        total_sanctions=total_sanctions,
        nouveaux_agents=nouveaux_agents,
        proches_retraite=proches_retraite,
        derniers_agents=derniers_agents
    )
@app.route("/recherche")
@login_required
def recherche():
    q = request.args.get("q", "").strip()

    agents = []
    if q:
        agents = Agent.query.filter(
            (Agent.agent.ilike(f"%{q}%")) |
            (Agent.matricule.ilike(f"%{q}%")) |
            (Agent.genre.ilike(f"%{q}%")) |
            (Agent.poste_comptable.ilike(f"%{q}%")) |
            (Agent.poste_type.ilike(f"%{q}%")) 
            
        ).all()

    return render_template(
        "recherche.html",
        agents=agents,
        q=q,
        page="recherche"
    )


@app.route("/profil")
@login_required
def profil():
    return render_template("profil.html", page="profil")


@app.route('/personnels_actifs')
@login_required
def personnels_actifs():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    pagination = Agent.query.filter_by(statut="Actif").order_by(Agent.agent).paginate(page=page, per_page=per_page, error_out=False)
    agents = pagination.items
    total_actifs = pagination.total
    
    return render_template('personnels_actifs.html', agents=agents, pagination=pagination, total_actifs=total_actifs, page='actifs')



@app.route("/fiche/<int:id>")
@login_required
def fiche_agent(id):
    agent = (
        Agent.query.options(
            selectinload(Agent.mouvements),
            selectinload(Agent.sanctions),
        )
        .filter_by(id=id)
        .first_or_404()
    )
    historique = agent.historique_complet

    return render_template(
        "fiche.html",
        agent=agent,
        historique=historique
    )


@app.route('/api/agents_inactifs')
@login_required
def api_agents_inactifs():
    agents = Agent.query.filter_by(statut="Inactif").all()
    return jsonify([serialize_agent(agent) for agent in agents])


@app.route('/importer_agents', methods=['POST'])
@login_required
def importer_agents():
    fichier = request.files.get('fichier')
    if not fichier or fichier.filename == '':
        flash("Aucun fichier sélectionné.", "danger")
        return redirect(url_for('personnels_actifs'))

    filename = secure_filename(fichier.filename)
    chemin_fichier = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        fichier.save(chemin_fichier)
        df = pd.read_excel(chemin_fichier)
    except Exception as exc:
        logger.exception("Erreur lors de la lecture du fichier d'import")
        flash(f"Erreur import : {exc}", "danger")
        return redirect(url_for('personnels_actifs'))

    df = normalize_import_columns(df)
    df = df.where(pd.notnull(df), None)
    df.dropna(how='all', inplace=True)

    if 'matricule' not in df.columns:
        flash("Colonne 'matricule' introuvable.", "danger")
        return redirect(url_for('personnels_actifs'))

    for col in AGENT_FIELDS:
        if col not in df.columns:
            df[col] = None

    records = []
    erreurs = 0
    for row in df[AGENT_FIELDS].to_dict(orient='records'):
        payload = build_agent_payload(
            row,
            AGENT_FIELDS,
            defaults={"genre": "Homme", "statut": "Actif"},
        )
        if not payload["matricule"]:
            erreurs += 1
            continue
        if not payload["agent"]:
            payload["agent"] = "Agent inconnu"
        records.append(payload)

    existing_agents = get_existing_agents_by_matricule(
        {record["matricule"] for record in records}
    )

    total_ajoutes = 0
    total_updates = 0

    try:
        for index, payload in enumerate(records, start=1):
            agent = existing_agents.get(payload["matricule"])
            if agent is None:
                agent = Agent(**payload)
                db.session.add(agent)
                existing_agents[payload["matricule"]] = agent
                total_ajoutes += 1
            else:
                apply_agent_payload(agent, payload, keep_existing=True)
                total_updates += 1

            if index % 200 == 0:
                db.session.flush()

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erreur base de donnees pendant l'import des agents")
        flash(f"Erreur base de donnees : {exc}", "danger")
        return redirect(url_for('personnels_actifs'))

    logger.info(
        "Import agents termine: %s ajoutes, %s mis a jour, %s erreurs",
        total_ajoutes,
        total_updates,
        erreurs,
    )
    flash(
        f"Import termine : {total_ajoutes} ajoutes -- {total_updates} mis a jour -- {erreurs} erreurs",
        "success",
    )
    return redirect(url_for('personnels_actifs'))
    
@app.route('/personnels_inactifs')
@login_required
def personnels_inactifs():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    pagination = Agent.query.filter_by(statut="Inactif").order_by(Agent.agent).paginate(page=page, per_page=per_page, error_out=False)
    agents = pagination.items
    total_inactifs = pagination.total
    
    return render_template('personnels_inactifs.html', agents=agents, pagination=pagination, total_inactifs=total_inactifs, page='inactifs')


@app.route('/statistiques')
@login_required
def statistiques():
    today = date.today()

    statut_data = db.session.query(
        Agent.statut, func.count(Agent.id)
    ).group_by(Agent.statut).all()

    labels_statut = [s for s, _ in statut_data]
    data_statut = [c for _, c in statut_data]

    agents_actifs_query = Agent.query.filter_by(statut='Actif')

    poste_comptable_data = db.session.query(
        Agent.poste_comptable, func.count(Agent.id)
    ).filter(
        Agent.statut == 'Actif',
        Agent.poste_comptable.isnot(None)
    ).group_by(Agent.poste_comptable).all()

    labels_poste_comptable = [g for g, _ in poste_comptable_data]
    data_poste_comptable = [c for _, c in poste_comptable_data]

    corps_data = db.session.query(
        Agent.corps, func.count(Agent.id)
    ).filter(
        Agent.statut == 'Actif',
        Agent.corps.isnot(None)
    ).group_by(Agent.corps).all()

    labels_corps = [c for c, _ in corps_data]
    data_corps = [nb for _, nb in corps_data]

    tranches = {"-30": 0, "30-39": 0, "40-49": 0, "50-59": 0, "60+": 0}
    agents = agents_actifs_query.filter(Agent.date_naissance.isnot(None)).all()

    for agent in agents:
        age = calculate_age(agent.date_naissance, today)
        if age is None:
            continue

        if age < 30:
            tranches["-30"] += 1
        elif age < 40:
            tranches["30-39"] += 1
        elif age < 50:
            tranches["40-49"] += 1
        elif age < 60:
            tranches["50-59"] += 1
        else:
            tranches["60+"] += 1

    labels_age = list(tranches.keys())
    data_age = list(tranches.values())

    AGE_RETRAITE = 60
    PROCHE_RETRAITE = 5

    agents_proches_retraite = []

    for agent in agents:
        age = calculate_age(agent.date_naissance, today)
        if age is None:
            continue

        annees_restantes = AGE_RETRAITE - age
        if 0 <= annees_restantes <= PROCHE_RETRAITE:
            agents_proches_retraite.append({
                'agent': getattr(agent, 'agent', ''),
                'matricule': getattr(agent, 'matricule', ''),
                'date_naissance': agent.date_naissance,
                'age': age,
                'annees_restantes': annees_restantes
            })

    total_agents = Agent.query.count()
    agents_actifs = Agent.query.filter_by(statut='Actif').count()
    agents_inactifs = Agent.query.filter_by(statut='Inactif').count()

    return render_template(
        'statistiques.html',
        page='stats',
        labels_statut=labels_statut,
        data_statut=data_statut,
        labels_poste_comptable=labels_poste_comptable,
        data_poste_comptable=data_poste_comptable,
        labels_corps=labels_corps,
        data_corps=data_corps,
        labels_age=labels_age,
        data_age=data_age,
        agents_proches_retraite=agents_proches_retraite,
        total_agents=total_agents,
        agents_actifs=agents_actifs,
        agents_inactifs=agents_inactifs
    )

@app.route("/sanctions")
def sanctions():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    pagination = Sanction.query.order_by(Sanction.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    sanctions_list = pagination.items
    agents = Agent.query.order_by(Agent.agent).all()

    return render_template(
        "sanctions.html",
        sanctions=sanctions_list,
        pagination=pagination,
        agents=agents
    )
@app.route("/sanctions/ajouter", methods=["GET", "POST"])
def ajouter_sanction():
    if request.method == "POST":
        nouvelle = Sanction(
            agent_id=request.form["agent_id"],
            type_sanction=request.form["type_sanction"],
            motif=request.form["motif"],
            date_traitement=parse_optional_date(request.form["date_traitement"]),
            date_levee=parse_optional_date(request.form.get("date_levee")),
            decision_par=request.form["decision_par"],
            levee_par=request.form["levee_par"],
            observation=request.form["observation"]
        )

        db.session.add(nouvelle)
        db.session.commit()

        return redirect(url_for("sanctions"))

    agents = Agent.query.all()
    return render_template("sanctions.html", agents=agents)

@app.route("/sanction/update_statut/<int:id>", methods=["POST"])
def update_statut(id):
    data = request.get_json() or {}
    sanction = db.session.get(Sanction, id)
    if sanction is None:
        return {"success": False, "message": "Sanction introuvable"}, 404

    statut = data.get("statut")

    sanction.statut = statut

    if statut == "Levé":
        sanction.date_levee = parse_optional_date(data.get("date_levee"))
        sanction.levee_par = data.get("levee_par")
    else:
        sanction.date_levee = None
        sanction.levee_par = None

    db.session.commit()
    return {"success": True}

@app.route('/repartition')
@login_required
def repartition():

    corps = request.args.get('corps')
    statut = request.args.get('statut')
    poste_type = request.args.get('poste_type')
    poste_comptable = request.args.get('poste_comptable')
    page = request.args.get('page', 1, type=int)
    per_page = 30

    query = Agent.query

    if corps: 
        query = query.filter(Agent.corps == corps)

    if statut:
        query = query.filter(Agent.statut == statut)

    if poste_type:
        query = query.filter(Agent.poste_type == poste_type)

    if poste_comptable:
        query = query.filter(Agent.poste_comptable == poste_comptable)

    pagination = query.order_by(Agent.agent).paginate(page=page, per_page=per_page, error_out=False)
    agents = pagination.items
    
    # Listes DISTINCT pour filtres
    corps_list = [c[0] for c in db.session.query(Agent.corps).distinct().all() if c[0]]
    statut_list = [s[0] for s in db.session.query(Agent.statut).distinct().all() if s[0]]
    poste_type_list = [p[0] for p in db.session.query(Agent.poste_type).distinct().all() if p[0]]
    poste_comptable_list = [pc[0] for pc in db.session.query(Agent.poste_comptable).distinct().all() if pc[0]]

    total = pagination.total

    return render_template(
        'repartition.html',
        agents=agents,
        pagination=pagination,
        total=total,
        corps_list=corps_list,
        statut_list=statut_list,
        poste_type_list=poste_type_list,
        poste_comptable_list=poste_comptable_list,
        selected_corps=corps,
        selected_statut=statut,
        selected_poste_type=poste_type,
        selected_pc=poste_comptable
    )

@app.route("/mouvements")
def mouvements():
    page = request.args.get('page', 1, type=int)
    per_page = 30

    query = (
        db.session.query(
            Mouvement.id,
            Agent.matricule.label("matricule"),
            Agent.agent.label("agent"),
            Mouvement.date_mouvement,
            Mouvement.type_mouvement,
            Mouvement.champ_modifie,
            Mouvement.ancienne_valeur,
            Mouvement.nouvelle_valeur,
            Mouvement.auteur
        )
        .join(Agent, Mouvement.agents_id == Agent.id)
        .order_by(Mouvement.date_mouvement.desc())
    )
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    mouvements = pagination.items

    return render_template(
        "mouvements.html",
        mouvements=mouvements,
        pagination=pagination,
        page="mouvements"
    )

    



@app.route('/ajouter_agent', methods=['GET', 'POST'])
@login_required
def ajouter_agent():
    if request.method == 'POST':
        payload = build_agent_payload(
            request.form,
            AGENT_FIELDS,
            defaults={"statut": "Actif"},
        )

        if not payload["agent"] or not payload["matricule"]:
            flash("Le nom et le matricule sont obligatoires.", "danger")
            return redirect(url_for('ajouter_agent'))

        if Agent.query.filter_by(matricule=payload["matricule"]).first():
            flash("Un agent avec ce matricule existe déjà.", "danger")
            return redirect(url_for('ajouter_agent'))

        try:
            nouvel_agent = Agent(**payload)
            db.session.add(nouvel_agent)
            db.session.flush()

            enregistrer_mouvement(
                agents_id=nouvel_agent.id,
                champ="agent",
                ancienne_valeur=None,
                nouvelle_valeur=nouvel_agent.agent,
                auteur=session.get("username", "system"),
                type_mouvement="creation"
            )

            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.exception("Erreur lors de l'ajout d'un agent")
            flash(f"Erreur lors de l'ajout : {exc}", "danger")
            return redirect(url_for('ajouter_agent'))

        flash("Agent ajouté avec succès !", "success")
        return redirect(url_for('personnels_actifs'))

    return render_template('ajouter_agent.html', page='ajouter')



@app.route('/modifier_agent/<int:id>', methods=['POST'])
@login_required
def modifier_agent(id):
    agent = Agent.query.get_or_404(id)
    data = request.get_json() or {}
    anciennes_valeurs = collect_original_values(agent, AGENT_FIELDS)
    payload = build_merged_agent_payload(agent, data, AGENT_FIELDS)

    apply_agent_payload(agent, payload)
    record_agent_movements(
        agent.id,
        anciennes_valeurs,
        payload,
        session.get("username", "system"),
    )
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Agent actif modifié avec succès"
    })


@app.route('/api/agent/<int:id>')
@login_required
def api_get_agent(id):
    agent = db.session.get(Agent, id)
    if not agent:
        return {"error": "Agent introuvable"}, 404

    return serialize_agent(agent)

@app.route('/api/agent/inactiver/<int:id>', methods=['POST'])
@login_required
def api_inactiver(id):
    agent = Agent.query.get_or_404(id)
    data = request.get_json() or {}
    ancien_statut = agent.statut

    payload = build_agent_payload(
        {
            "statut": "Inactif",
            "motif_inactivite": data.get("motif_inactivite"),
            "date_inactivite": data.get("date_inactivite"),
            "commentaire_inactivite": data.get("commentaire_inactivite"),
        },
        ["statut", *AGENT_INACTIVITY_FIELDS],
    )
    apply_agent_payload(agent, payload)

    if ancien_statut != agent.statut:
        nouvelle_valeur = "Inactif"
        if payload["motif_inactivite"]:
            nouvelle_valeur += f" - {payload['motif_inactivite']}"
        details = normalize_value(data.get("details_motif"))
        if details:
            nouvelle_valeur += f" ({details})"

        enregistrer_mouvement(
            agents_id=agent.id,
            type_mouvement="inactivation",
            champ="statut",
            ancienne_valeur=ancien_statut,
            nouvelle_valeur=nouvelle_valeur,
            auteur=session.get("username", "system"),
        )

    db.session.commit()

    return jsonify({"success": True})




@app.route('/api/agent/update/<int:id>', methods=['POST'])
@login_required
def api_update_agent(id):
    agent = Agent.query.get_or_404(id)
    data = request.get_json() or {}
    fields = AGENT_FIELDS + AGENT_INACTIVITY_FIELDS
    anciennes_valeurs = collect_original_values(agent, fields)
    payload = build_merged_agent_payload(agent, data, fields)

    if anciennes_valeurs["statut"] == "Inactif" and payload["statut"] == "Actif":
        payload["motif_inactivite"] = None
        payload["date_inactivite"] = None
        payload["commentaire_inactivite"] = None

    apply_agent_payload(agent, payload)
    record_agent_movements(
        agent.id,
        anciennes_valeurs,
        payload,
        session.get("username", "system"),
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "agent": serialize_agent(agent)
    })


@app.route('/supprimer_agent/<int:id>')
@login_required
def supprimer_agent(id):
    agent = Agent.query.get_or_404(id)
    db.session.delete(agent)
    db.session.commit()
    flash("Agent supprimé avec succès !", "info")
    return redirect(url_for('personnels_actifs'))




@app.route('/changer_statut/<int:id>', methods=['POST'])
@login_required
def changer_statut(id):
    agent = Agent.query.get_or_404(id)

    ancien_statut = agent.statut

    agent.statut = "Inactif" if agent.statut == "Actif" else "Actif"
    nouveau_statut = agent.statut

    if nouveau_statut == "Actif":
        agent.motif_inactivite = None
        agent.date_inactivite = None
        agent.commentaire_inactivite = None

    if ancien_statut != nouveau_statut:
        enregistrer_mouvement(
            agents_id=agent.id,
            type_mouvement="reactivation" if nouveau_statut == "Actif" else "inactivation",
            champ="statut",
            ancienne_valeur=ancien_statut,
            nouvelle_valeur=nouveau_statut,
            auteur=session.get("username", current_user.username),
        )

    db.session.commit()

    flash(f"Statut de {agent.agent} changé en {agent.statut}", "warning")
    return redirect(url_for('personnels_inactifs'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            session["username"] = user.username
            flash("Connexion réussie", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Identifiants incorrects", "danger")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop("username", None)
    logout_user()
    return redirect(url_for('login'))

@app.route('/changer_mdp', methods=['GET', 'POST'])
@login_required
def changer_mdp():
    if request.method == 'POST':
        ancien = request.form['ancien_mdp']
        nouveau = request.form['nouveau_mdp']
        confirmation = request.form['confirmation']

        if not current_user.check_password(ancien):
            flash("Ancien mot de passe incorrect", "danger")
        elif len(nouveau) < 6:
            flash("Le nouveau mot de passe doit faire au moins 6 caractères", "danger")
        elif nouveau != confirmation:
            flash("Les nouveaux mots de passe ne correspondent pas", "danger")
        else:
            current_user.set_password(nouveau)
            db.session.commit()
            flash("Mot de passe changé avec succès", "success")
            return redirect(url_for('dashboard'))

    return render_template('changer_mdp.html')

@app.route('/utilisateurs', methods=['GET', 'POST'])
@admin_required
def utilisateurs():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        role = request.form.get('role', 'gestionnaire')

        try:
            create_user_account(username, password, role)
            db.session.commit()
            flash(f"Utilisateur '{normalize_value(username)}' créé avec succès.", "success")
            return redirect(url_for('utilisateurs'))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except Exception as exc:
            db.session.rollback()
            logger.exception("Erreur lors de la création d'un utilisateur")
            flash(f"Erreur lors de la création : {exc}", "danger")

    users = User.query.order_by(User.role.asc(), User.username.asc()).all()
    return render_template(
        'utilisateurs.html',
        users=users,
        roles=USER_ROLES,
        page='utilisateurs',
    )

@app.route('/init_admin')
def init_admin():
    admin_user = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    existing_admin = User.query.filter_by(role='admin').first()

    if existing_admin:
        return (
            f"Le compte admin existe déjà : {existing_admin.username}. "
            "Connectez-vous puis allez sur /utilisateurs pour créer les autres comptes."
        )

    if admin_user and admin_user.role != 'admin':
        return (
            f"L'utilisateur '{DEFAULT_ADMIN_USERNAME}' existe déjà avec le rôle "
            f"'{admin_user.role}'. Modifiez-le manuellement en admin avant de continuer."
        )

    try:
        create_user_account(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, 'admin')
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return str(exc)
    except Exception as exc:
        db.session.rollback()
        logger.exception("Erreur lors de l'initialisation du compte admin")
        return f"Erreur lors de l'initialisation du compte admin : {exc}"

    return (
        f"Compte admin créé : {DEFAULT_ADMIN_USERNAME}/{DEFAULT_ADMIN_PASSWORD}. "
        "Connectez-vous puis allez sur /utilisateurs pour créer les autres comptes."
    )

@app.route('/init_users')
@admin_required
def init_users():
    users = [
        ("gestionnaire", "sirh2024", "Gestionnaire RH", "gestionnaire"),
        ("lecteur", "sirh2024", "Lecteur", "lecteur"),
    ]

    created_users = []
    for username, password, _nom, role in users:
        if User.query.filter_by(username=username).first():
            continue
        create_user_account(username, password, role)
        created_users.append(username)

    if not created_users:
        return "Les comptes par défaut existent déjà."

    db.session.commit()
    return (
        "Utilisateurs créés : " +
        ", ".join(created_users) +
        "."
    )


# === CRÉATION DES TABLES SI NON EXISTANTES ===
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
