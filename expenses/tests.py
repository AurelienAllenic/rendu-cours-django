"""
expenses/tests.py

Suite de tests unitaires pour la logique métier de `expenses/services.py`.

Chaque test est autonome : setUp recrée une base vide grâce à TestCase
(Django enroule chaque test dans une transaction rollbackée).

Couverture :
  - Test 1 : Dépense unique équitable (cas de base de l'énoncé)
  - Test 2 : Équilibre parfait → aucun remboursement attendu
  - Test 3 : Scénario complexe multi-dépenses → minimisation des transactions
  - Test 4 : Membre inactif → solde nul, absent des virements
  - Test 5 : Appel par ID entier (groupe_id) au lieu d'une instance

Commande pour lancer uniquement cette suite :
    python manage.py test expenses.tests
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Depense, Groupe, Part
from .services import calculer_soldes


class CalculSoldesTestCase(TestCase):
    """Classe de base commune : utilisateurs + groupe partagés entre les tests."""

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _creer_depense(self, groupe, titre, montant, payeur, parts):
        """
        Crée une Depense et ses Parts en une seule opération.

        Args:
            parts: liste de tuples (user, montant_part: Decimal)
        """
        depense = Depense.objects.create(
            groupe=groupe,
            titre=titre,
            montant=Decimal(str(montant)),
            payeur=payeur,
        )
        Part.objects.bulk_create([
            Part(depense=depense, participant=user, montant_part=Decimal(str(mp))
            ) for user, mp in parts
        ])
        return depense

    def _solde(self, resultat, user):
        """Extrait le solde Decimal d'un utilisateur depuis le résultat du service."""
        for entry in resultat["soldes"]:
            if entry["utilisateur_id"] == user.pk:
                return Decimal(entry["solde"])
        self.fail(f"Utilisateur '{user.username}' absent des soldes retournés.")

    def _ids_impliques(self, resultat):
        """Retourne l'ensemble des user_id présents dans les remboursements."""
        rembs = resultat["remboursements"]
        return {r["de"] for r in rembs} | {r["a"] for r in rembs}

    # ── setUp ──────────────────────────────────────────────────────────────────

    def setUp(self):
        """
        Crée 4 utilisateurs et un groupe commun avant chaque test.
        Les PKs sont auto-incrémentés dans l'ordre de création :
        alice < bob < carol < dave — important pour prévoir l'ordre dans les heaps.
        """
        self.alice = User.objects.create_user("alice", password="pass")
        self.bob   = User.objects.create_user("bob",   password="pass")
        self.carol = User.objects.create_user("carol", password="pass")
        self.dave  = User.objects.create_user("dave",  password="pass")

        self.groupe = Groupe.objects.create(nom="Groupe Test", createur=self.alice)
        self.groupe.membres.add(self.alice, self.bob, self.carol, self.dave)


# ==============================================================================
# Test 1 — Dépense unique, répartition équitable
# ==============================================================================

class DepenseUniqueEquitableTest(CalculSoldesTestCase):
    """
    Scénario : Alice paie 30 € pour un repas partagé à parts égales
               entre Alice, Bob et Carol (10 € chacun).

    Soldes attendus :
        Alice  : +30 payé  − 10 dû  = +20 €  (créancière)
        Bob    :   0 payé  − 10 dû  = −10 €  (débiteur)
        Carol  :   0 payé  − 10 dû  = −10 €  (débitrice)
        Dave   :   0 payé  −  0 dû  =   0 €  (inactif dans cette dépense)

    Remboursements attendus (ordre greedy — Bob a le pk le plus bas) :
        Bob  → Alice : 10 €
        Carol→ Alice : 10 €
    """

    def setUp(self):
        super().setUp()
        self._creer_depense(
            groupe=self.groupe,
            titre="Repas",
            montant="30.00",
            payeur=self.alice,
            parts=[
                (self.alice, "10.00"),
                (self.bob,   "10.00"),
                (self.carol, "10.00"),
            ],
        )
        self.resultat = calculer_soldes(self.groupe)

    def test_solde_creanciere_alice(self):
        self.assertEqual(self._solde(self.resultat, self.alice), Decimal("20.00"))

    def test_solde_debiteur_bob(self):
        self.assertEqual(self._solde(self.resultat, self.bob), Decimal("-10.00"))

    def test_solde_debitrice_carol(self):
        self.assertEqual(self._solde(self.resultat, self.carol), Decimal("-10.00"))

    def test_nombre_de_remboursements(self):
        """Exactement 2 virements pour solder 3 participants actifs."""
        self.assertEqual(len(self.resultat["remboursements"]), 2)

    def test_montants_des_remboursements(self):
        """Bob et Carol versent chacun 10 € à Alice."""
        rembs = self.resultat["remboursements"]

        # Construit un mapping débiteur → montant pour des assertions indépendantes
        # de l'ordre de sortie du greedy.
        montant_par_debiteur = {r["de"]: Decimal(r["montant"]) for r in rembs}

        self.assertEqual(montant_par_debiteur[self.bob.pk],   Decimal("10.00"))
        self.assertEqual(montant_par_debiteur[self.carol.pk], Decimal("10.00"))

    def test_destinataire_unique_alice(self):
        """Alice est la seule créancière : tous les virements lui sont destinés."""
        destinataires = {r["a"] for r in self.resultat["remboursements"]}
        self.assertEqual(destinataires, {self.alice.pk})


