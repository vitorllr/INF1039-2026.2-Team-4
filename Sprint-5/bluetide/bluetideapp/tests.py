import io
import json
from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings
from django.utils import timezone

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
        result = recommend(replace(self.conditions, wind_speed=None), "tranquilo", now=NOW)

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
        self.assertTrue(any("integração de dados" in blocker for blocker in result.blockers))

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
        self.assertTrue(any(NOW - item.water_observed_at > timedelta(days=8) for item in conditions if item.water_observed_at))
        self.assertTrue(any(item.wind_speed is None for item in conditions))

    @patch("bluetideapp.services.providers.urlopen")
    def test_open_meteo_adapter_requests_and_maps_only_needed_fields(self, mocked_urlopen):
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
        self.assertTrue(all(call.kwargs["timeout"] == 2 for call in mocked_urlopen.call_args_list))

    @override_settings(BLUETIDE_DATA_MODE="live")
    def test_service_falls_back_without_raising_on_timeout(self):
        live_provider = type(
            "FailingProvider",
            (),
            {"fetch": lambda *args, **kwargs: (_ for _ in ()).throw(OSError("timeout"))},
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
        live_provider = type("LiveProvider", (), {"fetch": lambda *args, **kwargs: live_result})()
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
            "/perfil/",
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
        self.assertContains(response, "Nenhum dado é apresentado como leitura oficial ao vivo")
