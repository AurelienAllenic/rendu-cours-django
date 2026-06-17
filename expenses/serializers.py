from decimal import Decimal

from rest_framework import serializers

from .models import Depense, Groupe, Part


class GroupeSerializer(serializers.ModelSerializer):
    createur = serializers.StringRelatedField(read_only=True)
    membres = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Groupe
        fields = ['id', 'nom', 'description', 'date_creation', 'createur', 'membres']
        read_only_fields = ['id', 'date_creation', 'createur', 'membres']


class PartSerializer(serializers.ModelSerializer):
    participant_username = serializers.StringRelatedField(
        source='participant', read_only=True
    )

    class Meta:
        model = Part
        fields = ['id', 'participant', 'participant_username', 'montant_part']


class DepenseSerializer(serializers.ModelSerializer):
    parts = PartSerializer(many=True)
    payeur_username = serializers.StringRelatedField(source='payeur', read_only=True)

    class Meta:
        model = Depense
        fields = [
            'id', 'groupe', 'titre', 'montant',
            'payeur', 'payeur_username', 'date_creation', 'parts',
        ]
        read_only_fields = ['id', 'date_creation']

    def validate(self, data):
        parts = data.get('parts', [])

        if not parts:
            raise serializers.ValidationError(
                {'parts': "Au moins une part est requise."}
            )

        total_parts = sum(Decimal(str(p['montant_part'])) for p in parts)
        montant = Decimal(str(data['montant']))

        if total_parts != montant:
            raise serializers.ValidationError(
                {
                    'parts': (
                        f"La somme des parts ({total_parts} €) "
                        f"doit être égale au montant total ({montant} €)."
                    )
                }
            )

        return data

    def create(self, validated_data):
        parts_data = validated_data.pop('parts')
        depense = Depense.objects.create(**validated_data)
        Part.objects.bulk_create([
            Part(depense=depense, **part) for part in parts_data
        ])
        return depense

    def update(self, instance, validated_data):
        parts_data = validated_data.pop('parts', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if parts_data is not None:
            # Remplacement complet des parts existantes
            instance.parts.all().delete()
            Part.objects.bulk_create([
                Part(depense=instance, **part) for part in parts_data
            ])

        return instance
