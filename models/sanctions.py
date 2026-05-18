from models import db
from datetime import datetime

class Sanction(db.Model):
    __tablename__ = "sanction"

    id = db.Column(db.Integer, primary_key=True)

    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'), nullable=False)

    
    agent = db.relationship("Agent", back_populates="sanctions")
    type_sanction = db.Column(db.String(100), nullable=False)
    motif = db.Column(db.Text, nullable=False)

    
    statut = db.Column(db.String(50), default="En cours")

    date_traitement = db.Column(db.Date, nullable=True)
    date_levee = db.Column(db.Date, nullable=True)
    levee_par = db.Column(db.String(100), nullable=True)

    decision_par = db.Column(db.String(100))
    observation = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)