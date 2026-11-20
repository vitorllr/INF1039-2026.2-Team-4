from datetime import timedelta

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from .services.catalog import BEACH_POINTS, BEACH_POINTS_BY_SLUG
from .services.providers import ConditionsService
from .services.recommendations import PROFILE_LABELS, normalize_profile, rank, recommend


FAVORITE_SLUGS = {"ipanema-posto-8", "ipanema-posto-9", "ipanema-posto-10"}


def _age_label(observed_at, now):
    if observed_at is None:
        return "horário indisponível"
    age = max(now - observed_at, timedelta())
    if age < timedelta(hours=1):
        minutes = max(1, int(age.total_seconds() // 60))
        return f"há {minutes} min"
    hours = int(age.total_seconds() // 3600)
    if hours < 48:
        return f"há {hours} h"
    return f"há {age.days} dias"


def _status_presentation(status):
    return {
        "propria": ("Água própria", "success"),
        "impropria": ("Água imprópria", "danger"),
    }.get(status, ("Sem boletim", "neutral"))


def _dataset(request):
    now = timezone.now()
    profile = normalize_profile(request.GET.get("perfil"))
    service = ConditionsService()
    items = []
    for beach in BEACH_POINTS:
        conditions = service.get(beach, now=now)
        recommendation = recommend(conditions, profile=profile, now=now)
        water_label, water_tone = _status_presentation(conditions.water_status)
        items.append(
            {
                "conditions": conditions,
                "recommendation": recommendation,
                "water_label": water_label,
                "water_tone": water_tone,
                "water_age": _age_label(conditions.water_observed_at, now),
                "marine_age": _age_label(conditions.marine_observed_at, now),
                "favorite": beach.slug in FAVORITE_SLUGS,
            }
        )
    items = rank(items)
    data_errors = sorted(
        {
            item["conditions"].provider_error
            for item in items
            if item["conditions"].provider_error
        }
    )
    return {
        "items": items,
        "profile": profile,
        "profile_label": PROFILE_LABELS[profile],
        "profiles": PROFILE_LABELS,
        "data_mode": settings.BLUETIDE_DATA_MODE,
        "is_demo": settings.BLUETIDE_DATA_MODE != "live",
        "data_errors": data_errors,
    }


def home(request):
    return mapa_web(request)


def mapa_web(request):
    return render(request, "mapa.html", _dataset(request))


def pesquisa(request):
    context = _dataset(request)
    query = request.GET.get("q", "").strip().casefold()
    if query:
        context["items"] = [
            item
            for item in context["items"]
            if query in item["conditions"].beach.display_name.casefold()
            or query in item["conditions"].beach.neighborhood.casefold()
        ]
    context["query"] = request.GET.get("q", "").strip()
    return render(request, "pesquisa.html", context)


def perfil(request):
    return render(request, "perfil.html")


def favoritos(request):
    context = _dataset(request)
    context["items"] = [item for item in context["items"] if item["favorite"]]
    return render(request, "favoritos.html", context)


def duvidas(request):
    return render(request, "duvidas_frequentes.html")


def alertas(request):
    return render(request, "alertas.html")


def filtros(request):
    return render(request, "filtro-toggle.html")


def detalhes(request, slug="ipanema-posto-9"):
    if slug not in BEACH_POINTS_BY_SLUG:
        raise Http404("Ponto de praia não encontrado")
    context = _dataset(request)
    context["item"] = next(
        item for item in context["items"] if item["conditions"].beach.slug == slug
    )
    return render(request, "detalhes.html", context)


def comparar(request):
    context = _dataset(request)
    selected = set(request.GET.getlist("ponto"))
    if selected:
        context["items"] = [
            item for item in context["items"] if item["conditions"].beach.slug in selected
        ]
    return render(request, "comparar.html", context)
