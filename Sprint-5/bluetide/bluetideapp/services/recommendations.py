from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .providers import Conditions


# Regra da Sprint 9: Sprint-9/Vitor-Rocha/logica-recomendacao
FRESH_WATER_DAYS = 9
MAX_WATER_DAYS = 30
RAIN_1H_HEAVY_MM = 7.6
RAIN_1H_MODERATE_MM = 2.5
RAIN_24H_HEAVY_MM = 20.0
RAIN_24H_MODERATE_MM = 5.0
RAIN_24H_MODERATE_HIGH_TIDE_MM = 1.0
MAX_RAIN_AGE = timedelta(hours=3)

GREEN, YELLOW, RED = "verde", "amarelo", "vermelho"
SEVERITY = {GREEN: 0, YELLOW: 1, RED: 2}
COLOR_PRESENTATION = {
    GREEN: ("Recomendado", "success"),
    YELLOW: ("Atenção", "warning"),
    RED: ("Evite o banho", "danger"),
}
CONFIDENCE_LABELS = {"alta": "Confiança alta", "media": "Confiança média", "baixa": "Confiança baixa"}

VALID_PROFILES = {"tranquilo", "surf", "neutro"}
PROFILE_LABELS = {
    "tranquilo": "Banho tranquilo",
    "surf": "Surf iniciante",
    "neutro": "Sem preferência",
}
PROFILE_PRIORITIES = {
    "tranquilo": "Pesa mais a onda, depois a chuva, o vento e, por último, a maré alta.",
    "surf": "Pesa mais a onda, depois o vento. A chuva pesa pouco e a maré não entra.",
    "neutro": "Vale só a cor. Onda, vento e chuva desempatam com o mesmo peso.",
}

CALM_WAVE_M = 0.8
BATHER_MAX_WAVE_M = 1.2
SURF_MIN_WAVE_M = 0.7
SURF_MAX_WAVE_M = 1.4
LIGHT_WIND_KMH = 15
STRONG_WIND_KMH = 25
DRY_RAIN_MM = 1.0


@dataclass(frozen=True)
class Recommendation:
    available: bool
    color: str | None
    confidence: str | None
    label: str
    tone: str
    summary: str
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    fit: int = 0

    @property
    def confidence_label(self) -> str:
        return CONFIDENCE_LABELS.get(self.confidence, "")

    @property
    def recommendable(self) -> bool:
        return self.available and self.color != RED


def normalize_profile(value: str | None) -> str:
    return value if value in VALID_PROFILES else "tranquilo"


def recommend(conditions: Conditions, profile: str, now=None) -> Recommendation:
    profile = normalize_profile(profile)
    now = now or timezone.now()

    if conditions.provider_error:
        blockers = ("A integração de dados está incompleta; os valores de apoio não geram recomendação.",)
        return Recommendation(
            available=False,
            color=None,
            confidence=None,
            label="Sem recomendação",
            tone="neutral",
            summary=blockers[0],
            reasons=(),
            blockers=blockers,
        )

    water, age_days = _classify_water(conditions, now)
    rain = _classify_rain(conditions, now)
    confidence = _confidence(conditions, water, rain)
    collected = _collected_label(conditions)
    rain_text = _rain_text(conditions)

    reds, yellows = [], []
    if water != "sem_dado" and conditions.water_status == "impropria":
        reds.append(f"Boletim: ponto impróprio na coleta de {collected} ({_days(age_days)}).")
    if rain == "forte":
        reds.append(f"Chuva forte ({rain_text}).")

    if reds:
        color, reasons = RED, reds
    else:
        if water == "sem_dado":
            yellows.append("Sem coleta de qualidade da água usável nos últimos 30 dias.")
        elif water == "antiga":
            yellows.append(f"A coleta de {collected} tem {_days(age_days)}, mais que um ciclo.")
        if rain == "moderada":
            only_tide = (
                conditions.high_tide
                and conditions.rain_24h < RAIN_24H_MODERATE_MM
                and (conditions.rain_1h or 0.0) <= RAIN_1H_MODERATE_MM
            )
            kind = "Chuva fraca com maré alta" if only_tide else "Chuva moderada"
            yellows.append(f"{kind} ({rain_text}).")
        if rain == "indisponivel":
            yellows.append("Sem dado de chuva recente.")
        if yellows:
            color, reasons = YELLOW, yellows
        else:
            color = GREEN
            reasons = [f"Água própria na coleta de {collected} e chuva baixa."]

    if color != RED and conditions.high_tide is None:
        reasons.append("Maré sem dado: considerada não alta.")

    fit, fit_reasons = _profile_fit(conditions, profile)
    label, tone = COLOR_PRESENTATION[color]
    return Recommendation(
        available=True,
        color=color,
        confidence=confidence,
        label=label,
        tone=tone,
        summary=reasons[0],
        reasons=tuple(reasons + fit_reasons),
        blockers=(),
        fit=fit,
    )


def rank(recommendations):
    return sorted(
        recommendations,
        key=lambda item: (
            not item["recommendation"].available,
            SEVERITY.get(item["recommendation"].color, 0),
            -item["recommendation"].fit,
            _posto_number(item["conditions"].beach.posto),
        ),
    )


