from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from expenses.views import dashboard_view, login_view, logout_view, send_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('expenses.urls')),

    # Schéma OpenAPI brut (JSON/YAML téléchargeable)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Interface Swagger UI interactive
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Interface ReDoc (alternative plus lisible)
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Frontend pages
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('send/', send_view, name='send'),
    path('', RedirectView.as_view(url='/dashboard/'), name='home'),
]
