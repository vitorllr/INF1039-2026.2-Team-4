import io
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import Client, SimpleTestCase, override_settings
from django.utils import timezone

from .services import providers
from .services.catalog import BEACH_POINTS
from .services.providers import (
    ConditionsService,
    FixtureConditionsProvider,
    OpenMeteoProvider,
)
from .services.recommendations import rank, recommend, water_color
from .services.tide import (
    OpenMeteoTideProvider,
    TideReading,
    is_high_tide,
    read_tide_from_hourly,
    unavailable,
)


NOW = timezone.make_aware(datetime(2026, 11, 8, 12, 0))


class RecommendationTests(SimpleTestCase):

    def setUp(self):
        self.conditions = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=NOW)

    def test_complete_safe_point_is_green_and_explained(self):
        result = recommend(self.conditions, "tranquilo", now=NOW)

        self.assertEqual(result.color, "verde")
        self.assertEqual(result.label, "Recomendada")
        self.assertEqual(result.tone, "success")
        self.assertIn("INEA próprio", result.summary)
        self.assertIn("Ondas baixas", " ".join(r.capitalize() for r in result.reasons))

    def test_missing_water_quality_is_yellow_with_low_confidence(self):
        result = recommend(
            replace(self.conditions, water_status=None, water_observed_at=None),
            "tranquilo",
            now=NOW,
        )

        self.assertEqual(result.color, "amarelo")
        self.assertEqual(result.confidence, "baixa")
        self.assertIn("sem coleta do INEA", result.reasons[0])

    def test_old_water_quality_is_yellow(self):
        result = recommend(replace(self.conditions, water_observed_at=NOW - timedelta(days=11)), "tranquilo", now=NOW)

        self.assertEqual(result.color, "amarelo")
        self.assertIn("11 dias", result.summary)

    def test_improper_water_is_red_for_every_profile_and_hides_profile_reasons(self):
        unsafe = replace(self.conditions, water_status="impropria")

        for profile in ("tranquilo", "surf", "neutro"):
            with self.subTest(profile=profile):
                result = recommend(unsafe, profile, now=NOW)
                self.assertEqual(result.color, "vermelho")
                self.assertEqual(result.tone, "danger")
                self.assertTrue(all("INEA" in reason for reason in result.reasons))

    def test_heavy_rain_is_red(self):
        result = recommend(replace(self.conditions, rain_24h=25), "surf", now=NOW)

        self.assertEqual(result.color, "vermelho")
        self.assertIn("chuva forte", result.summary)

    def test_fallback_values_never_give_green(self):
        fallback = replace(self.conditions, origin="fallback", provider_error="timeout")

        for profile in ("tranquilo", "surf", "neutro"):
            with self.subTest(profile=profile):
                result = recommend(fallback, profile, now=NOW)
                self.assertEqual(result.color, "amarelo")
                self.assertEqual(result.confidence, "baixa")
                self.assertIn("dados ao vivo incompletos", result.reasons[0])

    def test_ranking_puts_green_then_yellow_then_red(self):
        green = self.conditions
        yellow = replace(self.conditions, beach=BEACH_POINTS[0], water_observed_at=NOW - timedelta(days=11))
        red = replace(self.conditions, beach=BEACH_POINTS[2], water_status="impropria")
        items = [
            {"conditions": c, "recommendation": recommend(c, "tranquilo", now=NOW)}
            for c in (red, yellow, green)
        ]

        first = rank(items)
        second = rank(list(reversed(items)))

        self.assertEqual(first, second)
        self.assertEqual([item["recommendation"].color for item in first], ["verde", "amarelo", "vermelho"])

    def test_inside_the_same_color_more_confidence_comes_first(self):
        known = replace(self.conditions, water_observed_at=NOW - timedelta(days=11))
        unknown = replace(self.conditions, beach=BEACH_POINTS[0], water_status=None)
        items = [
            {"conditions": c, "recommendation": recommend(c, "tranquilo", now=NOW)}
            for c in (unknown, known)
        ]

        ordered = rank(items)

        self.assertEqual([item["recommendation"].confidence for item in ordered], ["media", "baixa"])

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
        service = ConditionsService(live_provider=live_provider, tide_provider=FakeTideProvider(None))

        conditions = service.get(BEACH_POINTS[2], now=NOW)
        result = recommend(conditions, "tranquilo", now=NOW)

        self.assertNotEqual(result.color, "verde")
        self.assertEqual(result.confidence, "baixa")
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
        surf = self.client.get("/praias/ipanema-posto-9/", {"perfil": "surf"})
        bather = self.client.get("/praias/ipanema-posto-9/", {"perfil": "tranquilo"})

        self.assertContains(surf, "Ondas de 0,9 m, na faixa do surf iniciante")
        self.assertContains(bather, "Ondas moderadas (0,9 m)")
        self.assertContains(bather, "Maré alta: menos faixa de areia")

    def test_unknown_beach_returns_404(self):
        self.assertEqual(self.client.get("/praias/inexistente/").status_code, 404)

    def test_missing_stale_and_incomplete_states_are_visible(self):
        response = self.client.get("/comparar/")

        self.assertContains(response, "Sem coleta do INEA usável")
        self.assertContains(response, "tem 10 dias, mais que um ciclo")
        self.assertContains(response, "Vento indisponível")
        self.assertContains(response, "Maré sem dado: considerada não alta")

    def test_screens_show_color_and_reason(self):
        detail = self.client.get("/praias/ipanema-posto-9/", {"perfil": "tranquilo"})
        card_list = self.client.get("/pesquisa/", {"perfil": "tranquilo"})
        map_page = self.client.get("/web/", {"perfil": "tranquilo"})

        self.assertContains(detail, "badge-warning")
        self.assertContains(detail, "Com atenção")
        self.assertContains(detail, "Confiança média")
        self.assertContains(detail, "Com atenção para banho tranquilo: chuva fraca com maré alta")
        self.assertContains(card_list, "Recomendada")
        self.assertContains(card_list, "Boa para banho tranquilo: INEA próprio")
        self.assertContains(map_page, "map-pin-success")
        self.assertContains(map_page, "map-pin-warning")

    def test_red_point_is_shown_in_red(self):
        red = replace(FixtureConditionsProvider().fetch(BEACH_POINTS[1]), water_status="impropria")
        with patch.object(ConditionsService, "get", return_value=red):
            response = self.client.get("/web/")

        self.assertContains(response, "map-pin-danger")
        self.assertContains(response, "Evite hoje")

    def test_profile_screen_links_profiles_and_explains_weights(self):
        response = self.client.get("/perfil/", {"perfil": "surf"})

        self.assertContains(response, 'href="/web/?perfil=surf"')
        self.assertContains(response, "Pesa mais a onda, depois o vento")

    def test_demo_data_is_never_presented_as_live(self):
        response = self.client.get("/web/")

        self.assertContains(response, "Modo demonstração")
        self.assertContains(response, "Nenhum dado é apresentado como leitura oficial ao vivo")

    def test_map_identifies_approximate_coast_and_places_pins_from_coordinates(self):
        response = self.client.get("/web/")

        self.assertContains(response, "não é mapa de navegação")
        for point in BEACH_POINTS:
            self.assertContains(response, f'cx="{point.map_x}" cy="{point.map_y}"')


