from flask import Flask, render_template, request, redirect, url_for, flash
from models import db
import mysql.connector
from models.agents import Agent
from models.users import User
from models.mouvements import Mouvement
from flask import session
from models.mouvements import enregistrer_mouvement
from models.sanctions import Sanction
import pandas as pd
print(enregistrer_mouvement)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import date
from sqlalchemy import extract

from datetime import date, datetime
from sqlalchemy import extract
from models.documents import Document

import os
import math
from datetime import date
from flask import request, jsonify
from datetime import date
from collections import defaultdict
from sqlalchemy import extract
from sqlalchemy import or_
from flask import request
from werkzeug.security import generate_password_hash, check_password_hash

import os
print("DB UTILISÉE PAR FLASK:", os.path.abspath("database.db"))

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



app = Flask(__name__)
app.secret_key = "dev"  # nécessaire pour les messages flash
app.secret_key = "sirh_secret_key"  # à sécuriser plus tard

# === CONFIG BASE DE DONNÉES ===
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root@localhost/sirh'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# === FLASK-LOGIN ===
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="sirh"
    )

# === ROUTES PRINCIPALES ===
@login_required
@app.route('/')



@app.route("/dashboard")
@login_required
def dashboard():

    today = date.today()

    # --- KPI ---
    total_actifs = Agent.query.filter_by(statut="Actif").count()
    total_inactifs = Agent.query.filter_by(statut="Inactif").count()

    # Nouveaux agents du mois
    nouveaux_agents = Agent.query.filter(
        extract("month", Agent.date_premiere_prise_service) == today.month,
        extract("year", Agent.date_premiere_prise_service) == today.year
    ).count()

    # Proches de la retraite (55 à 59 ans)
    agents_avec_date = Agent.query.filter(
        Agent.date_naissance.isnot(None)
    ).all()

    proches_retraite = 0

    for a in agents_avec_date:

        # ⚡ Conversion si nécessaire
        if isinstance(a.date_naissance, str):
            try:
                date_naissance = datetime.strptime(a.date_naissance, "%Y-%m-%d").date()
            except ValueError:
                # Si la date est mal formatée, on ignore cet agent
                continue
        else:
            date_naissance = a.date_naissance

        # Calcul de l'âge
        age = today.year - date_naissance.year - (
            (today.month, today.day) < (date_naissance.month, date_naissance.day)
        )

        if 55 <= age < 60:
            proches_retraite += 1

    # Derniers agents ajoutés ce mois (max 5)
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


@login_required
@app.route('/personnels_actifs')
@login_required
def personnels_actifs():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    pagination = Agent.query.filter_by(statut="Actif").order_by(Agent.agent).paginate(page=page, per_page=per_page, error_out=False)
    agents = pagination.items
    total_actifs = pagination.total
    
    return render_template('personnels_actifs.html', agents=agents, pagination=pagination, total_actifs=total_actifs, page='actifs')



from datetime import datetime, date

def construire_historique(agent):
    print("Agent ID :", agent.id)
    print("Mouvements :", agent.mouvements)
    print("Sanctions :", agent.sanctions)

    historique = []

    # 🔹 Mouvements
    if hasattr(agent, "mouvements"):
        for m in agent.mouvements:

            d = m.date_mouvement
            if isinstance(d, date) and not isinstance(d, datetime):
                d = datetime.combine(d, datetime.min.time())

            historique.append({
                "date": d,
                "type": "Mouvement",
                "type_mouvement": m.type_mouvement,
                "champ": m.champ_modifie,
                "ancienne_valeur": m.ancienne_valeur,
                "nouvelle_valeur": m.nouvelle_valeur,
                
                "auteur": m.auteur
            })

    # 🔹 Sanctions
    if hasattr(agent, "sanctions"):
        for s in agent.sanctions:

            d = s.date_traitement
            if isinstance(d, date) and not isinstance(d, datetime):
                d = datetime.combine(d, datetime.min.time())

            historique.append({
                "date": d,
                "type": "Sanction",
                "motif": s.motif,
                "statut": s.statut,
                "date_levee": s.date_levee,
                
                "auteur": getattr(s, "auteur", None)
            })

    # 🔹 Trier du plus récent au plus ancien
    historique = sorted(
        historique,
        key=lambda x: x["date"] if x["date"] else datetime.min,
        reverse=True
    )
    

    return historique

