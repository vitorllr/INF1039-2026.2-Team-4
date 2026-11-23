import re
import unicodedata
from datetime import date

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
    "propria": "propria",
    "impropria": "impropria",
    "nao realizada": "nao_realizada",
    "amostragem nao realizada": "nao_realizada",
}

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


def normalizar_status(texto):
    semacento = unicodedata.normalize("NFD", texto)
    semacento = "".join(c for c in semacento if not unicodedata.combining(c))
    chave = " ".join(semacento.casefold().split())
    if chave not in STATUS_DO_PDF:
        raise ValueError(f"Status desconhecido no PDF do INEA: {texto!r}")
    return STATUS_DO_PDF[chave]


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
    x_esquerda, _, x_direita, _ = tabela.rows[PRIMEIRA_LINHA_DE_DADOS].cells[COLUNA_PRAIA]
    _, topo, _, base = linha_desenhada.bbox
    meio_da_linha = (topo + base) / 2

    inicio_do_grupo = max((y for y in divisorias if y <= meio_da_linha), default=topo)
    fim_do_grupo = min((y for y in divisorias if y > meio_da_linha), default=base)

    area_do_grupo = (x_esquerda, inicio_do_grupo, x_direita, fim_do_grupo)
    return pagina.crop(area_do_grupo).extract_text().replace("\n", " ").strip()


def ler_historico(caminho_do_pdf):
    """Lê o histórico anual do INEA. Devolve {codigo: {praia, localizacao, coletas}}."""
    import pdfplumber

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
                        "praia": ler_nome_da_praia(pagina, tabela, linha_desenhada, divisorias),
                        "localizacao": (textos[COLUNA_LOCALIZACAO] or "").strip(),
                        "coletas": [],
                    }

                celulas = textos[PRIMEIRA_COLUNA_DE_DATA : PRIMEIRA_COLUNA_DE_DATA + len(datas)]
                for data, texto_da_celula in zip(datas, celulas):
                    texto = (texto_da_celula or "").strip()
                    if texto:
                        pontos[codigo]["coletas"].append((data, normalizar_status(texto)))
    return pontos
