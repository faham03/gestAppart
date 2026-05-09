from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from models import db, Chambre, Releve, ConfigPrix
from functools import wraps
import secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:0510@localhost/gestappart_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'gestappart-clé-secrète-à-changer'

ADMIN_PASSWORD = 'admin123'

db.init_app(app)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        error = 'Mot de passe incorrect'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_config():
    config = ConfigPrix.query.first()
    if not config:
        config = ConfigPrix(prix_eau=300, prix_elec=200)
        db.session.add(config)
        db.session.commit()
    return config


# ── Chambres ───────────────────────────────────────────────────────────────────

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
    chambre = db.get_or_404(Chambre, id)
    data = request.json
    chambre.numero = data.get('numero', chambre.numero)
    chambre.nom_locataire = data.get('nom_locataire', chambre.nom_locataire)
    chambre.caution = data.get('caution', chambre.caution)
    chambre.avance = data.get('avance', chambre.avance)
    db.session.commit()
    return jsonify({'message': 'Chambre modifiée'})


@app.route('/api/chambres/<int:id>', methods=['DELETE'])
def delete_chambre(id):
    chambre = db.get_or_404(Chambre, id)
    db.session.delete(chambre)
    db.session.commit()
    return jsonify({'message': 'Chambre supprimée'})


# ── Relevés ────────────────────────────────────────────────────────────────────

@app.route('/api/releves', methods=['POST'])
def add_releve():
    data = request.json
    eau_a  = data.get('eau_ancien', 0)
    eau_n  = data.get('eau_nouveau', 0)
    elec_a = data.get('elec_ancien', 0)
    elec_n = data.get('elec_nouveau', 0)

    if eau_n < eau_a:
        return jsonify({'error': "Le nouveau relevé eau ne peut pas être inférieur à l'ancien"}), 400
    if elec_n < elec_a:
        return jsonify({'error': "Le nouveau relevé électricité ne peut pas être inférieur à l'ancien"}), 400

    existant = Releve.query.filter_by(
        chambre_id=data['chambre_id'],
        mois=data['mois'],
        annee=data['annee']
    ).first()
    if existant:
        return jsonify({'error': f"Un relevé existe déjà pour {data['mois']}/{data['annee']}"}), 409

    new_releve = Releve(
        chambre_id=data['chambre_id'],
        mois=data['mois'],
        annee=data['annee'],
        eau_ancien=eau_a,
        eau_nouveau=eau_n,
        elec_ancien=elec_a,
        elec_nouveau=elec_n
    )
    db.session.add(new_releve)
    db.session.commit()
    return jsonify({'message': 'Relevé ajouté'}), 201


@app.route('/api/releves/<int:chambre_id>', methods=['GET'])
def get_releves(chambre_id):
    releves = Releve.query.filter_by(chambre_id=chambre_id)\
        .order_by(Releve.annee.desc(), Releve.mois.desc()).all()
    return jsonify([{
        'id': r.id,
        'mois': r.mois,
        'annee': r.annee,
        'eau_ancien': r.eau_ancien,
        'eau_nouveau': r.eau_nouveau,
        'elec_ancien': r.elec_ancien,
        'elec_nouveau': r.elec_nouveau
    } for r in releves])


@app.route('/api/releves/<int:id>', methods=['DELETE'])
def delete_releve(id):
    releve = db.get_or_404(Releve, id)
    db.session.delete(releve)
    db.session.commit()
    return jsonify({'message': 'Relevé supprimé'})


# ── Facture ────────────────────────────────────────────────────────────────────

@app.route('/api/facture/<int:chambre_id>', methods=['GET'])
def get_facture(chambre_id):
    releve = Releve.query.filter_by(chambre_id=chambre_id)\
        .order_by(Releve.annee.desc(), Releve.mois.desc()).first()
    if not releve:
        return jsonify({'error': 'Aucun relevé trouvé pour cette chambre'}), 404

    config  = _get_config()
    chambre = db.get_or_404(Chambre, chambre_id)

    conso_eau   = releve.eau_nouveau  - releve.eau_ancien
    montant_eau = conso_eau * config.prix_eau
    conso_elec   = releve.elec_nouveau - releve.elec_ancien
    montant_elec = conso_elec * config.prix_elec

    return jsonify({
        'chambre_id': chambre_id,
        'numero': chambre.numero,
        'locataire': chambre.nom_locataire,
        'mois': releve.mois,
        'annee': releve.annee,
        'eau': {
            'ancien': releve.eau_ancien, 'nouveau': releve.eau_nouveau,
            'consommation': conso_eau, 'prix_unitaire': config.prix_eau, 'montant': montant_eau
        },
        'electricite': {
            'ancien': releve.elec_ancien, 'nouveau': releve.elec_nouveau,
            'consommation': conso_elec, 'prix_unitaire': config.prix_elec, 'montant': montant_elec
        },
        'total': montant_eau + montant_elec
    })


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    dernier = Releve.query.order_by(Releve.annee.desc(), Releve.mois.desc()).first()
    if not dernier:
        return jsonify({'total_eau': 0, 'total_electricite': 0, 'total_general': 0,
                        'nb_chambres_facturees': 0, 'message': 'Aucun relevé enregistré'})

    releves = Releve.query.filter_by(mois=dernier.mois, annee=dernier.annee).all()
    config  = _get_config()

    total_eau  = sum((r.eau_nouveau  - r.eau_ancien)  * config.prix_eau  for r in releves)
    total_elec = sum((r.elec_nouveau - r.elec_ancien) * config.prix_elec for r in releves)

    return jsonify({
        'total_eau': total_eau, 'total_electricite': total_elec,
        'total_general': total_eau + total_elec,
        'nb_chambres_facturees': len(releves),
        'mois': dernier.mois, 'annee': dernier.annee,
        'prix_eau_unitaire': config.prix_eau, 'prix_elec_unitaire': config.prix_elec
    })


