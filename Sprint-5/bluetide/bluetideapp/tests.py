import io
import json
import tempfile
from dataclasses import replace
from pathlib import Path
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings
from django.utils import timezone

from .services import inea
from .services.catalog import BEACH_POINTS
from .services.providers import (
    ConditionsService,
    FixtureConditionsProvider,
    OpenMeteoProvider,
)
from .services.recommendations import rank, recommend


NOW = timezone.make_aware(datetime(2026, 11, 8, 12, 0))


SPRINT9_NOW = timezone.make_aware(datetime(2026, 10, 19, 10, 0))
SPRINT9_RAIN_READ = timezone.make_aware(datetime(2026, 10, 19, 9, 40))


def sprint9_conditions(status, collected, rain_1h, rain_24h, high_tide, quality="observada", read_at=SPRINT9_RAIN_READ):
    base = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=SPRINT9_NOW)
    return replace(
        base,
        water_status=status,
        water_observed_at=timezone.make_aware(datetime.combine(collected, datetime.min.time())) if collected else None,
        rain_1h=rain_1h,
        rain_24h=rain_24h,
        rain_quality=quality,
        rain_observed_at=read_at,
        high_tide=high_tide,
    )


COLLECTED_15_10 = date(2026, 10, 15)
SPRINT9_EXAMPLES = (
    ("1 tudo calmo", ("propria", COLLECTED_15_10, 0.0, 0.4, False), "verde", "alta"),
    ("2 chuva moderada", ("propria", COLLECTED_15_10, 0.0, 6.2, False), "amarelo", "alta"),
    ("3 chuva fraca com mare alta", ("propria", COLLECTED_15_10, 0.0, 2.0, True), "amarelo", "alta"),
    ("4 chuva forte", ("propria", COLLECTED_15_10, 9.0, 34.0, False), "vermelho", "alta"),
    ("5 improprio sem chuva", ("impropria", COLLECTED_15_10, 0.0, 0.0, False), "vermelho", "alta"),
    ("6 coleta de 11 dias", ("propria", date(2026, 10, 8), 0.0, 0.0, False), "amarelo", "media"),
    ("7 sem dado de chuva", ("propria", COLLECTED_15_10, None, None, False, None, None), "amarelo", "baixa"),
    ("8 coleta de 32 dias", ("propria", date(2026, 9, 17), 0.0, 0.0, False), "amarelo", "baixa"),
    ("9 improprio com 11 dias", ("impropria", date(2026, 10, 8), 0.0, 0.0, False), "vermelho", "media"),
    ("10 chuva modelada e mare sem dado", ("propria", COLLECTED_15_10, 0.6, 1.1, None, "modelada"), "verde", "media"),
)