TIDE_PERIOD_HOURS = 12.42


def hourly_tide_payload(now, phase, hours_before=24, hours_after=24):
    current_hour = timezone.localtime(now).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    times, heights = [], []
    for k in range(-hours_before, hours_after + 1):
        times.append((current_hour + timedelta(hours=k)).isoformat(timespec="minutes"))
        heights.append(round(0.6 * math.cos(2 * math.pi * k / TIDE_PERIOD_HOURS + phase), 3))
    return {"hourly": {"time": times, "sea_level_height_msl": heights}}


class FakeTideProvider:
    def __init__(self, high):
        self.high = high

    def read(self, beach, now=None):
        if self.high is None:
            return unavailable("Open-Meteo Marine não respondeu: timeout")
        return TideReading(self.high, 0.5, -0.5, 0.6, now, "Open-Meteo Marine")


class TideModuleTests(SimpleTestCase):
    def test_high_tide_when_now_is_in_the_top_quarter(self):
        reading = read_tide_from_hourly(hourly_tide_payload(NOW, phase=0), NOW)

        self.assertTrue(reading.available)
        self.assertTrue(reading.high)
        self.assertIsNone(reading.unavailable_reason)

    def test_low_tide_when_now_is_at_the_bottom(self):
        reading = read_tide_from_hourly(hourly_tide_payload(NOW, phase=math.pi), NOW)

        self.assertTrue(reading.available)
        self.assertFalse(reading.high)

    def test_mid_tide_is_not_high(self):
        reading = read_tide_from_hourly(hourly_tide_payload(NOW, phase=math.pi / 2), NOW)

        self.assertFalse(reading.high)

    def test_unavailable_when_series_does_not_cover_now(self):
        later = NOW + timedelta(days=3)

        reading = read_tide_from_hourly(hourly_tide_payload(NOW, phase=0), later)

        self.assertIsNone(reading.high)
        self.assertIn("hora atual", reading.unavailable_reason)

    def test_unavailable_when_window_is_too_short(self):
        payload = hourly_tide_payload(NOW, phase=0, hours_before=3, hours_after=3)

        reading = read_tide_from_hourly(payload, NOW)

        self.assertIsNone(reading.high)
        self.assertIn("insuficientes", reading.unavailable_reason)

    def test_flat_sea_level_is_unavailable(self):
        self.assertIsNone(is_high_tide(0.3, [0.3] * 49))

    @patch("bluetideapp.services.tide.urlopen")
    def test_provider_requests_hourly_sea_level_with_timeout(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(json.dumps(hourly_tide_payload(NOW, phase=0)).encode())

        reading = OpenMeteoTideProvider(timeout=2).read(BEACH_POINTS[2], now=NOW)

        self.assertTrue(reading.high)
        url = mocked_urlopen.call_args.args[0]
        self.assertIn("marine-api.open-meteo.com", url)
        self.assertIn("hourly=sea_level_height_msl", url)
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 2)

    @patch("bluetideapp.services.tide.urlopen", side_effect=OSError("timeout"))
    def test_provider_never_raises_when_api_fails(self, mocked_urlopen):
        reading = OpenMeteoTideProvider(timeout=2).read(BEACH_POINTS[2], now=NOW)

        self.assertIsNone(reading.high)
        self.assertIn("não respondeu", reading.unavailable_reason)

    @patch("bluetideapp.services.tide.urlopen")
    def test_provider_never_raises_on_unexpected_format(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeResponse(b'{"hourly": "quebrado"}')

        reading = OpenMeteoTideProvider(timeout=2).read(BEACH_POINTS[2], now=NOW)

        self.assertIsNone(reading.high)


class TideInConditionsTests(SimpleTestCase):
    def setUp(self):
        providers._LIVE_CACHE.clear()

    def tearDown(self):
        providers._LIVE_CACHE.clear()

    def test_fixture_carries_high_low_and_missing_tide(self):
        provider = FixtureConditionsProvider()
        by_slug = {point.slug: provider.fetch(point, now=NOW) for point in BEACH_POINTS}

        self.assertTrue(by_slug["ipanema-posto-9"].tide_high)
        self.assertFalse(by_slug["ipanema-posto-8"].tide_high)
        self.assertIsNone(by_slug["ipanema-posto-11"].tide_high)

    @override_settings(BLUETIDE_DATA_MODE="live")
    def test_live_service_delivers_tide_to_conditions(self):
        live_result = replace(FixtureConditionsProvider().fetch(BEACH_POINTS[3], now=NOW), origin="live")
        live_provider = type("LiveProvider", (), {"fetch": lambda *args, **kwargs: live_result})()
        service = ConditionsService(live_provider=live_provider, tide_provider=FakeTideProvider(True))

        conditions = service.get(BEACH_POINTS[3], now=NOW)

        self.assertTrue(conditions.tide_high)
        self.assertEqual(conditions.tide_source, "Open-Meteo Marine")

    @override_settings(BLUETIDE_DATA_MODE="live")
    def test_tide_failure_does_not_turn_live_data_into_fallback(self):
        live_result = replace(FixtureConditionsProvider().fetch(BEACH_POINTS[4], now=NOW), origin="live")
        live_provider = type("LiveProvider", (), {"fetch": lambda *args, **kwargs: live_result})()
        service = ConditionsService(live_provider=live_provider, tide_provider=FakeTideProvider(None))

        conditions = service.get(BEACH_POINTS[4], now=NOW)

        self.assertEqual(conditions.origin, "live")
        self.assertIsNone(conditions.tide_high)
        self.assertIn("não respondeu", conditions.tide_note)


class Sprint9RuleWithTideTests(SimpleTestCase):
    def setUp(self):
        self.base = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=NOW)

    def color(self, **changes):
        return water_color(replace(self.base, **changes), now=NOW)

    def test_light_rain_with_high_tide_turns_yellow(self):
        result = self.color(rain_24h=2.0, tide_high=True)

        self.assertEqual(result.cor, "amarelo")
        self.assertIn("chuva fraca com maré alta", " ".join(result.motivos))

    def test_light_rain_with_low_tide_stays_green(self):
        result = self.color(rain_24h=2.0, tide_high=False)

        self.assertEqual(result.cor, "verde")
        self.assertEqual(result.confianca, "media")

    def test_light_rain_with_tide_unavailable_counts_as_not_high(self):
        result = self.color(rain_24h=2.0, tide_high=None)

        self.assertEqual(result.cor, "verde")
        self.assertEqual(result.confianca, "media")
        self.assertIn("maré sem dado", " ".join(result.motivos))

    def test_tide_never_makes_red_on_its_own(self):
        result = self.color(rain_24h=0.0, tide_high=True)

        self.assertEqual(result.cor, "verde")

    def test_heavy_rain_is_red(self):
        self.assertEqual(self.color(rain_24h=25.0).cor, "vermelho")

    def test_improper_water_is_red(self):
        self.assertEqual(self.color(water_status="impropria").cor, "vermelho")

    def test_old_collection_is_yellow(self):
        result = self.color(water_observed_at=NOW - timedelta(days=11))

        self.assertEqual(result.cor, "amarelo")
        self.assertIn("11 dias", " ".join(result.motivos))

    def test_provider_error_never_gives_green(self):
        result = self.color(provider_error="timeout")

        self.assertEqual(result.cor, "amarelo")
        self.assertEqual(result.confianca, "baixa")

    def test_recommendation_service_exposes_color_and_confidence(self):
        result = recommend(replace(self.base, rain_24h=2.0, tide_high=True), "tranquilo", now=NOW)

        self.assertEqual(result.color, "amarelo")
        self.assertEqual(result.confidence, "media")
        self.assertIn("chuva fraca com maré alta", " ".join(result.reasons))