def _days(count):
    return f"{count} dia" if count == 1 else f"{count} dias"


def _posto_number(posto: str) -> int:
    digits = "".join(char for char in posto if char.isdigit())
    return int(digits) if digits else 0


def _classify_water(conditions, now):
    observed = conditions.water_observed_at
    if conditions.water_status not in ("propria", "impropria") or observed is None:
        return "sem_dado", None
    age = (timezone.localtime(now).date() - timezone.localtime(observed).date()).days
    if age < 0 or age > MAX_WATER_DAYS:
        return "sem_dado", age
    return ("antiga" if age > FRESH_WATER_DAYS else "fresca"), age


def _classify_rain(conditions, now):
    if conditions.rain_24h is None or conditions.rain_observed_at is None:
        return "indisponivel"
    if now - conditions.rain_observed_at > MAX_RAIN_AGE:
        return "indisponivel"
    rain_1h = conditions.rain_1h or 0.0
    moderate_24h = RAIN_24H_MODERATE_HIGH_TIDE_MM if conditions.high_tide else RAIN_24H_MODERATE_MM
    if conditions.rain_24h >= RAIN_24H_HEAVY_MM or rain_1h > RAIN_1H_HEAVY_MM:
        return "forte"
    if conditions.rain_24h >= moderate_24h or rain_1h > RAIN_1H_MODERATE_MM:
        return "moderada"
    return "baixa"


def _confidence(conditions, water, rain):
    if water == "sem_dado" or rain == "indisponivel":
        return "baixa"
    if water == "antiga" or conditions.rain_quality == "modelada" or conditions.high_tide is None:
        return "media"
    return "alta"


def _collected_label(conditions):
    if conditions.water_observed_at is None:
        return ""
    return timezone.localtime(conditions.water_observed_at).strftime("%d/%m")


def _rain_text(conditions):
    if conditions.rain_24h is None:
        return ""
    rain_1h = conditions.rain_1h if conditions.rain_1h is not None else 0.0
    return f"{conditions.rain_24h:g} mm em 24 h, {rain_1h:g} mm na última hora"


def _profile_fit(conditions, profile):
    """Preferência só ordena pontos de mesma cor; não muda a cor."""
    return PROFILE_FIT[profile](conditions)


def _bather_fit(conditions):
    fit, reasons = 0, []
    wave, wind, rain = conditions.wave_height, conditions.wind_speed, conditions.rain_24h
    if wave is None:
        fit -= 1
    elif wave <= CALM_WAVE_M:
        fit += 3
        reasons.append("Ondas baixas combinam com banho tranquilo.")
    elif wave <= BATHER_MAX_WAVE_M:
        fit += 1
        reasons.append("Ondas moderadas pedem atenção ao entrar no mar.")
    else:
        fit -= 2
        reasons.append("Ondas acima do ideal para banho tranquilo.")

    if rain is not None and rain < DRY_RAIN_MM:
        fit += 2
        reasons.append("Pouca chuva nas últimas 24 horas.")

    if wind is None:
        fit -= 1
    elif wind <= LIGHT_WIND_KMH:
        fit += 1
        reasons.append("Vento leve no momento.")
    elif wind > STRONG_WIND_KMH:
        fit -= 1
        reasons.append("Vento forte deixa a praia desconfortável.")

    if conditions.high_tide:
        fit -= 1
        reasons.append("Maré alta: menos faixa de areia.")
    return fit, reasons


def _surf_fit(conditions):
    fit, reasons = 0, []
    wave, wind, rain = conditions.wave_height, conditions.wind_speed, conditions.rain_24h
    if wave is None:
        fit -= 1
    elif wave < SURF_MIN_WAVE_M:
        reasons.append("Ondas pequenas podem limitar a prática de surf.")
    elif wave <= SURF_MAX_WAVE_M:
        fit += 3
        reasons.append("Faixa de ondas compatível com surf iniciante.")
    else:
        fit -= 2
        reasons.append("Ondas acima da faixa escolhida para iniciantes.")

    if wind is None:
        fit -= 1
    elif wind <= LIGHT_WIND_KMH:
        fit += 2
        reasons.append("Vento fraco deixa o mar mais arrumado.")
    elif wind <= STRONG_WIND_KMH:
        fit += 1
        reasons.append("Vento moderado no momento.")
    else:
        fit -= 2
        reasons.append("Vento forte bagunça o mar.")

    if rain is not None and rain < DRY_RAIN_MM:
        fit += 1
    return fit, reasons


def _neutral_fit(conditions):
    fit = 0
    if conditions.wave_height is not None and conditions.wave_height <= BATHER_MAX_WAVE_M:
        fit += 1
    if conditions.wind_speed is not None and conditions.wind_speed <= STRONG_WIND_KMH:
        fit += 1
    if conditions.rain_24h is not None and conditions.rain_24h < DRY_RAIN_MM:
        fit += 1
    return fit, []


PROFILE_FIT = {
    "tranquilo": _bather_fit,
    "surf": _surf_fit,
    "neutro": _neutral_fit,
}
