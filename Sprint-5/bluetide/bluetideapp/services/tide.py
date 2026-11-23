from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.utils import timezone


HIGH_TIDE_FRACTION = 0.75
WINDOW_HOURS = 24
MIN_HOURS_IN_WINDOW = 24


@dataclass(frozen=True)
class TideReading:
    high: bool | None
    height: float | None
    lowest: float | None
    highest: float | None
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.high is not None


def unavailable(reason: str) -> TideReading:
    return TideReading(high=None, height=None, lowest=None, highest=None, unavailable_reason=reason)


def is_high_tide(height_now: float | None, heights_around: list) -> bool | None:
    valid = [float(h) for h in heights_around if h is not None]
    if height_now is None or len(valid) < MIN_HOURS_IN_WINDOW:
        return None
    lowest, highest = min(valid), max(valid)
    if highest == lowest:
        return None
    return float(height_now) >= lowest + HIGH_TIDE_FRACTION * (highest - lowest)


def read_tide_from_hourly(payload: dict[str, Any], now: datetime) -> TideReading:
    try:
        return _read(payload, now)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return unavailable(f"resposta de maré em formato inesperado: {exc}")


def _read(payload: dict[str, Any], now: datetime) -> TideReading:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    heights = hourly.get("sea_level_height_msl") or []
    if not times or len(times) != len(heights):
        return unavailable("a resposta da maré veio sem a série hora a hora")

    current_hour = timezone.localtime(now).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    try:
        index = times.index(current_hour.isoformat(timespec="minutes"))
    except ValueError:
        return unavailable("a série de maré não cobre a hora atual")

    height_now = heights[index]
    if height_now is None:
        return unavailable("sem altura de maré para a hora atual")

    window = heights[max(0, index - WINDOW_HOURS) : index + WINDOW_HOURS + 1]
    high = is_high_tide(height_now, window)
    if high is None:
        return unavailable("dados de maré insuficientes nas 24 h antes e depois")

    valid = [float(h) for h in window if h is not None]
    return TideReading(high=high, height=float(height_now), lowest=min(valid), highest=max(valid))