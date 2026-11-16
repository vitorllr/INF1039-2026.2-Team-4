# PoC de importação de dados de chuva

Este script baixa a chuva recente das 12 praias que o BlueTide cobre e grava tudo em `chuva_por_praia.json`.
É a entrada de chuva da regra de recomendação especificada em `Sprint-9/Vitor-Rocha/logica-recomendacao/`.
As mesmas 12 praias do `Sprint-8/Vitor-Rocha/poc-dados-clima/` estão aqui, mas aquela PoC traz o clima geral por hora (temperatura, vento, UV) e esta só cuida de chuva.

## Como rodar

```
pip install requests
python importar_chuva.py
```

Precisa de Python 3 e da biblioteca `requests`, mais nada.
Não precisa de chave de API.
O script imprime uma linha por praia e grava `chuva_por_praia.json` ao lado dele.
Se nenhuma das duas fontes responder, ele sai com erro e não mexe no arquivo que já existe.

## Fonte escolhida

A fonte principal são os pluviômetros do Sistema Alerta Rio, da Prefeitura do Rio, lidos neste endereço:

`https://websempre.rio.rj.gov.br/json/chuvas`

Cada estação devolve a chuva acumulada em mm nas últimas janelas de tempo (campos `m05`, `m15`, `h01`, `h02`, `h03`, `h04`, `h24`, `h96` e `mes`), a posição e o horário da leitura (`read_at`).
Não achei documentação oficial desse endereço.
Os significados dos campos são uma leitura minha a partir dos nomes e dos valores: nas 33 estações da rodada de exemplo os números nunca diminuem de `m05` até `h96`, como acontece com acumulados.

Cada praia usa a estação mais próxima em linha reta (fórmula de haversine).
Do que vem do feed o script guarda `h01`, `h03`, `h24` e `h96` como `chuva_1h_mm`, `chuva_3h_mm`, `chuva_24h_mm` e `chuva_96h_mm`.

### Por que essa fonte

A regra de recomendação precisa saber se choveu nas últimas 24 horas, porque é isso que o INEA pede para considerar antes de entrar no mar.
Pluviômetro mede a chuva que caiu de fato e já devolve o acumulado de 1h e de 24h pronto, sem a gente somar nada.
O Open-Meteo, que a Sprint 8 usou, é um modelo de previsão.
Na rodada de 16/11/2026 ele deu 4,7 mm em 24h para as dez praias da Zona Sul e da Baía, enquanto os pluviômetros mediram de 1,2 a 6,2 mm, e deu 0,6 mm na última hora onde os pluviômetros mediram 0,0.

### Atualização, licença e limites

- O `read_at` mudou de 12:30 para 12:40 entre duas consultas que fiz no mesmo dia, então o feed atualiza em passos de 10 minutos ou menos.
  O site do Alerta Rio fala em dados de 15 em 15 minutos nos downloads.
  Não achei garantia de frequência para esse endereço.
- Os termos de uso do site do Alerta Rio (https://alertario.rio.rj.gov.br/institucional/termos-de-uso/) pedem que a fonte seja citada como "Sistema Alerta Rio, da Prefeitura do Rio de Janeiro".
  Também proíbem uso comercial e pedem autorização para reproduzir o conteúdo em meios de divulgação.
  Não achei um termo específico para o feed, então a equipe precisa confirmar com o Alerta Rio antes de publicar o app.
- Não tem chave de API nem limite de chamadas documentado.
  Nos testes, o servidor respondeu "Request Rejected" para o `curl` puro e aceitou o `requests` do Python, por isso o script manda um `User-Agent` que se identifica como a PoC da disciplina.
  Quando o bloqueio acontece vem uma página HTML com status 200, e o script trata isso como falha e tenta de novo (3 tentativas, 5 segundos entre elas).

## Fallback e previsão

Quando não dá para confiar no pluviômetro, a praia usa a chuva do modelo do Open-Meteo (https://api.open-meteo.com/v1/forecast, variável `precipitation` por hora, soma da hora anterior).
Isso acontece em três casos:

- o feed do Alerta Rio não respondeu;
- a estação mais próxima fica a mais de 10 km da praia;
- a leitura da estação tem mais de 60 minutos.

Os 10 km e os 60 minutos são chute inicial meu, a validar com a equipe.
Nesses casos o campo `qualidade` vem como `modelada` (e `observada` quando é pluviômetro) e `motivo_do_fallback` diz o que aconteceu.

O Open-Meteo é gratuito para uso não comercial, com menos de 10.000 chamadas por dia, e os dados saem sob CC BY 4.0 (https://open-meteo.com/en/terms).
Um app com anúncio ou assinatura já seria uso comercial e pediria plano pago.

A mesma chamada traz a previsão das próximas 6h e 24h (`previsao_6h_mm` e `previsao_24h_mm`).
A regra v1 não usa esses dois campos, eles ficam no arquivo para a tela de detalhes.

## Saída

Exemplo de uma praia em `chuva_por_praia.json`:

```json
"Copacabana": {
  "chuva": {
    "fonte": "alerta_rio",
    "qualidade": "observada",
    "estacao": "Copacabana",
    "distancia_km": 1.9,
    "lido_em": "2026-11-16T12:40:00-03:00",
    "chuva_1h_mm": 0.0,
    "chuva_3h_mm": 0.0,
    "chuva_24h_mm": 6.2,
    "chuva_96h_mm": 6.2
  },
  "previsao": { "previsao_6h_mm": 3.8, "previsao_24h_mm": 7.5 }
}
```

A regra de recomendação lê de `chuva` os campos `chuva_1h_mm`, `chuva_24h_mm`, `qualidade` e `lido_em`.

## Exemplo de execução

O `chuva_por_praia.json` desta pasta foi gerado em 16/11/2026, às 12:46 (horário de Brasília), contra as duas fontes ao vivo.
Todas as 12 praias saíram com chuva observada, com estações entre 0,2 e 4,6 km.

## Limitações

- Estação mais próxima em linha reta ignora o relevo. Em praia com serra por perto, a chuva medida a poucos quilômetros pode ser bem diferente da que cai na areia.
- Barra da Tijuca usa a estação Barra/Riocentro, a 4,6 km. A Barra/Barrinha e a Recreio dos Bandeirantes ficam mais longe.
- O feed não é uma API documentada e pode mudar de formato sem aviso. O script avisa quando o formato muda e cai para o modelo.
- A PoC faz uma chamada por rodada e não guarda histórico. Num app de verdade vale cachear o resultado por 10 a 15 minutos.
