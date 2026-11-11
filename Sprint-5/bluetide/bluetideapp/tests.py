import base64
import io
import json
import shutil
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .security import (
    consume_recovery_code,
    generate_recovery_codes,
    hash_recovery_code,
    matching_totp_step,
    totp_code,
    verify_totp,
)
from .services.catalog import BEACH_POINTS
from .services.providers import (
    ConditionsService,
    FixtureConditionsProvider,
    OpenMeteoProvider,
)
from .services.recommendations import rank, recommend


NOW = timezone.make_aware(datetime(2026, 11, 8, 12, 0))


class RecommendationTests(SimpleTestCase):
    def setUp(self):
        self.conditions = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=NOW)

    def test_complete_safe_point_is_explainable_and_recommended(self):
        result = recommend(self.conditions, "tranquilo", now=NOW)

        self.assertTrue(result.available)
        self.assertEqual(result.label, "Melhor escolha")
        self.assertGreaterEqual(len(result.reasons), 3)
        self.assertIn("Ondas baixas", " ".join(result.reasons))

    def test_missing_water_quality_blocks_recommendation(self):
        result = recommend(
            replace(self.conditions, water_status=None, water_observed_at=None),
            "tranquilo",
            now=NOW,
        )

        self.assertFalse(result.available)
        self.assertIn("Não há boletim", result.blockers[0])

    def test_stale_water_quality_blocks_recommendation(self):
        stale = replace(self.conditions, water_observed_at=NOW - timedelta(days=9))

        result = recommend(stale, "tranquilo", now=NOW)

        self.assertFalse(result.available)
        self.assertTrue(any("desatualizado" in blocker for blocker in result.blockers))

    def test_incomplete_marine_fields_block_recommendation(self):
        result = recommend(
            replace(self.conditions, wind_speed=None), "tranquilo", now=NOW
        )

        self.assertFalse(result.available)
        self.assertTrue(any("vento" in blocker for blocker in result.blockers))

    def test_improper_water_and_heavy_rain_never_recommend(self):
        unsafe = replace(self.conditions, water_status="impropria", rain_24h=25)

        result = recommend(unsafe, "surf", now=NOW)

        self.assertFalse(result.available)
        self.assertTrue(any("imprópria" in blocker for blocker in result.blockers))
        self.assertTrue(any("chuva intensa" in blocker for blocker in result.blockers))

    def test_fallback_values_are_visible_but_not_recommended(self):
        fallback = replace(self.conditions, origin="fallback", provider_error="timeout")

        result = recommend(fallback, "tranquilo", now=NOW)

        self.assertFalse(result.available)
        self.assertTrue(
            any("integração de dados" in blocker for blocker in result.blockers)
        )

    def test_ranking_is_deterministic_and_puts_unavailable_points_last(self):
        best = recommend(self.conditions, "tranquilo", now=NOW)
        unavailable_conditions = replace(self.conditions, water_status=None)
        unavailable = recommend(unavailable_conditions, "tranquilo", now=NOW)
        items = [
            {"conditions": unavailable_conditions, "recommendation": unavailable},
            {"conditions": self.conditions, "recommendation": best},
        ]

        first = rank(items)
        second = rank(list(reversed(items)))

        self.assertEqual(first, second)
        self.assertTrue(first[0]["recommendation"].available)
        self.assertFalse(first[-1]["recommendation"].available)

    def test_map_positions_follow_geographic_coordinates(self):
        points_west_to_east = sorted(BEACH_POINTS, key=lambda point: point.longitude)
        points_north_to_south = sorted(
            BEACH_POINTS, key=lambda point: point.latitude, reverse=True
        )

        self.assertEqual(
            [point.posto for point in points_west_to_east],
            ["Posto 11", "Posto 10", "Posto 9", "Posto 8", "Posto 7"],
        )
        self.assertEqual(
            sorted(point.map_x for point in points_west_to_east),
            [point.map_x for point in points_west_to_east],
        )
        self.assertEqual(
            sorted(point.map_y for point in points_north_to_south),
            [point.map_y for point in points_north_to_south],
        )
        self.assertLess(
            max(point.map_y for point in BEACH_POINTS)
            - min(point.map_y for point in BEACH_POINTS),
            300,
        )
        self.assertGreater(
            max(point.map_x for point in BEACH_POINTS)
            - min(point.map_x for point in BEACH_POINTS),
            2700,
        )


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class ProviderTests(SimpleTestCase):
    def test_fixture_contains_absent_stale_and_incomplete_examples(self):
        provider = FixtureConditionsProvider()
        conditions = [provider.fetch(point, now=NOW) for point in BEACH_POINTS]

        self.assertTrue(any(item.water_status is None for item in conditions))
        self.assertTrue(
            any(
                NOW - item.water_observed_at > timedelta(days=8)
                for item in conditions
                if item.water_observed_at
            )
        )
        self.assertTrue(any(item.wind_speed is None for item in conditions))

    @patch("bluetideapp.services.providers.urlopen")
    def test_open_meteo_adapter_requests_and_maps_only_needed_fields(
        self, mocked_urlopen
    ):
        marine_payload = {
            "current": {
                "time": "2026-11-08T11:30",
                "wave_height": 0.7,
                "wave_period": 8,
                "sea_surface_temperature": 23.2,
                "sea_level_height_msl": 0.4,
            }
        }
        weather_payload = {
            "current": {"temperature_2m": 28.0, "wind_speed_10m": 12.0},
            "hourly": {
                "time": ["2026-11-08T10:00", "2026-11-08T11:00"],
                "precipitation": [0.2, 0.3],
            },
        }
        mocked_urlopen.side_effect = [
            FakeResponse(json.dumps(marine_payload).encode()),
            FakeResponse(json.dumps(weather_payload).encode()),
        ]
        base = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=NOW)

        result = OpenMeteoProvider(timeout=2).fetch(BEACH_POINTS[1], base=base, now=NOW)

        self.assertEqual(result.origin, "live")
        self.assertEqual(result.wave_height, 0.7)
        self.assertEqual(result.rain_24h, 0.5)
        self.assertEqual(result.wind_speed, 12.0)
        self.assertEqual(mocked_urlopen.call_count, 2)
        self.assertTrue(
            all(call.kwargs["timeout"] == 2 for call in mocked_urlopen.call_args_list)
        )

    @override_settings(BLUETIDE_DATA_MODE="live")
    def test_service_falls_back_without_raising_on_timeout(self):
        live_provider = type(
            "FailingProvider",
            (),
            {
                "fetch": lambda *args, **kwargs: (_ for _ in ()).throw(
                    OSError("timeout")
                )
            },
        )()
        service = ConditionsService(live_provider=live_provider)

        result = service.get(BEACH_POINTS[1], now=NOW)

        self.assertEqual(result.origin, "fallback")
        self.assertIn("timeout", result.provider_error)

    @override_settings(BLUETIDE_DATA_MODE="live", BLUETIDE_WATER_DATA_FILE="")
    def test_live_weather_without_official_water_file_stays_unavailable(self):
        live_result = replace(
            FixtureConditionsProvider().fetch(BEACH_POINTS[2], now=NOW),
            origin="live",
        )
        live_provider = type(
            "LiveProvider", (), {"fetch": lambda *args, **kwargs: live_result}
        )()
        service = ConditionsService(live_provider=live_provider)

        conditions = service.get(BEACH_POINTS[2], now=NOW)
        result = recommend(conditions, "tranquilo", now=NOW)

        self.assertFalse(result.available)
        self.assertIn("BLUETIDE_WATER_DATA_FILE", conditions.provider_error)