@app.route("/fiche/<int:id>")
@login_required
def fiche_agent(id):

    agent = Agent.query.get_or_404(id)

    # historique
    historique = agent.historique_complet

    return render_template(
        "fiche.html",
        agent=agent,
        historique=historique
    )


def calcul_age(date_naissance):
    if not date_naissance:
        return None
    today = datetime.today()
    return today.year - date_naissance.year - (
        (today.month, today.day) < (date_naissance.month, date_naissance.day)
    )

def calcul_anciennete(date_service):
    if not date_service:
        return None
    today = datetime.today()
    return today.year - date_service.year

@login_required
@app.route('/api/agents_inactifs')
def api_agents_inactifs():
    agents = Agent.query.filter_by(statut="Inactif").all()
    data = []
    for a in agents:
        data.append({
            "id": a.id,
            "matricule": a.matricule,
            "agent": a.agent,
            "telephone": a.telephone,
            "genre": a.genre,
            "date_naissance": a.date_naissance.isoformat() if a.date_naissance else None,
            "statut": a.statut,
            "corps": a.corps,
            "poste_type": a.poste_type,
            "poste_comptable": a.poste_comptable,
            "date_premiere_prise_service": a.date_premiere_prise_service.isoformat() if a.date_premiere_prise_service else None,
            "promotion_corps": a.promotion_corps,
            
            "epoux_epouse_nom_poste": a.epoux_epouse_nom_poste,
            "historique_formations": a.historique_formations,
            "motif_inactivite": a.motif_inactivite,
            "date_inactivite": a.date_inactivite.isoformat() if a.date_inactivite else None,
            "commentaire_inactivite": a.commentaire_inactivite
        })
    return jsonify(data)

from flask import Flask, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os





