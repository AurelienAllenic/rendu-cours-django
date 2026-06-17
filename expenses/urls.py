from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DepenseViewSet, GroupeViewSet

router = DefaultRouter()
router.register(r'groupes', GroupeViewSet, basename='groupe')
router.register(r'depenses', DepenseViewSet, basename='depense')

urlpatterns = [
    path('', include(router.urls)),
]
