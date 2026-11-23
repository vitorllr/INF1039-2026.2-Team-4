from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bluetideapp.services import inea


class Command(BaseCommand):
    help = "Gera o arquivo de qualidade da água a partir do histórico anual do INEA."

    def add_arguments(self, parser):
        parser.add_argument("--pdf", type=Path, help="Usa um PDF local em vez de baixar do INEA.")
        parser.add_argument("--output", type=Path, default=inea.WATER_FILE_PATH)
        parser.add_argument("--year", type=int)

    def handle(self, *args, **options):
        try:
            payload = inea.generate(options["output"], options["pdf"], options["year"])
        except Exception as exc:
            raise CommandError(f"Arquivo anterior mantido. Falha: {exc}") from exc
        for slug, point in payload["points"].items():
            water = point["water"]
            self.stdout.write(f"{slug}: {water['inea_point']} {water['status']} {water['collected_on']}")
        self.stdout.write(self.style.SUCCESS(f"Gravado em {options['output']}"))
