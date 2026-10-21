"""PoC: le o PDF "Historico dos Boletins de Balneabilidade" do INEA.

O PDF tem uma tabela em que cada linha e um ponto de coleta (ex: BG000) e cada
coluna e uma data de coleta. A celula diz "Propria", "Impropria" ou
"Nao Realizada". O INEA ja entrega o status classificado, entao nao precisamos
aplicar a regra do CONAMA nos numeros.

Como usar:
    pip install -r requirements.txt
    python parsing_pdf_inea.py historico_balneabilidade_inea.pdf

Gera "resultado_parsing.pdf" ao lado do script, com um resumo por ponto de coleta.
"""

import re
import sys
from datetime import date
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NUMERO_DE_MESES = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

# Como o status aparece no PDF -> como guardamos
STATUS_DO_PDF = {
    "Própria": "propria",
    "Imprópria": "impropria",
    "Não Realizada": "nao_realizada",
}

# Colunas da tabela antes das datas: praia, ponto de coleta, localizacao
COLUNA_PRAIA = 0
COLUNA_PONTO = 1
COLUNA_LOCALIZACAO = 2
PRIMEIRA_COLUNA_DE_DATA = 3

# Codigo do ponto de coleta no PDF: duas letras e tres numeros (ex: BG000)
FORMATO_DO_CODIGO = re.compile(r"[A-Z]{2}\d{3}")


def ler_meses_do_cabecalho(texto):
    """Le "janeiro-26 fevereiro-26" e devolve [(2026, 1), (2026, 2)]."""
    meses = []
    for nome_do_mes, ano_com_dois_digitos in re.findall(r"([a-zç]+)-(\d\d)", texto):
        ano = 2000 + int(ano_com_dois_digitos)
        meses.append((ano, NUMERO_DE_MESES[nome_do_mes]))
    return meses


def ler_dias_do_cabecalho(texto):
    """Le a linha "COLETA 7 14 21 28 3 11" e devolve [7, 14, 21, 28, 3, 11].

    No PDF a palavra COLETA fica numa linha e os dias na linha seguinte.
    """
    achou = re.search(r"COLETA\s+([\d ]+)", texto)
    return [int(dia) for dia in achou.group(1).split()]


def descobrir_datas_das_colunas(texto_da_pagina):
    """Devolve a data de coleta de cada coluna da tabela.

    O cabecalho lista os meses e, numa linha so, os dias de todos eles em
    sequencia. Nao diz a qual mes cada dia pertence, mas da pra deduzir:
    sempre que o dia diminui (ex: 28 e depois 3), comecou o mes seguinte.
    """
    meses = ler_meses_do_cabecalho(texto_da_pagina)
    dias = ler_dias_do_cabecalho(texto_da_pagina)

    datas = []
    indice_do_mes = 0
    dia_anterior = 0
    for dia in dias:
        if dia < dia_anterior:
            indice_do_mes += 1
        ano, mes = meses[indice_do_mes]
        datas.append(date(ano, mes, dia))
        dia_anterior = dia
    return datas


def ler_nome_da_praia(pagina, tabela, linha_da_tabela):
    """Devolve o nome da praia a que a linha pertence.

    O nome da praia fica numa celula mesclada: "Grumari" aparece uma vez e vale
    para as linhas GM000 e GM001. O texto que o pdfplumber extrai da tabela
    pode vir vazio ou na linha errada. Por isso olhamos o desenho: uma linha
    horizontal separa uma praia da outra, e o nome fica entre duas dessas linhas.
    """
    # Largura da coluna das praias: a primeira linha de dados sempre tem celula propria
    x_esquerda, _, x_direita, _ = tabela.rows[1].cells[COLUNA_PRAIA]
    _, topo, _, base = linha_da_tabela.bbox
    meio_da_linha = (topo + base) / 2

    # No PDF essas divisorias sao retangulos finos, e nao linhas de verdade
    divisorias = [
        (retangulo["top"] + retangulo["bottom"]) / 2
        for retangulo in pagina.rects
        if retangulo["height"] < 2 and retangulo["x0"] < 100 and retangulo["x1"] > 400
    ]
    divisorias_acima = [y for y in divisorias if y <= meio_da_linha]
    divisorias_abaixo = [y for y in divisorias if y > meio_da_linha]
    inicio_do_grupo = max(divisorias_acima, default=topo)
    fim_do_grupo = min(divisorias_abaixo, default=base)  # ultima praia da pagina: sem divisoria embaixo

    area_do_grupo = (x_esquerda, inicio_do_grupo, x_direita, fim_do_grupo)
    return pagina.crop(area_do_grupo).extract_text().replace("\n", " ").strip()


