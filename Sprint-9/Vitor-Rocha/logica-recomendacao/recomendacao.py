"""Regra de recomendação do BlueTide: verde, amarelo ou vermelho para um ponto de coleta.

A explicação de cada regra está em logica-recomendacao.pdf, nesta mesma pasta.
Os valores marcados como "premissa" são chute inicial da equipe e precisam de validação.

Para rodar os exemplos do PDF: python recomendacao.py
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

VERDE = "verde"
AMARELO = "amarelo"
VERMELHO = "vermelho"
GRAVIDADE = {VERDE: 0, AMARELO: 1, VERMELHO: 2}

# INEA: o histórico traz uma coleta a cada 4 a 9 dias (mediana de 7)
IDADE_FRESCA_DIAS = 9
IDADE_MAXIMA_DIAS = 30  # premissa: acima disso a coleta não entra mais na conta

# Chuva
CHUVA_1H_FORTE_MM = 7.6  # acima disso é chuva forte na escala da AMS (mm por hora)
CHUVA_1H_MODERADA_MM = 2.5  # entre 2,5 e 7,6 mm por hora é chuva moderada (AMS)
CHUVA_24H_FORTE_MM = 20.0  # premissa
CHUVA_24H_MODERADA_MM = 5.0  # premissa
CHUVA_24H_MODERADA_COM_MARE_ALTA_MM = 1.0  # premissa
IDADE_MAXIMA_DA_CHUVA = timedelta(hours=3)  # premissa

# Maré: alta quando está no quarto mais alto da variação das últimas e próximas 24h
FRACAO_DA_MARE_ALTA = 0.75  # premissa


@dataclass
class EntradaDoPonto:
    status_inea: str | None  # "propria", "impropria" ou None se não há coleta válida
    data_coleta: date | None
    chuva_1h_mm: float | None
    chuva_24h_mm: float | None
    chuva_qualidade: str | None  # "observada" ou "modelada"
    chuva_lido_em: datetime | None  # com fuso, no horário de Brasília
    mare_alta: bool | None  # None quando a maré não está disponível


@dataclass
class Recomendacao:
    cor: str
    confianca: str  # "alta", "media" ou "baixa"
    motivos: list = field(default_factory=list)


def ultima_coleta_valida(coletas):
    # coletas vem do parsing_pdf_inea.py: lista de (data, status) em ordem de data
    for data, status in reversed(coletas):
        if status in ("propria", "impropria"):
            return data, status
    return None, None


def mare_esta_alta(altura_agora_m, alturas_em_volta_m):
    # alturas_em_volta_m: sea_level_height_msl de hora em hora, 12h antes até 12h depois
    if altura_agora_m is None or len(alturas_em_volta_m) < 12:
        return None
    minima, maxima = min(alturas_em_volta_m), max(alturas_em_volta_m)
    if maxima == minima:
        return None
    return altura_agora_m >= minima + FRACAO_DA_MARE_ALTA * (maxima - minima)


def classificar_inea(entrada, hoje):
    if entrada.status_inea is None or entrada.data_coleta is None:
        return "sem_dado", None
    idade = (hoje - entrada.data_coleta).days
    if idade < 0 or idade > IDADE_MAXIMA_DIAS:
        return "sem_dado", idade
    if idade > IDADE_FRESCA_DIAS:
        return "antiga", idade
    return "fresca", idade


def classificar_chuva(entrada, agora):
    if entrada.chuva_24h_mm is None or entrada.chuva_lido_em is None:
        return "indisponivel"
    if agora - entrada.chuva_lido_em > IDADE_MAXIMA_DA_CHUVA:
        return "indisponivel"

    chuva_1h = entrada.chuva_1h_mm or 0.0
    limiar_moderada = (
        CHUVA_24H_MODERADA_COM_MARE_ALTA_MM
        if entrada.mare_alta
        else CHUVA_24H_MODERADA_MM
    )
    if entrada.chuva_24h_mm >= CHUVA_24H_FORTE_MM or chuva_1h > CHUVA_1H_FORTE_MM:
        return "forte"
    if entrada.chuva_24h_mm >= limiar_moderada or chuva_1h > CHUVA_1H_MODERADA_MM:
        return "moderada"
    return "baixa"


def calcular_confianca(entrada, inea, chuva):
    if inea == "sem_dado" or chuva == "indisponivel":
        return "baixa"
    if (
        inea == "antiga"
        or entrada.chuva_qualidade == "modelada"
        or entrada.mare_alta is None
    ):
        return "media"
    return "alta"


def recomendar_ponto(entrada, agora):
    # agora deve estar no horário de Brasília (UTC-3)
    inea, idade = classificar_inea(entrada, agora.date())
    chuva = classificar_chuva(entrada, agora)
    confianca = calcular_confianca(entrada, inea, chuva)
    coleta = entrada.data_coleta.strftime("%d/%m") if entrada.data_coleta else ""

    # 1. Vermelho: INEA impróprio ou chuva forte. Uma coisa sozinha já basta.
    vermelhos = []
    if inea != "sem_dado" and entrada.status_inea == "impropria":
        vermelhos.append(f"INEA: ponto impróprio na coleta de {coleta} ({idade} dias)")
    if chuva == "forte":
        vermelhos.append(
            f"chuva forte ({entrada.chuva_24h_mm} mm em 24h, {entrada.chuva_1h_mm} mm na última hora)"
        )
    if vermelhos:
        return Recomendacao(VERMELHO, confianca, vermelhos)

    # 2. Amarelo: qualquer dúvida que impeça de dizer que está tudo bem
    amarelos = []
    if inea == "sem_dado":
        amarelos.append("sem coleta do INEA usável nos últimos 30 dias")
    elif inea == "antiga":
        amarelos.append(
            f"coleta do INEA de {coleta} tem {idade} dias, mais que um ciclo"
        )
    if chuva == "moderada":
        so_pela_mare = (
            entrada.mare_alta
            and entrada.chuva_24h_mm < CHUVA_24H_MODERADA_MM
            and (entrada.chuva_1h_mm or 0.0) <= CHUVA_1H_MODERADA_MM
        )
        descricao = "chuva fraca com maré alta" if so_pela_mare else "chuva moderada"
        amarelos.append(
            f"{descricao} ({entrada.chuva_24h_mm} mm em 24h, {entrada.chuva_1h_mm} mm na última hora)"
        )
    if chuva == "indisponivel":
        amarelos.append("sem dado de chuva recente")
    if amarelos:
        return Recomendacao(AMARELO, confianca, amarelos)

    # 3. Verde: coleta própria e recente, chuva baixa e nenhuma dúvida pendente
    return Recomendacao(
        VERDE, confianca, [f"INEA próprio na coleta de {coleta} e chuva baixa"]
    )


def recomendar_praia(entradas_dos_pontos, agora):
    # A praia fica com a cor do pior ponto. A tela de detalhes mostra cada ponto.
    resultados = [recomendar_ponto(e, agora) for e in entradas_dos_pontos]
    return max(resultados, key=lambda r: GRAVIDADE[r.cor])


# Exemplos do PDF. Os códigos de ponto e os status vêm do histórico real do INEA
# (coleta de 15/10/2026). A chuva e a maré são valores inventados para exercitar a regra.
BRASILIA = timezone(timedelta(hours=-3))
AGORA = datetime(2026, 10, 19, 10, 0, tzinfo=BRASILIA)
LIDO_HA_20_MIN = datetime(2026, 10, 19, 9, 40, tzinfo=BRASILIA)


def exemplo(
    status,
    coleta,
    chuva_1h,
    chuva_24h,
    mare_alta,
    qualidade="observada",
    lido_em=LIDO_HA_20_MIN,
):
    return EntradaDoPonto(
        status, coleta, chuva_1h, chuva_24h, qualidade, lido_em, mare_alta
    )


COLETA_15_10 = date(2026, 10, 15)
EXEMPLOS = [
    # (nome, entrada, cor esperada)
    (
        "1. AR000 Arpoador, tudo calmo",
        exemplo("propria", COLETA_15_10, 0.0, 0.4, False),
        VERDE,
    ),
    (
        "2. CP100 Copacabana, chuva moderada",
        exemplo("propria", COLETA_15_10, 0.0, 6.2, False),
        AMARELO,
    ),
    (
        "3. LB000 Leblon, chuva fraca com maré alta",
        exemplo("propria", COLETA_15_10, 0.0, 2.0, True),
        AMARELO,
    ),
    (
        "4. IP006 Ipanema, chuva forte depois da coleta",
        exemplo("propria", COLETA_15_10, 9.0, 34.0, False),
        VERMELHO,
    ),
    (
        "5. BD010 Barra (Quebra-Mar), impróprio sem chuva",
        exemplo("impropria", COLETA_15_10, 0.0, 0.0, False),
        VERMELHO,
    ),
    (
        "6. LM002 Leme, coleta de 11 dias",
        exemplo("propria", date(2026, 10, 8), 0.0, 0.0, False),
        AMARELO,
    ),
    (
        "7. UR000 Urca, sem dado de chuva",
        exemplo("propria", COLETA_15_10, None, None, False, None, None),
        AMARELO,
    ),
    (
        "8. CP100 Copacabana, coleta de 32 dias",
        exemplo("propria", date(2026, 9, 17), 0.0, 0.0, False),
        AMARELO,
    ),
    (
        "9. BT000 Botafogo, impróprio com coleta de 11 dias",
        exemplo("impropria", date(2026, 10, 8), 0.0, 0.0, False),
        VERMELHO,
    ),
    (
        "10. FL000 Flamengo, própria mas chuva só do modelo e maré sem dado",
        exemplo("propria", COLETA_15_10, 0.6, 1.1, None, "modelada"),
        VERDE,
    ),
]

if __name__ == "__main__":
    for nome, entrada, esperado in EXEMPLOS:
        resultado = recomendar_ponto(entrada, AGORA)
        assert resultado.cor == esperado, (nome, resultado)
        print(
            f"{nome}\n   -> {resultado.cor} (confiança {resultado.confianca}): "
            + "; ".join(resultado.motivos)
        )
    print("\nTodos os exemplos bateram com o resultado esperado.")
