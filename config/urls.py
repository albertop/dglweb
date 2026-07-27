"""Root URL configuration.

- `/`            -> our landing view (the mock, Fase 1). Wagtail-served pages come later.
- `/cms/`        -> Wagtail admin (editorial users).
- `/django-admin/` -> Django admin.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from dglweb.core.views import documento_legal, health, home, pipeline_health, pizarra
from dglweb.stats.staticdata import views as staticdata_views

urlpatterns: list[URLPattern | URLResolver] = [
    path("health", health, name="health"),
    # El semáforo del refresco diario, para un monitor externo. Va público a propósito: quien
    # tiene que verlo es un servicio de afuera, y lo único que expone es si el pipeline corrió.
    path("health/pipeline", pipeline_health, name="pipeline_health"),
    path("django-admin/", admin.site.urls),
    # Las pantallas de carga de datos de apoyo cuelgan del Backoffice y van ANTES del include de
    # Wagtail, que se queda con todo lo demás bajo /cms/.
    path("cms/datos-apoyo/<int:pk>/", staticdata_views.upload, name="staticdata_upload"),
    path("cms/datos-apoyo/<int:pk>/confirmar/", staticdata_views.confirm, name="staticdata_confirm"),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("", home, name="home"),
    # Las tres páginas legales. Rutas fijas y no páginas del CMS a propósito — el porqué está en la
    # vista. Van ANTES del catch-all de Wagtail, que si no se queda con ellas.
    path("legal/<slug:documento>/", documento_legal, name="legal"),
    # El fragmento de la pizarra, que el navegador vuelve a pedir mientras haya juegos vivos.
    path("pizarra/", pizarra, name="pizarra"),
    path("", include("dglweb.profiles.urls")),  # /jugador/<slug>/ — before Wagtail's catch-all
    # Wagtail sirve las páginas: `/articulos/` y `/articulos/<slug>/` salen de acá desde la Fase 5.
    # Antes `/articulos/` era una vista Django con tarjetas de muestra, y estaba declarada ARRIBA de
    # este include, así que le ganaba. Al quitarla, el árbol de Wagtail se queda con esa ruta — que
    # es el punto de tener un CMS: el editor mueve o renombra la página sin tocar este archivo.
    path("", include(wagtail_urls)),
]

# Las imágenes que sube el editor, servidas por Django SOLO en desarrollo. `static()` se anula solo
# cuando `DEBUG` es falso, así que en producción esto no sirve nada: ahí las tiene que servir el
# proxy desde `MEDIA_ROOT`. Sin este par de líneas, en dev el CMS acepta la imagen y después la
# muestra rota, que es de los errores que más tiempo hacen perder porque parece un fallo de Wagtail.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
