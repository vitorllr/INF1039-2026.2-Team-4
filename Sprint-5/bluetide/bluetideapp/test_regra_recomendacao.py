"""Testes de validação da regra de recomendação (Sprint 10).

Os testes de tests.py já conferem os 10 exemplos do PDF da Sprint 9.
Aqui ficam os casos de fronteira de cada limiar da regra, a ordem de
prioridade entre vermelho, amarelo e verde, e uma comparação da regra do
app com a implementação de referência da Sprint 9
(Sprint-9/Vitor-Rocha/logica-recomendacao/recomendacao.py).

Rodar só este arquivo:
    python manage.py test bluetideapp.test_regra_recomendacao -v 2
"""

import importlib.util
import itertools
from dataclasses import replace
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from .services import recommendations as regra
from .services.catalog import BEACH_POINTS
from .services.providers import FixtureConditionsProvider
from .services.recommendations import rank, recommend


AGORA = timezone.make_aware(datetime(2026, 10, 19, 10, 0))
CHUVA_LIDA_HA_20_MIN = AGORA - timedelta(minutes=20)


def condicoes(
    status="propria",
    idade_dias=4,
    chuva_1h=0.0,
    chuva_24h=0.0,
    mare_alta=False,
    qualidade="observada",
    chuva_lida_em=CHUVA_LIDA_HA_20_MIN,
):
    """Monta um ponto com tudo bom e deixa mudar só o que o teste precisa."""
    base = FixtureConditionsProvider().fetch(BEACH_POINTS[1], now=AGORA)
    coleta = None
    if idade_dias is not None:
        dia = timezone.localtime(AGORA).date() - timedelta(days=idade_dias)
        coleta = timezone.make_aware(datetime.combine(dia, datetime.min.time()))
    return replace(
        base,
        water_status=status,
        water_observed_at=coleta,
        rain_1h=chuva_1h,
        rain_24h=chuva_24h,
        rain_quality=qualidade,
        rain_observed_at=chuva_lida_em,
        high_tide=mare_alta,
        provider_error=None,
    )


def resultado(**mudancas):
    return recommend(condicoes(**mudancas), "neutro", now=AGORA)


class LimiaresDaAguaTests(SimpleTestCase):
    """Coleta do INEA: fresca até 9 dias, antiga de 10 a 30, sem dado acima de 30."""

    def test_coleta_de_hoje_e_de_9_dias_e_verde_com_confianca_alta(self):
        for idade in (0, 9):
            with self.subTest(idade=idade):
                r = resultado(idade_dias=idade)
                self.assertEqual((r.color, r.confidence), ("verde", "alta"))

    def test_coleta_de_10_e_30_dias_e_amarela_com_confianca_media(self):
        for idade in (10, 30):
            with self.subTest(idade=idade):
                r = resultado(idade_dias=idade)
                self.assertEqual((r.color, r.confidence), ("amarelo", "media"))
                self.assertIn("mais que um ciclo", r.summary)

    def test_coleta_de_31_dias_nao_conta_e_fica_amarela_com_confianca_baixa(self):
        r = resultado(idade_dias=31)

        self.assertEqual((r.color, r.confidence), ("amarelo", "baixa"))
        self.assertIn("Sem coleta", r.summary)

    def test_coleta_com_data_no_futuro_e_tratada_como_sem_dado(self):
        r = resultado(idade_dias=-1)

        self.assertEqual((r.color, r.confidence), ("amarelo", "baixa"))

    def test_status_desconhecido_do_inea_e_tratado_como_sem_dado(self):
        for status in (None, "nao_realizada", "PROPRIA"):
            with self.subTest(status=status):
                self.assertEqual(resultado(status=status).color, "amarelo")

    def test_improprio_antigo_ainda_e_vermelho(self):
        r = resultado(status="impropria", idade_dias=30)

        self.assertEqual((r.color, r.confidence), ("vermelho", "media"))

    def test_improprio_com_mais_de_30_dias_deixa_de_valer_e_fica_amarelo(self):
        r = resultado(status="impropria", idade_dias=31)

        self.assertEqual(r.color, "amarelo")
        self.assertIn("Sem coleta", r.summary)


