"""
expenses/services.py

Logique métier pure : calcul des soldes et optimisation des remboursements.

Ce module est volontairement décorrélé de Django REST Framework et des vues.
Il ne manipule que des modèles ORM et des types Python standards (Decimal, dict,
list), ce qui le rend testable de manière totalement isolée.

Exemple de sortie de `calculer_soldes(groupe)` :

    {
        "soldes": [
            {"utilisateur_id": 1, "username": "alice", "solde": "60.00"},
            {"utilisateur_id": 2, "username": "bob",   "solde": "-20.00"},
            {"utilisateur_id": 3, "username": "carol", "solde": "-40.00"},
        ],
        "remboursements": [
            {"de": 3, "a": 1, "montant": "40.00"},
            {"de": 2, "a": 1, "montant": "20.00"},
        ]
    }

    Lecture : carol doit 40 € à alice, bob doit 20 € à alice.
    Deux transactions suffisent à solder un groupe de 3 personnes.
"""

import heapq
from decimal import Decimal

from django.db.models import Sum

from .models import Depense, Groupe, Part

# Seuil en-dessous duquel un solde est considéré comme nul.
# Évite de générer des virements pour des centimes résiduels
# causés par des divisions non exactes en base décimale.
TOLERANCE = Decimal("0.01")


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------

def calculer_soldes(groupe: Groupe | int) -> dict:
    """
    Calcule les soldes nets de chaque membre d'un groupe et retourne
    la liste minimale de virements pour solder tous les comptes.

    Args:
        groupe: Instance de Groupe ou ID entier du groupe.

    Returns:
        Dictionnaire avec deux clés :
        - "soldes"          : liste des soldes nets par membre
        - "remboursements"  : liste des virements suggérés
    """
    if isinstance(groupe, int):
        groupe = Groupe.objects.get(pk=groupe)

    soldes = _calculer_soldes_nets(groupe)
    remboursements = _optimiser_remboursements(soldes)

    return {
        "soldes": [
            {
                "utilisateur_id": uid,
                "username": info["username"],
                # quantize force l'affichage à deux décimales (ex: "5" → "5.00")
                "solde": str(info["solde"].quantize(Decimal("0.01"))),
            }
            for uid, info in soldes.items()
        ],
        "remboursements": remboursements,
    }


# ---------------------------------------------------------------------------
# Étape 1 : Calcul des soldes nets
# ---------------------------------------------------------------------------

def _calculer_soldes_nets(groupe: Groupe) -> dict:
    """
    Calcule le solde net de chaque membre du groupe.

    Formule par membre :
        solde = Σ(dépenses payées par lui) − Σ(ses parts dans toutes les dépenses)

    Un solde positif → le groupe lui doit de l'argent (créancier).
    Un solde négatif → il doit de l'argent au groupe (débiteur).

    Deux requêtes SQL agrégées suffisent, quel que soit le nombre de dépenses.
    Aucun risque de requêtes N+1.

    Returns:
        {
            user_id: {"username": str, "solde": Decimal},
            ...
        }
    """
    # Initialise tous les membres à 0, y compris ceux sans dépense ni part.
    # Ainsi un membre qui n'a rien fait apparaît quand même dans les résultats.
    soldes = {
        membre.pk: {"username": membre.username, "solde": Decimal("0")}
        for membre in groupe.membres.all()
    }

    # --- Requête 1 : total payé par chaque payeur dans ce groupe ---
    #
    # SELECT payeur_id, SUM(montant) AS total
    # FROM expenses_depense
    # WHERE groupe_id = %s
    # GROUP BY payeur_id
    payes = (
        Depense.objects.filter(groupe=groupe)
        .values("payeur_id")
        .annotate(total=Sum("montant"))
    )
    for row in payes:
        uid = row["payeur_id"]
        if uid in soldes:
            # On passe par str() avant Decimal pour éviter les imprécisions
            # liées à la conversion directe depuis un float Django peut renvoyer.
            soldes[uid]["solde"] += Decimal(str(row["total"]))

    # --- Requête 2 : total des parts dues par chaque participant ---
    #
    # SELECT participant_id, SUM(montant_part) AS total
    # FROM expenses_part
    # JOIN expenses_depense ON depense_id = expenses_depense.id
    # WHERE groupe_id = %s
    # GROUP BY participant_id
    dus = (
        Part.objects.filter(depense__groupe=groupe)
        .values("participant_id")
        .annotate(total=Sum("montant_part"))
    )
    for row in dus:
        uid = row["participant_id"]
        if uid in soldes:
            soldes[uid]["solde"] -= Decimal(str(row["total"]))

    return soldes