# -----------------------------
# CONFIGURATION UPLOAD
# -----------------------------
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
print("[INFO] Dossier upload configuré :", UPLOAD_FOLDER)

 
# -----------------------------
# ROUTE IMPORT AGENTS
# -----------------------------
@login_required
@app.route('/importer_agents', methods=['POST'])
def importer_agents():
    print("\n========== DEBUT IMPORT ==========")

    print("\n========== DÉBUT IMPORT ==========")

    # 1️⃣ Récupération fichier
    # -----------------------------
    fichier = request.files.get('fichier')
    if not fichier or fichier.filename == '':
        print("[ERREUR] Aucun fichier sélectionné")
        flash("Aucun fichier sélectionné.", "danger")
        flash("Aucun fichier selectionne.", "danger")
        return redirect(url_for('personnels_actifs'))

    filename = secure_filename(fichier.filename)
    chemin_fichier = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    try:
        fichier.save(chemin_fichier)
        print(f"[INFO] Fichier sauvegardé : {chemin_fichier}")
        print(f"[OK] Fichier sauvegarde : {chemin_fichier}")
    except Exception as e:
        print("[ERREUR] Sauvegarde fichier :", e)
        print(f"[ERREUR] Sauvegarde : {e}")
        flash(f"Erreur sauvegarde : {e}", "danger")
        return redirect(url_for('personnels_actifs'))

    # -----------------------------
    # 2️⃣ Lecture Excel
    # -----------------------------
    try:
        df = pd.read_excel(chemin_fichier)
        
    
        df.columns = df.columns.str.strip().str.lower()
        print("[DEBUG] Colonnes détectées :", df.columns.tolist())
        print("[DEBUG] Colonnes originales :", df.columns.tolist())
        print("[DEBUG] Nombre de lignes AVANT nettoyage :", len(df))
        print(f"[DEBUG] Lignes brutes : {len(df)}")
    except Exception as e:
        print("[ERREUR] Lecture Excel :", e)
        print(f"[ERREUR] Lecture Excel : {e}")
        flash(f"Erreur lecture Excel : {e}", "danger")
        return redirect(url_for('personnels_actifs'))

    df.columns = df.columns.str.strip().str.lower()

    rename_map = {
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
        "im": "matricule"
    }

    for old_name, new_name in rename_map.items():
        for col in df.columns:
            if old_name.lower() in col.lower():
                df.rename(columns={col: new_name}, inplace=True)

    if 'agent' not in df.columns:
        for col in df.columns:
            if any(p in col.lower() for p in ['nom', 'prenom', 'full', 'employe']):
                df.rename(columns={col: 'agent'}, inplace=True)
                break

    print(f"[DEBUG] Colonnes finales : {df.columns.tolist()}")
    if len(df) > 0:
        print(f"[DEBUG] Premiere ligne : {df.iloc[0].to_dict()}")

    df = df.where(pd.notnull(df), None)

    if 'genre' in df.columns:
        df['genre'] = df['genre'].apply(
            lambda x: 'Homme' if str(x).upper() in ['M', 'MALE', 'H', 'MASCULIN']
            else ('Femme' if str(x).upper() in ['F', 'FEMALE', 'FEMININ'] else ('Homme' if x is None or x == '' else x))
        )
    else:
        df['genre'] = 'Homme'

    for date_col in ['date_naissance', 'date_premiere_prise_service']:
        if date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce').dt.date

    df.dropna(how='all', inplace=True)

    if 'matricule' not in df.columns:
        flash("Colonne 'matricule' introuvable.", "danger")
        return redirect(url_for('personnels_actifs'))

    df = df[df['matricule'].notna()]
    df = df[df['matricule'].astype(str).str.strip() != '']

    print(f"[DEBUG] Lignes apres nettoyage : {len(df)}")

    colonnes_attendues = [
        'agent', 'matricule', 'genre', 'date_naissance', 'telephone',
        'statut', 'poste_type', 'poste_comptable', 'corps',
        'promotion_corps', 'date_premiere_prise_service',
        'historique_formations', 'epoux_epouse_nom_poste'
    ]
    for col in colonnes_attendues:
        if col not in df.columns:
            df[col] = None

    total_ajoutes = 0
    total_updates = 0
    erreurs = 0

    for i, (index, row) in enumerate(df.iterrows()):
        matricule_val = row.get("matricule")
        if matricule_val is None:
            continue

        matricule = str(matricule_val).replace(".0", "").strip()
        if not matricule or matricule == 'None':
            erreurs += 1
            continue

        try:
            agent_exist = Agent.query.filter_by(matricule=matricule).first()

            if agent_exist:
                agent_exist.agent = row.get("agent") or agent_exist.agent
                agent_exist.genre = row.get("genre") or agent_exist.genre
                agent_exist.date_naissance = row.get("date_naissance") or agent_exist.date_naissance
                agent_exist.telephone = row.get("telephone") or agent_exist.telephone
                agent_exist.statut = row.get("statut") or "Actif"
                agent_exist.poste_type = row.get("poste_type") or agent_exist.poste_type
                agent_exist.poste_comptable = row.get("poste_comptable") or agent_exist.poste_comptable
                agent_exist.corps = row.get("corps") or agent_exist.corps
                agent_exist.promotion_corps = row.get("promotion_corps") or agent_exist.promotion_corps
                agent_exist.date_premiere_prise_service = row.get("date_premiere_prise_service") or agent_exist.date_premiere_prise_service
                agent_exist.historique_formations = row.get("historique_formations") or agent_exist.historique_formations
                agent_exist.epoux_epouse_nom_poste = row.get("epoux_epouse_nom_poste") or agent_exist.epoux_epouse_nom_poste
                total_updates += 1
            else:
                nom_agent = row.get("agent") or row.get("agents") or "Agent inconnu"
                genre_agent = row.get("genre") or "Homme"

                nouvel_agent = Agent(
                    agent=nom_agent,
                    matricule=matricule,
                    genre=genre_agent,
                    date_naissance=row.get("date_naissance"),
                    telephone=row.get("telephone"),
                    statut=row.get("statut") or "Actif",
                    poste_type=row.get("poste_type"),
                    poste_comptable=row.get("poste_comptable"),
                    corps=row.get("corps"),
                    promotion_corps=row.get("promotion_corps"),
                    date_premiere_prise_service=row.get("date_premiere_prise_service"),
                    historique_formations=row.get("historique_formations"),
                    epoux_epouse_nom_poste=row.get("epoux_epouse_nom_poste"),
                )
                db.session.add(nouvel_agent)
                total_ajoutes += 1

            if (i + 1) % 100 == 0:
                db.session.commit()
                print(f"[PROGRESS] {i + 1}/{len(df)} agents traites...")

        except Exception as e:
            db.session.rollback()
            erreurs += 1
            print(f"[ERREUR] Matricule {matricule} : {e}")

    try:
        db.session.commit()
        print("[OK] Commit final reussi")
    except Exception as e:
        db.session.rollback()
        print(f"[ERREUR COMMIT] : {e}")
        flash(f"Erreur base de donnees : {e}", "danger")
        return redirect(url_for('personnels_actifs'))

    print(f"Resultat : {total_ajoutes} ajoutes, {total_updates} mis a jour, {erreurs} erreurs")
    print("========== FIN IMPORT ==========\n")

    flash(f"Import termine : {total_ajoutes} ajoutes -- {total_updates} mis a jour -- {erreurs} erreurs", "success")
    return redirect(url_for('personnels_actifs'))

    df = df[df['matricule'].notna()]  # supprimer lignes sans matricule
    df = df[df['matricule'].notna()]
    df = df[df['matricule'].astype(str).str.strip() != '']

    # -----------------------------
    # 4️⃣ Colonnes attendues
    # -----------------------------
    # Ajouter colonnes manquantes
    print(f"[DEBUG] Lignes apres nettoyage : {len(df)}")

    colonnes_attendues = [
        'agent', 'matricule', 'genre',
        'date_naissance', 'telephone', 'statut',
        'poste_type', 'poste_comptable', 'corps',
        'agent', 'matricule', 'genre', 'date_naissance', 'telephone',
        'statut', 'poste_type', 'poste_comptable', 'corps',
        'promotion_corps', 'date_premiere_prise_service',
        'historique_formations',
        'epoux_epouse_nom_poste',

        'historique_formations', 'epoux_epouse_nom_poste'
    ]
    for col in colonnes_attendues:
        if col not in df.columns:
            print(f"[WARNING] Colonne manquante ajoutée : {col}")
            df[col] = None

    if 'matricule' not in df.columns:
        print("[ERREUR] Colonne 'matricule' introuvable")

        print("[DEBUG] Colonnes après renommage :", df.columns.tolist())
    # -----------------------------
    # 5️⃣ Nettoyage dates
    # 4️⃣ INSERT / UPDATE avec commit par lots
    # -----------------------------
    def safe_date(value):
        try:
            if pd.isna(value):
                return None
            return pd.to_datetime(value).date()
        except:
            return None

    df["date_naissance"] = df["date_naissance"].apply(safe_date)
    df["date_premiere_prise_service"] = df["date_premiere_prise_service"].apply(safe_date)

    # -----------------------------
    # 6️⃣ INSERT / UPDATE
    # -----------------------------
    total_ajoutes = 0
    total_updates = 0
    erreurs = 0
    lot_size = 100

    for index, row in df.iterrows():
        print(f"\n[DEBUG] Ligne {index + 1}")
    for i, (index, row) in enumerate(df.iterrows()):
        matricule_val = row.get("matricule")
        if matricule_val is None:
            continue
        
        matricule = str(matricule_val).replace(".0", "").strip()

        if not matricule:
            print("[ERREUR] Matricule invalide")
        matricule = str(matricule_val).replace(".0", "").strip()
        if not matricule or matricule == 'None':
            erreurs += 1
            continue

        try:
            agent_exist = Agent.query.filter_by(matricule=matricule).first()

            if agent_exist:
                # UPDATE
                print(f"[UPDATE] Agent existant : {matricule}")
                agent_exist.agent = row.get("agent")
                agent_exist.genre = row.get("genre")
                agent_exist.date_naissance = row.get("date_naissance")
                agent_exist.telephone = row.get("telephone")
                agent_exist.agent = row.get("agent") or agent_exist.agent
                agent_exist.genre = row.get("genre") or agent_exist.genre
                agent_exist.date_naissance = row.get("date_naissance") or agent_exist.date_naissance
                agent_exist.telephone = row.get("telephone") or agent_exist.telephone
                agent_exist.statut = row.get("statut") or "Actif"
                agent_exist.poste_type = row.get("poste_type")
                agent_exist.poste_comptable = row.get("poste_comptable")
                agent_exist.corps = row.get("corps")
                agent_exist.promotion_corps = row.get("promotion_corps")
                agent_exist.date_premiere_prise_service = row.get("date_premiere_prise_service")
                agent_exist.historique_formations = row.get("historique_formations")
                agent_exist.epoux_epouse_nom_poste = row.get("epoux_epouse_nom_poste")
                agent_exist.poste_type = row.get("poste_type") or agent_exist.poste_type
                agent_exist.poste_comptable = row.get("poste_comptable") or agent_exist.poste_comptable
                agent_exist.corps = row.get("corps") or agent_exist.corps
                agent_exist.promotion_corps = row.get("promotion_corps") or agent_exist.promotion_corps
                agent_exist.date_premiere_prise_service = row.get("date_premiere_prise_service") or agent_exist.date_premiere_prise_service
                agent_exist.historique_formations = row.get("historique_formations") or agent_exist.historique_formations
                agent_exist.epoux_epouse_nom_poste = row.get("epoux_epouse_nom_poste") or agent_exist.epoux_epouse_nom_poste
                total_updates += 1

            else:
                nom_agent = row.get("agent") or row.get("agents") or "Agent inconnu"
                genre_agent = row.get("genre") or "Homme"

                nouvel_agent = Agent(
                    agent=nom_agent,
                    matricule=matricule,
                    genre=genre_agent,
                    date_naissance=row.get("date_naissance"),
                    telephone=row.get("telephone"),
                    statut=row.get("statut") or "Actif",
                    poste_type=row.get("poste_type"),
                    poste_comptable=row.get("poste_comptable"),
                    corps=row.get("corps"),
                    promotion_corps=row.get("promotion_corps"),
                    date_premiere_prise_service=row.get("date_premiere_prise_service"),
                    historique_formations=row.get("historique_formations"),
                    epoux_epouse_nom_poste=row.get("epoux_epouse_nom_poste"),
                )
                db.session.add(nouvel_agent)
                total_ajoutes += 1

            if (i + 1) % 100 == 0:
                db.session.commit()
                print(f"[PROGRESS] {i + 1}/{len(df)} agents traites...")

        except Exception as e:
            db.session.rollback()
            erreurs += 1
            print(f"[ERREUR] Matricule {matricule} : {e}")

    try:
        db.session.commit()
        print("[OK] Commit final reussi")
    except Exception as e:
        db.session.rollback()
        print(f"[ERREUR COMMIT] : {e}")
        flash(f"Erreur base de donnees : {e}", "danger")
        return redirect(url_for('personnels_actifs'))

    print(f"Resultat : {total_ajoutes} ajoutes, {total_updates} mis a jour, {erreurs} erreurs")
    print("========== FIN IMPORT ==========\n")

    flash(f"Import termine : {total_ajoutes} ajoutes -- {total_updates} mis a jour -- {erreurs} erreurs", "success")
    return redirect(url_for('personnels_actifs'))
    return redirect(url_for('personnels_actifs'))
    