class RecommendationTests(SimpleTestCase):
    def setUp(self):
        self.conditions = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=NOW)

    def test_sprint9_examples_match_color_and_confidence(self):
        for name, args, color, confidence in SPRINT9_EXAMPLES:
            with self.subTest(name):
                result = recommend(sprint9_conditions(*args), "neutro", now=SPRINT9_NOW)

                self.assertTrue(result.available)
                self.assertEqual((result.color, result.confidence), (color, confidence))
                self.assertTrue(result.reasons)

    def test_improper_water_and_heavy_rain_are_red_not_neutral(self):
        for conditions in (
            replace(self.conditions, water_status="impropria"),
            replace(self.conditions, rain_24h=25),
        ):
            result = recommend(conditions, "surf", now=NOW)

            self.assertEqual((result.color, result.tone, result.label), ("vermelho", "danger", "Evite o banho"))
            self.assertFalse(result.recommendable)

    def test_missing_water_quality_is_yellow_with_low_confidence(self):
        result = recommend(
            replace(self.conditions, water_status=None, water_observed_at=None),
            "tranquilo",
            now=NOW,
        )

        self.assertEqual((result.color, result.confidence), ("amarelo", "baixa"))
        self.assertIn("Sem coleta", result.summary)

    def test_stale_rain_reading_is_yellow(self):
        stale = replace(self.conditions, rain_observed_at=NOW - timedelta(hours=4))

        result = recommend(stale, "tranquilo", now=NOW)

        self.assertEqual((result.color, result.confidence), ("amarelo", "baixa"))

    def test_integration_error_blocks_recommendation(self):
        fallback = replace(self.conditions, origin="fallback", provider_error="timeout")

        result = recommend(fallback, "tranquilo", now=NOW)

        self.assertFalse(result.available)
        self.assertEqual(result.tone, "neutral")
        self.assertTrue(any("integração de dados" in blocker for blocker in result.blockers))

    def test_profile_only_reorders_points_of_the_same_color(self):
        calm = replace(self.conditions, wave_height=0.5)
        rough = replace(self.conditions, wave_height=1.3)
        red = replace(self.conditions, wave_height=0.5, water_status="impropria")

        def order(profile):
            items = [
                {"conditions": c, "recommendation": recommend(c, profile, now=NOW)}
                for c in (red, rough, calm)
            ]
            return [item["conditions"].wave_height for item in rank(items)]

        self.assertEqual(order("tranquilo"), [0.5, 1.3, 0.5])
        self.assertEqual(order("surf")[0], 1.3)
        self.assertEqual(order("surf")[-1], 0.5)

    def test_ranking_is_deterministic_and_puts_unavailable_points_last(self):
        best = recommend(self.conditions, "tranquilo", now=NOW)
        unavailable_conditions = replace(self.conditions, provider_error="timeout")
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

    def test_ties_break_by_posto_number_not_text_order(self):
        low, high = BEACH_POINTS[1], BEACH_POINTS[4]
        items = [
            {"conditions": replace(self.conditions, beach=beach), "recommendation": recommend(self.conditions, "neutro", now=NOW)}
            for beach in (high, low)
        ]

        self.assertEqual([i["conditions"].beach.posto for i in rank(items)], ["Posto 8", "Posto 11"])

    def test_map_positions_follow_geographic_coordinates(self):
        points_west_to_east = sorted(BEACH_POINTS, key=lambda point: point.longitude)
        points_north_to_south = sorted(BEACH_POINTS, key=lambda point: point.latitude, reverse=True)

        self.assertEqual([point.posto for point in points_west_to_east], ["Posto 11", "Posto 10", "Posto 9", "Posto 8", "Posto 7"])
        self.assertEqual(sorted(point.map_x for point in points_west_to_east), [point.map_x for point in points_west_to_east])
        self.assertEqual(sorted(point.map_y for point in points_north_to_south), [point.map_y for point in points_north_to_south])
        self.assertLess(max(point.map_y for point in BEACH_POINTS) - min(point.map_y for point in BEACH_POINTS), 300)
        self.assertGreater(max(point.map_x for point in BEACH_POINTS) - min(point.map_x for point in BEACH_POINTS), 2700)


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

    @override_settings(BLUETIDE_DATA_MODE="live", BLUETIDE_WATER_DATA_FILE=str(inea.WATER_FILE_PATH))
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


@override_settings(BLUETIDE_DATA_MODE="demo")
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

        self.assertContains(response, "Sem coleta de qualidade da água")
        self.assertContains(response, "mais que um ciclo")
        self.assertContains(response, "impróprio")

    def test_demo_data_is_never_presented_as_live(self):
        response = self.client.get("/web/")

        self.assertContains(response, "Modo demonstração")
        self.assertContains(response, "Nenhum dado é apresentado como leitura oficial ao vivo")

    def test_map_identifies_approximate_coast_and_places_pins_from_coordinates(self):
        response = self.client.get("/web/")

        self.assertContains(response, "não é mapa de navegação")
        for point in BEACH_POINTS:
            self.assertContains(response, f'cx="{point.map_x}" cy="{point.map_y}"')

    def test_map_shows_red_pin_legend_and_only_recommendable_points_as_best(self):
        response = self.client.get("/web/")

        self.assertContains(response, "map-pin-danger")
        self.assertContains(response, "Evite o banho")
        self.assertContains(response, "Legenda das cores")
        self.assertEqual(response.content.decode().count("beach-card-head"), 2)

    def test_map_pin_color_tracks_recommendation_color(self):
        html = self.client.get("/web/").content.decode()

        self.assertIn("map-pin-success", html)
        self.assertIn("map-pin-warning", html)
        self.assertIn("map-pin-danger", html)


def inea_points(last_status="impropria", last_date=date(2026, 11, 18)):
    point = {"praia": "Ipanema", "localizacao": "Em frente à Rua Joana Angélica"}
    points = {
        f"XX{n:03d}": {**point, "coletas": [(date(2026, 11, 11), "propria"), (last_date, "nao_realizada")]}
        for n in range(30)
    }
    for code in ("AR000", "IP006", "IP010", "LB003"):
        points[code] = {**point, "coletas": [(date(2026, 11, 11), "propria"), (last_date, last_status)]}
    return points


