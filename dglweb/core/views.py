from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Render the landing page (the approved mock, integrated as a Django template)."""
    return render(request, "home.html")


def health(request: HttpRequest) -> JsonResponse:
    """Liveness probe: is this process up? Does NOT touch the DB (used by the container
    healthcheck, so an upstream/DB blip can't mark a healthy web process as unhealthy)."""
    return JsonResponse({"status": "ok"})
