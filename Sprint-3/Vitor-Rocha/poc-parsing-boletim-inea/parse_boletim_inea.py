#!/usr/bin/env python3
"""PoC parser for INEA's public beach-water-quality bulletin (balneabilidade).

INEA's own page (https://www.inea.rj.gov.br/ar-agua-e-solo/balneabilidade-das-praias/)
publishes the current statewide bulletin only as a weekly PDF whose per-point
status is drawn as colored markers on map images, not as extractable text
(see README.md). The same classification INEA publishes for Niteroi's beaches
is also exposed as structured JSON through Niteroi's public GIS portal, in a
layer named "Boletins de Balneabilidade - INEA". This script queries that
ArcGIS FeatureServer and extracts one record per monitoring point: beach
name, municipality, status (propria/impropria) and bulletin date.

See README.md in this folder for source details and caveats (this covers
Niteroi only, and the feed has not been updated since 2023).
"""

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

LAYER_URL = (
    "https://geo.niteroi.rj.gov.br/arcgis/rest/services/"
    "Aplicacoes/AplicacaoINEA/FeatureServer/0/query"
)
MUNICIPIO = "Niteroi"

FIELDS = [
    "praia",
    "codigo_ponto",
    "localizacao",
    "ultima_data_atualizacao",
    "ultimo_status",
]

# This host's TLS chain does not include the intermediate CA, so strict
# verification fails locally ("unable to verify the first certificate").
# See README.md caveats. We fall back to an unverified context rather than
# silently failing.
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE

_STATUS_MAP = {
    "Própria": "propria",
    "Propria": "propria",
    "Imprópria": "impropria",
    "Impropria": "impropria",
}


def fetch_points(timeout: int = 20) -> list[dict]:
    query = {
        "where": "1=1",
        "outFields": ",".join(FIELDS),
        "returnDistinctValues": "true",
        "returnGeometry": "false",
        "f": "json",
    }
    url = f"{LAYER_URL}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "BlueTide-PoC/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    if "error" in payload:
        raise RuntimeError(f"ArcGIS error: {payload['error']}")

    return [f["attributes"] for f in payload.get("features", [])]


def _epoch_ms_to_date(value) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def parse_points(raw_points: list[dict]) -> list[dict]:
    pontos = []
    for attrs in raw_points:
        status_raw = attrs.get("ultimo_status")
        pontos.append(
            {
                "praia": attrs.get("praia"),
                "municipio": MUNICIPIO,
                "codigo_ponto": attrs.get("codigo_ponto"),
                "localizacao": attrs.get("localizacao"),
                "status": _STATUS_MAP.get(status_raw, status_raw),
                "data_publicacao_boletim": _epoch_ms_to_date(
                    attrs.get("ultima_data_atualizacao")
                ),
            }
        )
    pontos.sort(key=lambda p: (p["praia"] or "", p["codigo_ponto"] or ""))
    return pontos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="-", help="Output file path, or - for stdout")
    args = ap.parse_args()

    errors = []
    pontos = []
    try:
        pontos = parse_points(fetch_points())
    except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        errors.append({"erro": str(exc)})

    output = {
        "fonte": LAYER_URL,
        "extraido_em": datetime.now(timezone.utc).isoformat(),
        "total_pontos": len(pontos),
        "pontos": pontos,
        "erros": errors,
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    sys.exit(main())
