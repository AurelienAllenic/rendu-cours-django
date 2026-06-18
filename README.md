# Tricount API

API REST de partage de dépenses entre amis, développée avec **Django 5.1** et **Django REST Framework 3.15**.

---

## Fonctionnalités

- Création et gestion de **groupes** avec membres
- **Ajout / retrait de membres** d'un groupe existant, avec **autocomplétion** des utilisateurs
- Enregistrement de **dépenses** avec répartition personnalisée des parts
- Calcul automatique des **soldes nets** par membre
- Algorithme glouton de **minimisation des remboursements**
- **Interface web moderne** (login, dashboard, ajout de dépense)
- Documentation API interactive (Swagger UI & ReDoc)
- Suite de tests unitaires complète

---

## Stack technique

| Composant | Technologie |
|---|---|
| Framework | Django 5.1 + Django REST Framework 3.15 |
| Base de données | SQLite (dev) |
| Interface web | Templates Django + Vanilla JS (fetch API) |
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

### 6. Charger les données de démo (optionnel)

Une fixture prête à l'emploi crée **5 utilisateurs de test**, 2 groupes et plusieurs dépenses cohérentes :

```bash
python manage.py loaddata demo_data
```

Les 5 comptes utilisent tous le mot de passe **`password`** :

| username | mot de passe |
|---|---|
| `alice` | `password` |
| `bob` | `password` |
| `charlie` | `password` |
| `diana` | `password` |
| `evan` | `password` |

Tu peux ensuite te connecter sur `/login/` avec n'importe lequel de ces comptes.

> **Notes** : les PK sont fixées à partir de `9001` pour éviter toute collision avec des données existantes — relancer `loaddata demo_data` réinitialise donc le jeu de démo (idempotent). Le fichier source est `expenses/fixtures/demo_data.json`.

### 7. Lancer le serveur de développement

```bash
python manage.py runserver
```

---

## Interface web

L'application dispose d'une interface web moderne accessible directement depuis le navigateur, sans client séparé.

### Pages disponibles

| URL | Page | Description |
|---|---|---|
| `/` | — | Redirige vers `/dashboard/` |
| `/login/` | Connexion / Inscription | Formulaire avec onglets, gestion d'erreurs |
| `/dashboard/` | Dashboard groupe | Soldes membres, remboursements suggérés, historique des dépenses, création de groupe |
| `/send/` | Nouvelle dépense | Formulaire d'ajout avec répartition égale ou personnalisée en temps réel |
| `/logout/` | — | Déconnexion et redirection vers `/login/` |

### Fonctionnement

- L'authentification repose sur les **sessions Django** (cookie de session). Les pages `/dashboard/` et `/send/` nécessitent d'être connecté.
- Les pages communiquent avec l'API REST via **fetch** côté client, en transmettant le token CSRF dans les en-têtes.
- Les soldes et remboursements sont **calculés côté frontend** à partir des données renvoyées par `/api/depenses/`.
- Le filtre `?groupe=<id>` sur `/api/depenses/` permet de charger uniquement les dépenses d'un groupe sélectionné.

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
| `GET` | `/api/groupes/{id}/search_users/?q=<texte>` | Autocomplétion : utilisateurs non-membres correspondant à `q` (max 8) |
| `POST` | `/api/groupes/{id}/add_member/` | Ajouter un membre via `{"username": "..."}` |
| `POST` | `/api/groupes/{id}/remove_member/` | Retirer un membre via `{"username": "..."}` |

> **Gestion des membres** : le créateur ne peut pas être retiré, et un membre déjà impliqué financièrement (payeur ou détenteur d'une part) est protégé contre le retrait pour préserver l'intégrité des soldes. La gestion se fait aussi depuis le dashboard via le bouton **« Gérer »**.

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

> **Note** : le champ `membres_detail` a été ajouté à la réponse de `/api/groupes/` et `/api/groupes/{id}/`. Il expose `[{"id": 1, "username": "alice"}, …]` en lecture seule, en complément du champ `membres` existant (liste de chaînes).

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

**32 tests** couvrant :
- Dépense unique équitable
- Équilibre parfait (0 remboursement)
- Scénario complexe multi-dépenses (minimisation des transactions)
- Membre inactif (solde nul, absent des virements)
- Appel du service par instance ou par ID entier
- API de gestion des membres (ajout, retrait, protections, permissions, autocomplétion)

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
│   ├── urls.py                 # Routes API + pages frontend
│   ├── wsgi.py
│   └── asgi.py
│
└── expenses/                   # Application métier
    ├── models.py               # Groupe, Depense, Part
    ├── serializers.py          # Sérialisation + validation imbriquée + membres_detail
    ├── views.py                # ViewSets API + vues frontend (login, dashboard, send)
    ├── services.py             # Logique métier pure (calcul des soldes)
    ├── permissions.py          # IsGroupMember
    ├── urls.py                 # Routeur DRF
    ├── admin.py                # Interface d'administration
    ├── tests.py                # Suite de tests unitaires
    ├── fixtures/
    │   └── demo_data.json      # Données de démo (5 users, groupes, dépenses)
    └── templates/
        └── expenses/
            ├── login.html      # Page connexion / inscription
            ├── dashboard.html  # Dashboard groupe (soldes, remboursements, dépenses)
            └── send.html       # Formulaire d'ajout de dépense
```

---

## Administration Django

Accessible sur `/admin/` après création d'un superutilisateur.

Fonctionnalités disponibles :
- Gestion des groupes avec sélecteur de membres (`filter_horizontal`)
- Gestion des dépenses avec les parts en ligne (`TabularInline`)