@override_settings(BLUETIDE_DATA_MODE="fixture")
class ViewTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")

    def test_every_user_facing_route_renders(self):
        routes = (
            "/",
            "/web/",
            "/pesquisa/",
            "/login/",
            "/favoritos/",
            "/faq/",
            "/alertas/",
            "/filtros/",
            "/comparar/",
            "/detalhes/",
            "/praias/ipanema-posto-8/",
        )

        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)

    def test_search_filters_without_client_side_script(self):
        response = self.client.get("/pesquisa/", {"q": "Posto 8"})

        self.assertContains(response, "Posto 8")
        self.assertNotContains(response, "Posto 9")

    def test_profile_changes_explanation(self):
        response = self.client.get("/praias/ipanema-posto-9/", {"perfil": "surf"})

        self.assertContains(response, "surf iniciante")
        self.assertContains(response, "Faixa de ondas compatível")

    def test_unknown_beach_returns_404(self):
        self.assertEqual(self.client.get("/praias/inexistente/").status_code, 404)

    def test_missing_stale_and_incomplete_states_are_visible(self):
        response = self.client.get("/comparar/")

        self.assertContains(response, "Não há boletim")
        self.assertContains(response, "desatualizado")
        self.assertContains(response, "Faltam dados essenciais")

    def test_demo_data_is_never_presented_as_live(self):
        response = self.client.get("/web/")

        self.assertContains(response, "Modo demonstração")
        self.assertContains(
            response, "Nenhum dado é apresentado como leitura oficial ao vivo"
        )

    def test_map_identifies_approximate_coast_and_places_pins_from_coordinates(self):
        response = self.client.get("/web/")

        self.assertContains(response, "não é mapa de navegação")
        for point in BEACH_POINTS:
            self.assertContains(response, f'cx="{point.map_x}" cy="{point.map_y}"')


