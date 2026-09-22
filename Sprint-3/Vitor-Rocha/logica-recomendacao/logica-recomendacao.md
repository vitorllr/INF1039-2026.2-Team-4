# Logica da recomendacao (verde / amarelo / vermelho)

Item do quadro: "Especificar a logica da recomendacao" (Sprint 3, dificil, entrega 11/09/2026).

## Status da evidencia sobre o boletim do INEA

A tarefa irma `inf1039-poc-parsing-inea`, que deveria confirmar quais campos o boletim do INEA
realmente expoe, ainda nao tem `sample-output.json` nem README publicados em
`Sprint-3/Vitor-Rocha/poc-parsing-boletim-inea/` nem em PR aberto no repositorio (verificado em
22/09/2026).
Por isso, os campos do INEA usados abaixo vem de duas fontes que ja temos: o levantamento de
fontes de dados do Sprint 2 (`Sprint-2/Vitor-Rocha/fontes-de-dados.pdf`) e o proprio texto
institucional do INEA.
Essas fontes confirmam que o boletim e semanal, cobre 291 pontos em 197 praias do estado, e
publica um status por ponto de coleta (proprio ou improprio).
Tudo que vai alem disso, como nomes exatos de campos em JSON, formato de data, ou se existe
algum nivel de alerta alem de proprio/improprio, e uma suposicao explicita e precisa ser
conciliada quando a PoC de parsing entregar dados reais.

## Entradas concretas

