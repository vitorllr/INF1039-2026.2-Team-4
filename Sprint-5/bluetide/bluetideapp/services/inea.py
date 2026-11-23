"""Gera o arquivo de qualidade da água do app a partir do histórico anual do INEA."""

import hashlib
import json
import os
import tempfile
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .inea_pdf import ler_historico, ler_ultimo_boletim

PAGE_URL = "https://www.inea.rj.gov.br/rio-de-janeiro/"
USER_AGENT = "BlueTide/0.1 (projeto academico INF1039)"
LAST_BULLETIN_TEXT = "Último Boletim Divulgado"
HISTORY_HREF_MARKER = "barra_e_zona_sul_historico"
INEA_HOST = "inea.rj.gov.br"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
MIN_POINTS = 30
MIN_DATES = 10
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POINTS_MAP_PATH = DATA_DIR / "inea_pontos.json"
WATER_FILE_PATH = DATA_DIR / "agua_inea.json"


class IneaError(RuntimeError):
    pass


def fetch(url: str, timeout: float = 30) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise IneaError(f"INEA respondeu HTTP {response.status} em {url}")
            content = response.read(MAX_DOWNLOAD_BYTES + 1)
    except OSError as exc:
        raise IneaError(f"Falha ao baixar {url}: {exc}") from exc
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise IneaError(f"Arquivo grande demais em {url}")
    return content


class _LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def discover_links(html: str, base: str = PAGE_URL) -> tuple[str, dict[int, str]]:
    """Acha o "Último Boletim Divulgado" e os históricos por ano da seção Zona Sul, só pelo texto dos links.

    A página tem uma seção por região, cada uma aberta por um link "Último Boletim Divulgado".
    A Zona Sul é a que tem "barra_e_zona_sul_historico" nos links de ano.
    """
    collector = _LinkCollector()
    collector.feed(html)
    sections = []
    for href, text in collector.links:
        if not href:
            continue
        url = urljoin(base, href)
        if text == LAST_BULLETIN_TEXT:
            sections.append({"bulletin": url, "years": {}})
        elif sections and text.isdigit() and len(text) == 4:
            sections[-1]["years"][int(text)] = url
    south = [s for s in sections if any(HISTORY_HREF_MARKER in u for u in s["years"].values())]
    if len(south) != 1:
        raise IneaError(f"Esperava 1 seção Zona Sul na página do INEA, achei {len(south)}; a página mudou?")
    for url in [south[0]["bulletin"], *south[0]["years"].values()]:
        host = urlparse(url).hostname or ""
        if host != INEA_HOST and not host.endswith("." + INEA_HOST):
            raise IneaError(f"Link fora do domínio do INEA: {url}")
    return south[0]["bulletin"], south[0]["years"]


def fetch_pdf(url: str, cache_dir: Path, fetcher=fetch) -> tuple[Path, str]:
    """Baixa o PDF e guarda no cache pelo hash do conteúdo."""
    content = fetcher(url)
    if not content.startswith(b"%PDF"):
        raise IneaError(f"{url} não devolveu um PDF")
    digest = hashlib.sha256(content).hexdigest()
    path = cache_dir / f"{digest}.pdf"
    if not path.exists():
        write_atomic_bytes(path, content)
    return path, digest


def latest_valid(collections):
    for collected_on, status in reversed(collections):
        if status in ("propria", "impropria"):
            return collected_on, status
    return None, None


def build_water_data(
    points: dict, postos_map: dict, source_url: str, now: datetime | None = None, today: date | None = None
) -> dict:
    if len(points) < MIN_POINTS:
        raise IneaError(f"Só {len(points)} pontos lidos do PDF; o layout mudou?")
    today = today or date.today()
    output = {}
    for slug, spec in postos_map["postos"].items():
        code = spec["ponto"]
        if code not in points:
            raise IneaError(f"Ponto {code} sumiu do PDF do INEA")
        collected_on, status = latest_valid(points[code]["coletas"])
        if status is None:
            raise IneaError(f"Ponto {code} sem nenhuma coleta válida no PDF")
        if collected_on > today:
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


def write_atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def write_atomic(path: Path, payload: dict) -> None:
    write_atomic_bytes(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def check_dates(points: dict) -> None:
    dates = {collected_on for point in points.values() for collected_on, _ in point["coletas"]}
    if len(dates) < MIN_DATES:
        raise IneaError(f"Só {len(dates)} datas de coleta lidas do PDF; o layout mudou?")


def check_not_older(payload: dict, path: Path) -> None:
    """A coleta de um posto nunca pode andar para trás em relação ao arquivo atual."""
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for slug, new in payload["points"].items():
        old = previous.get("points", {}).get(slug, {}).get("water", {}).get("collected_on")
        if old and new["water"]["collected_on"] < old:
            raise IneaError(f"{slug}: coleta {new['water']['collected_on']} é mais antiga que a atual ({old})")


def add_bulletin(points: dict, bulletin_date: date, statuses: dict) -> None:
    """Plano B de janeiro: acrescenta ao histórico do ano anterior a coleta do último boletim, se for mais nova."""
    for code, status in statuses.items():
        collections = points[code]["coletas"] if code in points else None
        if collections is not None and (not collections or bulletin_date > collections[-1][0]):
            collections.append((bulletin_date, status))


def generate(
    output: Path = WATER_FILE_PATH,
    pdf_path: Path | None = None,
    year: int | None = None,
    cache_dir: Path | None = None,
    force: bool = False,
    today: date | None = None,
    fetcher=None,
    log=print,
) -> dict | None:
    """Baixa o histórico do ano (ou usa pdf_path), lê, valida e grava sem tocar no arquivo antigo se algo falhar.

    Devolve None quando nada mudou desde a última execução bem-sucedida.
    """
    today = today or date.today()
    fetcher = fetcher or fetch
    postos_map = json.loads(POINTS_MAP_PATH.read_text(encoding="utf-8"))
    bulletin = None
    state = None
    if pdf_path is not None:
        source_url = "arquivo local"
        history = pdf_path
    else:
        cache_dir = cache_dir or output.parent / ".inea-cache"
        bulletin_url, years = discover_links(fetcher(PAGE_URL).decode("utf-8", errors="replace"))
        year = year or today.year
        if year in years:
            source_url = years[year]
        elif today.month == 1 and year - 1 in years:
            source_url = years[year - 1]
            log(f"Histórico de {year} ainda não existe na página; plano B: {year - 1} mais o último boletim")
            bulletin, _ = fetch_pdf(bulletin_url, cache_dir, fetcher)
        else:
            raise IneaError(f"Link do histórico de {year} não encontrado na página do INEA")
        history, digest = fetch_pdf(source_url, cache_dir, fetcher)
        state = cache_dir / "ultimo_sucesso.json"
        key = f"{digest}+{bulletin.stem if bulletin else ''}@{today.isoformat()}"
        if not force and output.exists() and state.exists():
            try:
                if json.loads(state.read_text(encoding="utf-8")).get("key") == key:
                    return None
            except ValueError:
                pass
    try:
        points = ler_historico(history)
        if bulletin is not None:
            bulletin_date, statuses = ler_ultimo_boletim(bulletin)
            add_bulletin(points, bulletin_date, statuses)
    except Exception as exc:
        raise IneaError(f"Layout do PDF mudou ou PDF ilegível: {exc}") from exc
    check_dates(points)
    payload = build_water_data(points, postos_map, source_url, today=today)
    check_not_older(payload, output)
    write_atomic(output, payload)
    if state is not None:
        write_atomic(state, {"key": key})
    return payload