Usuario = get_user_model()
PASSWORD = "mare-calma-ipanema-2026"
# Smallest valid PNG (1x1 transparent pixel).
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def make_user(**overrides):
    fields = {
        "username": "pedro",
        "email": "pedro@example.com",
        "nome": "Pedro Santos",
        "cidade": "Rio de Janeiro",
        "estado": "RJ",
        "pontos_favoritos": ["ipanema-posto-10", "ipanema-posto-8", "ipanema-posto-9"],
    }
    fields.update(overrides)
    return Usuario.objects.create_user(password=PASSWORD, **fields)


def profile_payload(user, **overrides):
    payload = {
        "nome": user.nome,
        "email": user.email,
        "cidade": user.cidade,
        "estado": user.estado,
        "perfil_praia": user.perfil_praia,
        "meio_transporte_preferido": user.meio_transporte_preferido,
        "economia_dados": "on",
        "alertas_mudanca": "on",
    }
    payload.update(overrides)
    return {key: value for key, value in payload.items() if value is not None}


class TotpTests(SimpleTestCase):
    # RFC 6238 appendix B uses the ASCII secret "12345678901234567890".
    SECRET = base64.b32encode(b"12345678901234567890").decode()

    def test_matches_rfc_6238_reference_vectors(self):
        self.assertEqual(totp_code(self.SECRET, at_time=59), "287082")
        self.assertEqual(totp_code(self.SECRET, at_time=1111111109), "081804")
        self.assertEqual(totp_code(self.SECRET, at_time=2000000000), "279037")

    def test_accepts_one_step_of_clock_drift_and_nothing_more(self):
        code = totp_code(self.SECRET, at_time=1_000_000)

        self.assertTrue(verify_totp(self.SECRET, code, at_time=1_000_000 + 30))
        self.assertFalse(verify_totp(self.SECRET, code, at_time=1_000_000 + 90))

    def test_rejects_steps_already_used(self):
        code = totp_code(self.SECRET, at_time=1_000_000)
        step = matching_totp_step(self.SECRET, code, at_time=1_000_000)

        self.assertIsNotNone(step)
        self.assertIsNone(
            matching_totp_step(self.SECRET, code, at_time=1_000_000, after_step=step)
        )

    def test_rejects_malformed_and_non_ascii_digits(self):
        self.assertIsNone(matching_totp_step(self.SECRET, "12345"))
        self.assertIsNone(matching_totp_step(self.SECRET, "١٢٣٤٥٦"))

    def test_recovery_codes_are_single_use_and_stored_hashed(self):
        codes = generate_recovery_codes()
        stored = [hash_recovery_code(code) for code in codes]

        self.assertEqual(len(set(codes)), 8)
        self.assertTrue(all(code not in stored for code in codes))
        remaining = consume_recovery_code(stored, codes[0].upper().replace("-", " "))
        self.assertEqual(len(remaining), 7)
        self.assertIsNone(consume_recovery_code(remaining, codes[0]))


