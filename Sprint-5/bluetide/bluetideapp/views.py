import time
from datetime import timedelta
from urllib.parse import urlsplit

import segno
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    DisableTwoFactorForm,
    LoginCodeForm,
    LoginForm,
    ProfileForm,
    TwoFactorCodeForm,
)
from .security import (
    consume_recovery_code,
    generate_recovery_codes,
    generate_totp_secret,
    hash_recovery_code,
    matching_totp_step,
    provisioning_uri,
)
from .services.catalog import BEACH_POINTS, BEACH_POINTS_BY_SLUG
from .services.providers import ConditionsService
from .services.recommendations import PROFILE_LABELS, normalize_profile, rank, recommend


DEFAULT_FAVORITE_SLUGS = {"ipanema-posto-8", "ipanema-posto-9", "ipanema-posto-10"}
Usuario = get_user_model()


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


def _occupancy_presentation(level):
    return {
        "baixa": ("Ocupação baixa", "low"),
        "media": ("Ocupação média", "medium"),
        "alta": ("Ocupação alta", "high"),
    }.get(level, ("Ocupação indisponível", "unknown"))


def _favorite_slugs(request):
    """Favorites live on the account when signed in and in the session otherwise."""
    if request.user.is_authenticated:
        stored = request.user.pontos_favoritos
    else:
        stored = request.session.get("favorite_slugs", DEFAULT_FAVORITE_SLUGS)
    return {slug for slug in stored if slug in BEACH_POINTS_BY_SLUG}


def _save_favorite_slugs(request, slugs):
    ordered = sorted(slugs)
    if request.user.is_authenticated:
        request.user.pontos_favoritos = ordered
        request.user.save(update_fields=["pontos_favoritos"])
    else:
        request.session["favorite_slugs"] = ordered


