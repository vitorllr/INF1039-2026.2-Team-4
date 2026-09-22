# PoC: parsing do boletim do INEA

Prova de que é possível acessar e extrair, de forma estruturada, os dados
publicados pelo Sistema de Alerta de Cheias do INEA.
Item do quadro da Sprint 3: "PoC: parsing do boletim do INEA".

## Fonte usada

O INEA não expõe uma API pública documentada para esses dados.
O boletim real é o Sistema de Alerta de Cheias, publicado em páginas HTML no
domínio oficial do instituto:

- Página inicial: https://alertadecheias.inea.rj.gov.br/dados.php
- Tabela por região hidrográfica, por exemplo:
  https://alertadecheias.inea.rj.gov.br/dados/baia_de_guanabara.php

O site divide os dados em 9 regiões hidrográficas do estado do Rio de
Janeiro (RH I a RH IX).
Cada página de região traz uma tabela HTML com uma linha por estação de
monitoramento.

## O que o parser extrai

`parse_boletim_inea.py` busca a(s) página(s) de região escolhida(s) e
converte a tabela HTML em JSON, um objeto por estação:

- `regiao_hidrografica`: nome da região hidrográfica
- `municipio`: município onde fica a estação
- `curso_dagua`: nome do rio monitorado
- `nome_estacao`: nome da estação de monitoramento
- `tendencia_rio`: tendência do nível do rio (`estavel`, `subindo`,
  `descendo`), lida do ícone da tabela
- `ultima_leitura`: data/hora da última leitura da estação
- `nivel_alerta`: status de monitoramento da estação (por exemplo
  `VIGILÂNCIA` ou `Rede básica`, conforme publicado pelo INEA)
- `nivel_alerta_cor`: cor de fundo usada pelo INEA para esse status
- `chuva_acumulada_mm`: chuva acumulada em mm nas janelas `ultimo`, `1h`,
  `4h`, `24h`, `96h`, `30d`
- `nivel_rio_m`: nível do rio em metros nas janelas `ultimo`, `15min`,
  `30min`, `45min`

Um exemplo real de saída está em `sample-output.json`, gerado a partir da
região Baía de Guanabara (cobre a cidade do Rio de Janeiro e a Baixada
Fluminense, área mais relevante para o BlueTide).

## Como rodar

```bash
python3 parse_boletim_inea.py --region baia_de_guanabara
```

`--region` aceita qualquer um dos slugs das 9 regiões (por exemplo
`guandu`, `piabanha`, `rio_dois_rios`) ou `all` para buscar todas de uma vez.
`--out arquivo.json` grava em arquivo em vez de imprimir no terminal.

Sem dependências externas: usa só a biblioteca padrão do Python 3
(`urllib`, `html.parser`, `json`).

## Ressalvas

Sem API oficial: os dados vêm de páginas HTML feitas para navegador, não de
um endpoint JSON/XML documentado.
O parser depende da estrutura atual da tabela (`<table id="Table">` com 17
colunas), e qualquer mudança de layout no site do INEA pode quebrar a
extração.
É uma dependência frágil por natureza.

Certificado TLS incompleto: o servidor do INEA não envia a cadeia de
certificados intermediária, então uma verificação TLS padrão falha com
"unable to verify the first certificate".
O script contorna isso desabilitando a verificação de certificado só para
esse host.
Para um PoC isso é aceitável, mas antes de ir para produção vale revisar a
cadeia de certificados ou fixar o certificado esperado.

Sem autenticação nem rate limit visível: não há exigência de login nem
limite de requisições documentado, mas o site não é uma API pública
oficial, então vale evitar uso intenso por respeito à infraestrutura do
instituto.

Cobertura: o PoC valida a extração da tabela "Estações" (estações
atualizadas).
A aba "Estações desatualizadas", presente na mesma página, não foi
extraída.

Nomenclatura: os nomes de campos e valores de status (`VIGILÂNCIA`, `Rede
básica`, etc.) são os termos usados pelo próprio INEA no site, não uma
classificação própria do BlueTide.
