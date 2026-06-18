from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Depense, Groupe, Part
from .permissions import IsGroupMember
from .serializers import DepenseSerializer, GroupeSerializer


# ─── API ViewSets ─────────────────────────────────────────────────────────────

class GroupeViewSet(viewsets.ModelViewSet):
    serializer_class = GroupeSerializer
    permission_classes = [IsAuthenticated, IsGroupMember]
    queryset = Groupe.objects.all()

    def get_queryset(self):
        return Groupe.objects.filter(membres=self.request.user)

    def perform_create(self, serializer):
        groupe = serializer.save(createur=self.request.user)
        groupe.membres.add(self.request.user)

    @staticmethod
    def _resoudre_utilisateur(request):
        """
        Extrait et valide le username transmis dans le corps de la requête.

        Returns:
            (user, None)          si l'utilisateur existe ;
            (None, Response(...)) avec le code d'erreur adéquat sinon.
        """
        username = (request.data.get('username') or '').strip()
        if not username:
            return None, Response(
                {'detail': "Le nom d'utilisateur est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return User.objects.get(username=username), None
        except User.DoesNotExist:
            return None, Response(
                {'detail': f"Aucun utilisateur « {username} » n'existe."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Ajoute un membre au groupe via son nom d'utilisateur."""
        groupe = self.get_object()
        user, erreur = self._resoudre_utilisateur(request)
        if erreur:
            return erreur

        if groupe.membres.filter(pk=user.pk).exists():
            return Response(
                {'detail': f"« {user.username} » est déjà membre du groupe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        groupe.membres.add(user)
        return Response(self.get_serializer(groupe).data)

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Retire un membre du groupe via son nom d'utilisateur."""
        groupe = self.get_object()
        user, erreur = self._resoudre_utilisateur(request)
        if erreur:
            return erreur

        if user.pk == groupe.createur_id:
            return Response(
                {'detail': "Le créateur du groupe ne peut pas en être retiré."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not groupe.membres.filter(pk=user.pk).exists():
            return Response(
                {'detail': f"« {user.username} » n'est pas membre du groupe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # On protège l'intégrité des soldes : impossible de retirer un membre
        # déjà impliqué financièrement (en tant que payeur ou participant).
        a_paye = Depense.objects.filter(groupe=groupe, payeur=user).exists()
        a_une_part = Part.objects.filter(
            depense__groupe=groupe, participant=user
        ).exists()
        if a_paye or a_une_part:
            return Response(
                {
                    'detail': (
                        f"« {user.username} » a des dépenses ou des parts dans "
                        "ce groupe et ne peut pas être retiré."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        groupe.membres.remove(user)
        return Response(self.get_serializer(groupe).data)


class DepenseViewSet(viewsets.ModelViewSet):
    serializer_class = DepenseSerializer
    permission_classes = [IsAuthenticated]
    queryset = Depense.objects.all()

    def get_queryset(self):
        qs = (
            Depense.objects.filter(groupe__membres=self.request.user)
            .select_related('groupe', 'payeur')
            .prefetch_related('parts__participant')
        )
        groupe_id = self.request.query_params.get('groupe')
        if groupe_id:
            qs = qs.filter(groupe_id=groupe_id)
        return qs

    def perform_create(self, serializer):
        groupe = serializer.validated_data['groupe']
        payeur = serializer.validated_data['payeur']
        membres_ids = set(groupe.membres.values_list('pk', flat=True))

        if self.request.user.pk not in membres_ids:
            raise PermissionDenied("Vous n'êtes pas membre de ce groupe.")

        if payeur.pk not in membres_ids:
            raise PermissionDenied("Le payeur désigné n'est pas membre de ce groupe.")

        serializer.save()


# ─── Frontend Views ────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    active_tab = 'login'

    if request.method == 'POST':
        action = request.POST.get('action', 'login')
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        active_tab = action

        if action == 'login':
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('dashboard')
            error = "Identifiants incorrects. Vérifiez votre nom d'utilisateur et mot de passe."

        elif action == 'register':
            email = request.POST.get('email', '').strip()
            password2 = request.POST.get('password2', '')
            if not username:
                error = "Le nom d'utilisateur est requis."
            elif len(password) < 8:
                error = "Le mot de passe doit contenir au moins 8 caractères."
            elif password != password2:
                error = "Les mots de passe ne correspondent pas."
            elif User.objects.filter(username=username).exists():
                error = f"Le nom d'utilisateur « {username} » est déjà pris."
            else:
                user = User.objects.create_user(username=username, email=email, password=password)
                login(request, user)
                return redirect('dashboard')

    return render(request, 'expenses/login.html', {'error': error, 'active_tab': active_tab})


@login_required(login_url='/login/')
def dashboard_view(request):
    return render(request, 'expenses/dashboard.html', {'user': request.user})


@login_required(login_url='/login/')
def send_view(request):
    return render(request, 'expenses/send.html', {'user': request.user})


def logout_view(request):
    logout(request)
    return redirect('login')
