import json
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings
from django.utils import timezone

from .catalog import BeachPoint
from .tide import read_tide_from_hourly


MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
_LIVE_CACHE: dict[str, tuple[datetime, "Conditions"]] = {}


@dataclass(frozen=True)
class Conditions:
    beach: BeachPoint
    water_status: str | None
    water_observed_at: datetime | None
    water_source: str
    marine_observed_at: datetime | None
    wave_height: float | None
    wave_period: float | None
    sea_temperature: float | None
    sea_level: float | None
    air_temperature: float | None
    rain_24h: float | None
    wind_speed: float | None
    origin: str
    provider_error: str | None = None
    rain_1h: float | None = None
    rain_observed_at: datetime | None = None
    rain_quality: str | None = None
    high_tide: bool | None = None
    water_point: str | None = None
    tide_note: str | None = None


def is_demo_mode() -> bool:
    return settings.BLUETIDE_DATA_MODE in ("demo", "fixture")


class FixtureConditionsProvider:
    """Reads the demo fixture, or a water-quality file such as the INEA one."""

    def __init__(self, path: str | Path | None = None):
        default_path = Path(__file__).resolve().parent.parent / "fixtures" / "conditions.json"
        self.path = Path(path or default_path)

    def fetch(self, beach: BeachPoint, now: datetime | None = None) -> Conditions:
        now = now or timezone.now()
        with self.path.open(encoding="utf-8") as fixture_file:
            payload = json.load(fixture_file)
        raw = payload["points"].get(beach.slug, {})
        water = raw.get("water", {})
        marine = raw.get("marine", {})
        return Conditions(
            beach=beach,
            water_status=water.get("status"),
            water_observed_at=self._water_observed_at(now, water),
            water_source=water.get("source", "Boletim não informado"),
            marine_observed_at=self._relative_time(now, self._minutes_to_hours(marine.get("age_minutes"))),
            wave_height=self._number(marine.get("wave_height")),
            wave_period=self._number(marine.get("wave_period")),
            sea_temperature=self._number(marine.get("sea_temperature")),
            sea_level=self._number(marine.get("sea_level")),
            air_temperature=self._number(marine.get("air_temperature")),
            rain_24h=self._number(marine.get("rain_24h")),
            wind_speed=self._number(marine.get("wind_speed")),
            origin="fixture",
            rain_1h=self._number(marine.get("rain_1h")),
            rain_observed_at=self._relative_time(now, self._minutes_to_hours(marine.get("age_minutes"))),
            rain_quality=marine.get("rain_quality"),
            high_tide=marine.get("high_tide") if marine.get("high_tide") in (True, False) else None,
            water_point=self._water_point(water),
            tide_note=None if marine.get("high_tide") in (True, False) else "maré sem dado na demonstração",
        )

    @classmethod
    def _water_observed_at(cls, now: datetime, water: dict[str, Any]) -> datetime | None:
        collected_on = water.get("collected_on")
        if collected_on:
            midnight = datetime.combine(date.fromisoformat(collected_on), time.min)
            return timezone.make_aware(midnight, timezone.get_current_timezone())
        return cls._relative_time(now, water.get("age_hours"))

    @staticmethod
    def _water_point(water: dict[str, Any]) -> str | None:
        if not water.get("inea_point"):
            return None
        location = water.get("inea_location", "").strip()
        distance = water.get("distance_m")
        parts = [f"ponto {water['inea_point']}"]
        if location:
            parts.append(location[:1].lower() + location[1:])
        text = ", ".join(parts)
        return f"{text} (cerca de {distance} m do posto)" if distance else text

    @staticmethod
    def _relative_time(now: datetime, age_hours: float | None) -> datetime | None:
        if age_hours is None:
            return None
        return now - timedelta(hours=float(age_hours))

    @staticmethod
    def _minutes_to_hours(minutes: float | None) -> float | None:
        return None if minutes is None else float(minutes) / 60

    @staticmethod
    def _number(value: Any) -> float | None:
        return None if value is None else float(value)


