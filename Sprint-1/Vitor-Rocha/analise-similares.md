# Análise de similares

Levantamento das soluções que hoje informam o carioca sobre condições de praia, com foco em qualidade da água, para situar onde o nosso projeto se diferencia. Foram analisadas quatro ferramentas em uso: dois aplicativos (Beach In Rio e a ferramenta oficial do INEA), um site agregador (Praia Limpa) e um app de nicho adjacente (iScamar, voltado à pesca). 

## Beach In Rio

É o concorrente mais próximo da nossa ideia original. Mostra as praias num mapa com o semáforo verde/vermelho, o status próprio/impróprio e um percentual de qualidade dos últimos meses, tudo alimentado pelo boletim do INEA. Cobre a orla carioca com um punhado de praias e resolve bem a tarefa básica: "qual é o status oficial mais recente daqui?".

A limitação é que ele para exatamente aí. Reflete o boletim como ele é, sem cruzar com chuva, sem previsão, sem explicar por que uma praia está imprópria. É uma leitura fiel do dado oficial, com o mesmo atraso e a mesma opacidade que o dado oficial tem. Quem abre o app depois de uma noite de chuva forte vê o status da última coleta, que pode ser de dias antes do temporal.

## Partiu Praia (INEA)

É a ferramenta oficial do próprio órgão que produz o dado. Permite consulta com localização por GPS, apontando as praias monitoradas mais próximas e seu status. Por vir da fonte, é a referência de autoridade.

Justamente por ser a face pública do boletim, herda todas as suas características: descreve o presente segundo a última medição, não antecipa nada e não traduz o "próprio/impróprio" em orientação prática. 

## Praia Limpa

Projeto pessoal, sem anúncios, mantido de forma independente. Sua força é a cobertura: organiza o boletim por cidade, praia e ponto, e vai além do Rio, alcançando outros estados. Cada ponto traz o status e a data da última atualização.

É também o exemplo mais claro de duas fraquezas que valem registrar. Primeiro, é uma transcrição crua, sem mapa, sem chuva, sem maré, sem qualquer camada de interpretação sobre o número. Segundo, expõe sem querer o problema do dado defasado: em algumas cidades a "última atualização" tem mais de um mês, e nada no site sinaliza ao usuário que aquela informação já não é confiável. O dado velho é apresentado com o mesmo peso do dado fresco.

## iScamar

É o mais sofisticado do conjunto, embora mire outro público: pescadores. Vale analisá-lo menos como concorrente direto e mais como prova de conceito do modelo que queremos construir. O iScamar calcula uma "nota do dia" por ponto, combinando maré, vento, fase da lua e pressão. Ou seja, ele já faz a fusão de múltiplos sinais numa recomendação interpretada, que é o coração da nossa proposta.

Três lições concretas saem dele. Ele declara abertamente suas fontes de dados (vento, tempo e pressão via Open-Meteo. Tem maré por estação harmônica combinada a serviço de terceiros), o que valida a viabilidade técnica do nosso lado. Ele trata a balneabilidade como recurso secundário e, ao fazê-lo, deixa visível o mesmo problema de defasagem, com pontos marcados como "sem dado recente". E ele separa com cuidado a balneabilidade da segurança do pescado, uma nuance que mostra maturidade no trato do dado.

O que ele *não* faz abre nosso espaço: a nota é otimizada para prever se o peixe morde, não se a pessoa pode nadar. A lógica é oposta à nossa, e o público também. Não existe o equivalente do iScamar voltado ao banhista.

## Quadro comparativo

| Critério | Beach In Rio | Partiu Praia (INEA) | Praia Limpa | iScamar | Nosso projeto |
|---|:---:|:---:|:---:|:---:|:---:|
| Foco | Banho | Banho | Banho | Pesca | Frequentador de praia |
| Fonte da água | INEA | INEA | INEA | INEA / SIGeo | INEA |
| Mapa | ✓ | ✓ | — | ✓ | ✓ |
| Status próprio/impróprio | ✓ | ✓ | ✓ | ◐ | ✓ |
| Previsão pós-chuva | — | — | — | — | ✓ |
| Maré | — | — | — | ✓ | ✓ |
| Qualidade da areia | — | — | — | — | ✓ (v2) |
| Explica o *porquê* do status | — | — | — | ◐ | ✓ |
| Mostra a idade do dado | — | ◐ | ◐ | ◐ | ✓ |
| Resposta interpretada | — | — | — | ✓ | ✓ |

*✓ atende · ◐ atende parcialmente · — não atende*

## A lacuna

Três padrões atravessam todos os concorrentes de banho e definem o vazio que ocupamos.

**Todos descrevem o passado.** Beach In Rio, Partiu Praia e Praia Limpa mostram a última coleta oficial e nada além dela. Nenhum responde à pergunta que o banhista de fato faz depois de uma chuva: *"choveu ontem, posso nadar hoje?"*. A previsão pós-chuva, cruzando o boletim com a precipitação recente e modulada pela maré perto das fozes, é a diferença central e não tem paralelo entre os similares.

**Ninguém trata a areia.** Os quatro são ferramentas de água. O monitoramento municipal da areia existe, foi interrompido na divulgação e nunca teve uma interface pública decente, um espaço em branco que amplia nosso público de quem entra no mar para quem apenas usa a praia.

**O dado envelhece em silêncio.** Praia Limpa e iScamar mostram, involuntariamente, que a informação oficial fica velha e que as ferramentas não avisam. Tornar a idade do dado explícita, e apoiar a recomendação no modelo quando a coleta está defasada, é uma diferenciação de confiança que custa pouco e nenhum concorrente entrega.

O iScamar prova que o modelo de nota interpretada a partir de múltiplos sinais funciona e é tecnicamente viável. O que falta no mercado é esse mesmo modelo virado para o banhista, somando a camada de previsão, a dimensão da areia e a honestidade sobre a idade do dado. É esse cruzamento, e não cada peça isolada, que define o nosso projeto.