def ler_historico(caminho_do_pdf):
    """Le o PDF e devolve {codigo_do_ponto: dados do ponto}.

    Cada ponto vem assim:
        {"praia": "Grumari",
         "localizacao": "Centro da praia",
         "coletas": [(date(2026, 1, 7), "propria"), ...]}
    """
    pontos = {}

    with pdfplumber.open(caminho_do_pdf) as pdf:
        for pagina in pdf.pages:
            datas = descobrir_datas_das_colunas(pagina.extract_text())

            tabela = pagina.find_tables()[0]
            for linha_da_tabela, linha in zip(tabela.rows, tabela.extract()):
                codigo = (linha[COLUNA_PONTO] or "").strip()
                if not FORMATO_DO_CODIGO.fullmatch(codigo):
                    continue  # cabecalho ou rodape, nao e um ponto de coleta

                nome_da_praia = ler_nome_da_praia(pagina, tabela, linha_da_tabela)

                celulas = linha[PRIMEIRA_COLUNA_DE_DATA : PRIMEIRA_COLUNA_DE_DATA + len(datas)]
                coletas = []
                for data, texto_da_celula in zip(datas, celulas):
                    if texto_da_celula and texto_da_celula.strip():  # vazio = ainda sem coleta
                        coletas.append((data, STATUS_DO_PDF[texto_da_celula.strip()]))

                ponto = pontos.setdefault(
                    codigo,
                    {
                        "praia": nome_da_praia,
                        "localizacao": (linha[COLUNA_LOCALIZACAO] or "").strip(),
                        "coletas": [],
                    },
                )
                ponto["coletas"].extend(coletas)

    return pontos


def contar(coletas, status):
    return sum(1 for _, s in coletas if s == status)


ROTULO_DO_STATUS = {
    "propria": "Própria",
    "impropria": "Imprópria",
    "nao_realizada": "Não realizada",
}


def gerar_pdf_de_resultado(pontos, caminho_do_pdf_de_saida):
    """Escreve um PDF com uma linha por ponto de coleta."""
    cabecalho = [
        "Ponto",
        "Praia",
        "Localização",
        "Coletas",
        "Próprias",
        "Impróprias",
        "Não realizadas",
        "Última coleta",
        "Último status",
    ]
    linhas = [cabecalho]
    cores_do_ultimo_status = []

    for codigo, ponto in pontos.items():
        coletas = ponto["coletas"]
        ultima_data, ultimo_status = coletas[-1]
        linhas.append(
            [
                codigo,
                ponto["praia"],
                ponto["localizacao"],
                len(coletas),
                contar(coletas, "propria"),
                contar(coletas, "impropria"),
                contar(coletas, "nao_realizada"),
                ultima_data.strftime("%d/%m/%Y"),
                ROTULO_DO_STATUS[ultimo_status],
            ]
        )
        cor = {"propria": colors.HexColor("#d5f0dc"), "impropria": colors.HexColor("#f6d3d3")}
        cores_do_ultimo_status.append(cor.get(ultimo_status, colors.HexColor("#eeeeee")))

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3c5d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # Pinta so a celula do ultimo status (ultima coluna)
    for numero_da_linha, cor in enumerate(cores_do_ultimo_status, start=1):
        estilo.append(("BACKGROUND", (-1, numero_da_linha), (-1, numero_da_linha), cor))

    tabela = Table(linhas, repeatRows=1)
    tabela.setStyle(TableStyle(estilo))

    estilos_de_texto = getSampleStyleSheet()
    documento = SimpleDocTemplate(str(caminho_do_pdf_de_saida), pagesize=landscape(A4))
    documento.build(
        [
            Paragraph("Resultado do parsing - Histórico de balneabilidade (INEA)", estilos_de_texto["Title"]),
            Paragraph(f"{len(pontos)} pontos de coleta lidos do PDF.", estilos_de_texto["Normal"]),
            Spacer(1, 12),
            tabela,
        ]
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python parsing_pdf_inea.py caminho/do/historico.pdf")

    pontos = ler_historico(sys.argv[1])

    for codigo, ponto in pontos.items():
        ultima_data, ultimo_status = ponto["coletas"][-1]
        print(f"{codigo:6} {ponto['praia']:25} {ultimo_status:14} {ultima_data}  ({len(ponto['coletas'])} coletas)")

    saida = Path(__file__).parent / "resultado_parsing.pdf"
    gerar_pdf_de_resultado(pontos, saida)
    print(f"\nPDF de resultado: {saida}")