@override_settings(BLUETIDE_DATA_MODE="fixture")
class MapAndFavoritesHeuristicTests(TestCase):
    def test_map_legend_explains_each_marker_color_and_icon(self):
        response = self.client.get("/web/")

        self.assertContains(response, "Legenda do mapa")
        for meaning in (
            "Melhor escolha ou boa alternativa",
            "Escolha com atenção",
            "Sem recomendação",
        ):
            self.assertContains(response, meaning)
        for tone in ("success", "warning", "neutral"):
            self.assertContains(response, f"legend-pin legend-pin-{tone}")
        # Every marker carries a shape glyph, so meaning never depends on color alone.
        self.assertContains(
            response, 'class="map-pin-badge"', count=len(BEACH_POINTS) + 3
        )

    def test_search_without_results_explains_and_offers_recovery(self):
        response = self.client.get("/pesquisa/", {"q": "Copacabana"})

        self.assertContains(response, "0 pontos encontrados")
        self.assertContains(response, "Nenhum ponto encontrado")
        self.assertContains(response, 'value="Copacabana"')
        self.assertContains(response, "Limpar busca")

    def test_favorites_show_labelled_occupancy_with_its_own_palette(self):
        response = self.client.get("/favoritos/")

        self.assertContains(response, "Como ler os selos")
        self.assertContains(response, "Ocupação da areia")
        self.assertContains(response, "Ocupação baixa")
        self.assertContains(response, "Ocupação média")
        self.assertContains(response, "Ocupação alta")
        self.assertContains(response, "badge badge-occupancy badge-occupancy-")
        self.assertNotContains(response, 'badge badge-success">Ocupação')
        css = (Path(__file__).parent / "static/css/design-system.css").read_text()
        occupancy_rule = css.split(".badge-occupancy {", 1)[1].split("}", 1)[0]
        for reserved in ("--success", "--warning", "--danger", "--neutral"):
            self.assertNotIn(reserved, occupancy_rule)

    def test_removing_a_favorite_without_javascript_offers_a_real_undo(self):
        response = self.client.post(
            "/favoritos/ipanema-posto-8/remover/", {"next": "/favoritos/"}, follow=True
        )

        self.assertNotContains(response, 'data-slug="ipanema-posto-8"')
        self.assertContains(response, "Ipanema · Posto 8 saiu dos favoritos.")
        self.assertContains(response, 'action="/favoritos/ipanema-posto-8/restaurar/"')
        # The offer is one-shot, like a flash message.
        self.assertNotContains(self.client.get("/favoritos/"), "saiu dos favoritos.")

        restored = self.client.post(
            "/favoritos/ipanema-posto-8/restaurar/",
            {"next": "/favoritos/"},
            follow=True,
        )
        self.assertContains(restored, 'data-slug="ipanema-posto-8"')

    def test_xhr_removal_and_undo_return_state_for_the_snackbar(self):
        removed = self.client.post("/favoritos/ipanema-posto-9/remover/", **XHR)

        self.assertEqual(
            removed.json(),
            {
                "slug": "ipanema-posto-9",
                "name": "Ipanema · Posto 9",
                "favorite": False,
                "count": 2,
            },
        )
        self.assertNotIn("favorite_undo", self.client.session)
        restored = self.client.post("/favoritos/ipanema-posto-9/restaurar/", **XHR)
        self.assertEqual(restored.json()["favorite"], True)
        self.assertEqual(restored.json()["count"], 3)

    def test_favorite_endpoints_reject_get_unknown_points_and_open_redirects(self):
        self.assertEqual(
            self.client.get("/favoritos/ipanema-posto-8/remover/").status_code, 405
        )
        self.assertEqual(
            self.client.post("/favoritos/copacabana/remover/").status_code, 404
        )
        response = self.client.post(
            "/favoritos/ipanema-posto-8/remover/", {"next": "https://evil.example/"}
        )
        self.assertRedirects(response, "/favoritos/", fetch_redirect_response=False)

    def test_signed_in_favorites_persist_on_the_account(self):
        user = make_user()
        self.client.force_login(user)

        self.client.post("/favoritos/ipanema-posto-10/remover/", **XHR)

        user.refresh_from_db()
        self.assertEqual(user.pontos_favoritos, ["ipanema-posto-8", "ipanema-posto-9"])

    def test_empty_favorites_state_is_explained(self):
        for slug in ("ipanema-posto-8", "ipanema-posto-9", "ipanema-posto-10"):
            self.client.post(f"/favoritos/{slug}/remover/", **XHR)

        response = self.client.get("/favoritos/")

        self.assertContains(response, "Nenhum favorito por enquanto")
        self.assertNotContains(response, "data-favorites-empty hidden")