class Sprint9PdfExamplesTests(SimpleTestCase):

    def test_the_ten_examples_keep_color_and_confidence(self):
        from datetime import date
        from datetime import timezone as dt_timezone

        from .services.regra_sprint9 import EntradaDoPonto, recomendar_ponto

        brasilia = dt_timezone(timedelta(hours=-3))
        agora = datetime(2026, 10, 19, 10, 0, tzinfo=brasilia)
        lido = datetime(2026, 10, 19, 9, 40, tzinfo=brasilia)
        coleta = date(2026, 10, 15)
        cases = [
            ("propria", coleta, 0.0, 0.4, False, "observada", lido, "verde", "alta"),
            ("propria", coleta, 0.0, 6.2, False, "observada", lido, "amarelo", "alta"),
            ("propria", coleta, 0.0, 2.0, True, "observada", lido, "amarelo", "alta"),
            ("propria", coleta, 9.0, 34.0, False, "observada", lido, "vermelho", "alta"),
            ("impropria", coleta, 0.0, 0.0, False, "observada", lido, "vermelho", "alta"),
            ("propria", date(2026, 10, 8), 0.0, 0.0, False, "observada", lido, "amarelo", "media"),
            ("propria", coleta, None, None, False, None, None, "amarelo", "baixa"),
            ("propria", date(2026, 9, 17), 0.0, 0.0, False, "observada", lido, "amarelo", "baixa"),
            ("impropria", date(2026, 10, 8), 0.0, 0.0, False, "observada", lido, "vermelho", "media"),
            ("propria", coleta, 0.6, 1.1, None, "modelada", lido, "verde", "media"),
        ]
        for number, (status, day, h1, h24, tide, quality, read_at, color, confidence) in enumerate(cases, 1):
            with self.subTest(example=number):
                result = recomendar_ponto(EntradaDoPonto(status, day, h1, h24, quality, read_at, tide), agora)
                self.assertEqual((result.cor, result.confianca), (color, confidence))


