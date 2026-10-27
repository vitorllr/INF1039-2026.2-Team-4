import json
from datetime import date, datetime, timezone
from pathlib import Path

import requests

URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"
FUSO = "America/Sao_Paulo"
TEMPO_LIMITE = 30
ARQUIVO_DE_SAIDA = Path(__file__).parent / "dados_clima.json"

CAMPOS_POR_HORA = [
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "uv_index",
]

# Coordenadas aproximadas do centro de cada praia
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


def importar_clima():
    # O Open-Meteo aceita várias coordenadas numa chamada só
    # e devolve uma resposta por coordenada, na mesma ordem.
    resposta = requests.get(
        URL_PREVISAO,
        params={
            "latitude": ",".join(str(p["latitude"]) for p in PRAIAS),
            "longitude": ",".join(str(p["longitude"]) for p in PRAIAS),
            "timezone": FUSO,
            "hourly": ",".join(CAMPOS_POR_HORA),
            # Os dois dias passados respondem "choveu ontem?"
            "past_days": 2,
            "forecast_days": 2,
        },
        timeout=TEMPO_LIMITE,
    )
    resposta.raise_for_status()

    por_praia = {}
    for praia, resposta_da_praia in zip(PRAIAS, resposta.json()):
        horas = resposta_da_praia["hourly"]
        por_praia[praia["nome"]] = [
            {"hora": hora, **{campo: horas[campo][i] for campo in CAMPOS_POR_HORA}}
            for i, hora in enumerate(horas["time"])
        ]
    return por_praia


def resumo_do_dia(serie, campo, agregacao):
    hoje = date.today().isoformat()
    valores = [
        h[campo] for h in serie if h["hora"].startswith(hoje) and h[campo] is not None
    ]
    return round(agregacao(valores), 2) if valores else None


if __name__ == "__main__":
    clima = importar_clima()
    ARQUIVO_DE_SAIDA.write_text(
        json.dumps(
            {
                "gerado_em": datetime.now(timezone.utc).isoformat(),
                "fonte": URL_PREVISAO,
                "clima_por_praia": clima,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    for nome, horas in clima.items():
        print(
            f"{nome}: {len(horas)} horas,"
            f" máx hoje {resumo_do_dia(horas, 'temperature_2m', max)} °C,"
            f" chuva hoje {resumo_do_dia(horas, 'precipitation', sum)} mm,"
            f" vento máx {resumo_do_dia(horas, 'wind_speed_10m', max)} km/h,"
            f" UV máx {resumo_do_dia(horas, 'uv_index', max)}"
        )
    print(f"\nDados completos em {ARQUIVO_DE_SAIDA.name}")