class LimiaresDaChuvaTests(SimpleTestCase):
    """Chuva em 24 h: moderada a partir de 5 mm, forte a partir de 20 mm.
    Chuva na última hora: moderada acima de 2,5 mm, forte acima de 7,6 mm."""

    def test_chuva_em_24_horas(self):
        casos = ((4.9, "verde"), (5.0, "amarelo"), (19.9, "amarelo"), (20.0, "vermelho"))
        for chuva, cor in casos:
            with self.subTest(chuva_24h=chuva):
                self.assertEqual(resultado(chuva_24h=chuva).color, cor)

    def test_chuva_na_ultima_hora(self):
        casos = ((2.5, "verde"), (2.6, "amarelo"), (7.6, "amarelo"), (7.7, "vermelho"))
        for chuva, cor in casos:
            with self.subTest(chuva_1h=chuva):
                self.assertEqual(resultado(chuva_1h=chuva, chuva_24h=0.0).color, cor)

    def test_chuva_da_ultima_hora_sem_valor_conta_como_zero(self):
        r = resultado(chuva_1h=None, chuva_24h=0.4)

        self.assertEqual((r.color, r.confidence), ("verde", "alta"))

    def test_leitura_de_chuva_com_exatamente_3_horas_ainda_vale(self):
        r = resultado(chuva_lida_em=AGORA - timedelta(hours=3))

        self.assertEqual((r.color, r.confidence), ("verde", "alta"))

    def test_leitura_de_chuva_com_mais_de_3_horas_vira_sem_dado(self):
        r = resultado(chuva_lida_em=AGORA - timedelta(hours=3, minutes=1))

        self.assertEqual((r.color, r.confidence), ("amarelo", "baixa"))
        self.assertIn("Sem dado de chuva recente.", r.reasons)

    def test_chuva_sem_horario_de_leitura_vira_sem_dado(self):
        self.assertEqual(resultado(chuva_lida_em=None).color, "amarelo")

    def test_chuva_so_do_modelo_baixa_a_confianca_para_media(self):
        r = resultado(qualidade="modelada")

        self.assertEqual((r.color, r.confidence), ("verde", "media"))


class MareTests(SimpleTestCase):
    """Com maré alta, a chuva em 24 h já é moderada a partir de 1 mm."""

    def test_limiar_de_1_mm_com_mare_alta(self):
        self.assertEqual(resultado(chuva_24h=0.9, mare_alta=True).color, "verde")
        r = resultado(chuva_24h=1.0, mare_alta=True)
        self.assertEqual(r.color, "amarelo")
        self.assertIn("Chuva fraca com maré alta", r.summary)

    def test_mesma_chuva_com_mare_baixa_e_verde(self):
        self.assertEqual(resultado(chuva_24h=1.0, mare_alta=False).color, "verde")

    def test_chuva_moderada_com_mare_alta_e_descrita_como_chuva_moderada(self):
        r = resultado(chuva_24h=6.0, mare_alta=True)

        self.assertEqual(r.color, "amarelo")
        self.assertIn("Chuva moderada", r.summary)

    def test_mare_sem_dado_conta_como_nao_alta_e_baixa_a_confianca(self):
        r = resultado(chuva_24h=1.0, mare_alta=None)

        self.assertEqual((r.color, r.confidence), ("verde", "media"))
        self.assertIn("Maré sem dado: considerada não alta.", r.reasons)


class PrioridadeDasCoresTests(SimpleTestCase):
    def test_vermelho_vence_qualquer_duvida(self):
        r = resultado(status="impropria", chuva_24h=None, chuva_lida_em=None, mare_alta=None)

        self.assertEqual((r.color, r.confidence), ("vermelho", "baixa"))
        self.assertFalse(r.recommendable)

    def test_improprio_com_chuva_forte_lista_os_dois_motivos(self):
        r = resultado(status="impropria", chuva_24h=25.0)

        self.assertEqual(r.color, "vermelho")
        self.assertEqual(len([m for m in r.reasons if "impróprio" in m or "Chuva forte" in m]), 2)

    def test_amarelo_junta_todos_os_motivos_de_duvida(self):
        r = resultado(idade_dias=12, chuva_24h=6.0)

        self.assertEqual(r.color, "amarelo")
        self.assertTrue(any("mais que um ciclo" in m for m in r.reasons))
        self.assertTrue(any("Chuva moderada" in m for m in r.reasons))

    def test_amarelo_ainda_e_recomendavel_e_vermelho_nao(self):
        self.assertTrue(resultado(chuva_24h=6.0).recommendable)
        self.assertFalse(resultado(chuva_24h=20.0).recommendable)

    def test_erro_de_integracao_suspende_mesmo_com_dados_bons(self):
        conditions = replace(condicoes(), provider_error="timeout")

        r = recommend(conditions, "neutro", now=AGORA)

        self.assertFalse(r.available)
        self.assertIsNone(r.color)
        self.assertEqual(r.label, "Sem recomendação")
        self.assertFalse(r.recommendable)

    def test_toda_recomendacao_disponivel_tem_motivo_e_confianca(self):
        for chuva, idade, status in itertools.product((0.0, 6.0, 25.0), (2, 12, 40), ("propria", "impropria")):
            with self.subTest(chuva=chuva, idade=idade, status=status):
                r = resultado(chuva_24h=chuva, idade_dias=idade, status=status)
                self.assertTrue(r.summary)
                self.assertIn(r.confidence, ("alta", "media", "baixa"))


