# Telas do aplicativo

> Documento de referência para a definição da interface e dos fluxos do aplicativo de monitoramento de praias.
>
> As telas abaixo não estão necessariamente em ordem de implementação.

## 1. Splash Screen

Tela inicial de carregamento do aplicativo.

### Elementos
- Nome do aplicativo
- Logo

---

## 2. Homepage

Tela de entrada do usuário, com acesso à autenticação e criação de conta.

### 2.1 Login

Campos:
- Nome de usuário ou e-mail
- Senha

### 2.2 Criar conta

Campos:
- Nome
- E-mail
- Senha
- Confirmação de senha

Após o cadastro, deverá ser apresentado um questionário rápido de configuração inicial.

### 2.3 Questionário rápido

Informações coletadas:
1. Permissão de acesso à localização
2. Cidade onde mora
3. Praias/postos de preferência
4. Meio de transporte normalmente utilizado

Essas informações poderão ser utilizadas para personalizar a experiência do usuário.

---

## 3. Tela principal

Tela central do aplicativo, baseada em um mapa da área de preferência do usuário.

### Funcionalidades

- Mapa central da área de preferência
- Monitor de lotação
- Marcadores de condição da água:
  - Própria
  - Imprópria
  - Sem informação
- Altura da onda
- Informações climáticas:
  - Chuva
  - Vento
  - Outras condições relevantes

---

## 4. Pesquisa de praias

Tela destinada à localização e filtragem de praias.

### 4.1 Formas de pesquisa

A pesquisa poderá ser realizada por:
- Praia
- Bairro
- Cidade
- Posto de coleta

### 4.2 Filtros de pesquisa

- Balneabilidade
- Ondas
- Condições climáticas
- Distância

---

## 5. Detalhes sobre a praia

Tela com informações detalhadas sobre uma praia ou ponto selecionado.

### Informações

- Data da última checagem
- Condições do mar
- Vento
- Clima do dia
- Previsão dos próximos períodos/dias
- Chuva
- Temperatura

---

## 6. Previsão da praia

Tela dedicada à apresentação da previsão das condições da praia.

Deve apresentar informações relevantes para auxiliar o usuário na avaliação das condições previstas.

---

## 7. Comparação entre praias

Tela que permite comparar diferentes praias.

### Critérios de comparação

- Condições da água
- Clima
- Ondas
- Deslocamento

O objetivo é permitir que o usuário avalie diferentes opções antes de decidir qual praia frequentar.

---

## 8. Praias favoritas

Tela destinada às praias salvas pelo usuário.

### Funcionalidade

- Adicionar praia aos favoritos
- Remover praia dos favoritos
- Consultar rapidamente as condições das praias favoritas

> **Observação:** é necessário adicionar a função de gerenciamento de praias favoritas ao sistema.

---

## 9. Alertas

Tela para configuração e consulta de alertas relacionados às praias.

### Tipos de alerta

- Avisar quando uma praia ficar imprópria
- Avisar após chuva intensa
- Avisos importantes

---

## 10. Perfil do usuário

Tela com informações pessoais, preferências e configurações do usuário.

### Informações

- Nome
- Cidade/Estado
- Praias favoritas
- Alertas
- Preferências de condições da praia

### 10.1 Localização

Opções:
- Usar localização do celular
- Definir localização padrão

### 10.2 Segurança

Área destinada às configurações relacionadas à segurança da conta.

### 10.3 Configurações do aplicativo

Área destinada às configurações gerais do aplicativo.

### 10.4 Sobre o aplicativo

Informações:
- Fontes dos dados
- Versão do aplicativo

---

## 11. FAQ

Tela de perguntas frequentes.

Deve concentrar informações para auxiliar o usuário na utilização do aplicativo e na compreensão das informações apresentadas.

---

## 12. Tela de erro

Tela ou estados de erro apresentados quando o aplicativo não consegue concluir uma operação.

### Situações previstas

- Não foi possível encontrar os dados solicitados
- Erro de comunicação com o aplicativo/servidor
- Problemas de conexão com a internet

A mensagem apresentada deve informar o problema de forma clara e, quando possível, oferecer uma ação para tentar novamente.

---

# Resumo das telas

| Nº | Tela | Prioridade inicial |
|---:|---|---|
| 1 | Splash Screen | Média |
| 2 | Homepage / Login | Alta |
| 2.1 | Login | Alta |
| 2.2 | Criar conta | Alta |
| 2.3 | Questionário rápido | Alta |
| 3 | Tela principal / Mapa | **Essencial** |
| 4 | Pesquisa de praias | **Essencial** |
| 5 | Detalhes sobre a praia | **Essencial** |
| 6 | Previsão da praia | Alta |
| 7 | Comparação entre praias | Média |
| 8 | Praias favoritas | Média |
| 9 | Alertas | Média |
| 10 | Perfil do usuário | Alta |
| 11 | FAQ | Baixa |
| 12 | Tela de erro | **Essencial** |

## Fluxo principal esperado

O fluxo principal do aplicativo deverá priorizar a descoberta e avaliação de praias:

**Acesso → Localização/preferências → Mapa → Pesquisa/Filtros → Detalhes da praia → Previsão**

Fluxos secundários:

**Mapa → Favoritos → Detalhes**

**Mapa → Comparação → Escolha da praia**

**Perfil → Preferências → Alertas**

**Perfil → Configurações / Segurança / Sobre**

