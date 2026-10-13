from django.shortcuts import render


def home(request):
    return render(request, "mapa.html")


def pesquisa(request):
    return render(request, "pesquisa.html")
