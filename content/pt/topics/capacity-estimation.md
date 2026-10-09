---
id: capacity-estimation
title: Estimativas de capacidade e restrições de sistemas
description: Derive estimativas de tráfego, armazenamento, utilização e capacidade de pico com hipóteses explícitas, sem confundir médias com garantias.
category: system-design
difficulty: intermediate
updated: 2026-10-09
prerequisites:
- complexity-analysis
sources:
- title: Google SRE Book — Handling Overload
  url: https://sre.google/sre-book/handling-overload/
  kind: engineering book
- title: Google SRE Workbook — Implementing SLOs
  url: https://sre.google/workbook/implementing-slos/
  kind: engineering workbook
---
Antes de desenhar microsserviços ou escolher banco de dados, traduza requisitos em grandezas: usuários ativos, leituras e escritas por segundo, volume por objeto, retenção, picos e latência admissível. Uma estimativa útil não pretende adivinhar a produção; sua função é revelar ordens de grandeza e pontos onde decisões arquiteturais mudam [1].

## Definir carga, unidade e período
`RPS` significa requisições por segundo. Se um sistema recebe `N` requisições por dia, sua média é `N/86.400`, mas o pico pode ser várias vezes maior. Separe requisições de usuário das chamadas internas: uma única operação pode disparar três consultas e duas mensagens. Separar leitura e escrita também importa, porque seus custos e possibilidades de cache diferem. O livro de SRE do Google discute a proteção contra sobrecarga e a importância de limites explícitos para absorver demanda [1]. O SRE Workbook relaciona a operação a SLOs mensuráveis [2].

## Cenário resolvido
Admita, hipoteticamente, dez milhões de requisições diárias, um fator de pico igual a seis e tamanho médio de resposta de 4 KiB. A média é cerca de `116 req/s`; o pico estimado é `694 req/s`. A largura de banda de saída nesse pico é aproximadamente `694 × 4096 ≈ 2,84 MB/s` antes dos cabeçalhos, retransmissões e outros protocolos. Esses valores dependem **integralmente** das hipóteses.

Se cada servidor consegue processar 200 req/s em carga sustentada medida e a política admite usar no máximo 60% dessa capacidade nominal, o orçamento por servidor é 120 req/s. Para 694 req/s, seriam necessários ao menos `ceil(694/120)=6` servidores, antes da reserva para falhas, crescimento e balanceamento irregular. O número não prova disponibilidade: regiões, domínio de falha e autocorreção precisam ser tratados separadamente.

## Estimar armazenamento e fila
Com 100 mil objetos novos por dia de tamanho médio 2 KiB, dados brutos anuais totalizam aproximadamente `100000 × 2048 × 365 ≈ 74,8 GB` em unidades decimais. Índices, réplicas, versões, backups, logs e fragmentação aumentam esse valor. Não some tudo sem distinguir armazenamento primário de cópias derivadas.

Quando taxa de chegada `λ` se aproxima da taxa de serviço `μ`, o tempo de espera pode aumentar dramaticamente. Uma fila não resolve por si só a falta de capacidade: se entradas chegam permanentemente mais rápido do que podem ser processadas, o backlog cresce sem limite [2]. Monitore ocupação, latência percentual, erros e taxa de crescimento da fila.

## Hipóteses e erros comuns
Não confunda requisições com usuários, bytes com bits ou megabytes decimais com mebibytes binários. Um cache pode reduzir leituras ao banco, mas uma falha simultânea em cache e backend invalida médias anteriores. Repita os cálculos para cenários de pico, falha de instância e carga desbalanceada.

## Exercícios e verificação
1. Para 8,64 milhões de requisições/dia, a média é 100 req/s. Com pico 5×, projete 500 req/s.
2. Se cada worker sustenta 80 operações/s e chegadas persistentes são 100/s, o atraso cresce; identifique o mecanismo de rejeição ou ampliação de capacidade.
3. Compare resultados ao alterar o fator de pico e documente quais decisões permanecem estáveis. Uma estimativa só é útil quando seus pressupostos estão visíveis.
