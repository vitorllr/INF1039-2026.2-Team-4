import json
import tempfile
from datetime import date
from io import StringIO
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from .services import inea
from .services.inea_pdf import ler_historico, ler_ultimo_boletim, normalizar_status

try:
    import pdfplumber  # noqa: F401
except ImportError:
    pdfplumber = None

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "inea"
BULLETIN_URL = "https://www.inea.rj.gov.br/wp-content/uploads/2026/11/Zona-sudoeste-e-Zona-sul-18-11-26.pdf"
URL_2026 = "https://www.inea.rj.gov.br/wp-content/uploads/2026/11/barra_e_zona_sul_historico-3.pdf"
URL_2025 = "https://www.inea.rj.gov.br/wp-content/uploads/2026/01/barra_e_zona_sul_historico.pdf"
TODAY = date(2026, 11, 23)


def read(name):
    return (FIXTURES / name).read_bytes()


def fake_fetcher(responses):
    def fetcher(url):
        if url not in responses:
            raise inea.IneaError(f"sem resposta falsa para {url}")
        return responses[url]

    return fetcher


def normal_responses():
    return {
        inea.PAGE_URL: read("pagina_rio_de_janeiro.html"),
        URL_2026: read("historico_2026.pdf"),
        URL_2025: read("historico_2026.pdf"),
        BULLETIN_URL: read("ultimo_boletim_2026-11-18.pdf"),
    }


class LinkDiscoveryTests(SimpleTestCase):
    def test_finds_bulletin_and_years_by_link_text(self):
        html = read("pagina_rio_de_janeiro.html").decode("utf-8", errors="replace")

        bulletin, years = inea.discover_links(html)

        self.assertEqual(bulletin, BULLETIN_URL)
        self.assertEqual(years[2026], URL_2026)
        self.assertEqual(years[2025], URL_2025)

    def test_pdf_name_and_folder_do_not_matter(self):
        html = (
            '<a href="/x/novo-nome.pdf">Último Boletim Divulgado</a>'
            '<a href="/y/barra_e_zona_sul_historico-9.pdf"> 2027 </a>'
        )

        bulletin, years = inea.discover_links(html)

        self.assertEqual(bulletin, "https://www.inea.rj.gov.br/x/novo-nome.pdf")
        self.assertEqual(years[2027], "https://www.inea.rj.gov.br/y/barra_e_zona_sul_historico-9.pdf")

    def test_page_without_south_zone_section_fails(self):
        with self.assertRaises(inea.IneaError):
            inea.discover_links('<a href="https://www.inea.rj.gov.br/a.pdf">Último Boletim Divulgado</a>')

    def test_link_outside_inea_domain_fails(self):
        html = (
            '<a href="https://evil.example/a.pdf">Último Boletim Divulgado</a>'
            '<a href="https://evil.example/barra_e_zona_sul_historico.pdf">2026</a>'
        )
        with self.assertRaises(inea.IneaError):
            inea.discover_links(html)


@skipUnless(pdfplumber, "pdfplumber not installed (requirements-inea.txt)")
class ParserTests(SimpleTestCase):
    def test_history_2026(self):
        points = ler_historico(FIXTURES / "historico_2026.pdf")

        self.assertEqual(len(points), 39)
        self.assertEqual(points["IP006"]["coletas"][-1], (date(2026, 11, 18), "impropria"))

    def test_last_bulletin_normalizes_four_character_codes(self):
        bulletin_date, statuses = ler_ultimo_boletim(FIXTURES / "ultimo_boletim_2026-11-18.pdf")

        self.assertEqual(bulletin_date, date(2026, 11, 18))
        self.assertEqual(statuses["IP003"], "impropria")
        self.assertEqual(statuses["JT000"], "nao_realizada")

    def test_unknown_status_text_fails_loudly(self):
        self.assertEqual(normalizar_status("Amostragem não realizada"), "nao_realizada")
        with self.assertRaises(ValueError):
            normalizar_status("Talvez")