# ==============================================================================
# Test 2 — Équilibre parfait
# ==============================================================================

class EquilibreParfaitTest(CalculSoldesTestCase):
    """
    Scénario : 3 dépenses symétriques où chacun paie 30 € et doit 30 €.

        Dépense d'Alice  : Alice paie 30 € → parts Alice 10, Bob 10, Carol 10
        Dépense de Bob   : Bob   paie 30 € → parts Alice 10, Bob 10, Carol 10
        Dépense de Carol : Carol paie 30 € → parts Alice 10, Bob 10, Carol 10

    Soldes attendus :
        Chacun : payé 30 € − dû 30 € = 0 €

    Remboursements attendus : aucun.
    """

    def setUp(self):
        super().setUp()
        for payeur in [self.alice, self.bob, self.carol]:
            self._creer_depense(
                groupe=self.groupe,
                titre=f"Dépense de {payeur.username}",
                montant="30.00",
                payeur=payeur,
                parts=[
                    (self.alice, "10.00"),
                    (self.bob,   "10.00"),
                    (self.carol, "10.00"),
                ],
            )
        self.resultat = calculer_soldes(self.groupe)

    def test_tous_les_soldes_a_zero(self):
        for user in [self.alice, self.bob, self.carol]:
            with self.subTest(user=user.username):
                self.assertEqual(self._solde(self.resultat, user), Decimal("0.00"))

    def test_aucun_remboursement_genere(self):
        self.assertEqual(self.resultat["remboursements"], [])


# ==============================================================================
# Test 3 — Scénario complexe multi-dépenses
# ==============================================================================

class ScenarioComplexeTest(CalculSoldesTestCase):
    """
    Scénario : Alice avance 90 €, Bob avance 30 €, parts équitables à 3.

        Dépense 1 — Alice paie 90 € → parts Alice 30, Bob 30, Carol 30
        Dépense 2 — Bob   paie 30 € → parts Alice 10, Bob 10, Carol 10

    Soldes attendus :
        Alice  : payé 90 − dû (30+10)=40  → +50 €
        Bob    : payé 30 − dû (30+10)=40  → −10 €
        Carol  : payé  0 − dû (30+10)=40  → −40 €

    Trace de l'algorithme glouton :
        Itération 1 → plus gros créancier : Alice (+50)
                       plus gros débiteur  : Carol (−40)
                       Virement Carol → Alice : 40 €
                       Alice résiduel : +10, Carol : soldée
        Itération 2 → plus gros créancier : Alice (+10)
                       plus gros débiteur  : Bob   (−10)
                       Virement Bob → Alice : 10 €
                       Tous soldés.

    → 2 transactions (optimal : n−1 pour n participants déséquilibrés).
    """

    def setUp(self):
        super().setUp()
        self._creer_depense(
            groupe=self.groupe,
            titre="Week-end ski",
            montant="90.00",
            payeur=self.alice,
            parts=[
                (self.alice, "30.00"),
                (self.bob,   "30.00"),
                (self.carol, "30.00"),
            ],
        )
        self._creer_depense(
            groupe=self.groupe,
            titre="Essence",
            montant="30.00",
            payeur=self.bob,
            parts=[
                (self.alice, "10.00"),
                (self.bob,   "10.00"),
                (self.carol, "10.00"),
            ],
        )
        self.resultat = calculer_soldes(self.groupe)

    def test_solde_alice(self):
        self.assertEqual(self._solde(self.resultat, self.alice), Decimal("50.00"))

    def test_solde_bob(self):
        self.assertEqual(self._solde(self.resultat, self.bob), Decimal("-10.00"))

    def test_solde_carol(self):
        self.assertEqual(self._solde(self.resultat, self.carol), Decimal("-40.00"))

    def test_nombre_minimal_de_transactions(self):
        """L'algorithme glouton produit 2 transactions et non 3."""
        self.assertEqual(len(self.resultat["remboursements"]), 2)

    def test_total_vire_egal_somme_soldes_positifs(self):
        """La somme des virements doit couvrir exactement les créances positives."""
        total = sum(Decimal(r["montant"]) for r in self.resultat["remboursements"])
        self.assertEqual(total, Decimal("50.00"))

    def test_remboursements_specifiques(self):
        """Vérifie les montants exacts produits par le greedy."""
        rembs = self.resultat["remboursements"]
        montant_par_debiteur = {r["de"]: Decimal(r["montant"]) for r in rembs}

        self.assertEqual(montant_par_debiteur[self.carol.pk], Decimal("40.00"))
        self.assertEqual(montant_par_debiteur[self.bob.pk],   Decimal("10.00"))

    def test_soldes_residuels_nuls_apres_application(self):
        """
        Simule l'application de chaque virement sur les soldes initiaux.
        Si l'algorithme est correct, tous les soldes finaux doivent être nuls.
        """
        soldes_sim = {
            self.alice.pk: Decimal("50.00"),
            self.bob.pk:   Decimal("-10.00"),
            self.carol.pk: Decimal("-40.00"),
        }

        for r in self.resultat["remboursements"]:
            montant = Decimal(r["montant"])
            soldes_sim[r["de"]] += montant   # le débiteur paie → son solde remonte
            soldes_sim[r["a"]]  -= montant   # le créancier reçoit → sa créance baisse

        for uid, solde_final in soldes_sim.items():
            with self.subTest(user_id=uid):
                self.assertEqual(
                    solde_final,
                    Decimal("0.00"),
                    msg=f"Solde résiduel non nul pour user_id={uid} : {solde_final} €",
                )


