# BlueTide

BlueTide é um app web que ajuda a decidir em qual ponto da praia vale a pena entrar no mar.
Para cada posto de Ipanema ele cruza a qualidade da água medida pelo INEA, a chuva recente e a maré, e mostra uma cor: verde (recomendado), amarelo (atenção) ou vermelho (evite o banho).
Quando falta um dado importante, o app avisa e não finge que está tudo bem.

Projeto da disciplina INF1039, 2026.2, Equipe 4.

## Onde está cada coisa

O repositório é organizado por sprint, e cada sprint tem uma pasta por integrante.

| Pasta | O que tem |
| --- | --- |
| `Sprint-1` a `Sprint-3` | Pesquisa com usuários, hipóteses, escopo, fluxos, modelagem de dados e identidade visual |
| `Sprint-4` | Primeiras telas em HTML e CSS |
| `Sprint-5/bluetide` | **O app em Django.** É esta pasta que se executa |
| `Sprint-7` a `Sprint-9` | Provas de conceito da leitura do PDF do INEA, do clima, da chuva e a lógica de recomendação |
| `Sprint-10` | Testes, documentação e revisões finais |

## Como executar o app

Você precisa do Python 3.10 ou mais novo (recomendado 3.12) e do Git.

### 1. Baixar o projeto

```bash
git clone https://github.com/vitorllr/INF1039-2026.2-Team-4.git
cd INF1039-2026.2-Team-4/Sprint-5/bluetide
```

### 2. Criar o ambiente virtual e instalar as dependências

No macOS ou Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Preparar o banco e iniciar o servidor

```bash
python manage.py migrate
python manage.py runserver
```

Abra **http://127.0.0.1:8000/web/** no navegador. Para parar o servidor, aperte `Ctrl+C`.

### Telas disponíveis

| Endereço | Tela |
| --- | --- |
| `/web/` | Mapa de Ipanema com os pontos e os melhores para o seu perfil |
| `/pesquisa/` | Explorar e buscar pontos |
| `/comparar/` | Comparar todos os pontos lado a lado |
| `/praias/ipanema-posto-9/` | Detalhes de um ponto (troque o posto no endereço) |
| `/perfil/` | Perfil e preferência (banho tranquilo, surf iniciante ou sem preferência) |
| `/favoritos/`, `/alertas/`, `/faq/`, `/filtros/` | Favoritos, alertas, dúvidas frequentes e filtros |

## Modo ao vivo e modo demonstração

Por padrão o app roda **ao vivo**: a qualidade da água vem do arquivo do INEA guardado no repositório (`bluetideapp/data/agua_inea.json`) e o mar, o vento, a chuva e a maré vêm da Open-Meteo pela internet.
Sem internet, o app mostra o aviso "Atualização incompleta" e suspende as recomendações.

O **modo demonstração** usa dados fixos, não precisa de internet e é o que os testes usam. Toda tela mostra o aviso "Modo demonstração".

```bash
# macOS ou Linux
BLUETIDE_DATA_MODE=demo python manage.py runserver

# Windows (PowerShell)
$env:BLUETIDE_DATA_MODE="demo"; python manage.py runserver
```

Outras variáveis de ambiente (todas opcionais no desenvolvimento) estão explicadas no [README técnico do app](Sprint-5/bluetide/README.md#data-configuration).

## Atualizar os dados do INEA

O INEA não tem API: ele publica um PDF com o histórico das coletas. Este comando baixa o PDF mais recente e regrava `bluetideapp/data/agua_inea.json`. Se algo der errado, o arquivo anterior é mantido.

```bash
pip install -r requirements-inea.txt
python manage.py atualizar_agua_inea
```

## Rodar os testes

Dentro de `Sprint-5/bluetide`, com o ambiente virtual ativo:

```bash
python manage.py test
```

Para rodar só os testes de validação da regra de recomendação da Sprint 10:

```bash
python manage.py test bluetideapp.test_regra_recomendacao -v 2
```

Esses testes conferem cada limiar da regra (idade da coleta, chuva em 1 h e em 24 h, maré, idade da leitura de chuva) e comparam o app com a implementação de referência da Sprint 9 em 12.960 combinações.

## Problemas comuns

| Problema | O que fazer |
| --- | --- |
| `ModuleNotFoundError: No module named 'django'` | O ambiente virtual não está ativo. Rode de novo o `source .venv/bin/activate` (ou o `Activate.ps1` no Windows) |
| `python3: command not found` no Windows | Use `py` no lugar de `python3` |
| Todas as praias aparecem como "Sem recomendação" | Sem acesso à Open-Meteo. Verifique a internet ou use o modo demonstração |
| "Coleta do INEA antiga" ou "vencida" | O arquivo do INEA ficou velho. Rode `python manage.py atualizar_agua_inea` |
| `Error: That port is already in use` | Outro servidor está rodando. Feche-o ou use outra porta: `python manage.py runserver 8001` |

## Fontes dos dados e licenças

- Qualidade da água: boletins de balneabilidade do [INEA](https://www.inea.rj.gov.br/rio-de-janeiro/), órgão do governo do estado do Rio de Janeiro.
- Mar, clima, chuva e maré: [Open-Meteo.com](https://open-meteo.com/), sob licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt_BR). O uso gratuito da API é só para fins não comerciais.
- Fontes de texto: Inter e Sora, do Google Fonts, sob a SIL Open Font License 1.1.

O levantamento completo está em [`Sprint-10/Bernardo-Sznejder/fontes-e-licencas.md`](Sprint-10/Bernardo-Sznejder/fontes-e-licencas.md).
O código do projeto está sob a [licença MIT](LICENSE).
