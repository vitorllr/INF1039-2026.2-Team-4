#!/usr/bin/env python3
"""PoC parser for INEA's public flood alert bulletin (Sistema de Alerta de Cheias).

Fetches the per-region station tables published at
https://alertadecheias.inea.rj.gov.br/dados/<regiao>.php and extracts them
into structured JSON: municipality, watercourse, station name, river trend,
last reading timestamp, alert level, accumulated rainfall and river level
readings.

See README.md in this folder for source details and caveats.
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser

BASE_URL = "https://alertadecheias.inea.rj.gov.br"

# The 9 hydrographic regions ("regioes hidrograficas") INEA publishes data for,
# as listed on https://alertadecheias.inea.rj.gov.br/dados.php
REGIONS = {
    "medio_paraiba_do_sul": "RH III Medio Paraiba do Sul",
    "guandu": "RH II Guandu",
    "baia_da_ilha_grande": "RH I Baia da Ilha Grande",
    "piabanha": "RH IV Piabanha",
    "baia_de_guanabara": "RH V Baia de Guanabara",
    "lagos_sao_joao": "RH VI Lagos Sao Joao",
    "baixo_paraiba_do_sul_e_itabapoana": "RH IX Baixo Paraiba do Sul e Itabapoana",
    "macae_e_das_ostras": "RH VIII Macae e das Ostras",
    "rio_dois_rios": "RH VII Rio Dois Rios",
}

# INEA's TLS chain for this host does not include the intermediate CA, so
# strict verification fails locally ("unable to verify the first certificate").
# See README.md caveats for details. We fall back to an unverified context
# rather than silently failing.
_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "BlueTide-PoC/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        raw = resp.read()
    # The page's <meta charset> tags are contradictory (both utf-8 and
    # windows-1252 are declared), but the actual bytes served are UTF-8.
    return raw.decode("utf-8", errors="replace")


class _TableParser(HTMLParser):
    """Minimal HTML table extractor: walks <table id="Table"> row by row."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_target_table = False
        self.table_depth = 0
        self.in_row = False
        self.in_cell = False
        self.current_cell_text = []
        self.current_cell_attrs = {}
        self.current_row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            if attrs.get("id") == "Table":
                self.in_target_table = True
                self.table_depth = 1
            elif self.in_target_table:
                self.table_depth += 1
        if not self.in_target_table:
            return
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell_text = []
            self.current_cell_attrs = attrs
        elif tag == "img" and self.in_cell:
            # Trend/status icons carry their meaning in the filename, e.g.
            # imagens/estavel.png, imagens/subindo.png, imagens/descendo.png
            src = attrs.get("src", "")
            self.current_cell_text.append(f"__IMG__:{src}")

    def handle_endtag(self, tag):
        if not self.in_target_table:
            return
        if tag == "table":
            self.table_depth -= 1
            if self.table_depth <= 0:
                self.in_target_table = False
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            text = "".join(self.current_cell_text).strip()
            self.current_row.append(
                {
                    "text": text,
                    "style": self.current_cell_attrs.get("style", ""),
                }
            )
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if self.current_row:
                self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell_text.append(data)


def _cell_alert_color(style: str) -> str | None:
    match = re.search(r"background-color:\s*([^;]+)", style)
    return match.group(1).strip() if match else None


def _cell_trend(text: str) -> str | None:
    match = re.search(r"__IMG__:.*?/(\w+)\.png", text)
    return match.group(1) if match else None


def parse_region_html(html: str, region_slug: str) -> list[dict]:
    parser = _TableParser()
    parser.feed(html)

    stations = []
    for row in parser.rows:
        cells = [c["text"] for c in row]
        # Header rows repeat the column titles; skip anything that isn't a
        # real 17-column data row (the table has a fixed column count).
        if len(cells) < 17:
            continue
        if cells[0] in ("Municipio", "Município", ""):
            continue

        trend = _cell_trend(cells[3])
        alert_color = _cell_alert_color(row[5]["style"])

        stations.append(
            {
                "regiao_hidrografica": REGIONS.get(region_slug, region_slug),
                "municipio": cells[0],
                "curso_dagua": cells[1],
                "nome_estacao": cells[2],
                "tendencia_rio": trend,
                "ultima_leitura": cells[4],
                "nivel_alerta": cells[5],
                "nivel_alerta_cor": alert_color,
                "chuva_acumulada_mm": {
                    "ultimo": cells[6],
                    "1h": cells[7],
                    "4h": cells[8],
                    "24h": cells[9],
                    "96h": cells[10],
                    "30d": cells[11],
                },
                "nivel_rio_m": {
                    "ultimo": cells[12],
                    "15min": cells[13],
                    "30min": cells[14],
                    "45min": cells[15],
                },
            }
        )
    return stations


def fetch_and_parse_region(region_slug: str) -> list[dict]:
    url = f"{BASE_URL}/dados/{region_slug}.php"
    html = fetch(url)
    return parse_region_html(html, region_slug)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--region",
        choices=sorted(REGIONS) + ["all"],
        default="baia_de_guanabara",
        help="Which hydrographic region to fetch (default: baia_de_guanabara, "
        "which covers the city of Rio de Janeiro and Baixada Fluminense).",
    )
    ap.add_argument("--out", default="-", help="Output file path, or - for stdout")
    args = ap.parse_args()

    slugs = list(REGIONS) if args.region == "all" else [args.region]

    all_stations = []
    errors = []
    for slug in slugs:
        try:
            all_stations.extend(fetch_and_parse_region(slug))
        except (urllib.error.URLError, TimeoutError) as exc:
            errors.append({"regiao": slug, "erro": str(exc)})

    output = {
        "fonte": f"{BASE_URL}/dados.php",
        "extraido_em": datetime.now(timezone.utc).isoformat(),
        "regioes_consultadas": slugs,
        "total_estacoes": len(all_stations),
        "estacoes": all_stations,
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
