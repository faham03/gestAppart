from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Chambre(db.Model):
    __tablename__ = 'chambres'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), nullable=False, unique=True)
    nom_locataire = db.Column(db.String(100), nullable=False)
    caution = db.Column(db.Float, default=0)
    avance = db.Column(db.Float, default=0)
    token = db.Column(db.String(100), unique=True, nullable=False)

class Releve(db.Model):
    __tablename__ = 'releves'
    id = db.Column(db.Integer, primary_key=True)
    chambre_id = db.Column(db.Integer, db.ForeignKey('chambres.id'), nullable=False)
    mois = db.Column(db.Integer, nullable=False)
    annee = db.Column(db.Integer, nullable=False)
    eau_ancien = db.Column(db.Float, nullable=False)
    eau_nouveau = db.Column(db.Float, nullable=False)
    elec_ancien = db.Column(db.Float, nullable=False)
    elec_nouveau = db.Column(db.Float, nullable=False)

class ConfigPrix(db.Model):
    __tablename__ = 'config_prix'
    id = db.Column(db.Integer, primary_key=True)
    prix_eau = db.Column(db.Float, default=300)
    prix_elec = db.Column(db.Float, default=200)