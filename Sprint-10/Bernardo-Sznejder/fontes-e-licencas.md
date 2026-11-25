# Revisão das fontes e licenças dos dados

Sprint 10, Bernardo Sznejder. Revisão feita em 25/11/2026 sobre o estado do repositório depois do PR #49.

## Resumo

| Fonte | Onde é usada | Licença ou termo | Situação |
| --- | --- | --- | --- |
| INEA, boletins de balneabilidade | App (`Sprint-5`), PoC da Sprint 7 | Informação pública do governo do estado, sem licença aberta declarada | OK, com citação da fonte e da data |
| Open-Meteo Weather API | App, PoCs das Sprints 8 e 9 | Dados em CC BY 4.0; API gratuita só para uso não comercial | **Corrigido nesta sprint**: faltava o link de atribuição |
| Open-Meteo Marine API | App (ondas, temperatura do mar, maré) | CC BY 4.0, mais crédito aos modelos de origem (Copernicus, ECMWF, NOAA, DWD) | OK com o crédito à Open-Meteo; ver ponto de atenção 2 |
| Alerta Rio (Prefeitura do Rio) | Só na PoC da Sprint 9, não no app | Sem licença declarada no endpoint usado | Atenção antes de levar para o app |
| Google Fonts: Inter e Sora | App e protótipos | SIL Open Font License 1.1 | OK |
| Bootstrap 5.3 | Protótipos da Sprint 4 | MIT | OK |
| Leaflet 1.9.4 | Protótipo do mapa da Sprint 4 | BSD 2-Clause | OK |
| OpenStreetMap (tiles) | Protótipo do mapa da Sprint 4 | Dados ODbL, crédito obrigatório | OK, o protótipo já mostra "© OpenStreetMap contributors" |
| Foto `beach.jpg` | App, fundo do cartão de destaque | **Origem não registrada** | Pendente, ver ponto de atenção 1 |
| Ícones PNG (`icone-*.png`, `marcador-*.png`) | Protótipos da Sprint 4 (copiados para o app, mas não usados nele) | **Origem não registrada** | Pendente, ver ponto de atenção 1 |
| Logos da identidade visual | `Sprint-3/Vitor-Rocha/identidade-visual` | Criação da equipe (a confirmar) | Pendente, ver ponto de atenção 1 |
| Código do repositório | Todo o projeto | MIT, copyright "vitorllr" | OK, ver ponto de atenção 4 |

## Detalhe por fonte

### INEA (qualidade da água)

- O que usamos: o PDF anual "barra_e_zona_sul_historico" publicado em https://www.inea.rj.gov.br/rio-de-janeiro/. O comando `atualizar_agua_inea` baixa o PDF e grava `bluetideapp/data/agua_inea.json` com a URL de origem e a data de cada coleta.
- Licença: o INEA não declara uma licença aberta para os boletins. São informações públicas de um órgão estadual, de acesso garantido pela Lei de Acesso à Informação (Lei 12.527/2011). O uso acadêmico com citação da fonte é adequado.
- O que o app já faz certo: mostra "dados reais do INEA", a data da coleta, o ponto de monitoramento usado e avisa que o INEA não mede por posto. O arquivo JSON guarda `source_url`.
- Cuidado: o app não deve dar a entender que é um serviço oficial do INEA. Hoje ele não dá.
- O PDF `Sprint-7/Vitor-Rocha/poc-parsing-pdf/historico_balneabilidade_inea.pdf` é uma cópia de documento público. Pode ficar no repositório, com a fonte citada na PoC.

### Open-Meteo (clima, chuva, mar e maré)

