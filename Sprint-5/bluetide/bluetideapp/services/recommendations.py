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
        reds.append(f"Boletim: ponto impróprio na coleta de {collected} ({age_days} dias).")
    if rain == "forte":
        reds.append(f"Chuva forte ({rain_text}).")

    if reds:
        color, reasons = RED, reds
    else:
        if water == "sem_dado":
            yellows.append("Sem coleta de qualidade da água usável nos últimos 30 dias.")
        elif water == "antiga":
            yellows.append(f"A coleta de {collected} tem {age_days} dias, mais que um ciclo.")
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
    fit, reasons = 0, []
    wave, wind = conditions.wave_height, conditions.wind_speed
    if wave is None:
        fit -= 1
    elif profile == "tranquilo":
        if wave <= 0.8:
            fit += 3
            reasons.append("Ondas baixas combinam com banho tranquilo.")
        elif wave <= 1.2:
            fit += 1
            reasons.append("Ondas moderadas pedem atenção ao entrar no mar.")
        else:
            fit -= 2
            reasons.append("Ondas acima do ideal para banho tranquilo.")
    elif profile == "surf":
        if 0.7 <= wave <= 1.4:
            fit += 3
            reasons.append("Faixa de ondas compatível com surf iniciante.")
        elif wave < 0.7:
            fit += 1
            reasons.append("Ondas pequenas podem limitar a prática de surf.")
        else:
            fit -= 2
            reasons.append("Ondas acima da faixa escolhida para iniciantes.")

    if wind is None:
        fit -= 1
    elif wind <= 15:
        fit += 2
        reasons.append("Vento leve no momento.")
    elif wind <= 25:
        fit += 1
        reasons.append("Vento moderado no momento.")
    else:
        reasons.append("Vento forte pode piorar o conforto e o mar.")
    return fit, reasons