@login_required
@app.route('/personnels_inactifs')
def personnels_inactifs():
    page = request.args.get('page', 1, type=int)
    per_page = 30
    pagination = Agent.query.filter_by(statut="Inactif").order_by(Agent.agent).paginate(page=page, per_page=per_page, error_out=False)
    agents = pagination.items
    total_inactifs = pagination.total
    
    return render_template('personnels_inactifs.html', agents=agents, pagination=pagination, total_inactifs=total_inactifs, page='inactifs')

from datetime import date, datetime
from sqlalchemy import func
from flask import render_template


@login_required
@app.route('/statistiques')
def statistiques():
    today = date.today()

    
    # 
    # STATUT (pour info générale, peut inclure tous) ---
    statut_data = db.session.query(
        Agent.statut, func.count(Agent.id)
    ).group_by(Agent.statut).all()

    labels_statut = [s for s, _ in statut_data]
    data_statut = [c for _, c in statut_data]
    # ==========================
    # AGENTS ACTIFS
    # ==========================
    agents_actifs_query = Agent.query.filter_by(statut='Actif')

    # --- POSTE COMPTABLE (agents actifs uniquement) ---
    poste_comptable_data = db.session.query(
        Agent.poste_comptable, func.count(Agent.id)
    ).filter(
        Agent.statut == 'Actif',
        Agent.poste_comptable.isnot(None)
    ).group_by(Agent.poste_comptable).all()

    labels_poste_comptable = [g for g, _ in poste_comptable_data]
    data_poste_comptable = [c for _, c in poste_comptable_data]

    # --- CORPS (agents actifs uniquement) ---
    corps_data = db.session.query(
        Agent.corps, func.count(Agent.id)
    ).filter(
        Agent.statut == 'Actif',
        Agent.corps.isnot(None)
    ).group_by(Agent.corps).all()

    labels_corps = [c for c, _ in corps_data]
    data_corps = [nb for _, nb in corps_data]

    # --- TRANCHES D'ÂGE (agents actifs uniquement) ---
    tranches = {"-30": 0, "30-39": 0, "40-49": 0, "50-59": 0, "60+": 0}
    agents = agents_actifs_query.filter(Agent.date_naissance.isnot(None)).all()

    def safe_age(dn):
        """Calcule l'âge à partir de la date de naissance"""
        if isinstance(dn, str):
            try:
                dn_date = datetime.strptime(dn, "%Y-%m-%d").date()
            except ValueError:
                return None
        else:
            dn_date = dn
        return today.year - dn_date.year - ((today.month, today.day) < (dn_date.month, dn_date.day))

    for agent in agents:
        age = safe_age(agent.date_naissance)
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

    # ==========================
    # TOTALS
    # ==========================
    total_agents = agents_actifs_query.count()
    agents_actifs = total_agents
    agents_inactifs = Agent.query.filter_by(statut='Inactif').count()

    
    # --- AGENTS PROCHES DE LA RETRAITE ---
    AGE_RETRAITE = 60
    PROCHE_RETRAITE = 5  # agents dans les 5 ans avant retraite

    agents_proches_retraite = []

    for agent in agents:
        age = safe_age(agent.date_naissance)
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

    # --- TOTALS ---
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
def calcul_age(date_naissance):
    today = date.today()
    return today.year - date_naissance.year - (
        (today.month, today.day) < (date_naissance.month, date_naissance.day)
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
            date_traitement=request.form["date_traitement"],
            date_levee=request.form.get("date_levee") or None,
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
    data = request.get_json()
    sanction = Sanction.query.get(id)

    statut = data.get("statut")

    # 🔥 MAJ STATUT
    sanction.statut = statut

    if statut == "Levé":
        sanction.date_levee = data.get("date_levee")
        sanction.levee_par = data.get("levee_par")
    else:
        sanction.date_levee = None
        sanction.levee_par = None

    db.session.commit()
    return {"success": True}

@login_required
@app.route('/repartition')
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
            Agent.agent.label("matricule"),
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

    



@login_required
@app.route('/ajouter_agent', methods=['GET', 'POST'])
def ajouter_agent():
    if request.method == 'POST':

        # Récupération des champs
        agent = request.form['agent']
        matricule = request.form['matricule']
        genre = request.form.get("genre")
        date_naissance = request.form['date_naissance']
        telephone = request.form.get('telephone')
        statut = request.form.get('statut', 'Actif')

        epoux_epouse_nom_poste = request.form.get('epoux_epouse_nom_poste')
        poste_type = request.form['poste_type']
        poste_comptable = request.form['poste_comptable']
        corps = request.form['corps']

        historique_formations = request.form.get('historique_formations')
        date_premiere_prise_service = request.form['date_premiere_prise_service']
        promotion_corps = request.form.get('promotion_corps')
       

        # Création de l'agent
        nouvel_agent = Agent(
            agent=agent,
            matricule=matricule,
            genre=genre,
            date_naissance=date_naissance,
            telephone=telephone,
            statut=statut,
            epoux_epouse_nom_poste=epoux_epouse_nom_poste,
            corps=corps,
            poste_type=poste_type,
            poste_comptable=poste_comptable,
            historique_formations=historique_formations,
            date_premiere_prise_service=date_premiere_prise_service,
            promotion_corps=promotion_corps
            
        )

        # 🔹 1. Insertion agent
        db.session.add(nouvel_agent)
        db.session.commit()  # ⬅️ indispensable pour avoir nouvel_agent.id

        # 🔹 2. Enregistrement du mouvement
        enregistrer_mouvement(
            agents_id=nouvel_agent.id,
            champ="agent",
            ancienne_valeur=None,
            nouvelle_valeur=nouvel_agent.agent,
            auteur=session.get("username", "system"),
            type_mouvement="creation"
        )

        db.session.commit()

        flash("Agent ajouté avec succès !", "success")
        return redirect(url_for('personnels_actifs'))

    return render_template('ajouter_agent.html', page='ajouter')



@login_required
@app.route('/modifier_agent/<int:id>', methods=['POST'])
def modifier_agent(id):
    agent = Agent.query.get_or_404(id)
    data = request.get_json()   

    anciennes_valeurs = {
        "agent": agent.agent,
        "matricule": agent.matricule,
        "telephone": agent.telephone,
        "genre": agent.genre,
        "date_naissance": agent.date_naissance,
        "statut": agent.statut,
        "corps": agent.corps,
        "poste_type": agent.poste_type,
        "poste_comptable": agent.poste_comptable,
        "date_premiere_prise_service": agent.date_premiere_prise_service,
        "historique_formations": agent.historique_formations,
        "epoux_epouse_nom_poste": agent.epoux_epouse_nom_poste,
        "promotion_corps": agent.promotion_corps,
        
    }


    agent.agent = data.get('agent')
    agent.matricule = data.get('matricule')
    agent.telephone = data.get('telephone')
    agent.genre = data.get('genre')
    agent.date_naissance = data.get('date_naissance')
    agent.statut = data.get('statut')
    agent.corps = data.get('corps')
    agent.poste_type = data.get('poste_type')
    agent.poste_comptable = data.get('poste_comptable')
    agent.date_premiere_prise_service = data.get('date_premiere_prise_service')
    agent.historique_formations = data.get('historique_formations')
    agent.epoux_epouse_nom_poste = data.get('epoux_epouse_nom_poste')
    agent.promotion_corps = data.get('promotion_corps')
    


    for champ, ancienne_valeur in anciennes_valeurs.items():
        nouvelle_valeur = data.get(champ)

        ancienne_str = (
            ancienne_valeur.isoformat()
            if hasattr(ancienne_valeur, "isoformat")
            else str(ancienne_valeur) if ancienne_valeur is not None else ""
        )

        nouvelle_str = (
            str(nouvelle_valeur)
            if nouvelle_valeur is not None else ""
        )

        if ancienne_str != nouvelle_str:
            enregistrer_mouvement(
                agent_id=agent.id,
                champ=champ,
                ancienne_valeur=ancienne_str,
                nouvelle_valeur=nouvelle_str,
                auteur=session.get("username", "system"),
                type_mouvement="modification"
            )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Agent actif modifié avec succès"
    })


