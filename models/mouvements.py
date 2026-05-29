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
        agent_name = self.agent.agent if self.agent else "inconnu"
        return f"<Mouvement {self.type_mouvement} - {agent_name}>"


def enregistrer_mouvement(
    agents_id=None,
    champ=None,
    ancienne_valeur=None,
    nouvelle_valeur=None,
    auteur="system",
    type_mouvement="modification",
    commit=False,
    agent_id=None,
):
    target_agent_id = agents_id if agents_id is not None else agent_id
    if target_agent_id is None:
        raise ValueError("agents_id est obligatoire pour enregistrer un mouvement")

    mouvement = Mouvement(
        agents_id=target_agent_id,
        champ_modifie=champ,
        ancienne_valeur="" if ancienne_valeur is None else str(ancienne_valeur),
        nouvelle_valeur="" if nouvelle_valeur is None else str(nouvelle_valeur),
        auteur=auteur,
        type_mouvement=type_mouvement,
        date_mouvement=datetime.utcnow()
    )

    db.session.add(mouvement)
    if commit:
        db.session.commit()
    return mouvement