# ---------------------------------------------------------------------------
# Étape 2 : Algorithme glouton de minimisation des transactions
# ---------------------------------------------------------------------------

def _optimiser_remboursements(soldes: dict) -> list:
    """
    Génère la liste minimale de virements pour équilibrer tous les soldes.

    Algorithme glouton (greedy) :
    ─────────────────────────────
    À chaque itération :
      1. Prendre le plus gros créancier  (celui qui a le solde positif le plus élevé).
      2. Prendre le plus gros débiteur   (celui dont le solde négatif est le plus bas).
      3. Le débiteur vire au créancier : min(solde_créancier, |solde_débiteur|).
      4. Mettre à jour leurs soldes et répéter jusqu'à ce que tout soit soldé.

    Implémentation via deux tas (heaps) pour une complexité O(n log n) :
      - `crediteurs` : tas max simulé (on stocke les valeurs négatives dans un
                       tas min Python) → heappop donne toujours le plus gros solde.
      - `debiteurs`  : même principe → heappop donne la dette la plus élevée.

    Note : cet algorithme n'est pas toujours optimal au sens mathématique strict
    (le problème général est NP-complet), mais il produit en pratique le minimum
    ou quasi-minimum de transactions pour des groupes de taille raisonnable.

    Args:
        soldes: Dictionnaire issu de _calculer_soldes_nets().

    Returns:
        [{"de": user_id, "a": user_id, "montant": "XX.XX"}, ...]
    """
    remboursements = []

    # ── Construction des tas ────────────────────────────────────────────────
    #
    # Tas des créanciers : stocker (-solde, uid) pour simuler un max-heap.
    # Exemple : Alice avec solde +60 → (-60, alice_id) dans le tas.
    # heappop donnera le tuple le plus petit, soit celui avec -solde le plus
    # petit, soit le solde réel le plus grand. ✓
    crediteurs: list = []

    # Tas des débiteurs : stocker (solde, uid) — le solde est déjà négatif,
    # donc heappop donne naturellement la valeur la plus négative = plus grosse dette. ✓
    debiteurs: list = []

    for uid, info in soldes.items():
        solde = info["solde"]
        if solde > TOLERANCE:
            heapq.heappush(crediteurs, (-solde, uid))
        elif solde < -TOLERANCE:
            heapq.heappush(debiteurs, (solde, uid))
        # Solde dans [-TOLERANCE, +TOLERANCE] → considéré nul, ignoré.

    # ── Boucle principale ───────────────────────────────────────────────────
    while crediteurs and debiteurs:

        # Plus gros créancier
        neg_solde_cred, uid_cred = heapq.heappop(crediteurs)
        solde_cred = -neg_solde_cred               # repasse en positif

        # Plus gros débiteur (valeur la plus négative = dette la plus haute)
        solde_deb_neg, uid_deb = heapq.heappop(debiteurs)
        montant_du = -solde_deb_neg                # valeur absolue de la dette

        # Le virement est limité par le minimum des deux montants :
        #   - On ne peut pas rembourser plus que ce que le débiteur doit.
        #   - On ne peut pas recevoir plus que ce que le créancier attend.
        montant_virement = min(solde_cred, montant_du)

        remboursements.append({
            "de": uid_deb,
            "a": uid_cred,
            "montant": str(montant_virement.quantize(Decimal("0.01"))),
        })

        # ── Mise à jour des soldes résiduels ────────────────────────────────
        solde_cred_restant = solde_cred - montant_virement
        montant_du_restant = montant_du - montant_virement

        # Le créancier réintègre le tas seulement s'il lui reste de l'argent à recevoir.
        if solde_cred_restant > TOLERANCE:
            heapq.heappush(crediteurs, (-solde_cred_restant, uid_cred))

        # Le débiteur réintègre le tas seulement s'il a encore une dette résiduelle.
        if montant_du_restant > TOLERANCE:
            # On repasse en valeur négative pour respecter la convention du tas.
            heapq.heappush(debiteurs, (-montant_du_restant, uid_deb))

    return remboursements