def _dataset(request):
    now = timezone.now()
    requested_profile = request.GET.get("perfil")
    if requested_profile is None and request.user.is_authenticated:
        requested_profile = request.user.perfil_praia
    profile = normalize_profile(requested_profile)
    favorite_slugs = _favorite_slugs(request)
    service = ConditionsService()
    items = []
    for beach in BEACH_POINTS:
        conditions = service.get(beach, now=now)
        recommendation = recommend(conditions, profile=profile, now=now)
        water_label, water_tone = _status_presentation(conditions.water_status)
        occupancy_label, occupancy_tone = _occupancy_presentation(
            conditions.occupancy_level
        )
        items.append(
            {
                "conditions": conditions,
                "recommendation": recommendation,
                "water_label": water_label,
                "water_tone": water_tone,
                "water_age": _age_label(conditions.water_observed_at, now),
                "marine_age": _age_label(conditions.marine_observed_at, now),
                "occupancy_label": occupancy_label,
                "occupancy_tone": occupancy_tone,
                "occupancy_age": _age_label(conditions.occupancy_observed_at, now),
                "favorite": beach.slug in favorite_slugs,
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


# Pages that only make sense for a signed-in account. "Voltar" from the login
# screen must never point at them, otherwise it would loop back to login.
ACCOUNT_ONLY_ROUTES = {"perfil", "perfil_editar", "two_factor_setup"}
AUTH_ROUTES = {"login", "login_verify", "logout"}
PENDING_LOGIN_SECONDS = 5 * 60
MAX_CODE_ATTEMPTS = 5


def _local_path(request, candidate):
    """Return a same-site path for ``candidate`` or ``None`` when unsafe."""
    if not candidate or not url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return None
    parts = urlsplit(candidate)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def _route_name(path):
    try:
        return resolve(urlsplit(path).path).url_name
    except Resolver404:
        return None


def _login_back_url(request):
    candidate = _local_path(
        request,
        request.POST.get("back")
        or request.GET.get("back")
        or request.META.get("HTTP_REFERER"),
    )
    if candidate and _route_name(candidate) not in ACCOUNT_ONLY_ROUTES | AUTH_ROUTES | {
        None
    }:
        return candidate
    return reverse("mapa_web")


def _login_next_url(request):
    candidate = _local_path(
        request, request.POST.get("next") or request.GET.get("next")
    )
    if candidate and _route_name(candidate) not in AUTH_ROUTES | {None}:
        return candidate
    return reverse(settings.LOGIN_REDIRECT_URL)


def login_view(request):
    next_url = _login_next_url(request)
    if request.user.is_authenticated:
        return redirect(next_url)

    back_url = _login_back_url(request)
    form = LoginForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        user = form.user
        if user.two_factor_enabled:
            request.session["pending_login"] = {
                "user_id": str(user.pk),
                "next": next_url,
                "started": time.time(),
                "attempts": 0,
            }
            return redirect("login_verify")
        login(request, user)
        messages.success(
            request,
            f"Olá, {user.nome or user.get_username()}. Você entrou na sua conta.",
        )
        return redirect(next_url)
    return render(
        request,
        "login.html",
        {"form": form, "next": next_url, "back": back_url},
    )


def _accept_second_factor(user, form):
    code = form.cleaned_data["code"]
    if form.kind == "totp":
        step = matching_totp_step(
            user.two_factor_secret,
            code,
            after_step=user.two_factor_last_used_step,
        )
        if step is None:
            return False
        # Record the step atomically so the same code cannot be used twice.
        updated = (
            Usuario.objects.filter(pk=user.pk)
            .filter(
                Q(two_factor_last_used_step__isnull=True)
                | Q(two_factor_last_used_step__lt=step)
            )
            .update(two_factor_last_used_step=step)
        )
        return updated == 1

    with transaction.atomic():
        locked = Usuario.objects.select_for_update().get(pk=user.pk)
        remaining = consume_recovery_code(locked.two_factor_recovery_codes, code)
        if remaining is None:
            return False
        locked.two_factor_recovery_codes = remaining
        locked.save(update_fields=["two_factor_recovery_codes"])
    user.two_factor_recovery_codes = remaining
    return True


def login_verify(request):
    pending = request.session.get("pending_login")
    if not pending:
        return redirect("login")
    if time.time() - pending["started"] > PENDING_LOGIN_SECONDS:
        del request.session["pending_login"]
        messages.error(request, "A confirmação expirou. Entre com sua senha novamente.")
        return redirect("login")
    user = Usuario.objects.filter(pk=pending["user_id"], is_active=True).first()
    if user is None or not user.two_factor_enabled:
        del request.session["pending_login"]
        return redirect("login")

    form = LoginCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if _accept_second_factor(user, form):
            del request.session["pending_login"]
            login(request, user)
            if form.kind == "recovery":
                remaining = len(user.two_factor_recovery_codes)
                messages.warning(
                    request,
                    f"Você entrou com um código de recuperação. Restam {remaining}.",
                )
            else:
                messages.success(
                    request,
                    f"Olá, {user.nome or user.get_username()}. Código confirmado.",
                )
            return redirect(pending["next"])
        pending["attempts"] += 1
        remaining_attempts = MAX_CODE_ATTEMPTS - pending["attempts"]
        if remaining_attempts <= 0:
            del request.session["pending_login"]
            messages.error(
                request,
                "Muitas tentativas com código inválido. Entre com sua senha novamente.",
            )
            return redirect("login")
        request.session["pending_login"] = pending
        form.add_error(
            "code",
            "Código inválido ou já usado. "
            f"Confira o autenticador. {remaining_attempts} tentativa{'s' if remaining_attempts > 1 else ''} restante{'s' if remaining_attempts > 1 else ''}.",
        )

    return render(
        request, "login_verify.html", {"form": form, "account_email": user.email}
    )


def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(
            request,
            "Você saiu da conta. O mapa e as condições continuam abertos para consulta.",
        )
        return redirect("mapa_web")
    if not request.user.is_authenticated:
        return redirect("mapa_web")
    return render(request, "logout_confirm.html")


PROFILE_EFFECTS = {
    "tranquilo": "Coloca no topo do mapa e da busca os postos com ondas de até 0,8 m.",
    "surf": "Coloca no topo do mapa e da busca os postos com ondas entre 0,7 m e 1,4 m.",
    "neutro": "Não favorece nenhuma faixa de ondas. A ordem usa só água, chuva, vento e temperatura.",
}
TRANSPORT_EFFECT = (
    "Fica salvo na sua conta. Por enquanto, não muda a ordem dos postos: "
    "ela depende só das condições do mar, da água e do perfil de praia."
)
# Stored preferences whose feature is not built yet say so instead of
# promising an effect the app does not deliver.
SETTING_EFFECTS = {
    "usar_localizacao_celular": (
        "Quando o recurso sair da demonstração, vai mostrar primeiro os postos mais perto de você. "
        "Por enquanto, a localização não é pedida nem usada."
    ),
    "economia_dados": (
        "Evita atualizações em segundo plano. Por enquanto, o BlueTide já só busca condições "
        "quando você abre ou atualiza uma tela."
    ),
    "alertas_mudanca": (
        "Quando os avisos saírem da demonstração, vão indicar se um favorito perder a recomendação. "
        "Por enquanto, nenhum aviso é enviado."
    ),
}


def _preference_effects(user):
    return {
        "perfil_praia": PROFILE_EFFECTS[user.perfil_praia],
        "meio_transporte_preferido": TRANSPORT_EFFECT,
        **SETTING_EFFECTS,
    }


@login_required
def perfil(request):
    return render(
        request,
        "perfil.html",
        {
            "effects": _preference_effects(request.user),
            "recovery_count": len(request.user.two_factor_recovery_codes),
        },
    )


@login_required
def perfil_editar(request):
    previous_photo = request.user.foto.name if request.user.foto else ""
    form = ProfileForm(
        request.POST or None, request.FILES or None, instance=request.user
    )
    photo_dropped = False
    if request.method == "POST":
        if form.is_valid():
            user = form.save()
            if previous_photo and previous_photo != (
                user.foto.name if user.foto else ""
            ):
                user.foto.storage.delete(previous_photo)
            if "perfil_praia" in form.changed_data:
                messages.success(
                    request,
                    "Perfil atualizado. O mapa e a busca já usam o novo perfil de praia.",
                )
            else:
                messages.success(request, "Perfil atualizado.")
            return redirect("perfil")
        # A failed save must not leave half-applied values on the signed-in user.
        request.user.refresh_from_db()
        # Browsers never refill a file input, so a valid photo sent together with
        # an invalid field is lost and the page has to say so.
        photo_dropped = "foto" in request.FILES and "foto" not in form.errors
    return render(
        request,
        "perfil_editar.html",
        {
            "form": form,
            "photo_dropped": photo_dropped,
            "profile_choices": [
                (choice, PROFILE_EFFECTS[choice.data["value"]])
                for choice in form["perfil_praia"]
            ],
            "transport_effect": TRANSPORT_EFFECT,
            "setting_effects": SETTING_EFFECTS,
        },
    )


def _qr_svg(uri):
    return segno.make(uri, error="m").svg_inline(
        scale=5, border=2, dark="#062b42", light="#ffffff"
    )


@login_required
def two_factor_setup(request):
    user = request.user
    action = request.POST.get("action") if request.method == "POST" else None

    if user.two_factor_enabled:
        disable_form = DisableTwoFactorForm(
            request.POST if action == "disable" else None, user=user
        )
        if action == "disable" and disable_form.is_valid():
            user.two_factor_enabled = False
            user.two_factor_secret = ""
            user.two_factor_last_used_step = None
            user.two_factor_recovery_codes = []
            user.save(
                update_fields=(
                    "two_factor_enabled",
                    "two_factor_secret",
                    "two_factor_last_used_step",
                    "two_factor_recovery_codes",
                )
            )
            messages.success(request, "Verificação em duas etapas desativada.")
            return redirect("perfil")
        return render(
            request,
            "two_factor_setup.html",
            {
                "enabled": True,
                "disable_form": disable_form,
                "recovery_count": len(user.two_factor_recovery_codes),
            },
        )

    pending_secret = request.session.get("pending_totp_secret")
    if action == "restart" or not pending_secret:
        pending_secret = generate_totp_secret()
        request.session["pending_totp_secret"] = pending_secret

    code_form = TwoFactorCodeForm(request.POST if action == "activate" else None)
    if action == "activate" and code_form.is_valid():
        step = matching_totp_step(pending_secret, code_form.cleaned_data["code"])
        if step is not None:
            recovery_codes = generate_recovery_codes()
            user.two_factor_secret = pending_secret
            user.two_factor_enabled = True
            user.two_factor_last_used_step = step
            user.two_factor_recovery_codes = [
                hash_recovery_code(code) for code in recovery_codes
            ]
            user.save(
                update_fields=(
                    "two_factor_secret",
                    "two_factor_enabled",
                    "two_factor_last_used_step",
                    "two_factor_recovery_codes",
                )
            )
            del request.session["pending_totp_secret"]
            # Rendered directly, never stored: the plain codes are shown only once.
            return render(
                request, "two_factor_done.html", {"recovery_codes": recovery_codes}
            )
        code_form.add_error(
            "code",
            "Esse código não confere. Use o código atual do autenticador; ele muda a cada 30 segundos.",
        )

    uri = provisioning_uri(pending_secret, user.email)
    return render(
        request,
        "two_factor_setup.html",
        {
            "enabled": False,
            "code_form": code_form,
            "secret": pending_secret,
            "grouped_secret": " ".join(
                pending_secret[index : index + 4]
                for index in range(0, len(pending_secret), 4)
            ),
            "provisioning_uri": uri,
            "qr_svg": _qr_svg(uri),
        },
    )


def favoritos(request):
    context = _dataset(request)
    context["items"] = [item for item in context["items"] if item["favorite"]]
    return render(request, "favoritos.html", context)


def _beach_or_404(slug):
    beach = BEACH_POINTS_BY_SLUG.get(slug)
    if beach is None:
        raise Http404("Ponto de praia não encontrado")
    return beach


def _favorite_response(request, beach, favorite):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "slug": beach.slug,
                "name": beach.display_name,
                "favorite": favorite,
                "count": len(_favorite_slugs(request)),
            }
        )
    destination = _local_path(request, request.POST.get("next")) or reverse("favoritos")
    return redirect(destination)


@require_POST
def favorite_remove(request, slug):
    beach = _beach_or_404(slug)
    favorites = _favorite_slugs(request)
    favorites.discard(slug)
    _save_favorite_slugs(request, favorites)
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        # Without JavaScript the undo offer is rendered by the next page.
        request.session["favorite_undo"] = slug
    return _favorite_response(request, beach, False)


@require_POST
def favorite_restore(request, slug):
    beach = _beach_or_404(slug)
    favorites = _favorite_slugs(request)
    favorites.add(slug)
    _save_favorite_slugs(request, favorites)
    request.session.pop("favorite_undo", None)
    return _favorite_response(request, beach, True)


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
            item
            for item in context["items"]
            if item["conditions"].beach.slug in selected
        ]
    return render(request, "comparar.html", context)