@override_settings(BLUETIDE_DATA_MODE="fixture")
class LoginTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_login_offers_back_and_guest_access(self):
        response = self.client.get(
            "/login/", HTTP_REFERER="http://testserver/pesquisa/?q=Posto"
        )

        self.assertContains(response, 'class="back-link" href="/pesquisa/?q=Posto"')
        self.assertContains(response, "Continuar sem conta")
        self.assertContains(response, 'href="/web/">Continuar sem conta')

    def test_back_link_never_points_to_external_or_account_only_pages(self):
        for referer in (
            "https://evil.example/",
            "http://testserver/perfil/",
            "http://testserver/login/",
        ):
            with self.subTest(referer=referer):
                response = self.client.get("/login/", HTTP_REFERER=referer)
                self.assertContains(response, 'class="back-link" href="/web/"')

    def test_empty_submit_flags_email_and_password_together(self):
        response = self.client.post("/login/", {"email": "", "password": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe seu e-mail.", count=2)
        self.assertContains(response, "Informe sua senha.", count=2)
        self.assertContains(response, "Revise 2 campos para entrar")
        self.assertContains(response, 'aria-invalid="true"', count=2)
        self.assertContains(response, 'aria-describedby="id_email_errors"')
        self.assertContains(response, 'aria-describedby="id_password_errors"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_wrong_password_keeps_email_and_does_not_reveal_which_field_failed(self):
        response = self.client.post(
            "/login/", {"email": "pedro@example.com", "password": "errada"}
        )

        self.assertContains(response, "E-mail ou senha incorretos.")
        self.assertContains(response, 'value="pedro@example.com"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_valid_login_is_case_insensitive_and_follows_safe_next(self):
        response = self.client.post(
            "/login/",
            {"email": "Pedro@Example.com", "password": PASSWORD, "next": "/favoritos/"},
        )

        self.assertRedirects(response, "/favoritos/", fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))

    def test_next_cannot_redirect_off_site(self):
        response = self.client.post(
            "/login/",
            {
                "email": "pedro@example.com",
                "password": PASSWORD,
                "next": "//evil.example/",
            },
        )

        self.assertRedirects(response, "/perfil/", fetch_redirect_response=False)

    def test_header_offers_login_to_guests_and_avatar_to_members(self):
        self.assertContains(self.client.get("/web/"), 'class="login-chip"')
        self.client.force_login(self.user)
        response = self.client.get("/web/")
        self.assertNotContains(response, 'class="login-chip"')
        self.assertContains(response, "Abrir perfil de Pedro Santos")


@override_settings(BLUETIDE_DATA_MODE="fixture")
class TwoFactorLoginTests(TestCase):
    def setUp(self):
        self.recovery_codes = generate_recovery_codes()
        self.user = make_user(
            two_factor_enabled=True,
            two_factor_secret=TotpTests.SECRET,
            two_factor_recovery_codes=[
                hash_recovery_code(code) for code in self.recovery_codes
            ],
        )

    def start_login(self):
        response = self.client.post(
            "/login/", {"email": "pedro@example.com", "password": PASSWORD}
        )
        self.assertRedirects(response, "/login/codigo/", fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_password_alone_does_not_sign_in(self):
        self.start_login()

        self.assertRedirects(
            self.client.get("/perfil/"),
            "/login/?next=/perfil/",
            fetch_redirect_response=False,
        )

    def test_current_code_signs_in_and_cannot_be_replayed(self):
        self.start_login()
        code = totp_code(TotpTests.SECRET)

        response = self.client.post("/login/codigo/", {"code": code})

        self.assertRedirects(response, "/perfil/", fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.client.logout()
        self.start_login()
        replay = self.client.post("/login/codigo/", {"code": code})
        self.assertContains(replay, "Código inválido ou já usado.")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_wrong_codes_are_limited(self):
        self.start_login()
        wrong = "000000" if totp_code(TotpTests.SECRET) != "000000" else "111111"

        for attempt in range(4):
            response = self.client.post("/login/codigo/", {"code": wrong})
            self.assertContains(response, f"{4 - attempt} tentativa")
            self.assertContains(
                response, 'aria-describedby="id_code_helptext id_code_errors"'
            )
        response = self.client.post("/login/codigo/", {"code": wrong})

        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertNotIn("pending_login", self.client.session)

    def test_expired_pending_login_requires_the_password_again(self):
        self.start_login()
        session = self.client.session
        session["pending_login"]["started"] = time.time() - 301
        session.save()

        response = self.client.post(
            "/login/codigo/", {"code": totp_code(TotpTests.SECRET)}
        )

        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_recovery_code_works_once(self):
        self.start_login()

        response = self.client.post(
            "/login/codigo/", {"code": self.recovery_codes[0]}, follow=True
        )

        self.assertContains(
            response, "Você entrou com um código de recuperação. Restam 7."
        )
        self.client.logout()
        self.start_login()
        reused = self.client.post("/login/codigo/", {"code": self.recovery_codes[0]})
        self.assertContains(reused, "Código inválido ou já usado.")


@override_settings(BLUETIDE_DATA_MODE="fixture")
class ProfileTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        media = override_settings(MEDIA_ROOT=self.media_root)
        media.enable()
        self.addCleanup(media.disable)
        self.client.force_login(self.user)

    def test_profile_requires_an_account(self):
        self.client.logout()

        self.assertRedirects(
            self.client.get("/perfil/"),
            "/login/?next=/perfil/",
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get("/perfil/editar/"),
            "/login/?next=/perfil/editar/",
            fetch_redirect_response=False,
        )

    def test_profile_explains_what_each_preference_changes(self):
        response = self.client.get("/perfil/")

        self.assertContains(response, "O que cada escolha muda")
        self.assertContains(response, "ondas de até 0,8 m")
        self.assertContains(response, "não muda a ordem dos postos")
        self.assertContains(response, "a localização não é pedida nem usada")
        self.assertContains(response, "nenhum aviso é enviado")

    def test_beach_profile_preference_really_changes_the_ranking(self):
        default_order = self.client.get("/web/").context["items"]
        self.user.perfil_praia = "surf"
        self.user.save()
        surf_order = self.client.get("/web/").context["items"]

        self.assertEqual(default_order[0]["conditions"].beach.posto, "Posto 8")
        self.assertEqual(surf_order[0]["conditions"].beach.posto, "Posto 9")

    def test_logout_asks_for_confirmation_before_ending_the_session(self):
        profile = self.client.get("/perfil/")
        self.assertContains(profile, 'data-dialog-open="logout-dialog"')
        self.assertContains(profile, "Sair da conta?")

        confirm = self.client.get("/logout/")
        self.assertContains(confirm, "Sair da conta?")
        self.assertContains(confirm, "Cancelar")
        self.assertIn(SESSION_KEY, self.client.session)

        response = self.client.post("/logout/", follow=True)
        self.assertRedirects(response, "/web/")
        self.assertContains(response, "Você saiu da conta.")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_edit_name_region_preferences_and_photo(self):
        photo = SimpleUploadedFile("eu.png", PNG_BYTES, content_type="image/png")

        response = self.client.post(
            "/perfil/editar/",
            profile_payload(
                self.user,
                nome="  Pedro   Alves Santos ",
                cidade="Niterói",
                estado="RJ",
                perfil_praia="surf",
                meio_transporte_preferido="carro",
                economia_dados=None,
                foto=photo,
            ),
            follow=True,
        )

        self.assertRedirects(response, "/perfil/")
        self.assertContains(
            response,
            "Perfil atualizado. O mapa e a busca já usam o novo perfil de praia.",
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.nome, "Pedro Alves Santos")
        self.assertEqual(self.user.cidade, "Niterói")
        self.assertEqual(self.user.perfil_praia, "surf")
        self.assertEqual(self.user.meio_transporte_preferido, "carro")
        self.assertFalse(self.user.economia_dados)
        self.assertRegex(
            self.user.foto.name, r"^avatars/\d{4}/\d{2}/[0-9a-f]{32}\.png$"
        )
        self.assertContains(response, f'src="{self.user.foto.url}"')

    def test_saving_without_changing_beach_profile_does_not_claim_a_new_order(self):
        response = self.client.post(
            "/perfil/editar/", profile_payload(self.user, cidade="Niterói"), follow=True
        )

        self.assertRedirects(response, "/perfil/")
        self.assertContains(response, "Perfil atualizado.")
        self.assertNotContains(response, "novo perfil de praia")

    def test_photo_must_really_be_an_image(self):
        fake = SimpleUploadedFile(
            "foto.png", b"<script>alert(1)</script>", content_type="image/png"
        )

        response = self.client.post(
            "/perfil/editar/", profile_payload(self.user, foto=fake)
        )

        self.assertContains(response, "Use uma imagem JPG, PNG ou WebP.")
        self.assertNotContains(response, "A foto escolhida não foi mantida")
        self.user.refresh_from_db()
        self.assertFalse(self.user.foto)

    def test_failed_save_says_the_chosen_photo_must_be_picked_again(self):
        # Browsers never refill a file input, so a good photo sent together with
        # an invalid field is lost. The page must say so instead of dropping it
        # silently.
        photo = SimpleUploadedFile("eu.png", PNG_BYTES, content_type="image/png")

        response = self.client.post(
            "/perfil/editar/", profile_payload(self.user, nome="", foto=photo)
        )

        self.assertContains(response, "Revise 1 campo antes de salvar:")
        self.assertContains(response, "A foto escolhida não foi mantida", count=2)
        self.assertContains(response, 'href="#id_foto">Escolha a foto de novo</a>')
        self.assertContains(
            response, 'aria-describedby="id_foto_helptext id_foto_notice"'
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.foto)
        self.assertEqual(
            [path for path in Path(self.media_root).rglob("*") if path.is_file()], []
        )

    def test_failed_save_without_a_photo_does_not_mention_the_photo(self):
        response = self.client.post(
            "/perfil/editar/", profile_payload(self.user, nome="")
        )

        self.assertContains(response, "Revise 1 campo antes de salvar:")
        self.assertNotContains(response, "A foto escolhida não foi mantida")

    def test_changing_email_requires_the_current_password(self):
        without = self.client.post(
            "/perfil/editar/", profile_payload(self.user, email="novo@example.com")
        )
        self.assertContains(without, "Confirme sua senha atual para trocar o e-mail.")
        self.assertContains(without, 'value="novo@example.com"')

        wrong = self.client.post(
            "/perfil/editar/",
            profile_payload(self.user, email="novo@example.com", senha_atual="errada"),
        )
        self.assertContains(wrong, "Senha atual incorreta.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "pedro@example.com")

        self.client.post(
            "/perfil/editar/",
            profile_payload(self.user, email="Novo@Example.com", senha_atual=PASSWORD),
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "novo@example.com")

    def test_email_already_used_by_another_account_is_rejected(self):
        make_user(username="ana", email="ana@example.com", nome="Ana")

        response = self.client.post(
            "/perfil/editar/",
            profile_payload(self.user, email="ANA@example.com", senha_atual=PASSWORD),
        )

        self.assertContains(response, "Este e-mail já está em uso por outra conta.")

    def test_failed_save_does_not_change_the_header(self):
        response = self.client.post(
            "/perfil/editar/", profile_payload(self.user, nome="   ")
        )

        self.assertContains(response, "Informe seu nome.")
        self.assertContains(response, "Abrir perfil de Pedro Santos")


@override_settings(BLUETIDE_DATA_MODE="fixture")
class TwoFactorSetupTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def pending_secret(self):
        response = self.client.get("/perfil/seguranca/2fa/")
        self.assertContains(response, "<svg")
        return response.context["secret"]

    def test_setup_stays_disabled_until_a_valid_code_is_confirmed(self):
        secret = self.pending_secret()
        wrong = "000000" if totp_code(secret) != "000000" else "111111"

        response = self.client.post(
            "/perfil/seguranca/2fa/", {"action": "activate", "code": wrong}
        )

        self.assertContains(response, "Esse código não confere.")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'aria-describedby="id_code_errors"')
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)
        self.assertEqual(self.user.two_factor_secret, "")
        self.assertEqual(response.context["secret"], secret)

    def test_valid_code_enables_and_shows_recovery_codes_once(self):
        secret = self.pending_secret()

        response = self.client.post(
            "/perfil/seguranca/2fa/", {"action": "activate", "code": totp_code(secret)}
        )

        self.assertContains(response, "Verificação ativada")
        codes = response.context["recovery_codes"]
        self.assertEqual(len(codes), 8)
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)
        self.assertEqual(self.user.two_factor_secret, secret)
        self.assertTrue(
            all(code not in self.user.two_factor_recovery_codes for code in codes)
        )
        manage = self.client.get("/perfil/seguranca/2fa/")
        self.assertContains(manage, "Proteção ativa")
        self.assertContains(manage, "Restam 8 códigos")
        self.assertTrue(all(code not in manage.content.decode() for code in codes))
        self.assertContains(self.client.get("/perfil/"), "status-pill status-on")

    def test_restart_generates_a_new_secret(self):
        first = self.pending_secret()

        response = self.client.post("/perfil/seguranca/2fa/", {"action": "restart"})

        self.assertNotEqual(response.context["secret"], first)

    def test_disabling_requires_the_password(self):
        secret = self.pending_secret()
        self.client.post(
            "/perfil/seguranca/2fa/", {"action": "activate", "code": totp_code(secret)}
        )

        wrong = self.client.post(
            "/perfil/seguranca/2fa/", {"action": "disable", "password": "errada"}
        )
        self.assertContains(wrong, "Senha incorreta.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.two_factor_enabled)

        self.client.post(
            "/perfil/seguranca/2fa/", {"action": "disable", "password": PASSWORD}
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.two_factor_enabled)
        self.assertEqual(self.user.two_factor_secret, "")
        self.assertEqual(self.user.two_factor_recovery_codes, [])


class DemoAccountCommandTests(TestCase):
    def test_creates_the_fictional_demo_account_with_a_supplied_password(self):
        with patch.dict("os.environ", {"BLUETIDE_DEMO_PASSWORD": PASSWORD}):
            call_command("criar_conta_demo", stdout=io.StringIO())

        user = Usuario.objects.get(email="pedro@example.com")
        self.assertEqual(user.nome, "Pedro Santos")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.two_factor_enabled)

    def test_resets_the_demo_account_after_its_email_and_photo_were_edited(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media_root):
            with patch.dict("os.environ", {"BLUETIDE_DEMO_PASSWORD": PASSWORD}):
                call_command("criar_conta_demo", stdout=io.StringIO())
            user = Usuario.objects.get(email="pedro@example.com")
            user.email = "pedro.santos@example.com"
            user.nome = "Pedro Alves Santos"
            user.foto = SimpleUploadedFile(
                "eu.png", PNG_BYTES, content_type="image/png"
            )
            user.save()
            photo_path = Path(user.foto.path)
            self.assertTrue(photo_path.exists())

            with patch.dict("os.environ", {"BLUETIDE_DEMO_PASSWORD": PASSWORD}):
                call_command("criar_conta_demo", stdout=io.StringIO())

        self.assertEqual(Usuario.objects.count(), 1)
        user.refresh_from_db()
        self.assertEqual(user.email, "pedro@example.com")
        self.assertEqual(user.nome, "Pedro Santos")
        self.assertFalse(user.foto)
        self.assertFalse(photo_path.exists())