| Entrada | Fonte | Unidade / formato | Observacao |
|---|---|---|---|
| `status_inea` | Boletim semanal do INEA, PDF institucional (https://www.inea.rj.gov.br/ar-agua-e-solo/balneabilidade-das-praias/) | enum `proprio` \| `improprio` \| `desconhecido` | Por ponto de coleta mais proximo da praia consultada. Campo exato do parser ainda nao confirmado (ver secao acima); `desconhecido` cobre falha de parsing ou boletim indisponivel. |
| `data_boletim` | Mesmo boletim do INEA | data (ISO 8601) | Data de publicacao/coleta do boletim usado para calcular a "idade" do dado. |
| `chuva_24h_mm` | Open-Meteo Weather API (https://open-meteo.com/en/docs), campo `precipitation` horario | milimetros, somados nas ultimas 24h antes do horario de consulta | Coordenadas da praia consultada. API gratuita, sem chave, confirmada em uso no Sprint 2. |
| `mare_altura_m` | Tabua de mare (fonte listada em `Sprint-1/Eduardo-Sepulveda/APIs-usadas.md`; ainda sem URL/provedor especifico escolhido) | metros, altura prevista no horario de consulta | O Sprint 2 avaliou a Open-Meteo Marine API para mare e descartou por baixa precisao nesse dado; mare vem de uma tabua de mare separada, provedor a definir. |
| `mare_sizigia` | Mesma tabua de mare | booleano | Indica mare de sizigia (mare alta acima do normal), quando a fonte fornecer essa informacao. |

## Regra de combinacao

A regra segue duas ideias que ja temos evidencia para sustentar:
a recomendacao do proprio INEA de evitar banho do mar nas primeiras 24h depois de chuva forte
(citada no boletim institucional), e o fato de o boletim ser semanal, ou seja, pode estar
"desatualizado" em relacao a uma chuva que caiu depois da coleta.
Os limiares numericos de chuva e mare abaixo (`RAIN_HEAVY_MM`, `RAIN_MODERATE_MM`,
`MARE_ALTA_M`) sao um ponto de partida da equipe, nao um limiar cientifico com citacao, e
precisam de validacao (por exemplo contra series historicas de chuva forte no Rio ou contra a
tabua de mare local).

Prioridade de avaliacao (a primeira condicao que bater decide a cor):

1. `status_inea == improprio` -> **vermelho**. O status oficial de contaminacao da agua
   prevalece sobre qualquer leitura de chuva ou mare.
2. `status_inea == proprio` e `chuva_24h_mm >= RAIN_HEAVY_MM` -> **vermelho**. Chuva forte
   recente pode ja ter contaminado a agua antes do proximo boletim, entao o dado do INEA fica
   defasado.
3. `status_inea == desconhecido` e (`chuva_24h_mm` desconhecida ou `chuva_24h_mm >=
   RAIN_MODERATE_MM`) -> **vermelho**. Sem confirmacao oficial e com sinal de chuva relevante
   ou ausente, o cenario mais seguro e o mais restritivo.
4. `status_inea == proprio` e (`chuva_24h_mm >= RAIN_MODERATE_MM` ou `mare_sizigia == true` ou
   idade do boletim > `BOLETIM_VALIDO_DIAS`) -> **amarelo**. Chuva moderada, mare de sizigia
   (que pode comprometer drenagem e empurrar poluicao de volta pra praia) ou boletim
   desatualizado sao motivo de cautela, mas nao de bloqueio total.
5. `status_inea == desconhecido` e `chuva_24h_mm < RAIN_MODERATE_MM` -> **amarelo**. Sem
   confirmacao do INEA nunca chega a verde, mesmo com chuva baixa.
6. Qualquer outro caso (`status_inea == proprio`, chuva baixa, sem mare de sizigia, boletim
   dentro da validade) -> **verde**.

Limiares assumidos (a validar com a equipe):

- `RAIN_HEAVY_MM = 20` (chuva acumulada em 24h considerada forte)
- `RAIN_MODERATE_MM = 5` (chuva acumulada em 24h considerada moderada)
- `MARE_ALTA_M`: nao usado diretamente na regra acima porque preferimos o booleano
  `mare_sizigia` da propria tabua de mare quando disponivel; se a fonte so entregar altura em
  metros, um valor de referencia precisa ser definido por estacao/porto local antes de virar
  numero fixo aqui.
- `BOLETIM_VALIDO_DIAS = 8` (7 dias de ciclo semanal mais 1 dia de tolerancia)

## Exemplos trabalhados

**Verde**: Praia da Reserva, `status_inea = proprio` (boletim de 2 dias atras), `chuva_24h_mm =
1.2`, `mare_sizigia = false`. Nenhuma condicao de vermelho ou amarelo bate, cai na regra 6 ->
verde.

**Amarelo (chuva moderada)**: Praia do Recreio, `status_inea = proprio` (boletim de 1 dia
atras), `chuva_24h_mm = 8`, `mare_sizigia = false`. Bate a regra 4 pela chuva moderada ->
amarelo.

**Amarelo (mare de sizigia)**: Praia da Barra, `status_inea = proprio` (boletim de 3 dias
atras), `chuva_24h_mm = 2`, `mare_sizigia = true`. Bate a regra 4 pela mare de sizigia, mesmo
com chuva baixa -> amarelo.

**Amarelo (boletim desatualizado)**: Praia de Ipanema, `status_inea = proprio`, mas o boletim
usado tem 10 dias, `chuva_24h_mm = 0.5`, `mare_sizigia = false`. Bate a regra 4 pela idade do
boletim -> amarelo.

**Vermelho (status improprio)**: Praia de Copacabana, `status_inea = improprio`,
`chuva_24h_mm = 0`. Bate a regra 1 direto -> vermelho, independente de chuva ou mare.

**Vermelho (chuva forte recente)**: Praia de Botafogo, `status_inea = proprio` (boletim de 1
dia atras), `chuva_24h_mm = 35`. Bate a regra 2, chuva forte apos a coleta do boletim ->
vermelho.

## Casos de borda

- **INEA indisponivel ou boletim nao parseavel**: `status_inea = desconhecido`. Nunca cai em
  verde (regras 3 e 5); no maximo amarelo, e vermelho se a chuva tambem for alta ou
  desconhecida.
- **Chuva indisponivel (API fora do ar)**: tratada como "chuva desconhecida" para efeito da
  regra 3; se `status_inea = proprio`, ainda cai em amarelo pela regra 4 (idade do boletim ou
  mare continuam valendo; se nenhuma delas bater e a chuva for a unica informacao faltando,
  o sistema deve registrar essa lacuna e nao promover automaticamente para verde).
- **Mare indisponivel**: como a mare so participa como um gatilho adicional para amarelo
  (regra 4), a ausencia dela nao impede calcular verde ou vermelho pelas outras entradas; o
  sistema deve apenas sinalizar que a mare nao entrou na conta daquela recomendacao.
- **Sinais conflitantes (INEA proprio, chuva forte)**: e o caso coberto explicitamente pela
  regra 2. A logica assume que um evento de chuva forte depois da coleta do boletim invalida
  o status "proprio" ainda nao verificado desde a chuva, entao a chuva vence.
- **Boletim muito antigo (acima de `BOLETIM_VALIDO_DIAS`)**: nunca promove a verde mesmo se
  todo o resto estiver bom, pela regra 4.

## Pseudocodigo / implementacao de referencia

Implementacao de referencia em `recomendacao.py` neste mesmo diretorio, para a proxima tarefa
de engenharia usar direto em vez de re-derivar a regra a partir do texto acima.