class OpenMeteoProvider:
    """Fetches only the marine and weather fields used by the product."""

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout or settings.BLUETIDE_HTTP_TIMEOUT

    def fetch(self, beach: BeachPoint, base: Conditions, now: datetime | None = None) -> Conditions:
        now = now or timezone.now()
        marine = self._request_json(
            MARINE_URL,
            {
                "latitude": beach.latitude,
                "longitude": beach.longitude,
                "current": "wave_height,wave_period,sea_surface_temperature,sea_level_height_msl",
                "hourly": "sea_level_height_msl",
                "past_days": 1,
                "forecast_days": 2,
                "timezone": "America/Sao_Paulo",
            },
        )
        weather = self._request_json(
            WEATHER_URL,
            {
                "latitude": beach.latitude,
                "longitude": beach.longitude,
                "current": "temperature_2m,wind_speed_10m,precipitation",
                "hourly": "precipitation",
                "past_days": 1,
                "forecast_days": 1,
                "timezone": "America/Sao_Paulo",
            },
        )
        marine_current = marine.get("current", {})
        weather_current = weather.get("current", {})
        observed_at = self._parse_time(marine_current.get("time")) or now
        tide = read_tide_from_hourly(marine, now)
        return replace(
            base,
            marine_observed_at=observed_at,
            wave_height=self._number(marine_current.get("wave_height")),
            wave_period=self._number(marine_current.get("wave_period")),
            sea_temperature=self._number(marine_current.get("sea_surface_temperature")),
            sea_level=self._number(marine_current.get("sea_level_height_msl")),
            air_temperature=self._number(weather_current.get("temperature_2m")),
            rain_24h=self._rain_last_24_hours(weather, now),
            wind_speed=self._number(weather_current.get("wind_speed_10m")),
            origin="live",
            provider_error=None,
            rain_1h=self._number(weather_current.get("precipitation")),
            rain_observed_at=self._parse_time(weather_current.get("time")) or now,
            rain_quality="modelada",
            high_tide=tide.high,
            tide_note=tide.unavailable_reason,
        )

    def _request_json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        with urlopen(url, timeout=self.timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Open-Meteo respondeu HTTP {response.status}")
            return json.load(response)

    @classmethod
    def _rain_last_24_hours(cls, payload: dict[str, Any], now: datetime) -> float | None:
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        precipitation = hourly.get("precipitation", [])
        if len(times) != len(precipitation):
            return None
        local_now = timezone.localtime(now).replace(tzinfo=None)
        cutoff = local_now - timedelta(hours=24)
        values = []
        for raw_time, raw_value in zip(times, precipitation, strict=True):
            parsed = cls._parse_time(raw_time)
            if parsed is None:
                continue
            local_time = parsed.replace(tzinfo=None)
            if cutoff < local_time <= local_now and raw_value is not None:
                values.append(float(raw_value))
        return round(sum(values), 1) if values else 0.0

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value)
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @staticmethod
    def _number(value: Any) -> float | None:
        return None if value is None else float(value)


class ConditionsService:
    def __init__(self, fixture_provider=None, live_provider=None):
        if fixture_provider is None:
            path = None if is_demo_mode() else settings.BLUETIDE_WATER_DATA_FILE
            fixture_provider = FixtureConditionsProvider(path)
        self.fixture_provider = fixture_provider
        self.live_provider = live_provider or OpenMeteoProvider()

    def get(self, beach: BeachPoint, now: datetime | None = None) -> Conditions:
        now = now or timezone.now()
        try:
            base = self.fixture_provider.fetch(beach, now=now)
        except (OSError, ValueError, KeyError) as exc:
            return Conditions(
                beach=beach,
                water_status=None,
                water_observed_at=None,
                water_source="Dados do INEA indisponíveis",
                marine_observed_at=None,
                wave_height=None,
                wave_period=None,
                sea_temperature=None,
                sea_level=None,
                air_temperature=None,
                rain_24h=None,
                wind_speed=None,
                origin="fallback",
                provider_error=f"Arquivo de água do INEA indisponível: {exc}",
            )
        if is_demo_mode():
            return base
        cached = _LIVE_CACHE.get(beach.slug)
        if cached and now - cached[0] < timedelta(seconds=settings.BLUETIDE_DATA_CACHE_SECONDS):
            return cached[1]
        try:
            result = self.live_provider.fetch(beach, base=base, now=now)
            if not settings.BLUETIDE_WATER_DATA_FILE:
                result = replace(
                    result,
                    provider_error="Configure BLUETIDE_WATER_DATA_FILE com um boletim oficial atualizado.",
                )
            _LIVE_CACHE[beach.slug] = (now, result)
            return result
        except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return replace(
                base,
                origin="fallback",
                provider_error=f"Condições ao vivo indisponíveis: {exc}",
            )