@login_required
@app.route('/api/agent/<int:id>')
def api_get_agent(id):
    agent = Agent.query.get(id)
    if not agent:
        return {"error": "Agent introuvable"}, 404

    return {
        "id": agent.id,
        "matricule": agent.matricule,
        "agent": agent.agent,   # NOM COMPLET
        "telephone": agent.telephone,
        "genre": agent.genre,
        "date_naissance": agent.date_naissance.isoformat() if agent.date_naissance else None,
        "statut": agent.statut,
        "corps": agent.corps,
        "poste_type": agent.poste_type,
        "poste_comptable": agent.poste_comptable,
        "date_premiere_prise_service": agent.date_premiere_prise_service.isoformat() if agent.date_premiere_prise_service else None,
        "historique_formations": agent.historique_formations,
        "epoux_epouse_nom_poste": agent.epoux_epouse_nom_poste,
        "promotion_corps": agent.promotion_corps,
        

        # ➕ CHAMPS D’INACTIVITÉ (à ajouter ici)
        "motif_inactivite": agent.motif_inactivite,
        "date_inactivite": agent.date_inactivite.isoformat() if agent.date_inactivite else None,
        "commentaire_inactivite": agent.commentaire_inactivite
    }

from datetime import date

@login_required
@app.route('/api/agent/inactiver/<int:id>', methods=['POST'])
def api_inactiver(id):
    agent = Agent.query.get_or_404(id)
    data = request.get_json()

    #  Sauvegarde ancien statut
    ancien_statut = agent.statut

    #  Données reçues
    motif = data.get("motif_inactivite")
    details = data.get("details_motif")
    commentaire = data.get("commentaire_inactivite")
    date_inact = data.get("date_inactivite")

    #  Mise à jour agent
    agent.statut = "Inactif"
    agent.motif_inactivite = motif
    agent.commentaire_inactivite = commentaire

    if date_inact:
        agent.date_inactivite = date.fromisoformat(date_inact)

    #  Mouvement RH structuré
    if ancien_statut != agent.statut:
        nouvelle_valeur = "Inactif"
        if motif:
            nouvelle_valeur += f" – {motif}"
        if details:
            nouvelle_valeur += f" ({details})"

        mouvement = Mouvement(
            agents_id=agent.id,
            type_mouvement="Inactivité",
            champ_modifie="statut",
            ancienne_valeur=ancien_statut,
            nouvelle_valeur=nouvelle_valeur,
            auteur=session.get("username", "system")
        )

        db.session.add(mouvement)

    # Commit unique
    db.session.commit()

    return jsonify({"success": True})




