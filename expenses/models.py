from django.contrib.auth.models import User
from django.db import models


class Groupe(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    date_creation = models.DateTimeField(auto_now_add=True)

    createur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='groupes_crees',
    )
    membres = models.ManyToManyField(
        User,
        related_name='groupes',
        blank=True,
    )

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Groupe'
        verbose_name_plural = 'Groupes'

    def __str__(self):
        return self.nom


class Depense(models.Model):
    groupe = models.ForeignKey(
        Groupe,
        on_delete=models.CASCADE,
        related_name='depenses',
    )
    titre = models.CharField(max_length=255)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    payeur = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='depenses_payees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    # M2M explicite via la table Part (through) pour stocker montant_part
    participants = models.ManyToManyField(
        User,
        through='Part',
        related_name='depenses_participees',
    )

    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'Dépense'
        verbose_name_plural = 'Dépenses'

    def __str__(self):
        return f"{self.titre} ({self.groupe})"


class Part(models.Model):
    depense = models.ForeignKey(
        Depense,
        on_delete=models.CASCADE,
        related_name='parts',
    )
    participant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='parts',
    )
    montant_part = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        # Un participant ne peut apparaître qu'une fois par dépense
        unique_together = [('depense', 'participant')]
        verbose_name = 'Part'
        verbose_name_plural = 'Parts'

    def __str__(self):
        return f"{self.participant} → {self.montant_part} € ({self.depense})"
