from rest_framework.permissions import BasePermission


class IsGroupMember(BasePermission):
    """Autorise l'accès uniquement aux membres du groupe ciblé."""

    message = "Vous n'êtes pas membre de ce groupe."

    def has_object_permission(self, request, view, obj):
        return obj.membres.filter(pk=request.user.pk).exists()
