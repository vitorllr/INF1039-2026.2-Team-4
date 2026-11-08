# Demonstração de usabilidade: Pedro em Ipanema

## Persona e objetivo

Pedro tem 23 anos e quer escolher onde entrar no mar em Ipanema.
Ele não quer comparar apenas praias diferentes.
Ele quer entender como as condições mudam entre os postos da mesma praia e tomar uma decisão com confiança.

## Roteiro gravado

1. Pedro abre o mapa com o perfil “Banho tranquilo”.
2. Ele entende que o vídeo usa dados determinísticos porque o modo de demonstração está visível.
3. Ele abre o Posto 8 e lê altura da onda, vento, temperatura da água e chuva acumulada.
4. Ele lê os motivos da recomendação e confere a origem e a idade dos dados.
5. Ele abre a comparação lado a lado.
6. Ele vê que o Posto 10 não tem boletim, o Posto 11 não tem vento e o Posto 7 tem boletim vencido.
7. Ele testa o perfil “Surf iniciante” e observa a mudança de ordem sem remover os bloqueios de segurança.
8. Ele volta para “Banho tranquilo” e escolhe o Posto 8.

Não existe carregamento assíncrono no fluxo atual porque as páginas são renderizadas no servidor.
Por isso, o vídeo não inventa um estado de carregamento que o produto não possui.
Os estados de erro, ausência, vencimento e incompletude aparecem na comparação real.

## Reprodução

```bash
ffplay artifacts/bluetide-pedro-demo.mp4
```

O arquivo tem resolução de 1280 por 720 pixels, usa H.264 e não contém credenciais nem dados pessoais reais.

## Regeneração

```bash
BLUETIDE_DATA_MODE=fixture python manage.py runserver 127.0.0.1:8765
pip install -r requirements-demo.txt
python -m playwright install ffmpeg
python scripts/record_demo.py
```
