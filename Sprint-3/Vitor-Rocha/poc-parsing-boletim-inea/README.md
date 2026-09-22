# PoC: parsing do boletim do INEA

Prova de que é possível acessar e extrair, de forma estruturada, os dados de
balneabilidade das praias publicados pelo INEA.
Item do quadro da Sprint 3: "PoC: parsing do boletim do INEA".

Este é o boletim que a `logica-recomendacao` (ver
`Sprint-3/Vitor-Rocha/logica-recomendacao/logica-recomendacao.md`, PR #12)
consome como `status_inea`: o boletim de balneabilidade (próprio/impróprio
por ponto de praia), não o Sistema de Alerta de Cheias (que é sobre nível de
rio/enchente, domínio errado para um app sobre ir ou não à praia).

## Fonte usada

Página oficial do INEA sobre o tema:
https://www.inea.rj.gov.br/ar-agua-e-solo/balneabilidade-das-praias/

Essa página publica o boletim estadual atual só como PDF semanal (por
exemplo
`https://www.inea.rj.gov.br/wp-content/uploads/2026/07/Site-Boletim-de-Balneabilidade-do-Estado-do-RJ_03.07.2026_v2.pdf`).
O status por ponto de coleta nesse PDF é desenhado como marcador colorido em
cima de um mapa (imagem), não como texto ou tabela: a camada de texto do PDF
só traz título, sumário e nomes de praias/página, sem os status. Não dá para
extrair "próprio/impróprio" por ponto desse PDF sem OCR/reconhecimento de
imagem, o que foge do escopo de um PoC de parsing estruturado.

A mesma classificação que o INEA publica para as praias de Niterói também
está disponível como JSON estruturado, através do portal de geoprocessamento
da Prefeitura de Niterói, numa camada ArcGIS chamada "Boletins de
Balneabilidade - INEA":

- Endpoint usado:
  `https://geo.niteroi.rj.gov.br/arcgis/rest/services/Aplicacoes/AplicacaoINEA/FeatureServer/0/query`

Essa camada é alimentada com os mesmos dados que o INEA classifica e
divulga (fonte primária), só que republicados pela prefeitura em formato de
API GIS em vez de PDF. `parse_boletim_inea.py` usa esse endpoint.

## O que o parser extrai

`parse_boletim_inea.py` consulta a camada ArcGIS com `returnDistinctValues`
e devolve um objeto por ponto de monitoramento:

- `praia`: nome da praia
- `municipio`: fixo em `"Niteroi"` (ver Cobertura abaixo)
- `codigo_ponto`: código do ponto de coleta usado pelo INEA (ex.: `IC000`)
- `localizacao`: descrição textual do local do ponto na praia
- `status`: `propria` ou `impropria`
- `data_publicacao_boletim`: data do boletim a que esse status se refere

Um exemplo real de saída está em `sample-output.json`.

## Como rodar

```bash
python3 parse_boletim_inea.py
```

`--out arquivo.json` grava em arquivo em vez de imprimir no terminal.

Sem dependências externas: usa só a biblioteca padrão do Python 3
(`urllib`, `json`, `ssl`).

## Ressalvas

Cobertura geográfica: essa camada cobre só as praias de Niterói (29 pontos
de monitoramento). O boletim estadual completo do INEA cobre 291 pontos em
197 praias em 19 municípios, mas só achamos essa API estruturada para
Niterói; não confirmamos se outros municípios do estado publicam uma camada
GIS equivalente.

Dado desatualizado: todos os pontos retornam `data_publicacao_boletim` igual
a `2023-12-11`, então essa camada não vem sendo atualizada desde então (o
boletim semanal real do INEA é publicado toda semana). Para virar produção,
seria necessário confirmar com a prefeitura de Niterói ou com o INEA se essa
camada ainda é mantida, ou trocar por uma fonte que receba as atualizações
semanais.

Certificado TLS incompleto: o servidor `geo.niteroi.rj.gov.br` não envia a
cadeia de certificados intermediária, então uma verificação TLS padrão falha
com "unable to verify the first certificate" (mesmo problema encontrado
antes no domínio do INEA). O script contorna isso desabilitando a
verificação de certificado só para esse host. Para um PoC isso é aceitável,
mas antes de produção vale revisar a cadeia de certificados ou fixar o
certificado esperado.

Sem autenticação nem rate limit visível: o endpoint é público e não pede
login, mas não é uma API oficial documentada do INEA, então vale evitar uso
intenso por respeito à infraestrutura da prefeitura.

Nomenclatura: os valores de status (`Própria`/`Imprópria`) são os termos
usados pelo próprio INEA, normalizados aqui para `propria`/`impropria`.
