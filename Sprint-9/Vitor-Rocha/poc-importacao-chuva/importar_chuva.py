import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

URL_ALERTA_RIO = "https://websempre.rio.rj.gov.br/json/chuvas"
URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"
FUSO = "America/Sao_Paulo"
TEMPO_LIMITE = 30
TENTATIVAS = 3
PAUSA_ENTRE_TENTATIVAS = 5
# O Alerta Rio bloqueia alguns clientes sem identificação, então a gente se apresenta
CABECALHOS = {"User-Agent": "BlueTide-PoC (projeto da disciplina INF1039)"}
ARQUIVO_DE_SAIDA = Path(__file__).parent / "chuva_por_praia.json"

# Os dois valores abaixo são chute inicial da equipe e precisam ser validados
DISTANCIA_MAXIMA_KM = 10
IDADE_MAXIMA_DA_LEITURA_MIN = 60

# Mesmas 12 praias do Sprint-8/Vitor-Rocha/poc-dados-clima/importar_clima.py
PRAIAS = [
    {"nome": "Leme", "latitude": -22.9636, "longitude": -43.1690},
    {"nome": "Copacabana", "latitude": -22.9711, "longitude": -43.1822},
    {"nome": "Arpoador", "latitude": -22.9890, "longitude": -43.1925},
    {"nome": "Ipanema", "latitude": -22.9868, "longitude": -43.2050},
    {"nome": "Leblon", "latitude": -22.9874, "longitude": -43.2232},
    {"nome": "São Conrado", "latitude": -22.9996, "longitude": -43.2660},
    {"nome": "Barra da Tijuca", "latitude": -23.0110, "longitude": -43.3650},
    {"nome": "Recreio", "latitude": -23.0272, "longitude": -43.4660},
    {"nome": "Urca", "latitude": -22.9470, "longitude": -43.1620},
    {"nome": "Vermelha", "latitude": -22.9550, "longitude": -43.1650},
    {"nome": "Botafogo", "latitude": -22.9440, "longitude": -43.1820},
    {"nome": "Flamengo", "latitude": -22.9330, "longitude": -43.1720},
]


def arredondar(valor):
    return None if valor is None else round(valor, 1)


def somar(valores):
    valores = [v for v in valores if v is not None]
    return round(sum(valores), 1) if valores else None


def distancia_em_km(lat1, lon1, lat2, lon2):
    # Fórmula de haversine, raio médio da Terra de 6371 km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(a))


def buscar_json(nome_da_fonte, url, **pedido):
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = requests.get(
                url, headers=CABECALHOS, timeout=TEMPO_LIMITE, **pedido
            )
            resposta.raise_for_status()
            # Quando o bloqueio pega, vem uma página HTML com status 200 e o json() falha
            return resposta.json()
        except (requests.RequestException, ValueError) as erro:
            print(f"{nome_da_fonte}, tentativa {tentativa}/{TENTATIVAS}: {erro}")
            if tentativa < TENTATIVAS:
                time.sleep(PAUSA_ENTRE_TENTATIVAS)
    return None


def baixar_estacoes():
    resposta = buscar_json("Alerta Rio", URL_ALERTA_RIO)
    if resposta is None:
        return None
    try:
        return [
            ler_estacao(o) for o in resposta["objects"] if o["kind"] == "pluviometric"
        ]
    except (KeyError, TypeError, ValueError) as erro:
        print(f"Alerta Rio, formato inesperado: {erro!r}")
        return None


def ler_estacao(objeto):
    dados = objeto["data"]
    return {
        "nome": objeto["name"],
        "latitude": objeto["location"][0],
        "longitude": objeto["location"][1],
        "lido_em": datetime.fromisoformat(objeto["read_at"]),
        # No feed os campos h01, h03, h24 e h96 são a chuva acumulada nas últimas N horas, em mm
        "chuva_1h_mm": arredondar(dados.get("h01")),
        "chuva_3h_mm": arredondar(dados.get("h03")),
        "chuva_24h_mm": arredondar(dados.get("h24")),
        "chuva_96h_mm": arredondar(dados.get("h96")),
    }


def baixar_chuva_do_modelo():
    respostas = buscar_json(
        "Open-Meteo",
        URL_PREVISAO,
        params={
            "latitude": ",".join(str(p["latitude"]) for p in PRAIAS),
            "longitude": ",".join(str(p["longitude"]) for p in PRAIAS),
            "timezone": FUSO,
            "current": "precipitation",
            "hourly": "precipitation",
            "past_days": 4,
            "forecast_days": 2,
        },
    )
    if respostas is None:
        return None

    modelo = {}
    for praia, resposta_da_praia in zip(PRAIAS, respostas):
        fuso = timezone(timedelta(seconds=resposta_da_praia["utc_offset_seconds"]))
        horas = resposta_da_praia["hourly"]["time"]
        chuva = resposta_da_praia["hourly"]["precipitation"]

        # O valor de cada hora é a chuva da hora anterior a ela. Então a última hora
        # completa é a hora cheia mais recente, e dela pra trás a gente soma as janelas.
        hora_cheia = resposta_da_praia["current"]["time"][:13] + ":00"
        i = horas.index(hora_cheia)

        modelo[praia["nome"]] = {
            "lido_em": datetime.fromisoformat(hora_cheia).replace(tzinfo=fuso),
            "chuva_1h_mm": somar(chuva[i : i + 1]),
            "chuva_3h_mm": somar(chuva[i - 2 : i + 1]),
            "chuva_24h_mm": somar(chuva[i - 23 : i + 1]),
            "chuva_96h_mm": somar(chuva[i - 95 : i + 1]),
            "previsao_6h_mm": somar(chuva[i + 1 : i + 7]),
            "previsao_24h_mm": somar(chuva[i + 1 : i + 25]),
        }
    return modelo


