from datetime import datetime
from models import db

class Mouvement(db.Model):
    __tablename__ = "mouvements"

    id = db.Column(db.Integer, primary_key=True)

    # Relation avec la table agents (sans backref pour éviter conflit)
    agents_id = db.Column(
        db.Integer,
        db.ForeignKey("agents.id"),
        nullable=False
    )
    agent = db.relationship("Agent")  # juste pour pouvoir accéder à l'agent depuis un mouvement

    date_mouvement = db.Column(db.DateTime, default=datetime.utcnow)
    type_mouvement = db.Column(db.String(50))
    champ_modifie = db.Column(db.String(100))
    ancienne_valeur = db.Column(db.Text)
    nouvelle_valeur = db.Column(db.Text)
    auteur = db.Column(db.String(100))

    def __repr__(self):
        return f"<Mouvement {self.type_mouvement} - {self.agent.agent}>"

def enregistrer_mouvement(
    agents_id,
    champ,
    ancienne_valeur,
    nouvelle_valeur,
    auteur,
    type_mouvement="modification"
):
    mouvement = Mouvement(
        agents_id=agents_id,
        champ_modifie=champ,
        ancienne_valeur=str(ancienne_valeur),
        nouvelle_valeur=str(nouvelle_valeur),
        auteur=auteur,
        type_mouvement=type_mouvement,
        date_mouvement=datetime.utcnow()
    )

    db.session.add(mouvement)
    db.session.commit()
    return mouvement