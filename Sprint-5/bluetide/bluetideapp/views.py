from django.shortcuts import render


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
