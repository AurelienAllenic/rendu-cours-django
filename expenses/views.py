from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .models import Depense, Groupe
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
