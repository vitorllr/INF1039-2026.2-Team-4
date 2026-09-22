"""Esqueleto da API do BlueTide (FastAPI).

Prova de conceito do shape descrito em stack-arquitetura-api.md.
Os endpoints devolvem dados mocados; nao ha polling nem parsing real ainda.
Rodar com: uvicorn main:app --reload
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="BlueTide API", version="0.0.1")


class Praia(BaseModel):
    id: str
    nome: str
    lat: float
    lon: float


class BoletimIneaComponente(BaseModel):
    status: Literal["proprio", "improprio", "sem_dado"]
    coletado_em: datetime
    idade_horas: float


class ChuvaComponente(BaseModel):
    mm_ultimas_24h: float
    dentro_janela_restricao: bool
    fonte: str
    atualizado_em: datetime


class MareComponente(BaseModel):
    fase: Literal["enchente", "vazante", "preamar", "baixa_mar"]
    altura_m: float
    atualizado_em: datetime


class Componentes(BaseModel):
    boletim_inea: BoletimIneaComponente
    chuva: ChuvaComponente
    mare: MareComponente


class Recomendacao(BaseModel):
    praia_id: str
    praia_nome: str
    status: Literal["verde", "amarelo", "vermelho"]
    motivo: str
    atualizado_em: datetime
    componentes: Componentes


PRAIAS_MOCK = [
    Praia(
        id="copacabana-posto-6", nome="Copacabana - Posto 6", lat=-22.9711, lon=-43.1822
    ),
    Praia(id="ipanema-posto-9", nome="Ipanema - Posto 9", lat=-22.9868, lon=-43.2013),
]


@app.get("/api/v1/praias", response_model=list[Praia])
def listar_praias() -> list[Praia]:
    return PRAIAS_MOCK


@app.get("/api/v1/praias/{praia_id}/recomendacao", response_model=Recomendacao)
def obter_recomendacao(praia_id: str) -> Recomendacao:
    praia = next((p for p in PRAIAS_MOCK if p.id == praia_id), None)
    if praia is None:
        raise HTTPException(status_code=404, detail="Praia nao encontrada")

    agora = datetime.now(timezone.utc)
    return Recomendacao(
        praia_id=praia.id,
        praia_nome=praia.nome,
        status="amarelo",
        motivo="Chuva forte nas ultimas 18h; dentro da janela de 24h de restricao do INEA.",
        atualizado_em=agora,
        componentes=Componentes(
            boletim_inea=BoletimIneaComponente(
                status="proprio",
                coletado_em=agora,
                idade_horas=90,
            ),
            chuva=ChuvaComponente(
                mm_ultimas_24h=32.5,
                dentro_janela_restricao=True,
                fonte="open-meteo-weather-api",
                atualizado_em=agora,
            ),
            mare=MareComponente(
                fase="enchente",
                altura_m=0.8,
                atualizado_em=agora,
            ),
        ),
    )