- O que usamos: `api.open-meteo.com/v1/forecast` (temperatura, vento, chuva) e `marine-api.open-meteo.com/v1/marine` (ondas, temperatura do mar, nível do mar para a maré).
- Licença dos dados: CC BY 4.0. A página de licença pede um link para a Open-Meteo junto de qualquer lugar onde os dados aparecem, e a indicação da licença (https://open-meteo.com/en/licence).
- Termos de uso: a API gratuita é só para uso não comercial, com limite de 10.000 chamadas por dia, 5.000 por hora e 600 por minuto (https://open-meteo.com/en/terms). Um projeto acadêmico sem anúncios nem assinatura se encaixa. O app faz 2 chamadas por posto e guarda em cache por 5 minutos, então fica bem abaixo do limite.
- Problema encontrado: o app só escrevia "Open-Meteo" na tela de detalhes, sem link nem licença, e não dava crédito no mapa, na busca e na comparação, onde ondas, vento e chuva também aparecem.
- Correção feita: o aviso de dados (`_data_notice.html`), que aparece em todas as telas com dados, ganhou a linha "Mar e clima: dados de Open-Meteo.com, licença CC BY 4.0. Qualidade da água: boletins do INEA", com links. A tela de detalhes agora tem link para Open-Meteo.com e cita a licença.

### Alerta Rio (chuva observada)

- Usado só em `Sprint-9/Vitor-Rocha/poc-importacao-chuva/importar_chuva.py`, pelo endpoint `websempre.rio.rj.gov.br/json/chuvas`.
- Não achei termos de uso ou licença publicados para esse endpoint. Ele não é uma API documentada.
- Recomendação: se a equipe quiser levar a chuva observada do Alerta Rio para o app, citar "Sistema Alerta Rio, Prefeitura do Rio de Janeiro" na tela e confirmar se há termos no portal de dados abertos da prefeitura (data.rio). Hoje o app usa só a chuva modelada da Open-Meteo e marca a confiança como média por isso.

### Fontes tipográficas, bibliotecas e mapas

- Inter e Sora vêm do Google Fonts, ambas sob SIL Open Font License 1.1, que permite uso livre em sites.
- Bootstrap (MIT) e Leaflet (BSD 2-Clause) aparecem só nos protótipos da Sprint 4. Carregados por CDN, as licenças já vão junto dos arquivos.
- Os tiles do OpenStreetMap no protótipo da Sprint 4 exigem o crédito "© OpenStreetMap contributors", que já está no código. O app final usa um esquema próprio em SVG, sem tiles.

## Pontos de atenção

1. **Origem das imagens.** Não há registro de onde vieram `beach.jpg`, os ícones PNG e os logos. Se forem de banco de imagens, precisam da licença e, quando pedido, do crédito. Se foram criados pela equipe ou gerados por IA, vale anotar isso aqui. Quem adicionou cada arquivo pode completar a tabela.
2. **Crédito aos modelos de origem da Marine API.** A documentação da Marine API pede que se credite também os provedores dos modelos (MeteoFrance/Copernicus Marine, ECMWF, NOAA, DWD). Para um projeto acadêmico, uma linha na tela de dúvidas frequentes resolve: "Dados marinhos da Open-Meteo, a partir de modelos da MeteoFrance (Copernicus Marine Service), ECMWF, NOAA e DWD."
3. **Uso comercial.** Se o BlueTide virar produto com anúncio ou assinatura, a API gratuita da Open-Meteo deixa de valer e é preciso um plano pago ou hospedar a própria instância (código AGPLv3).
4. **Copyright do código.** O arquivo `LICENSE` está em nome de "vitorllr". Se a equipe quiser que o crédito seja de todos, basta trocar para "Equipe 4 INF1039 2026.2" ou listar os nomes.

## Arquivos alterados por esta revisão

- `Sprint-5/bluetide/bluetideapp/templates/_data_notice.html`: linha de crédito das fontes.
- `Sprint-5/bluetide/bluetideapp/templates/detalhes.html`: link para Open-Meteo.com e licença.
- `Sprint-5/bluetide/bluetideapp/static/css/design-system.css`: estilo `.source-credit` e dos links de fonte.
