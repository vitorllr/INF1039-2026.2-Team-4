from django.shortcuts import render


def mapa(request):
    return render(request, 'core/mapa.html')