# ==============================================================================
# Test 4 — Membre inactif
# ==============================================================================

class MembreInactifTest(CalculSoldesTestCase):
    """
    Scénario : Dave est membre du groupe mais n'apparaît dans
               aucune dépense en tant que payeur ni participant.

    Attendus :
        - Dave figure dans les soldes avec 0 €.
        - Dave n'est ni émetteur ni destinataire d'aucun virement.
    """

    def setUp(self):
        super().setUp()
        # Dépense sans Dave
        self._creer_depense(
            groupe=self.groupe,
            titre="Pizza",
            montant="30.00",
            payeur=self.alice,
            parts=[
                (self.alice, "10.00"),
                (self.bob,   "10.00"),
                (self.carol, "10.00"),
            ],
        )
        self.resultat = calculer_soldes(self.groupe)

    def test_dave_present_dans_les_soldes(self):
        """Dave doit apparaître dans la liste des soldes (initialisé à zéro)."""
        ids = [s["utilisateur_id"] for s in self.resultat["soldes"]]
        self.assertIn(self.dave.pk, ids)

    def test_solde_dave_est_zero(self):
        self.assertEqual(self._solde(self.resultat, self.dave), Decimal("0.00"))

    def test_dave_absent_des_remboursements(self):
        self.assertNotIn(self.dave.pk, self._ids_impliques(self.resultat))


# ==============================================================================
# Test 5 — Appel par groupe_id (int) plutôt que par instance
# ==============================================================================

class AppelParIdTest(CalculSoldesTestCase):
    """
    Vérifie que calculer_soldes() accepte indifféremment une instance Groupe
    ou un entier (pk), comme documenté dans la signature de la fonction.
    """

    def setUp(self):
        super().setUp()
        self._creer_depense(
            groupe=self.groupe,
            titre="Transport",
            montant="20.00",
            payeur=self.alice,
            parts=[
                (self.alice, "10.00"),
                (self.bob,   "10.00"),
            ],
        )

    def test_appel_avec_instance(self):
        resultat = calculer_soldes(self.groupe)
        self.assertEqual(self._solde(resultat, self.alice), Decimal("10.00"))

    def test_appel_avec_id_entier(self):
        resultat = calculer_soldes(self.groupe.pk)
        self.assertEqual(self._solde(resultat, self.alice), Decimal("10.00"))

    def test_resultats_identiques_instance_vs_id(self):
        """Les deux formes d'appel doivent produire exactement le même résultat."""
        par_instance = calculer_soldes(self.groupe)
        par_id       = calculer_soldes(self.groupe.pk)
        self.assertEqual(par_instance, par_id)
