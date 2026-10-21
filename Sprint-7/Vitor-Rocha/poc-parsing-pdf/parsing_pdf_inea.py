import re
from datetime import date
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PASTA = Path(__file__).parent
PDF_DO_INEA = PASTA / "historico_balneabilidade_inea.pdf"
PDF_DE_RESULTADO = PASTA / "resultado_parsing.pdf"

NUMERO_DO_MES = {
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

STATUS_DO_PDF = {
    "Própria": "propria",
    "Imprópria": "impropria",
    "Não Realizada": "nao_realizada",
}

ROTULO_DO_STATUS = {
    "propria": "Própria",
    "impropria": "Imprópria",
    "nao_realizada": "Não realizada",
}

COR_DO_STATUS = {
    "propria": colors.HexColor("#d5f0dc"),
    "impropria": colors.HexColor("#f6d3d3"),
}
COR_NEUTRA = colors.HexColor("#eeeeee")

FORMATO_DO_CODIGO = re.compile(r"[A-Z]{2}\d{3}")

COLUNA_PRAIA = 0
COLUNA_PONTO = 1
COLUNA_LOCALIZACAO = 2
PRIMEIRA_COLUNA_DE_DATA = 3
PRIMEIRA_LINHA_DE_DADOS = 1

# Medidas, em pontos, que separam as divisórias entre praias de outros retângulos do PDF
ESPESSURA_MAXIMA_DA_DIVISORIA = 2
DIVISORIA_COMECA_ANTES_DE = 100
DIVISORIA_TERMINA_DEPOIS_DE = 400


def ler_meses_do_cabecalho(texto):
    meses = []
    for nome_do_mes, ano_com_dois_digitos in re.findall(r"([a-zç]+)-(\d\d)", texto):
        ano = 2000 + int(ano_com_dois_digitos)
        meses.append((ano, NUMERO_DO_MES[nome_do_mes]))
    return meses


def ler_dias_do_cabecalho(texto):
    achou = re.search(r"COLETA\s+([\d ]+)", texto)
    if not achou:
        raise ValueError("Linha 'COLETA' não encontrada no cabeçalho da página")
    return [int(dia) for dia in achou.group(1).split()]


def descobrir_datas_das_colunas(texto_da_pagina):
    meses = ler_meses_do_cabecalho(texto_da_pagina)
    dias = ler_dias_do_cabecalho(texto_da_pagina)

    datas = []
    indice_do_mes = 0
    dia_anterior = 0
    for dia in dias:
        # O cabeçalho só traz o dia. Quando ele diminui (30, depois 2), o mês virou.
        if dia < dia_anterior:
            indice_do_mes += 1
        ano, mes = meses[indice_do_mes]
        datas.append(date(ano, mes, dia))
        dia_anterior = dia
    return datas


def encontrar_divisorias(pagina):
    # As linhas entre uma praia e outra são desenhadas como retângulos bem finos
    return [
        (retangulo["top"] + retangulo["bottom"]) / 2
        for retangulo in pagina.rects
        if retangulo["height"] < ESPESSURA_MAXIMA_DA_DIVISORIA
        and retangulo["x0"] < DIVISORIA_COMECA_ANTES_DE
        and retangulo["x1"] > DIVISORIA_TERMINA_DEPOIS_DE
    ]


def ler_nome_da_praia(pagina, tabela, linha_desenhada, divisorias):

    x_esquerda, _, x_direita, _ = tabela.rows[PRIMEIRA_LINHA_DE_DADOS].cells[
        COLUNA_PRAIA
    ]
    _, topo, _, base = linha_desenhada.bbox
    meio_da_linha = (topo + base) / 2

    inicio_do_grupo = max((y for y in divisorias if y <= meio_da_linha), default=topo)
    fim_do_grupo = min((y for y in divisorias if y > meio_da_linha), default=base)

    area_do_grupo = (x_esquerda, inicio_do_grupo, x_direita, fim_do_grupo)
    return pagina.crop(area_do_grupo).extract_text().replace("\n", " ").strip()


def ler_historico(caminho_do_pdf):
    pontos = {}

    with pdfplumber.open(caminho_do_pdf) as pdf:
        for pagina in pdf.pages:
            datas = descobrir_datas_das_colunas(pagina.extract_text())
            divisorias = encontrar_divisorias(pagina)
            tabela = pagina.find_tables()[0]

            for linha_desenhada, textos in zip(tabela.rows, tabela.extract()):
                codigo = (textos[COLUNA_PONTO] or "").strip()
                if not FORMATO_DO_CODIGO.fullmatch(codigo):
                    continue

                if codigo not in pontos:
                    pontos[codigo] = {
                        "praia": ler_nome_da_praia(
                            pagina, tabela, linha_desenhada, divisorias
                        ),
                        "localizacao": (textos[COLUNA_LOCALIZACAO] or "").strip(),
                        "coletas": [],
                    }

                celulas = textos[
                    PRIMEIRA_COLUNA_DE_DATA : PRIMEIRA_COLUNA_DE_DATA + len(datas)
                ]
                for data, texto_da_celula in zip(datas, celulas):
                    texto = (texto_da_celula or "").strip()
                    if texto:
                        pontos[codigo]["coletas"].append((data, STATUS_DO_PDF[texto]))

    return pontos


def contar(coletas, status):
    return sum(1 for _, s in coletas if s == status)


def gerar_pdf_de_resultado(pontos, caminho_do_pdf_de_saida):
    linhas = [
        [
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
    ]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3c5d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    for numero_da_linha, (codigo, ponto) in enumerate(pontos.items(), start=1):
        coletas = ponto["coletas"]
        if coletas:
            ultima_data, ultimo_status = coletas[-1]
            texto_da_data = ultima_data.strftime("%d/%m/%Y")
            texto_do_status = ROTULO_DO_STATUS[ultimo_status]
        else:
            ultimo_status = None
            texto_da_data = "—"
            texto_do_status = "Sem coletas"

        linhas.append(
            [
                codigo,
                ponto["praia"],
                ponto["localizacao"],
                len(coletas),
                contar(coletas, "propria"),
                contar(coletas, "impropria"),
                contar(coletas, "nao_realizada"),
                texto_da_data,
                texto_do_status,
            ]
        )
        cor = COR_DO_STATUS.get(ultimo_status, COR_NEUTRA)
        estilo.append(("BACKGROUND", (-1, numero_da_linha), (-1, numero_da_linha), cor))

    tabela = Table(linhas, repeatRows=1)
    tabela.setStyle(TableStyle(estilo))

    estilos_de_texto = getSampleStyleSheet()
    documento = SimpleDocTemplate(str(caminho_do_pdf_de_saida), pagesize=landscape(A4))
    documento.build(
        [
            Paragraph(
                "Resultado do parsing - Histórico de balneabilidade (INEA)",
                estilos_de_texto["Title"],
            ),
            Paragraph(
                f"{len(pontos)} pontos de coleta lidos do PDF.",
                estilos_de_texto["Normal"],
            ),
            Spacer(1, 12),
            tabela,
        ]
    )


if __name__ == "__main__":
    pontos = ler_historico(PDF_DO_INEA)

    for codigo, ponto in pontos.items():
        if ponto["coletas"]:
            ultima_data, ultimo_status = ponto["coletas"][-1]
            print(codigo, ponto["praia"], ultimo_status, ultima_data)
        else:
            print(codigo, ponto["praia"], "sem coletas")

    gerar_pdf_de_resultado(pontos, PDF_DE_RESULTADO)
