from flask import Flask, request, jsonify
from models import db, Chambre, Releve, ConfigPrix
import secrets

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:0510@localhost/gestappart_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.route('/api/chambres', methods=['GET'])
def get_chambres():
    chambres = Chambre.query.all()
    return jsonify([{
        'id': c.id,
        'numero': c.numero,
        'nom_locataire': c.nom_locataire,
        'caution': c.caution,
        'avance': c.avance,
        'token': c.token
    } for c in chambres])

@app.route('/api/chambres', methods=['POST'])
def add_chambre():
    data = request.json
    token = secrets.token_urlsafe(32)
    new_chambre = Chambre(
        numero=data['numero'],
        nom_locataire=data['nom_locataire'],
        caution=data.get('caution', 0),
        avance=data.get('avance', 0),
        token=token
    )
    db.session.add(new_chambre)
    db.session.commit()
    return jsonify({'message': 'Chambre ajoutée', 'token': token}), 201

@app.route('/api/chambres/<int:id>', methods=['PUT'])
def update_chambre(id):
    chambre = Chambre.query.get_or_404(id)
    data = request.json
    chambre.numero = data.get('numero', chambre.numero)
    chambre.nom_locataire = data.get('nom_locataire', chambre.nom_locataire)
    chambre.caution = data.get('caution', chambre.caution)
    chambre.avance = data.get('avance', chambre.avance)
    db.session.commit()
    return jsonify({'message': 'Chambre modifiée'})

@app.route('/api/chambres/<int:id>', methods=['DELETE'])
def delete_chambre(id):
    chambre = Chambre.query.get_or_404(id)
    db.session.delete(chambre)
    db.session.commit()
    return jsonify({'message': 'Chambre supprimée'})

@app.route('/api/releves', methods=['POST'])

def add_releve():
    data = request.json
    new_releve = Releve(
        chambre_id = data['chambre_id'],
        mois = data['mois'],
        annee = data['annee'],
        eau_ancien = data['eau_ancien'],
        eau_nouveau = data['eau_nouveau'],
        elec_ancien = data['elec_ancien'],
        elec_nouveau = data['elec_nouveau']
    )

    db.session.add(new_releve)
    db.session.commit()
    return jsonify({'message': 'Relevé ajouté'}), 201

@app.route('/api/releves/<int:chambre_id>' , methods=['GET'])

def get_releves(chambre_id):
    releves = Releve.query.filter_by(chambre_id=chambre_id).all()
    return jsonify([{
        'id': r.id,
        'mois': r.mois,
        'annee': r.annee,
        'eau_ancien': r.eau_ancien,
        'eau_nouveau': r.eau_nouveau,
        'elec_ancien': r.elec_ancien,
        'elec_nouveau': r.elec_nouveau
    }for r in releves])

@app.route('/api/facture/<int:chambre_id>', methods=['GET'])
def get_facture(chambre_id):
    releve = Releve.query.filter_by(chambre_id=chambre_id).order_by(Releve.annee.desc(), Releve.mois.desc()).first()

    if not releve:
        return jsonify({'error': 'Aucun relevé trouvé pour cette cha,bre'}), 404
    
    config = ConfigPrix.query.first()
    if not config:
        config = ConfigPrix(prix_eau=300, prix_elec=200)
        db.session.add(config)
        db.session.commit()

    conso_eau = releve.eau_nouveau - releve.eau_ancien
    montant_eau = conso_eau * config.prix_eau

    conso_elec = releve.elec_nouveau - releve.elec_ancien
    montant_elec = conso_elec * config.prix_elec

    total = montant_eau + montant_elec

    chambre = Chambre.query.get_or_404(chambre_id)

    return jsonify ({
        'chambre_id': chambre_id,
        'numero': chambre.numero,
        'locataire': chambre.nom_locataire,
        'mois': releve.mois,
        'annnee': releve.annee,
        'eau': {
            'ancien': releve.eau_ancien,
            'nouveau': releve.eau_nouveau,
            'consommation': conso_eau,
            'prix_unitaire': config.prix_eau,
            'montant': montant_eau
        },
        'electricite': {
            'ancien': releve.elec_ancien,
            'nouveau': releve.elec_nouveau,
            'consommation': conso_elec,
            'prix_unitaire': config.prix_elec,
            'montant': montant_elec
        },
        'total': total
    })

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    dernier_releve = Releve.query.order_by(Releve.annee.desc(), Releve.mois.desc()).first()
    
    if not dernier_releve:
        return jsonify({
            'total_eau': 0,
            'total_electricite': 0,
            'total_general': 0,
            'nb_chambres_facturees': 0,
            'message': 'Aucun relevé existant'
        })
    
    mois_affiche = dernier_releve.mois
    annee_affiche = dernier_releve.annee
    
    releves_mois = Releve.query.filter_by(mois=mois_affiche, annee=annee_affiche).all()
    
    config = ConfigPrix.query.first()
    if not config:
        config = ConfigPrix(prix_eau=300, prix_elec=200)
    
    total_eau = 0
    total_elec = 0
    
    for releve in releves_mois:
        conso_eau = releve.eau_nouveau - releve.eau_ancien
        conso_elec = releve.elec_nouveau - releve.elec_ancien
        total_eau += conso_eau * config.prix_eau
        total_elec += conso_elec * config.prix_elec
    
    return jsonify({
        'total_eau': total_eau,
        'total_electricite': total_elec,
        'total_general': total_eau + total_elec,
        'nb_chambres_facturees': len(releves_mois),
        'mois': mois_affiche,
        'annee': annee_affiche,
        'prix_eau_unitaire': config.prix_eau,
        'prix_elec_unitaire': config.prix_elec
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)