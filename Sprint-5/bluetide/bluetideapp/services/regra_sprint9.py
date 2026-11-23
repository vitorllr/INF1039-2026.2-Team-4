from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

VERDE = "verde"
AMARELO = "amarelo"
VERMELHO = "vermelho"
GRAVIDADE = {VERDE: 0, AMARELO: 1, VERMELHO: 2}

IDADE_FRESCA_DIAS = 9
IDADE_MAXIMA_DIAS = 30

CHUVA_1H_FORTE_MM = 7.6
CHUVA_1H_MODERADA_MM = 2.5
CHUVA_24H_FORTE_MM = 20.0
CHUVA_24H_MODERADA_MM = 5.0
CHUVA_24H_MODERADA_COM_MARE_ALTA_MM = 1.0
IDADE_MAXIMA_DA_CHUVA = timedelta(hours=3)


@dataclass
class EntradaDoPonto:
    status_inea: str | None
    data_coleta: date | None
    chuva_1h_mm: float | None
    chuva_24h_mm: float | None
    chuva_qualidade: str | None
    chuva_lido_em: datetime | None
    mare_alta: bool | None


@dataclass
class Recomendacao:
    cor: str
    confianca: str
    motivos: list = field(default_factory=list)


def _mm(valor):
    return f"{valor:.1f}".replace(".", ",")


def _texto_da_chuva(entrada):
    texto = f"{_mm(entrada.chuva_24h_mm)} mm em 24h"
    if entrada.chuva_1h_mm is not None:
        texto += f", {_mm(entrada.chuva_1h_mm)} mm na última hora"
    return texto


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
    inea, idade = classificar_inea(entrada, agora.date())
    chuva = classificar_chuva(entrada, agora)
    confianca = calcular_confianca(entrada, inea, chuva)
    coleta = entrada.data_coleta.strftime("%d/%m") if entrada.data_coleta else ""

    vermelhos = []
    if inea != "sem_dado" and entrada.status_inea == "impropria":
        vermelhos.append(f"INEA: ponto impróprio na coleta de {coleta} ({idade} dias)")
    if chuva == "forte":
        vermelhos.append(f"chuva forte ({_texto_da_chuva(entrada)})")
    if vermelhos:
        return Recomendacao(VERMELHO, confianca, vermelhos)

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
        amarelos.append(f"{descricao} ({_texto_da_chuva(entrada)})")
    if chuva == "indisponivel":
        amarelos.append("sem dado de chuva recente")
    if amarelos:
        return Recomendacao(AMARELO, confianca, amarelos + _aviso_da_mare(entrada))

    return Recomendacao(
        VERDE,
        confianca,
        [f"INEA próprio na coleta de {coleta} e chuva baixa"] + _aviso_da_mare(entrada),
    )


def _aviso_da_mare(entrada):
    if entrada.mare_alta is None:
        return ["maré sem dado: considerada não alta"]
    return []


def recomendar_praia(entradas_dos_pontos, agora):
    resultados = [recomendar_ponto(e, agora) for e in entradas_dos_pontos]
    return max(resultados, key=lambda r: GRAVIDADE[r.cor])