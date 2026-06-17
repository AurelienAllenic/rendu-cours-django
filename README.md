# Tricount API

API REST de partage de dépenses entre amis, développée avec **Django 5.1** et **Django REST Framework 3.15**.

---

## Fonctionnalités

- Création et gestion de **groupes** avec membres
- Enregistrement de **dépenses** avec répartition personnalisée des parts
- Calcul automatique des **soldes nets** par membre
- Algorithme glouton de **minimisation des remboursements**
- Documentation API interactive (Swagger UI & ReDoc)
- Suite de tests unitaires complète

---

## Stack technique

| Composant | Technologie |
|---|---|
| Framework | Django 5.1 + Django REST Framework 3.15 |
| Base de données | SQLite (dev) |
| Documentation API | drf-spectacular (OpenAPI 3.0) |
| CORS | django-cors-headers |
| Tests | Django TestCase |

---

## Installation

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd rendu-django
```

### 2. Créer et activer l'environnement virtuel

```bash
# Création
python -m venv venv

# Activation (Windows)
.\venv\Scripts\Activate.ps1

# Activation (macOS / Linux)
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Appliquer les migrations

```bash
python manage.py migrate
```

### 5. Créer un superutilisateur (optionnel)

```bash
python manage.py createsuperuser
```

### 6. Lancer le serveur de développement

```bash
python manage.py runserver
```

---

## Endpoints disponibles

### Groupes

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/api/groupes/` | Lister ses groupes |
| `POST` | `/api/groupes/` | Créer un groupe |
| `GET` | `/api/groupes/{id}/` | Détail d'un groupe |
| `PUT` | `/api/groupes/{id}/` | Modifier un groupe |
| `DELETE` | `/api/groupes/{id}/` | Supprimer un groupe |

### Dépenses

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/api/depenses/` | Lister les dépenses accessibles |
| `POST` | `/api/depenses/` | Créer une dépense avec ses parts |
| `GET` | `/api/depenses/{id}/` | Détail d'une dépense |
| `PUT` | `/api/depenses/{id}/` | Modifier une dépense |
| `DELETE` | `/api/depenses/{id}/` | Supprimer une dépense |

### Documentation

| URL | Description |
|---|---|
| `/api/docs/` | Swagger UI (interface interactive) |
| `/api/redoc/` | ReDoc (documentation lisible) |
| `/api/schema/` | Schéma OpenAPI 3.0 brut (JSON/YAML) |

---

## Exemple de requête — Créer une dépense

```http
POST /api/depenses/
Content-Type: application/json

{
  "groupe": 1,
  "titre": "Restaurant",
  "montant": "60.00",
  "payeur": 1,
  "parts": [
    { "participant": 1, "montant_part": "20.00" },
    { "participant": 2, "montant_part": "20.00" },
    { "participant": 3, "montant_part": "20.00" }
  ]
}
```

**Contrainte** : la somme des `montant_part` doit être strictement égale au `montant` total, sinon l'API retourne une erreur 400.

---

## Logique métier — Calcul des soldes

La fonction `calculer_soldes(groupe)` dans `expenses/services.py` effectue deux opérations :

**Étape 1 — Soldes nets**

```
solde(membre) = Σ(dépenses payées) − Σ(parts dues)
```

- Solde **positif** → le groupe lui doit de l'argent (créancier)
- Solde **négatif** → il doit de l'argent au groupe (débiteur)

**Étape 2 — Algorithme glouton O(n log n)**

À chaque itération : le plus gros débiteur rembourse le plus gros créancier du montant minimum des deux. Répète jusqu'à solde zéro. Minimise le nombre de transactions.

```python
from expenses.services import calculer_soldes

resultat = calculer_soldes(groupe)
# {
#   "soldes": [{"utilisateur_id": 1, "username": "alice", "solde": "40.00"}, ...],
#   "remboursements": [{"de": 2, "a": 1, "montant": "40.00"}]
# }
```

---

## Tests

```bash
# Lancer toute la suite de tests
python manage.py test expenses.tests

# Mode verbeux
python manage.py test expenses.tests --verbosity=2

# Une seule classe
python manage.py test expenses.tests.ScenarioComplexeTest
```

**21 tests** couvrant :
- Dépense unique équitable
- Équilibre parfait (0 remboursement)
- Scénario complexe multi-dépenses (minimisation des transactions)
- Membre inactif (solde nul, absent des virements)
- Appel du service par instance ou par ID entier

---

## Structure du projet

```
rendu-django/
├── manage.py
├── requirements.txt
├── .gitignore
│
├── tricount_api/               # Configuration Django
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
└── expenses/                   # Application métier
    ├── models.py               # Groupe, Depense, Part
    ├── serializers.py          # Sérialisation + validation imbriquée
    ├── views.py                # ViewSets (GroupeViewSet, DepenseViewSet)
    ├── services.py             # Logique métier pure (calcul des soldes)
    ├── permissions.py          # IsGroupMember
    ├── urls.py                 # Routeur DRF
    ├── admin.py                # Interface d'administration
    └── tests.py                # Suite de tests unitaires
```

---

## Administration Django

Accessible sur `/admin/` après création d'un superutilisateur.

Fonctionnalités disponibles :
- Gestion des groupes avec sélecteur de membres (`filter_horizontal`)
- Gestion des dépenses avec les parts en ligne (`TabularInline`)
