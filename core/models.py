import uuid

from django.db import models


class Usuario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    senha_hash = models.CharField(max_length=255)
    cidade = models.CharField(max_length=255)
    estado = models.CharField(max_length=255)
    meio_transporte_preferido = models.CharField(max_length=255)
    localizacao_padrao_latitude = models.FloatField(null=True, blank=True)
    localizacao_padrao_longitude = models.FloatField(null=True, blank=True)
    usar_localizacao_celular = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome


class Praia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    bairro = models.CharField(max_length=255)
    cidade = models.CharField(max_length=255)
    estado = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.nome


class PostoColeta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name='postos')
    nome = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.nome


class CondicaoAgua(models.Model):
    class Status(models.TextChoices):
        PROPRIA = 'propria', 'Própria'
        IMPROPRIA = 'impropria', 'Imprópria'
        SEM_INFORMACAO = 'sem_informacao', 'Sem informação'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    posto = models.ForeignKey(PostoColeta, on_delete=models.CASCADE, related_name='condicoes_agua')
    data_checagem = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices)
    fonte = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.posto} - {self.status}'


class CondicaoClimaMar(models.Model):
    class Tipo(models.TextChoices):
        ATUAL = 'atual', 'Atual'
        PREVISAO = 'previsao', 'Previsão'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name='condicoes_clima_mar')
    data_hora = models.DateTimeField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    temperatura = models.FloatField()
    chuva_mm = models.FloatField()
    vento_velocidade = models.FloatField()
    vento_direcao = models.CharField(max_length=255)
    altura_onda = models.FloatField()

    def __str__(self):
        return f'{self.praia} - {self.tipo} - {self.data_hora}'


class Lotacao(models.Model):
    class Nivel(models.TextChoices):
        BAIXA = 'baixa', 'Baixa'
        MEDIA = 'media', 'Média'
        ALTA = 'alta', 'Alta'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name='lotacoes')
    data_hora = models.DateTimeField()
    nivel = models.CharField(max_length=20, choices=Nivel.choices)

    def __str__(self):
        return f'{self.praia} - {self.nivel}'


class Favorito(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='favoritos')
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name='favoritos')
    data_adicao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.usuario} - {self.praia}'


class Alerta(models.Model):
    class Tipo(models.TextChoices):
        IMPROPRIA = 'impropria', 'Imprópria'
        CHUVA_INTENSA = 'chuva_intensa', 'Chuva intensa'
        AVISO = 'aviso', 'Aviso'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='alertas')
    praia = models.ForeignKey(
        Praia, on_delete=models.CASCADE, related_name='alertas', null=True, blank=True
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.usuario} - {self.tipo}'


class PreferenciaPraia(models.Model):
    class Origem(models.TextChoices):
        QUESTIONARIO = 'questionario', 'Questionário'
        MANUAL = 'manual', 'Manual'

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='preferencias')
    praia = models.ForeignKey(Praia, on_delete=models.CASCADE, related_name='preferencias')
    origem = models.CharField(max_length=20, choices=Origem.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'praia'], name='preferencia_praia_unica'),
        ]

    def __str__(self):
        return f'{self.usuario} - {self.praia}'
