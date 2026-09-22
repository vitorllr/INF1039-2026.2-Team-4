"""Implementacao de referencia da logica de recomendacao do BlueTide.

Ve Sprint-3/Vitor-Rocha/logica-recomendacao/logica-recomendacao.md para a
justificativa de cada regra, os exemplos trabalhados e os casos de borda.

Os limiares abaixo sao um ponto de partida assumido pela equipe, nao um
valor cientifico citavel, e precisam de validacao.
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class StatusInea(str, Enum):
    PROPRIO = "proprio"
    IMPROPRIO = "improprio"
    DESCONHECIDO = "desconhecido"


class Recomendacao(str, Enum):
    VERDE = "verde"
    AMARELO = "amarelo"
    VERMELHO = "vermelho"


RAIN_HEAVY_MM = 20.0
RAIN_MODERATE_MM = 5.0
BOLETIM_VALIDO_DIAS = 8


@dataclass
class EntradaRecomendacao:
    status_inea: StatusInea
    data_boletim: date | None
    data_consulta: date
    chuva_24h_mm: float | None
    mare_sizigia: bool | None


def _boletim_desatualizado(entrada: EntradaRecomendacao) -> bool:
    if entrada.data_boletim is None:
        return True
    idade_dias = (entrada.data_consulta - entrada.data_boletim).days
    return idade_dias > BOLETIM_VALIDO_DIAS


def calcular_recomendacao(entrada: EntradaRecomendacao) -> Recomendacao:
    chuva = entrada.chuva_24h_mm
    chuva_desconhecida = chuva is None

    if entrada.status_inea == StatusInea.IMPROPRIO:
        return Recomendacao.VERMELHO

    if entrada.status_inea == StatusInea.PROPRIO and not chuva_desconhecida:
        if chuva >= RAIN_HEAVY_MM:
            return Recomendacao.VERMELHO

    if entrada.status_inea == StatusInea.DESCONHECIDO:
        if chuva_desconhecida or chuva >= RAIN_MODERATE_MM:
            return Recomendacao.VERMELHO

    if entrada.status_inea == StatusInea.PROPRIO:
        chuva_moderada = (not chuva_desconhecida) and chuva >= RAIN_MODERATE_MM
        mare_alta = bool(entrada.mare_sizigia)
        if chuva_moderada or mare_alta or _boletim_desatualizado(entrada):
            return Recomendacao.AMARELO

    if entrada.status_inea == StatusInea.DESCONHECIDO:
        return Recomendacao.AMARELO

    return Recomendacao.VERDE