class IneaGeneratorTests(SimpleTestCase):
    def test_postos_get_latest_valid_collection_of_their_inea_point(self):
        postos_map = json.loads(inea.POINTS_MAP_PATH.read_text(encoding="utf-8"))

        data = inea.build_water_data(inea_points(), postos_map, "https://inea.example/h.pdf")

        water = data["points"]["ipanema-posto-9"]["water"]
        self.assertEqual(water["inea_point"], "IP006")
        self.assertEqual(water["status"], "impropria")
        self.assertEqual(water["source"], "INEA, coleta de 18/11/2026")
        self.assertEqual(set(data["points"]), {point.slug for point in BEACH_POINTS})

    def test_not_performed_collection_falls_back_to_last_valid_one(self):
        postos_map = json.loads(inea.POINTS_MAP_PATH.read_text(encoding="utf-8"))
        points = inea_points()
        points["IP006"]["coletas"].append((date(2026, 11, 20), "nao_realizada"))

        data = inea.build_water_data(points, postos_map, "u")

        self.assertEqual(data["points"]["ipanema-posto-8"]["water"]["collected_on"], "2026-11-18")

    def test_guards_reject_suspicious_pdfs(self):
        postos_map = json.loads(inea.POINTS_MAP_PATH.read_text(encoding="utf-8"))
        points = inea_points()
        with self.assertRaises(inea.IneaError):
            inea.build_water_data({"AR000": points["AR000"]}, postos_map, "u")
        del points["IP010"]
        with self.assertRaises(inea.IneaError):
            inea.build_water_data(points, postos_map, "u")

    def test_failed_write_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "agua.json"
            target.write_text('{"ok": true}', encoding="utf-8")

            with self.assertRaises(TypeError):
                inea.write_atomic(target, {"bad": object()})

            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"ok": True})
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["agua.json"])

    def test_committed_file_covers_every_posto_with_a_real_collection_date(self):
        data = json.loads(inea.WATER_FILE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(set(data["points"]), {point.slug for point in BEACH_POINTS})
        for point in data["points"].values():
            date.fromisoformat(point["water"]["collected_on"])
            self.assertTrue(point["water"]["source"].startswith("INEA, coleta de "))


class IneaModeTests(SimpleTestCase):
    @override_settings(BLUETIDE_DATA_MODE="live", BLUETIDE_WATER_DATA_FILE="/nonexistent/agua.json")
    def test_missing_water_file_suspends_recommendation_without_crashing(self):
        conditions = ConditionsService().get(BEACH_POINTS[1], now=NOW)

        self.assertIn("INEA", conditions.provider_error)
        self.assertFalse(recommend(conditions, "tranquilo", now=NOW).available)

    def setUp(self):
        self.client = Client(HTTP_HOST="127.0.0.1")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.water_file = Path(self.folder.name) / "agua.json"
        postos_map = json.loads(inea.POINTS_MAP_PATH.read_text(encoding="utf-8"))
        self.payload = inea.build_water_data(inea_points(), postos_map, "u")
        self.water_file.write_text(json.dumps(self.payload), encoding="utf-8")

    def get(self, route, today):
        failing = type("Offline", (), {"fetch": lambda *a, **k: (_ for _ in ()).throw(OSError("offline"))})()
        with (
            override_settings(BLUETIDE_DATA_MODE="live", BLUETIDE_WATER_DATA_FILE=str(self.water_file)),
            patch("django.utils.timezone.now", return_value=today),
            patch("bluetideapp.services.providers.OpenMeteoProvider", return_value=failing),
        ):
            return self.client.get(route)

    def test_age_comes_from_the_real_collection_date(self):
        provider = FixtureConditionsProvider(self.water_file)
        for today, expected in ((datetime(2026, 11, 23, 9), 5), (datetime(2026, 11, 28, 22), 10)):
            now = timezone.make_aware(today)
            conditions = provider.fetch(BEACH_POINTS[1], now=now)
            self.assertEqual(
                (timezone.localtime(now).date() - timezone.localtime(conditions.water_observed_at).date()).days,
                expected,
            )

    def test_notice_labels_source_and_nearest_point(self):
        response = self.get("/praias/ipanema-posto-8/", timezone.make_aware(datetime(2026, 11, 23, 9)))

        self.assertContains(response, "dados reais do INEA")
        self.assertContains(response, "ponto de monitoramento do INEA mais próximo")
        self.assertContains(response, "INEA, coleta de 18/11/2026")
        self.assertContains(response, "Ponto IP006")
        self.assertNotContains(response, "Modo demonstração")
        self.assertNotContains(response, 'data-water-notice="old"')

    def test_old_collection_is_flagged(self):
        response = self.get("/web/", timezone.make_aware(datetime(2026, 11, 30, 9)))

        self.assertContains(response, 'data-water-notice="old"')
        self.assertContains(response, "Coleta do INEA antiga")

    def test_expired_collection_is_flagged(self):
        response = self.get("/web/", timezone.make_aware(datetime(2026, 12, 25, 9)))

        self.assertContains(response, 'data-water-notice="expired"')
        self.assertContains(response, "Coleta do INEA vencida")
