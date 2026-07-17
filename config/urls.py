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

from dglweb.core.views import home

urlpatterns: list[URLPattern | URLResolver] = [
    path("django-admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("", home, name="home"),
    # Wagtail page-serving catch-all (pages appear in Fase 5).
    path("", include(wagtail_urls)),
]
