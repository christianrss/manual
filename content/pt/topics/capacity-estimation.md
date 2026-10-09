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

## Modelo de capacidade com unidades e curva de saturação

A conta `instâncias=ceil(RPS_pico / RPS_testado_por_instância)` só tem sentido quando o denominador foi medido no objetivo de latência e erro exigido. Um benchmark de **vazão máxima** a 100% de CPU não constitui capacidade segura de operação. A carga depende da mistura de requisições, payload, localidade de dados, reutilização de conexões, tarefas em segundo plano e saturação de dependências. Para cada hipótese, registre uma faixa plausível e refaça a conta com valores pessimistas [1].

Separe **taxa de chegada** `λ` (tarefas/s), **taxa de serviço** `μ` (tarefas/s por trabalhador) e **concorrência** `L` (tarefas no sistema). A lei de Little `L=λW` vale para sistema estável e fronteiras de observação coerentes; não prevê sozinha a distribuição de latência. Numa fila idealizada M/M/1 com chegadas Poisson e serviços exponenciais, o tempo médio no sistema é `W=1/(μ−λ)` para `λ<μ`; isso é um *modelo*, não uma fórmula geral de produção. Quando `λ` se aproxima de `μ`, a espera cresce sem limite. Serviços reais com rajadas ou múltiplos recursos podem se comportar diferentemente.

## Redundância e orçamento de falhas

Considere pico de 2.400 RPS e servidor capaz de 600 RPS na latência pretendida e mistura de carga testada. Para operar a 60% desse limite, planeje `600×0,60=360` RPS por nó. `ceil(2400/360)=7` nós saudáveis cobrem o pico modelado. Para suportar falha de um nó mantendo o objetivo, provisione 8. É um *cenário*: se o banco não fornece 2.400 RPS, adicionar réplicas da aplicação não resolve o sistema completo.

Um SLO mensal de disponibilidade de 99,9% corresponde a aproximadamente 43,2 minutos de indisponibilidade permitida em 30 dias, quando a medida é proporção de tempo. Mas um SLO baseado em requisições conta erros por requisição; traduzir diretamente para minutos pode ser inadequado [2]. Declare o indicador e o critério de erro.

## Armazenamento, rede e retenção

Para `N` registros novos/dia, tamanho médio lógico `S` bytes e retenção de `D` dias, armazenamento lógico bruto ativo é `N×S×D`, sem exclusões nem compressão. Demanda física inclui índices, réplicas, logs transacionais, backups, sistema de arquivos e margem de segurança. Em rede, distinga MB decimal de MiB binário e payload de bytes transmitidos ou comprimidos. Sistemas com muitas leituras podem saturar banda antes da CPU.

| Incerteza | Medição necessária |
| --- | --- |
| Relação pico/média | Tráfego por período, região e endpoint |
| Capacidade por instância | Teste de carga com dependências representativas |
| Taxa de acerto do cache | Comparação entre cache frio e aquecido |
| Mistura de operações | Custo por rota e classe de usuário |
| Margem de recuperação | Derrubar uma réplica sob carga e observar p99 |

## Experimentos e registro de decisão

Execute testes de regime, rajada, partida a frio e falha de instância. Declare carga oferecida, vazão bem-sucedida, p95/p99, erros, CPU, memória, filas e condições das dependências. Se a carga oferecida cresce mas a vazão **concluída** deixa de aumentar, o excesso precisa ser rejeitado ou acumular em fila; contar apenas requisições aceitas disfarça a sobrecarga. Documente quando o controle de admissão passa a ser obrigatório [1].

**Verificação:** depois da falha de uma réplica, dimensione com as réplicas *restantes*. Se a taxa de acerto do cache normalmente é 95%, estime a carga na origem caso ela caia para zero; resiliência depende desse pico, não apenas da média.

## Exercícios e verificação
1. Para 8,64 milhões de requisições/dia, a média é 100 req/s. Com pico 5×, projete 500 req/s.
2. Se cada worker sustenta 80 operações/s e chegadas persistentes são 100/s, o atraso cresce; identifique o mecanismo de rejeição ou ampliação de capacidade.
3. Compare resultados ao alterar o fator de pico e documente quais decisões permanecem estáveis. Uma estimativa só é útil quando seus pressupostos estão visíveis.
