from django.shortcuts import render
import requests


def home(request):
    return render(request, "mapa.html")


def pesquisa(request):
    return render(request, "pesquisa.html")


def mapa_web(request):
    return render(request, "mapa-web.html")


def perfil(request):
    return render(request, "perfil.html")


def favoritos(request):
    return render(request, "favoritos.html")

def duvidas(request):
    return render(request, "duvidas_frequentes.html")

def alertas(request):
    return render(request, "alertas.html")

#meio que processa a api, através da biblioteca do requests. manda td em json
def detalhes(request):
    resposta = requests.get(
        "https://marine-api.open-meteo.com/v1/marine",
        params={
            "latitude": -22.9868,
            "longitude": -43.2050,
            "current": "wave_height,wave_period,sea_surface_temperature,sea_level_height_msl",
            "timezone": "America/Sao_Paulo",
        },
        timeout=10,
    )
    mar = resposta.json().get("current", {})
    return render(request, "detalhes.html", {"mar": mar})