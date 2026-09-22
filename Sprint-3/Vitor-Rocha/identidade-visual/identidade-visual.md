# Identidade visual - BlueTide

Este documento define a paleta de cores e a tipografia que vão guiar o visual das telas do BlueTide, o app que cruza o boletim do INEA, dados de chuva e maré numa recomendação verde/amarelo/vermelho.

## Paleta de cores

### Cores de marca

| Cor | Hex | Uso | Por que |
|---|---|---|---|
| Azul-maré (primária) | `#0B3C5D` | Cabeçalhos, ícone do app, elementos de navegação | Azul profundo remete a água e maré alta, e passa a seriedade de um app de segurança pública, sem parecer um app de lazer genérico |
| Teal-corrente (secundária) | `#1C7C93` | Botões, links, destaques de interface | Fica entre o azul-maré e o verde do status "seguro", funcionando como ponte visual entre marca e sistema de status |
| Espuma (apoio claro) | `#BFE3EA` | Fundos de cartões, divisores, estados hover | Simula a espuma da onda; clareia a interface sem recorrer a um cinza neutro sem relação com o tema |
| Tinta (texto) | `#0A1F2B` | Texto principal | Quase preto com leve dominante azulada, mantém contraste alto sem ser um preto puro dissonante da paleta |
| Papel (fundo) | `#F5F9FA` | Fundo padrão das telas | Branco levemente azulado, reduz o brilho excessivo de um branco puro em uso ao ar livre e sob sol forte |

### Cores de status (verde/amarelo/vermelho)

Essas três cores são o núcleo funcional do app: é o que a pessoa olha primeiro para decidir se pode ir à praia ou não. Por isso foram escolhidas e testadas separadamente da paleta de marca, priorizando contraste alto e diferenciação mesmo para quem tem alguma dificuldade de percepção de cor.

| Status | Hex | Contraste com texto branco | Por que |
|---|---|---|---|
| Verde (seguro) | `#1E8A5F` | Alto | Verde puxado para o azulado, mais escuro que um verde-limão comum, para não se confundir com o teal de marca nem "sumir" em telas de brilho alto |
| Amarelo (atenção) | `#C97A1E` | Alto | Amarelo puro tem contraste ruim contra fundo claro, então usei essa variante alaranjada e mais escura, que mantém a leitura imediata de "atenção" sem perder contraste |
| Vermelho (risco) | `#B23A2E` | Alto | Vermelho com leve tom terroso, evita o vermelho-neon que cansa a vista em uso recorrente, mas mantém urgência clara |

As três cores de status foram calibradas para terem luminosidade parecida entre si, então nenhuma delas "grita" mais que a outra por causa do brilho, só pela cor em si.

## Tipografia

- Títulos e elementos de destaque: Sora (peso 600-700)
- Texto de corpo e dados (chuva em mm, altura de maré, horários): Inter (peso 400-500, com números tabulares ativados)

### Por que essa combinação

A Sora tem traços geométricos com terminais levemente arredondados, o que dá um ar técnico e confiável sem ser frio, adequado para um app que comunica informação oficial (boletim do INEA) de um jeito acessível. Usada só em títulos e no nome do app, ela marca a identidade sem comprometer a legibilidade do restante da tela.

A Inter foi desenhada especificamente para telas e para leitura rápida em tamanhos pequenos, que é o cenário mais comum aqui: alguém checando o status antes de sair de casa, muitas vezes sob luz solar direta ou em uma tela pequena. Sua altura-x generosa e o suporte a números tabulares garantem que valores como "12mm" ou "1,8m" fiquem alinhados e legíveis em listas e cartões, sem embaralhar dígitos.

As duas fontes são gratuitas (Google Fonts), têm suporte completo a acentuação em português e mantêm um contraste de peso visual suficiente entre título e corpo para criar hierarquia clara nas telas, mesmo sem depender de cor para isso - importante porque o app já usa cor para o significado mais crítico (o status verde/amarelo/vermelho), então o resto da hierarquia visual não deve competir com esse uso.
