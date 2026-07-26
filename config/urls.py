"""Root URL configuration.

- `/`            -> our landing view (the mock, Fase 1). Wagtail-served pages come later.
- `/cms/`        -> Wagtail admin (editorial users).
- `/django-admin/` -> Django admin.
"""

from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from dglweb.core.views import health, home
from dglweb.stats.staticdata import views as staticdata_views

urlpatterns: list[URLPattern | URLResolver] = [
    path("health", health, name="health"),
    path("django-admin/", admin.site.urls),
    # Las pantallas de carga de datos de apoyo cuelgan del Backoffice y van ANTES del include de
    # Wagtail, que se queda con todo lo demás bajo /cms/.
    path("cms/datos-apoyo/<int:pk>/", staticdata_views.upload, name="staticdata_upload"),
    path("cms/datos-apoyo/<int:pk>/confirmar/", staticdata_views.confirm, name="staticdata_confirm"),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("", home, name="home"),
    path("", include("dglweb.profiles.urls")),  # /jugador/<slug>/ — before Wagtail's catch-all
    # Wagtail page-serving catch-all (pages appear in Fase 5).
    path("", include(wagtail_urls)),
]