class ProfileBehaviorTests(SimpleTestCase):

    def setUp(self):
        self.base = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=NOW)

    def rec(self, profile, **changes):
        return recommend(replace(self.base, **changes), profile, now=NOW)

    def test_bather_calm_sea_is_green(self):
        result = self.rec("tranquilo")

        self.assertEqual(result.color, "verde")
        self.assertIn("ondas baixas (0,6 m), boas para banho", result.reasons)

    def test_bather_big_waves_turn_yellow(self):
        result = self.rec("tranquilo", wave_height=1.5)

        self.assertEqual(result.color, "amarelo")
        self.assertEqual(result.water_color, "verde")
        self.assertIn("acima do ideal para banho tranquilo", result.summary)

    def test_bather_high_tide_only_lowers_the_order(self):
        low = self.rec("tranquilo", tide_high=False)
        high = self.rec("tranquilo", tide_high=True)

        self.assertEqual(high.color, "verde")
        self.assertLess(high.score, low.score)
        self.assertIn("maré alta: menos faixa de areia", high.reasons)

    def test_bather_missing_wind_does_not_change_the_color(self):
        result = self.rec("tranquilo", wind_speed=None)

        self.assertEqual(result.color, "verde")
        self.assertIn("vento indisponível", result.reasons)

    def test_bather_stale_marine_data_turns_yellow(self):
        result = self.rec("tranquilo", marine_observed_at=NOW - timedelta(hours=7))

        self.assertEqual(result.color, "amarelo")

    def test_surf_good_waves_and_light_wind_are_green(self):
        result = self.rec("surf", wave_height=0.9, wind_speed=10)

        self.assertEqual(result.color, "verde")
        self.assertIn("ondas de 0,9 m, na faixa do surf iniciante", result.reasons)
        self.assertIn("vento fraco, mar mais arrumado", result.reasons)

    def test_surf_flat_sea_turns_yellow(self):
        result = self.rec("surf", wave_height=0.4)

        self.assertEqual(result.color, "amarelo")
        self.assertIn("mar quase sem onda", result.summary)

    def test_surf_strong_wind_turns_yellow(self):
        result = self.rec("surf", wave_height=1.0, wind_speed=30)

        self.assertEqual(result.color, "amarelo")
        self.assertIn("vento forte (30 km/h) bagunça o mar", result.reasons)

    def test_surf_ignores_the_tide(self):
        low = self.rec("surf", wave_height=1.0, tide_high=False)
        high = self.rec("surf", wave_height=1.0, tide_high=True)

        self.assertEqual((low.color, low.score), (high.color, high.score))

    def test_neutral_follows_only_the_water_color(self):
        result = self.rec("neutro", wave_height=2.5, wind_speed=40)

        self.assertEqual(result.color, "verde")
        self.assertEqual(result.summary, "Boa hoje: " + result.reasons[0] + ".")

    def test_neutral_is_yellow_when_water_is_yellow(self):
        result = self.rec("neutro", rain_24h=2.0, tide_high=True)

        self.assertEqual(result.color, "amarelo")
        self.assertIn("chuva fraca com maré alta", result.summary)

    def test_profile_never_creates_red(self):
        for profile, changes in (
            ("tranquilo", {"wave_height": 3.0}),
            ("surf", {"wave_height": 3.0, "wind_speed": 50}),
        ):
            with self.subTest(profile=profile):
                self.assertEqual(self.rec(profile, **changes).color, "amarelo")

    def test_profile_never_improves_the_water_color(self):
        for profile in ("tranquilo", "surf", "neutro"):
            with self.subTest(profile=profile):
                result = self.rec(profile, wave_height=0.9, wind_speed=10, rain_24h=2.0, tide_high=True)
                self.assertEqual(result.color, "amarelo")

    def test_confidence_is_always_the_sprint9_one(self):
        expected = water_color(self.base, now=NOW).confianca
        for profile in ("tranquilo", "surf", "neutro"):
            with self.subTest(profile=profile):
                self.assertEqual(self.rec(profile).confidence, expected)

    def test_unknown_profile_falls_back_to_bather(self):
        self.assertEqual(recommend(self.base, "qualquer", now=NOW), recommend(self.base, "tranquilo", now=NOW))