@skipUnless(pdfplumber, "pdfplumber not installed (requirements-inea.txt)")
class JobTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.output = Path(folder.name) / "agua.json"
        self.cache = Path(folder.name) / "cache"
        self.logs = []

    def run_job(self, responses, today=TODAY, **kwargs):
        return inea.generate(
            self.output, cache_dir=self.cache, today=today, fetcher=fake_fetcher(responses), log=self.logs.append, **kwargs
        )

    def test_writes_real_data_and_caches_the_pdf_by_hash(self):
        self.run_job(normal_responses())

        data = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(data["source_url"], URL_2026)
        self.assertEqual(data["points"]["ipanema-posto-8"]["water"]["status"], "impropria")
        self.assertEqual(data["points"]["ipanema-posto-7"]["water"]["collected_on"], "2026-11-18")
        self.assertEqual(len(list(self.cache.glob("*.pdf"))), 1)
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])

    def test_second_run_without_changes_keeps_the_file(self):
        self.run_job(normal_responses())
        before = self.output.stat().st_mtime_ns

        self.assertIsNone(self.run_job(normal_responses()))
        self.assertEqual(self.output.stat().st_mtime_ns, before)
        self.assertIsNotNone(self.run_job(normal_responses(), force=True))

    def test_changed_layout_keeps_previous_file(self):
        self.run_job(normal_responses())
        before = self.output.read_bytes()
        broken = normal_responses()
        broken[URL_2026] = read("historico_2020_layout_quebrado.pdf")

        with self.assertRaisesRegex(inea.IneaError, "Layout"):
            self.run_job(broken, force=True)
        self.assertEqual(self.output.read_bytes(), before)

    def test_failures_never_create_the_file(self):
        for url, content in ((URL_2026, b"%PDF-1.4 truncado"), (URL_2026, b"<html>manutencao</html>")):
            broken = normal_responses()
            broken[url] = content
            with self.assertRaises(inea.IneaError):
                self.run_job(broken)
        with self.assertRaises(inea.IneaError):
            self.run_job({})
        self.assertFalse(self.output.exists())

    def test_year_without_link_fails_outside_january(self):
        with self.assertRaisesRegex(inea.IneaError, "2027"):
            self.run_job(normal_responses(), today=date(2027, 3, 10))

    def test_collection_going_back_in_time_fails(self):
        self.output.write_text(
            json.dumps({"points": {"ipanema-posto-8": {"water": {"collected_on": "2026-11-20"}}}}), encoding="utf-8"
        )
        with self.assertRaisesRegex(inea.IneaError, "mais antiga"):
            self.run_job(normal_responses())

    def test_january_without_new_history_uses_previous_year_and_bulletin(self):
        self.run_job(normal_responses(), today=date(2027, 1, 5))

        self.assertTrue(any("plano B" in line for line in self.logs))
        data = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(data["source_url"], URL_2026)
        self.assertEqual(data["points"]["ipanema-posto-9"]["water"]["collected_on"], "2026-11-18")

    def test_bulletin_adds_only_newer_collections_of_known_points(self):
        points = ler_historico(FIXTURES / "historico_2026.pdf")
        points["IP006"]["coletas"] = [c for c in points["IP006"]["coletas"] if c[0] < date(2026, 11, 18)]

        inea.add_bulletin(points, date(2026, 11, 18), {"IP006": "impropria", "ZZ001": "propria"})

        self.assertEqual(points["IP006"]["coletas"][-1], (date(2026, 11, 18), "impropria"))
        self.assertNotIn("ZZ001", points)

    def test_too_few_collection_dates_fails(self):
        points = ler_historico(FIXTURES / "historico_2026.pdf")
        for point in points.values():
            point["coletas"] = point["coletas"][:3]

        with self.assertRaisesRegex(inea.IneaError, "datas"):
            inea.check_dates(points)

    def test_future_collection_fails(self):
        with self.assertRaisesRegex(inea.IneaError, "futura"):
            self.run_job(normal_responses(), today=date(2026, 11, 10))


class CommandTests(SimpleTestCase):
    def test_error_exits_non_zero_and_keeps_the_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "agua.json"
            target.write_text("{}", encoding="utf-8")
            with patch.object(inea, "fetch", side_effect=inea.IneaError("site fora do ar")):
                with self.assertRaisesRegex(CommandError, "fora do ar"):
                    call_command("atualizar_agua_inea", output=target, stdout=StringIO())
            self.assertEqual(target.read_text(encoding="utf-8"), "{}")
