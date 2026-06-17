from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Depense, Groupe
from .permissions import IsGroupMember
from .serializers import DepenseSerializer, GroupeSerializer


class GroupeViewSet(viewsets.ModelViewSet):
    serializer_class = GroupeSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]
    # Utilisé par drf-spectacular pour l'inférence de type (pk = int).
    # get_queryset() filtre réellement les données à l'exécution.
    queryset = Groupe.objects.all()

    def get_queryset(self):
        return Groupe.objects.filter(membres=self.request.user)

    def perform_create(self, serializer):
        groupe = serializer.save(createur=self.request.user)
        groupe.membres.add(self.request.user)


class DepenseViewSet(viewsets.ModelViewSet):
    serializer_class = DepenseSerializer
    permission_classes = [IsAuthenticated]
    # Référence pour drf-spectacular uniquement.
    queryset = Depense.objects.all()

    def get_queryset(self):
        return (
            Depense.objects.filter(groupe__membres=self.request.user)
            .select_related('groupe', 'payeur')
            .prefetch_related('parts__participant')
        )

    def perform_create(self, serializer):
        groupe = serializer.validated_data['groupe']
        payeur = serializer.validated_data['payeur']
        membres_ids = set(groupe.membres.values_list('pk', flat=True))

        if self.request.user.pk not in membres_ids:
            raise PermissionDenied("Vous n'êtes pas membre de ce groupe.")

        if payeur.pk not in membres_ids:
            raise PermissionDenied("Le payeur désigné n'est pas membre de ce groupe.")

        serializer.save()