@login_required
@app.route('/api/agent/update/<int:id>', methods=['POST'])
def api_update_agent(id):
    agent = Agent.query.get_or_404(id)
    data = request.get_json() or {}

    #  Stocker les anciennes valeurs
    anciennes_valeurs = {
        "agent": agent.agent,
        "matricule": agent.matricule,
        "telephone": agent.telephone,
        "genre": agent.genre,
        "date_naissance": agent.date_naissance,
        "statut": agent.statut,
        "corps": agent.corps,
        "poste_type": agent.poste_type,
        "poste_comptable": agent.poste_comptable,
        "historique_formations": agent.historique_formations,
        "epoux_epouse_nom_poste": agent.epoux_epouse_nom_poste,
        "promotion_corps": agent.promotion_corps,
        "motif_inactivite": agent.motif_inactivite,
        "date_inactivite": agent.date_inactivite,
        "commentaire_inactivite": agent.commentaire_inactivite
    }

    # 🔹 Mettre à jour les champs
    for champ, ancienne_valeur in anciennes_valeurs.items():
        nouvelle_valeur = data.get(champ, ancienne_valeur)

        # Parse dates si nécessaire
        if champ in ["date_naissance", "date_premiere_prise_service", "date_inactivite"] and nouvelle_valeur:
            try:
                nouvelle_valeur = date.fromisoformat(nouvelle_valeur)
            except Exception:
                nouvelle_valeur = ancienne_valeur

        setattr(agent, champ, nouvelle_valeur)

        # 🔹 Enregistrer le mouvement si la valeur a changé
        if str(ancienne_valeur) != str(nouvelle_valeur):
            # type_mouvement = 'modification' ou 'reactivation' si statut
            type_mouv = "modification"
            if champ == "statut" and ancienne_valeur == "Inactif" and nouvelle_valeur == "Actif":
                type_mouv = "reactivation"
            elif champ == "statut" and ancienne_valeur == "Actif" and nouvelle_valeur == "Inactif":
                type_mouv = "inactivation"

            enregistrer_mouvement(
                agents_id=agent.id,
                champ=champ,
                ancienne_valeur=ancienne_valeur,
                nouvelle_valeur=nouvelle_valeur,
                auteur=session.get("username", "system"),
                type_mouvement=type_mouv
            )

    # 🔹 Nettoyage si réactivation
    if anciennes_valeurs["statut"] == "Inactif" and agent.statut == "Actif":
        agent.motif_inactivite = None
        agent.date_inactivite = None
        agent.commentaire_inactivite = None

    db.session.commit()

    return jsonify({
        "success": True,
        "agent": {
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
            "date_premiere_prise_service": agent.date_premiere_prise_service.isoformat() if agent.date_premiere_prise_service else None,
            "promotion_corps": agent.promotion_corps,
            "epoux_epouse_nom_poste": agent.epoux_epouse_nom_poste,
            "historique_formations": agent.historique_formations,
            "motif_inactivite": agent.motif_inactivite,
            "date_inactivite": agent.date_inactivite.isoformat() if agent.date_inactivite else None,
            "commentaire_inactivite": agent.commentaire_inactivite
        }
    })


