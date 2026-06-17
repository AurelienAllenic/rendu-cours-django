from django.contrib import admin

from .models import Depense, Groupe, Part


class PartInline(admin.TabularInline):
    model = Part
    extra = 1
    fields = ['participant', 'montant_part']


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    inlines = [PartInline]
    list_display = ['titre', 'groupe', 'montant', 'payeur', 'date_creation']
    list_filter = ['groupe']
    search_fields = ['titre', 'payeur__username']
    readonly_fields = ['date_creation']


@admin.register(Groupe)
class GroupeAdmin(admin.ModelAdmin):
    list_display = ['nom', 'createur', 'date_creation']
    filter_horizontal = ['membres']
    readonly_fields = ['date_creation']


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['depense', 'participant', 'montant_part']
    list_filter = ['depense__groupe']