class PerfilEOrdenacaoTests(SimpleTestCase):
    def test_perfil_desconhecido_usa_banho_tranquilo(self):
        c = condicoes()

        self.assertEqual(recommend(c, "qualquer", now=AGORA), recommend(c, "tranquilo", now=AGORA))
        self.assertEqual(recommend(c, None, now=AGORA), recommend(c, "tranquilo", now=AGORA))

    def test_ordem_e_verde_amarelo_vermelho_e_depois_sem_recomendacao(self):
        verde_ruim_para_perfil = replace(condicoes(), wave_height=3.0, wind_speed=40)
        amarelo_perfeito = replace(condicoes(chuva_24h=6.0), wave_height=0.4, wind_speed=5)
        vermelho = condicoes(status="impropria")
        suspenso = replace(condicoes(), provider_error="timeout")
        itens = [
            {"conditions": c, "recommendation": recommend(c, "tranquilo", now=AGORA)}
            for c in (suspenso, vermelho, amarelo_perfeito, verde_ruim_para_perfil)
        ]

        cores = [item["recommendation"].color for item in rank(itens)]

        self.assertEqual(cores, ["verde", "amarelo", "vermelho", None])

    def test_constantes_do_app_sao_as_mesmas_da_sprint_9(self):
        referencia = carregar_referencia_sprint9()
        if referencia is None:
            self.skipTest("arquivo da Sprint 9 não encontrado")
        pares = (
            (regra.FRESH_WATER_DAYS, referencia.IDADE_FRESCA_DIAS),
            (regra.MAX_WATER_DAYS, referencia.IDADE_MAXIMA_DIAS),
            (regra.RAIN_1H_HEAVY_MM, referencia.CHUVA_1H_FORTE_MM),
            (regra.RAIN_1H_MODERATE_MM, referencia.CHUVA_1H_MODERADA_MM),
            (regra.RAIN_24H_HEAVY_MM, referencia.CHUVA_24H_FORTE_MM),
            (regra.RAIN_24H_MODERATE_MM, referencia.CHUVA_24H_MODERADA_MM),
            (regra.RAIN_24H_MODERATE_HIGH_TIDE_MM, referencia.CHUVA_24H_MODERADA_COM_MARE_ALTA_MM),
            (regra.MAX_RAIN_AGE, referencia.IDADE_MAXIMA_DA_CHUVA),
        )
        for do_app, da_sprint9 in pares:
            self.assertEqual(do_app, da_sprint9)


def carregar_referencia_sprint9():
    raiz = Path(__file__).resolve().parents[3]
    caminho = raiz / "Sprint-9" / "Vitor-Rocha" / "logica-recomendacao" / "recomendacao.py"
    if not caminho.exists():
        return None
    spec = importlib.util.spec_from_file_location("recomendacao_sprint9", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class ComparacaoComASprint9Tests(SimpleTestCase):
    """Roda a regra do app e a da Sprint 9 em milhares de combinações e exige a mesma cor e confiança."""

    def test_app_e_sprint9_dao_a_mesma_cor_e_confianca(self):
        referencia = carregar_referencia_sprint9()
        if referencia is None:
            self.skipTest("arquivo da Sprint 9 não encontrado")
        brasilia = dt_timezone(timedelta(hours=-3))
        agora_ref = datetime(2026, 10, 19, 10, 0, tzinfo=brasilia)

        combinacoes = itertools.product(
            ("propria", "impropria", None),
            (0, 9, 10, 30, 31),
            (None, 0.0, 0.9, 1.0, 4.9, 5.0, 19.9, 20.0),
            (None, 0.0, 2.5, 2.6, 7.6, 7.7),
            (True, False, None),
            ("observada", "modelada"),
            (timedelta(minutes=20), timedelta(hours=3), timedelta(hours=3, minutes=1)),
        )
        total = 0
        for status, idade, chuva_24h, chuva_1h, mare, qualidade, idade_chuva in combinacoes:
            app = recommend(
                condicoes(status, idade, chuva_1h, chuva_24h, mare, qualidade, AGORA - idade_chuva),
                "neutro",
                now=AGORA,
            )
            entrada = referencia.EntradaDoPonto(
                status_inea=status,
                data_coleta=agora_ref.date() - timedelta(days=idade),
                chuva_1h_mm=chuva_1h,
                chuva_24h_mm=chuva_24h,
                chuva_qualidade=qualidade,
                chuva_lido_em=agora_ref - idade_chuva,
                mare_alta=mare,
            )
            esperado = referencia.recomendar_ponto(entrada, agora_ref)
            caso = (status, idade, chuva_24h, chuva_1h, mare, qualidade, idade_chuva)
            self.assertEqual((app.color, app.confidence), (esperado.cor, esperado.confianca), caso)
            total += 1
        self.assertEqual(total, 12960)
