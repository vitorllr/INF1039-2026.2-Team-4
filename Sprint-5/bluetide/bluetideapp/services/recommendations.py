from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from .providers import Conditions


WATER_MAX_AGE = timedelta(days=8)
MARINE_MAX_AGE = timedelta(hours=6)
HEAVY_RAIN_MM = 20.0
MODERATE_RAIN_MM = 5.0
VALID_PROFILES = {"tranquilo", "surf", "neutro"}
PROFILE_LABELS = {
    "tranquilo": "Banho tranquilo",
    "surf": "Surf iniciante",
    "neutro": "Sem preferência",
}


@dataclass(frozen=True)
class Recommendation:
    available: bool
    score: int | None
    label: str
    tone: str
    summary: str
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]


def normalize_profile(value: str | None) -> str:
    return value if value in VALID_PROFILES else "tranquilo"


def recommend(conditions: Conditions, profile: str, now=None) -> Recommendation:
    profile = normalize_profile(profile)
    now = now or timezone.now()
    blockers = _minimum_data_blockers(conditions, now)
    if conditions.provider_error:
        blockers.append("A integração de dados está incompleta; os valores de apoio não geram recomendação.")
    if blockers:
        return Recommendation(
            available=False,
            score=None,
            label="Sem recomendação",
            tone="neutral",
            summary=blockers[0],
            reasons=(),
            blockers=tuple(blockers),
        )

    score = 3
    reasons = ["Qualidade da água própria e dentro da validade."]
    wave = conditions.wave_height or 0
    rain = conditions.rain_24h or 0
    wind = conditions.wind_speed or 0

    if profile == "tranquilo":
        if wave <= 0.8:
            score += 3
            reasons.append("Ondas baixas combinam com banho tranquilo.")
        elif wave <= 1.2:
            score += 1
            reasons.append("Ondas moderadas pedem atenção ao entrar no mar.")
        else:
            score -= 2
            reasons.append("Ondas acima do ideal para banho tranquilo.")
    elif profile == "surf":
        if 0.7 <= wave <= 1.4:
            score += 3
            reasons.append("Faixa de ondas compatível com surf iniciante.")
        elif wave < 0.7:
            score += 1
            reasons.append("Ondas pequenas podem limitar a prática de surf.")
        else:
            score -= 2
            reasons.append("Ondas acima da faixa escolhida para iniciantes.")
    else:
        score += 1

    if rain < 1:
        score += 2
        reasons.append("Pouca chuva acumulada nas últimas 24 horas.")
    elif rain < MODERATE_RAIN_MM:
        score += 1
        reasons.append("Chuva leve no período, sem bloqueio automático.")
    else:
        reasons.append("Chuva moderada reduz a confiança da escolha.")

    if wind <= 15:
        score += 2
        reasons.append("Vento leve no momento.")
    elif wind <= 25:
        score += 1
        reasons.append("Vento moderado no momento.")
    else:
        reasons.append("Vento forte pode piorar o conforto e o mar.")

    if conditions.sea_temperature is not None and conditions.sea_temperature >= 22:
        score += 1

    if score >= 10:
        label = "Melhor escolha"
        tone = "success"
        summary = f"Combina melhor com {PROFILE_LABELS[profile].lower()} entre os pontos comparáveis."
    elif score >= 6:
        label = "Boa alternativa"
        tone = "success"
        summary = f"Condições compatíveis com {PROFILE_LABELS[profile].lower()}, com ressalvas leves."
    else:
        label = "Escolha com atenção"
        tone = "warning"
        summary = "Há dados suficientes, mas as condições não são as mais alinhadas ao perfil."

    return Recommendation(
        available=True,
        score=score,
        label=label,
        tone=tone,
        summary=summary,
        reasons=tuple(reasons[:4]),
        blockers=(),
    )


def rank(recommendations):
    return sorted(
        recommendations,
        key=lambda item: (
            not item["recommendation"].available,
            -(item["recommendation"].score or -1),
            item["conditions"].beach.slug,
        ),
    )


def _minimum_data_blockers(conditions: Conditions, now) -> list[str]:
    blockers = []
    if conditions.water_status is None:
        blockers.append("Não há boletim de qualidade da água para este ponto.")
    elif conditions.water_status == "impropria":
        blockers.append("A água está imprópria para banho no boletim mais recente.")
    elif conditions.water_status != "propria":
        blockers.append("A qualidade da água não permite uma recomendação segura.")

    if conditions.water_observed_at is None:
        blockers.append("A data do boletim de qualidade da água está ausente.")
    elif now - conditions.water_observed_at > WATER_MAX_AGE:
        blockers.append("O boletim de qualidade da água está desatualizado.")

    if conditions.marine_observed_at is None:
        blockers.append("A data das condições do mar está ausente.")
    elif now - conditions.marine_observed_at > MARINE_MAX_AGE:
        blockers.append("As condições do mar estão desatualizadas.")

    missing = []
    for label, value in (
        ("altura das ondas", conditions.wave_height),
        ("chuva em 24 horas", conditions.rain_24h),
        ("vento", conditions.wind_speed),
    ):
        if value is None:
            missing.append(label)
    if missing:
        blockers.append(f"Faltam dados essenciais: {', '.join(missing)}.")

    if conditions.rain_24h is not None and conditions.rain_24h >= HEAVY_RAIN_MM:
        blockers.append("A chuva intensa nas últimas 24 horas suspende a recomendação.")
    return blockers
