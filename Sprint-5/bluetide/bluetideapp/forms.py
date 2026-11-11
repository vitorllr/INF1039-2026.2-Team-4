import uuid

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.core.files.uploadedfile import UploadedFile

from .security import TOTP_DIGITS, normalize_recovery_code


Usuario = get_user_model()

MAX_PHOTO_BYTES = 2 * 1024 * 1024
ESTADOS = [
    ("", "Selecione"),
    ("AC", "AC"),
    ("AL", "AL"),
    ("AP", "AP"),
    ("AM", "AM"),
    ("BA", "BA"),
    ("CE", "CE"),
    ("DF", "DF"),
    ("ES", "ES"),
    ("GO", "GO"),
    ("MA", "MA"),
    ("MT", "MT"),
    ("MS", "MS"),
    ("MG", "MG"),
    ("PA", "PA"),
    ("PB", "PB"),
    ("PR", "PR"),
    ("PE", "PE"),
    ("PI", "PI"),
    ("RJ", "RJ"),
    ("RN", "RN"),
    ("RS", "RS"),
    ("RO", "RO"),
    ("RR", "RR"),
    ("SC", "SC"),
    ("SP", "SP"),
    ("SE", "SE"),
    ("TO", "TO"),
]


class DescribedErrorsMixin:
    """Link each input to its help text and error message for screen readers.

    Views also reject values after validation, such as a TOTP code that does
    not match, so the links are refreshed on every added error as well.
    """

    def full_clean(self):
        super().full_clean()
        self._link_descriptions()

    def add_error(self, field, error):
        super().add_error(field, error)
        self._link_descriptions()

    def _link_descriptions(self):
        errors = self._errors or {}
        for name, field in self.fields.items():
            bound = self[name]
            described_by = []
            if field.help_text:
                described_by.append(f"{bound.auto_id}_helptext")
            if name in errors:
                described_by.append(f"{bound.auto_id}_errors")
            if described_by:
                field.widget.attrs["aria-describedby"] = " ".join(described_by)
            else:
                field.widget.attrs.pop("aria-describedby", None)


def _image_extension(header: bytes) -> str | None:
    """Identify the image by its signature instead of trusting the browser."""
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


class LoginForm(DescribedErrorsMixin, forms.Form):
    email = forms.EmailField(
        label="E-mail",
        error_messages={
            "required": "Informe seu e-mail.",
            "invalid": "Digite um e-mail válido, como nome@exemplo.com.",
        },
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "voce@exemplo.com",
            }
        ),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        error_messages={"required": "Informe sua senha."},
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Sua senha",
            }
        ),
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user = None

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        candidate = Usuario.objects.filter(email__iexact=cleaned_data["email"]).first()
        if candidate is not None:
            self.user = authenticate(
                self.request,
                username=candidate.get_username(),
                password=cleaned_data["password"],
            )
        if self.user is None:
            raise forms.ValidationError(
                "E-mail ou senha incorretos. Confira os dois campos e tente de novo."
            )
        return cleaned_data


class ProfileForm(DescribedErrorsMixin, forms.ModelForm):
    estado = forms.ChoiceField(label="Estado", choices=ESTADOS, required=False)
    senha_atual = forms.CharField(
        label="Senha atual",
        required=False,
        strip=False,
        help_text="Necessária apenas para trocar o e-mail da conta.",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    class Meta:
        model = Usuario
        fields = (
            "foto",
            "nome",
            "email",
            "cidade",
            "estado",
            "perfil_praia",
            "meio_transporte_preferido",
            "usar_localizacao_celular",
            "economia_dados",
            "alertas_mudanca",
        )
        labels = {
            "foto": "Foto de perfil",
            "nome": "Nome",
            "email": "E-mail",
            "cidade": "Cidade",
            "perfil_praia": "Perfil de praia",
            "meio_transporte_preferido": "Como você costuma ir",
            "usar_localizacao_celular": "Usar minha localização",
            "economia_dados": "Economia de dados",
            "alertas_mudanca": "Alertas de mudança",
        }
        help_texts = {
            "foto": "JPG, PNG ou WebP com até 2 MB.",
        }
        error_messages = {
            "nome": {"required": "Informe seu nome."},
            "email": {
                "required": "Informe seu e-mail.",
                "invalid": "Digite um e-mail válido, como nome@exemplo.com.",
                "unique": "Este e-mail já está em uso por outra conta.",
            },
        }
        widgets = {
            "foto": forms.ClearableFileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            ),
            "nome": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "cidade": forms.TextInput(attrs={"autocomplete": "address-level2"}),
            "perfil_praia": forms.RadioSelect,
            "meio_transporte_preferido": forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].widget.attrs["autocomplete"] = "address-level1"
        self.original_email = self.instance.email

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if not nome:
            raise forms.ValidationError("Informe seu nome.")
        return nome

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        taken = Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("Este e-mail já está em uso por outra conta.")
        return email

    def clean_foto(self):
        photo = self.cleaned_data.get("foto")
        if not isinstance(photo, UploadedFile):
            return photo
        if photo.size > MAX_PHOTO_BYTES:
            raise forms.ValidationError(
                "A imagem tem mais de 2 MB. Escolha um arquivo menor."
            )
        photo.seek(0)
        extension = _image_extension(photo.read(16))
        photo.seek(0)
        if extension is None:
            raise forms.ValidationError("Use uma imagem JPG, PNG ou WebP.")
        photo.name = f"{uuid.uuid4().hex}.{extension}"
        return photo

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if email and email != self.original_email.lower():
            password = cleaned_data.get("senha_atual", "")
            if not password:
                self.add_error(
                    "senha_atual", "Confirme sua senha atual para trocar o e-mail."
                )
            elif not self.instance.check_password(password):
                self.add_error("senha_atual", "Senha atual incorreta.")
        return cleaned_data


class TwoFactorCodeForm(DescribedErrorsMixin, forms.Form):
    code = forms.RegexField(
        label="Código de 6 dígitos",
        regex=r"^\s*\d{3}\s?\d{3}\s*$",
        error_messages={
            "required": "Informe o código mostrado no autenticador.",
            "invalid": "Digite os 6 dígitos do código, sem letras.",
        },
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "maxlength": "7",
                "placeholder": "000 000",
            }
        ),
    )


class LoginCodeForm(DescribedErrorsMixin, forms.Form):
    kind = None
    code = forms.CharField(
        label="Código do autenticador",
        help_text="Sem acesso ao celular? Use um dos seus códigos de recuperação.",
        error_messages={"required": "Informe o código do autenticador."},
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "autocapitalize": "off",
                "autofocus": True,
                "spellcheck": "false",
                "placeholder": "000 000",
            }
        ),
    )

    def clean_code(self):
        raw = self.cleaned_data["code"]
        digits = "".join(character for character in raw if character in "0123456789")
        compact = "".join(character for character in raw if not character.isspace())
        if len(digits) == TOTP_DIGITS and len(compact) == TOTP_DIGITS:
            self.kind = "totp"
            return digits
        if len(normalize_recovery_code(raw)) == 10:
            self.kind = "recovery"
            return raw
        raise forms.ValidationError(
            "Digite os 6 dígitos do autenticador ou um código de recuperação."
        )


class DisableTwoFactorForm(DescribedErrorsMixin, forms.Form):
    password = forms.CharField(
        label="Senha atual",
        strip=False,
        error_messages={"required": "Informe sua senha para desativar."},
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Senha incorreta.")
        return password
