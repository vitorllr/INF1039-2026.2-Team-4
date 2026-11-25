# Testes de validação da regra de recomendação

Sprint 10, Bernardo Sznejder.

Os testes estão em `Sprint-5/bluetide/bluetideapp/test_regra_recomendacao.py` e rodam junto com os outros testes do app.

```bash
cd Sprint-5/bluetide
python manage.py test bluetideapp.test_regra_recomendacao -v 2
```

## O que já existia

O `tests.py` já conferia os 10 exemplos do PDF da Sprint 9, o efeito da maré e do perfil, e a ordenação. Faltava testar as fronteiras de cada limiar, que é onde um `>` trocado por `>=` passa despercebido.

## O que os novos testes cobrem (28 testes)

| Grupo | Casos |
| --- | --- |
| Idade da coleta do INEA | 0 e 9 dias verde com confiança alta; 10 e 30 dias amarelo com confiança média; 31 dias e data no futuro viram "sem dado" (amarelo, baixa); status desconhecido; impróprio com 30 dias ainda é vermelho e com 31 deixa de valer |
| Chuva em 24 h | 4,9 mm verde, 5,0 amarelo, 19,9 amarelo, 20,0 vermelho |
| Chuva na última hora | 2,5 mm verde, 2,6 amarelo, 7,6 amarelo, 7,7 vermelho; valor ausente conta como zero |
| Idade da leitura de chuva | exatamente 3 h ainda vale; 3 h e 1 min vira "sem dado de chuva"; sem horário vira "sem dado"; chuva só do modelo baixa a confiança para média |
| Maré | com maré alta, 0,9 mm é verde e 1,0 mm é amarelo ("chuva fraca com maré alta"); sem dado de maré conta como não alta e baixa a confiança |
| Prioridade | vermelho vence qualquer dúvida; impróprio com chuva forte lista os dois motivos; amarelo junta todos os motivos; erro de integração suspende mesmo com dados bons; amarelo é recomendável e vermelho não |
| Perfil e ordenação | perfil desconhecido vira banho tranquilo; ordem final é verde, amarelo, vermelho e por último sem recomendação, mesmo quando o perfil preferiria um ponto amarelo |
| Comparação com a Sprint 9 | as constantes do app são as mesmas da Sprint 9; app e `recomendacao.py` da Sprint 9 dão a mesma cor e confiança em 12.960 combinações de status, idade, chuva, maré, qualidade e idade da leitura |

## Resultado

Os 28 testes novos passam, e os 84 testes do app passam juntos (cerca de 1,5 s).

Para conferir que os testes pegam erros de verdade, troquei de propósito duas condições no código da regra:

- `chuva_24h >= 20` por `> 20`: 3 testes falharam, incluindo a comparação com a Sprint 9.
- remover a checagem de data no futuro da coleta: 1 teste falhou.

Depois desfiz as duas mudanças.

## Observação sobre a regra

Na comparação com a Sprint 9, as duas implementações bateram em todas as combinações. Um comportamento que vale a equipe conhecer: uma coleta **imprópria** com mais de 30 dias deixa de contar e o ponto fica **amarelo**, não vermelho. Isso segue a regra escrita na Sprint 9, e há um teste que documenta esse caso.
