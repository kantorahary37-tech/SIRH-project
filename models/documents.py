from models import db

class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.id'))
    nom_fichier = db.Column(db.String(255))
    chemin = db.Column(db.String(255))

    agent = db.relationship('Agent', backref='documents')
