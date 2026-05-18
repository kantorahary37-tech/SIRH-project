# config.py
from flask_sqlalchemy import SQLAlchemy
from flask import Flask

# Création de l'application Flask
app = Flask(__name__)

# Configuration de la base de données MySQL
# (remplace 'sirh' par le nom exact de ta base si différent)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root@localhost/sirh'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'cle_secrete_sirh'

# Initialisation de SQLAlchemy
db = SQLAlchemy(app)
