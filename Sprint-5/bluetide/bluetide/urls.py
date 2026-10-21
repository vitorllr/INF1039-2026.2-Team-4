"""
URL configuration for bluetide project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path

from bluetideapp import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("pesquisa/", views.pesquisa, name="pesquisa"),
    path("web/", views.mapa_web, name="mapa_web"),
    path("perfil/", views.perfil, name="perfil"),
    path("favoritos/", views.favoritos, name="favoritos"),
    path("faq/", views.duvidas, name="duvidas"),
    path("alertas/", views.alertas, name="alertas")
]