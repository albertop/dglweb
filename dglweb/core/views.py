from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Render the landing page (the approved mock, integrated as a Django template)."""
    return render(request, "home.html")
