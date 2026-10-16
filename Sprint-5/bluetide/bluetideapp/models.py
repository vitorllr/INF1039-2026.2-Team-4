import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    meio_transporte_preferido = models.CharField(max_length=50, blank=True)
    latitude_padrao = models.FloatField(null=True, blank=True)
    longitude_padrao = models.FloatField(null=True, blank=True)
    usar_localizacao_celular = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome or self.username


class Praia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    # coordenadas (PointField) -> latitude + longitude
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.nome


class PostoColeta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name="postos")
    nome = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return f"{self.nome} ({self.praia})"


class CondicaoAgua(models.Model):
    STATUS_CHOICES = [
        ("propria", "Própria"),
        ("impropria", "Imprópria"),
        ("sem_informacao", "Sem informação"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    posto = models.ForeignKey(PostoColeta, on_delete=models.CASCADE, related_name="condicoes_agua")
    data_checagem = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    fonte = models.CharField(max_length=100)

    class Meta:
        ordering = ["-data_checagem"]


class CondicaoClimaMar(models.Model):
    TIPO_CHOICES = [
        ("atual", "Atual"),
        ("previsao", "Previsão"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name="condicoes_clima_mar")
    data_hora = models.DateTimeField()
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    temperatura = models.FloatField(null=True, blank=True)
    chuva_mm = models.FloatField(null=True, blank=True)
    vento_velocidade = models.FloatField(null=True, blank=True)
    vento_direcao = models.CharField(max_length=10, blank=True)
    altura_onda = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-data_hora"]


class Lotacao(models.Model):
    NIVEL_CHOICES = [
        ("baixa", "Baixa"),
        ("media", "Média"),
        ("alta", "Alta"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name="lotacoes")
    data_hora = models.DateTimeField()
    nivel = models.CharField(max_length=10, choices=NIVEL_CHOICES)

    class Meta:
        ordering = ["-data_hora"]


class Favorito(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favoritos")
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name="favoritada_por")
    data_adicao = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "praia"], name="favorito_unico"),
        ]


class Alerta(models.Model):
    TIPO_CHOICES = [
        ("impropria", "Imprópria"),
        ("chuva_intensa", "Chuva intensa"),
        ("aviso", "Aviso"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alertas")
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, null=True, blank=True, related_name="alertas")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)


class PreferenciaPraia(models.Model):
    ORIGEM_CHOICES = [
        ("questionario", "Questionário"),
        ("manual", "Manual"),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferencias")
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name="preferida_por")
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "praia"], name="preferencia_unica"),
        ]