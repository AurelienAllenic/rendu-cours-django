from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Depense, Groupe
from .permissions import IsGroupMember
from .serializers import DepenseSerializer, GroupeSerializer


class GroupeViewSet(viewsets.ModelViewSet):
    serializer_class = GroupeSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]

    def get_queryset(self):
        return Groupe.objects.filter(membres=self.request.user)

    def perform_create(self, serializer):
        groupe = serializer.save(createur=self.request.user)
        groupe.membres.add(self.request.user)


class DepenseViewSet(viewsets.ModelViewSet):
    serializer_class = DepenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Depense.objects.filter(groupe__membres=self.request.user)
            .select_related('groupe', 'payeur')
            .prefetch_related('parts__participant')
        )

    def perform_create(self, serializer):
        groupe = serializer.validated_data['groupe']

        if not groupe.membres.filter(pk=self.request.user.pk).exists():
            raise PermissionDenied("Vous n'êtes pas membre de ce groupe.")

        serializer.save()
