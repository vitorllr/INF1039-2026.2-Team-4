# Revisão de responsividade e acessibilidade do design final

Sprint 10, Bernardo Sznejder. Revisão do app Django em `Sprint-5/bluetide` em 25/11/2026.

## Como foi feita

- Abri as 9 telas (`/web/`, `/pesquisa/`, `/perfil/`, `/favoritos/`, `/faq/`, `/alertas/`, `/filtros/`, `/comparar/` e `/praias/ipanema-posto-8/`) num Chromium automatizado, nas larguras de 320, 375, 768 e 1280 px, nos modos demonstração e ao vivo.
- Em cada tela medi se havia rolagem horizontal e se algum elemento clicável tinha menos de 24 × 24 px (critério 2.5.8 da WCAG 2.2).
- Em 375 e 1280 px rodei o axe-core 4.10 com as regras WCAG 2.0, 2.1 e 2.2 nível A e AA, mais as boas práticas.
- Conferi as cores do `design-system.css` com o cálculo de contraste da WCAG.

## Resultado antes das correções

| O que | Resultado |
| --- | --- |
| Rolagem horizontal | Nenhuma, em nenhuma largura. O layout já se adapta bem de 320 px até desktop |
| Menu no celular | Bom: botão com `aria-expanded`, foco vai para o menu ao abrir, `Esc` fecha, menu fica `inert` quando fechado |
| Link "Pular para o conteúdo", `lang="pt-BR"`, títulos de página, ícones com `aria-hidden` | Tudo presente |
| `prefers-reduced-motion` | Já respeitado |
| Contraste dos selos verde e laranja | **Falha**: 3,76:1 e 3,49:1 (mínimo 4,5:1). Aparece em quase todas as telas |
| Contraste do selo cinza ("Sem recomendação") | **Falha**: 3,44:1 |
| Contraste dos rótulos das métricas ("ONDAS", "VENTO") | **Falha**: 4,17:1 |
| Contorno de foco | **Fraco**: azul com 45% de transparência, pouco visível sobre o fundo claro |
| Foco nos pinos do mapa | **Fraco**: o contorno era removido e só aparecia uma sombra clara |
| Links "Alertas" e "Dúvidas frequentes" do menu | **Alvo pequeno**: 22 px de altura |
| Barra de navegação inferior do celular | Não indicava a página atual para leitores de tela (faltava `aria-current`) |
| Seletor de perfil no mapa e na comparação | Rótulo ignorado por leitores de tela (faltava `role="group"`) e perfil ativo sem `aria-current` |

## Correções feitas

Todas no CSS base (`design-system.css`) e nos templates, sem mudar o layout.

| Correção | Antes | Depois |
| --- | --- | --- |
| Novos tons de texto `--success-ink`, `--warning-ink`, `--neutral-ink` usados nos selos | 3,76 / 3,49 / 3,44 | 5,29 / 5,46 / 4,93 |
| `--ink-500` escurecido de `#637883` para `#566b76` | 4,17 | 5,05 |
| Contorno de foco sólido na cor `--tide-700` | transparente | 5,2:1 sobre o fundo |
| Anel escuro no pino do mapa focado pelo teclado | só sombra | anel de 24 px |
| `.quiet-link` com altura mínima de 24 px | 22 px | 24 px |
| `aria-current="page"` na barra inferior | ausente | presente |
| `role="group"` e `aria-current` no seletor de perfil | ausente | presente |

Depois das correções o axe-core não acusa nenhuma violação nas 9 telas, nos dois modos, e os 84 testes automáticos passam.
As cores dos pinos, das bordas e da identidade visual não mudaram. Só o texto dos selos ficou um pouco mais escuro.

## O que ficou para a equipe decidir

1. **Número dentro do pino do mapa.** O número branco sobre o pino laranja tem 4,08:1 e sobre o cinza 3,91:1. No desktop o número é grande e passa, mas no celular fica com uns 10 px. Como cada pino tem um `aria-label` completo e a lista de cartões repete a informação, não é bloqueante. Se quiserem resolver, a saída é escurecer os pinos ou tirar o número no celular.
2. **Cor como única diferença entre os pinos.** Quem não distingue cores não sabe a situação de cada pino só olhando o mapa. A legenda e os cartões ao lado têm o texto, então a informação existe. Uma melhoria seria usar formas diferentes (por exemplo um "!" no pino laranja e um "×" no vermelho).
3. **Botão de favorito e interruptores.** O coração ainda não faz nada (não há favoritos salvos) e não informa o estado com `aria-pressed`. Quando o favoritar for implementado, incluir esse atributo.
4. **Teste com leitor de tela real.** A revisão foi automática e por inspeção do código. Vale uma passada rápida com o VoiceOver (Cmd+F5 no Mac) no mapa e nos detalhes antes da entrega.