@login_required
@app.route('/supprimer_agent/<int:id>')
def supprimer_agent(id):
    agent = Agent.query.get_or_404(id)
    db.session.delete(agent)
    db.session.commit()
    flash("Agent supprimé avec succès !", "info")
    return redirect(url_for('personnels_actifs'))




@login_required
@app.route('/changer_statut/<int:id>', methods=['POST'])
def changer_statut(id):
    agent = Agent.query.get_or_404(id)

    ancien_statut = agent.statut

    # Changement
    agent.statut = "Inactif" if agent.statut == "Actif" else "Actif"
    nouveau_statut = agent.statut

    # Enregistrement du mouvement
    if ancien_statut != nouveau_statut:
        enregistrer_mouvement(
            agent_id=agent.id,
            type_mouvement="modification",
            champ="statut",
            ancienne_valeur=ancien_statut,
            nouvelle_valeur=nouveau_statut
        )

    db.session.commit()

    flash(f"Statut de {agent.nom} changé en {agent.statut}", "warning")
    return redirect(url_for('personnels_inactifs'))


@login_required
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
            flash("Connexion réussie", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Identifiants incorrects", "danger")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
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

@app.route('/init_users')
def init_users():
    if User.query.first():
        return "Des utilisateurs existent déjà. Supprimez la table users si vous voulez recréer."

    users = [
        ("admin", "admin123", "Administrateur", "admin"),
        ("gestionnaire", "sirh2024", "Gestionnaire RH", "gestionnaire"),
        ("lecteur", "sirh2024", "Lecteur", "lecteur"),
    ]
    for username, password, nom, role in users:
        u = User(username=username, nom_complet=nom, role=role)
        u.set_password(password)
        db.session.add(u)
    db.session.commit()
    return "3 utilisateurs créés : admin/admin123, gestionnaire/sirh2024, lecteur/sirh2024"


# === CRÉATION DES TABLES SI NON EXISTANTES ===
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
