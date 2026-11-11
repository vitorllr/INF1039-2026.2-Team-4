import os
import secrets
from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


DEMO_FAVORITES = ["ipanema-posto-10", "ipanema-posto-8", "ipanema-posto-9"]


class Command(BaseCommand):
    help = (
        "Cria ou redefine a conta fictícia da persona Pedro para demonstrar login, "
        "perfil e verificação em duas etapas. A senha nunca fica no repositório."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", default="pedro@example.com")
        parser.add_argument(
            "--password-env",
            default="BLUETIDE_DEMO_PASSWORD",
            help="Variável de ambiente lida para a senha. Sem ela, a senha é pedida ou gerada.",
        )
        parser.add_argument(
            "--generate-password",
            action="store_true",
            help="Gera uma senha aleatória e a mostra uma única vez.",
        )

    def handle(self, *args, email, password_env, generate_password, **options):
        password = os.environ.get(password_env, "")
        generated = False
        if not password and generate_password:
            password = secrets.token_urlsafe(12)
            generated = True
        if not password:
            password = getpass("Senha da conta demo: ")
        if not password:
            raise CommandError("Informe uma senha.")

        Usuario = get_user_model()
        # The username keeps the original e-mail even after the persona edits
        # its e-mail on the profile page, so it finds the account to reset.
        user = (
            Usuario.objects.filter(username__iexact=email).first()
            or Usuario.objects.filter(email__iexact=email).first()
            or Usuario(username=email)
        )
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error

        user.email = email.lower()
        user.nome = "Pedro Santos"
        user.cidade = "Rio de Janeiro"
        user.estado = "RJ"
        user.perfil_praia = "tranquilo"
        user.meio_transporte_preferido = "bicicleta"
        user.usar_localizacao_celular = False
        user.economia_dados = True
        user.alertas_mudanca = True
        user.pontos_favoritos = DEMO_FAVORITES
        user.two_factor_enabled = False
        user.two_factor_secret = ""
        user.two_factor_last_used_step = None
        user.two_factor_recovery_codes = []
        if user.foto:
            user.foto.delete(save=False)
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"Conta demo pronta: {user.email}"))
        if generated:
            self.stdout.write(f"Senha gerada (mostrada só agora): {password}")