def estacao_mais_proxima(praia, estacoes):
    candidatas = [e for e in estacoes if e["chuva_24h_mm"] is not None]
    if not candidatas:
        return None, None
    distancias = [
        distancia_em_km(
            praia["latitude"], praia["longitude"], e["latitude"], e["longitude"]
        )
        for e in candidatas
    ]
    menor = distancias.index(min(distancias))
    return candidatas[menor], round(distancias[menor], 1)


def escolher_chuva(praia, estacoes, modelo_da_praia, agora):
    # Primeiro tenta a chuva observada. Só cai pro modelo se não der pra confiar nela.
    motivo = "feed do Alerta Rio indisponível"
    if estacoes is not None:
        estacao, distancia = estacao_mais_proxima(praia, estacoes)
        if estacao is None:
            motivo = "nenhuma estação com leitura de 24h"
        else:
            idade_min = (agora - estacao["lido_em"]).total_seconds() / 60
            if distancia > DISTANCIA_MAXIMA_KM:
                motivo = f"estação mais próxima a {distancia} km"
            elif idade_min > IDADE_MAXIMA_DA_LEITURA_MIN:
                motivo = (
                    f"leitura da estação {estacao['nome']} com {round(idade_min)} min"
                )
            else:
                return {
                    "fonte": "alerta_rio",
                    "qualidade": "observada",
                    "estacao": estacao["nome"],
                    "distancia_km": distancia,
                    "lido_em": estacao["lido_em"].isoformat(),
                    "chuva_1h_mm": estacao["chuva_1h_mm"],
                    "chuva_3h_mm": estacao["chuva_3h_mm"],
                    "chuva_24h_mm": estacao["chuva_24h_mm"],
                    "chuva_96h_mm": estacao["chuva_96h_mm"],
                }

    if modelo_da_praia is None:
        return None
    return {
        "fonte": "open_meteo",
        "qualidade": "modelada",
        "motivo_do_fallback": motivo,
        "estacao": None,
        "distancia_km": None,
        "lido_em": modelo_da_praia["lido_em"].isoformat(),
        "chuva_1h_mm": modelo_da_praia["chuva_1h_mm"],
        "chuva_3h_mm": modelo_da_praia["chuva_3h_mm"],
        "chuva_24h_mm": modelo_da_praia["chuva_24h_mm"],
        "chuva_96h_mm": modelo_da_praia["chuva_96h_mm"],
    }


def importar_chuva():
    estacoes = baixar_estacoes()
    modelo = baixar_chuva_do_modelo()
    if estacoes is None and modelo is None:
        return None

    agora = datetime.now(timezone.utc)
    por_praia = {}
    for praia in PRAIAS:
        modelo_da_praia = modelo[praia["nome"]] if modelo else None
        previsao = None
        if modelo_da_praia:
            previsao = {
                "previsao_6h_mm": modelo_da_praia["previsao_6h_mm"],
                "previsao_24h_mm": modelo_da_praia["previsao_24h_mm"],
            }
        por_praia[praia["nome"]] = {
            "chuva": escolher_chuva(praia, estacoes, modelo_da_praia, agora),
            "previsao": previsao,
        }
    return por_praia


if __name__ == "__main__":
    chuva = importar_chuva()
    if chuva is None:
        print("Nenhuma fonte respondeu, o arquivo de saída não foi alterado.")
        sys.exit(1)

    ARQUIVO_DE_SAIDA.write_text(
        json.dumps(
            {
                "gerado_em": datetime.now(timezone.utc).isoformat(),
                "fontes": {
                    "observada": URL_ALERTA_RIO,
                    "modelada_e_previsao": URL_PREVISAO,
                },
                "chuva_por_praia": chuva,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    for nome, dados in chuva.items():
        medida = dados["chuva"]
        if medida is None:
            print(f"{nome}: sem dado de chuva")
            continue
        origem = (
            f"estação {medida['estacao']} a {medida['distancia_km']} km"
            if medida["estacao"]
            else f"modelo ({medida['motivo_do_fallback']})"
        )
        print(
            f"{nome}: {medida['chuva_1h_mm']} mm na última hora,"
            f" {medida['chuva_24h_mm']} mm em 24h - {medida['qualidade']}, {origem}"
        )
    print(f"\nDados completos em {ARQUIVO_DE_SAIDA.name}")