# ── Config prix ────────────────────────────────────────────────────────────────

@app.route('/api/config', methods=['GET'])
def get_config():
    config = _get_config()
    return jsonify({'prix_eau': config.prix_eau, 'prix_elec': config.prix_elec})


@app.route('/api/config', methods=['PUT'])
def update_config():
    data   = request.json
    config = _get_config()
    config.prix_eau  = data.get('prix_eau',  config.prix_eau)
    config.prix_elec = data.get('prix_elec', config.prix_elec)
    db.session.commit()
    return jsonify({'message': 'Paramètres mis à jour',
                    'prix_eau': config.prix_eau, 'prix_elec': config.prix_elec})


# ── Espace locataire ───────────────────────────────────────────────────────────

@app.route('/locataire/<int:id>/<string:token>', methods=['GET'])
def espace_locataire(id, token):
    chambre = db.get_or_404(Chambre, id)
    if chambre.token != token:
        return "Lien invalide ou expiré", 403

    releve = Releve.query.filter_by(chambre_id=id)\
        .order_by(Releve.annee.desc(), Releve.mois.desc()).first()
    if not releve:
        return f"<h3>Aucun relevé trouvé pour {chambre.nom_locataire}</h3>", 404

    config       = _get_config()
    conso_eau    = releve.eau_nouveau  - releve.eau_ancien
    montant_eau  = conso_eau * config.prix_eau
    conso_elec   = releve.elec_nouveau - releve.elec_ancien
    montant_elec = conso_elec * config.prix_elec
    total        = montant_eau + montant_elec

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Facture GestAppart</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Arial,sans-serif;background:#1e1e2f;color:#fff;padding:20px;line-height:1.6}}
.container{{max-width:600px;margin:0 auto;background:#2a2a3b;border-radius:15px;padding:25px;box-shadow:0 5px 20px rgba(0,0,0,.3)}}
h1{{color:#4CAF50;text-align:center;margin-bottom:10px}}
.salutation{{font-size:1.4em;margin-bottom:25px;text-align:center;color:#ddd}}
.card{{background:#3a3a4f;border-radius:12px;padding:18px;margin-bottom:20px}}
.card h3{{color:#FF9800;margin-bottom:12px;font-size:1.3em}}
.detail{{display:flex;justify-content:space-between;margin:8px 0;padding:5px 0;border-bottom:1px solid #555}}
.total{{background:#4CAF50;border-radius:12px;padding:20px;text-align:center;margin-top:20px}}
.total h2{{font-size:1.8em;margin-bottom:5px}}
.montant{{font-size:2em;font-weight:bold;color:#FFD700}}
.footer{{text-align:center;margin-top:20px;font-size:.8em;color:#888}}
.periode{{text-align:center;background:#1e1e2f;padding:8px;border-radius:8px;margin-bottom:20px}}
</style></head>
<body><div class="container">
<h1>GestAppart</h1>
<div class="salutation">Bonjour {chambre.nom_locataire}</div>
<div class="periode">Facture — {releve.mois}/{releve.annee}</div>
<div class="card"><h3>Eau</h3>
<div class="detail"><span>Ancien relevé :</span><span>{releve.eau_ancien} m3</span></div>
<div class="detail"><span>Nouveau relevé :</span><span>{releve.eau_nouveau} m3</span></div>
<div class="detail"><span>Consommation :</span><span>{conso_eau} m3</span></div>
<div class="detail"><span>Prix unitaire :</span><span>{config.prix_eau} FCFA/m3</span></div>
<div class="detail" style="border-bottom:none;font-weight:bold"><span>Montant :</span><span>{montant_eau:,.0f} FCFA</span></div>
</div>
<div class="card"><h3>Electricite</h3>
<div class="detail"><span>Ancien relevé :</span><span>{releve.elec_ancien} kWh</span></div>
<div class="detail"><span>Nouveau relevé :</span><span>{releve.elec_nouveau} kWh</span></div>
<div class="detail"><span>Consommation :</span><span>{conso_elec} kWh</span></div>
<div class="detail"><span>Prix unitaire :</span><span>{config.prix_elec} FCFA/kWh</span></div>
<div class="detail" style="border-bottom:none;font-weight:bold"><span>Montant :</span><span>{montant_elec:,.0f} FCFA</span></div>
</div>
<div class="total"><h2>TOTAL A PAYER</h2>
<div class="montant">{total:,.0f} FCFA</div></div>
<div class="footer">GestAppart — Facture detaillee<br>En cas d erreur, contactez le 90 02 54 63</div>
</div></body></html>"""
    return html


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)