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
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from bluetideapp import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("pesquisa/", views.pesquisa, name="pesquisa"),
    path("web/", views.mapa_web, name="mapa_web"),
    path("login/", views.login_view, name="login"),
    path("login/codigo/", views.login_verify, name="login_verify"),
    path("logout/", views.logout_view, name="logout"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/editar/", views.perfil_editar, name="perfil_editar"),
    path("perfil/seguranca/2fa/", views.two_factor_setup, name="two_factor_setup"),
    path("favoritos/", views.favoritos, name="favoritos"),
    path("favoritos/<slug:slug>/remover/", views.favorite_remove, name="favorite_remove"),
    path("favoritos/<slug:slug>/restaurar/", views.favorite_restore, name="favorite_restore"),
    path("faq/", views.duvidas, name="duvidas"),
    path("alertas/", views.alertas, name="alertas"),
    path("filtros/", views.filtros, name="filtros"),
    path("comparar/", views.comparar, name="comparar"),
    path("detalhes/", views.detalhes, name="detalhes"),
    path("praias/<slug:slug>/", views.detalhes, name="detalhes_praia"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
