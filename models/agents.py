from models import db
from datetime import date, datetime

print("=== AGENTS.PY CHARGÉ ===")
class Agent(db.Model):
    __tablename__ = 'agents'

    id = db.Column(db.Integer, primary_key=True)
    matricule = db.Column(db.String(50))
    agent = db.Column(db.String(200), nullable=False)

    telephone = db.Column(db.String(20))
    genre = db.Column(db.Enum("Homme", "Femme"), nullable=True)
    date_naissance = db.Column(db.Date)
    statut = db.Column(db.String(20), default="Actif", nullable=False)

    corps = db.Column(db.String(100))
    poste_type = db.Column(db.String(100))
    poste_comptable = db.Column(db.String(150))

    date_premiere_prise_service = db.Column(db.Date)
    historique_formations = db.Column(db.Text)

    epoux_epouse_nom_poste = db.Column(db.String(150))
    promotion_corps = db.Column(db.String(150))

    # 🔥 champs inactivité
    motif_inactivite = db.Column(db.String(20), nullable=True)
    date_inactivite = db.Column(db.Date, nullable=True)
    commentaire_inactivite = db.Column(db.Text)

    # 🔵 RELATIONS
    mouvements = db.relationship(
    'Mouvement',
    backref='agent_parent',
    lazy=True,
    foreign_keys='Mouvement.agents_id'
)
    
    sanctions = db.relationship("Sanction", back_populates="agent")

    # -----------------------
    # AGE
    # -----------------------
    @property
    def age(self):
        if not self.date_naissance:
            return ""
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) <
            (self.date_naissance.month, self.date_naissance.day)
        )

    # -----------------------
    # ANCIENNETE
    # -----------------------
    @property
    def anciennete(self):
        if self.date_premiere_prise_service:
            if not self.date_premiere_prise_service:
                return ""
        
        try:
            if isinstance(self.date_premiere_prise_service, str):
                if self.date_premiere_prise_service in ['0000-00-00', '', 'None']:
                    return ""
                prise = datetime.strptime(
                    self.date_premiere_prise_service,
                    "%Y-%m-%d"
                ).date()
            else:
                prise = self.date_premiere_prise_service

            return date.today().year - prise.year
        
    
        except (ValueError, TypeError):
            return ""

    

    @property
    def historique_complet(self):
        events = []

        # mouvements
        for m in self.mouvements:
            if m.date_mouvement:
                events.append({
                    "date": m.date_mouvement.date(),
                    "type": "Mouvement",
                    "type_mouvement": m.type_mouvement,
                    "champ_modifie": m.champ_modifie,
                    "ancienne_valeur": m.ancienne_valeur,
                    "nouvelle_valeur": m.nouvelle_valeur,
                    "auteur": m.auteur
                })

        # sanctions
        for s in self.sanctions:
            if s.date_traitement:
                events.append({
                    "date": s.date_traitement,
                    "type": "Sanction",
                    "type_sanction": s.type_sanction,
                    "motif": s.motif,
                    "date_levee": s.date_levee
                })

        # trier par date décroissante
        events.sort(key=lambda x: x["date"], reverse=True)

        return events