"""Gera o arquivo de qualidade da água do app a partir do histórico anual do INEA."""

import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

from .inea_pdf import ler_historico

PAGE_URL = "https://www.inea.rj.gov.br/rio-de-janeiro/"
USER_AGENT = "BlueTide/0.1 (projeto academico INF1039)"
HISTORY_HREF_MARKER = "barra_e_zona_sul_historico"
MIN_POINTS = 30
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POINTS_MAP_PATH = DATA_DIR / "inea_pontos.json"
WATER_FILE_PATH = DATA_DIR / "agua_inea.json"


class IneaError(RuntimeError):
    pass


def fetch(url: str, timeout: float = 60) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise IneaError(f"INEA respondeu HTTP {response.status} em {url}")
        return response.read()


def find_history_url(html: str, year: int) -> str:
    """O link muda a cada atualização, então a âncora é o texto do ano e o trecho do href."""
    found = []
    for href, label in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        text = " ".join(unescape(re.sub(r"<[^>]+>", "", label)).split())
        if text == str(year) and HISTORY_HREF_MARKER in href:
            found.append(href)
    if len(found) != 1:
        raise IneaError(f"Esperava 1 link do histórico {year}, achei {len(found)}")
    return found[0]


def latest_valid(collections):
    for collected_on, status in reversed(collections):
        if status in ("propria", "impropria"):
            return collected_on, status
    return None, None


def build_water_data(points: dict, postos_map: dict, source_url: str, now: datetime | None = None) -> dict:
    if len(points) < MIN_POINTS:
        raise IneaError(f"Só {len(points)} pontos lidos do PDF; o layout mudou?")
    output = {}
    for slug, spec in postos_map["postos"].items():
        code = spec["ponto"]
        if code not in points:
            raise IneaError(f"Ponto {code} sumiu do PDF do INEA")
        collected_on, status = latest_valid(points[code]["coletas"])
        if status is None:
            raise IneaError(f"Ponto {code} sem nenhuma coleta válida no PDF")
        if collected_on > date.today():
            raise IneaError(f"Coleta de {code} em data futura: {collected_on}")
        output[slug] = {
            "water": {
                "status": status,
                "collected_on": collected_on.isoformat(),
                "inea_point": code,
                "inea_location": points[code]["localizacao"],
                "distance_m": spec["distancia_m"],
                "source": f"INEA, coleta de {collected_on:%d/%m/%Y}",
            }
        }
    return {
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        "source_url": source_url,
        "points": output,
    }


def write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def generate(output: Path = WATER_FILE_PATH, pdf_path: Path | None = None, year: int | None = None) -> dict:
    """Baixa o histórico do ano (ou usa pdf_path), lê, e grava o arquivo sem tocar no antigo se algo falhar."""
    postos_map = json.loads(POINTS_MAP_PATH.read_text(encoding="utf-8"))
    if pdf_path is not None:
        source_url = "arquivo local"
        points = ler_historico(pdf_path)
    else:
        html = fetch(PAGE_URL).decode("utf-8", errors="replace")
        source_url = find_history_url(html, year or date.today().year)
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "historico.pdf"
            pdf.write_bytes(fetch(source_url))
            points = ler_historico(pdf)
    payload = build_water_data(points, postos_map, source_url)
    write_atomic(output, payload)
    return payload
