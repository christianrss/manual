---
id: usage-metering-system-design-assessment
title: "Avaliação Independente de System Design: Medição de Uso, Eventos Atrasados e Reconciliação"
description: "Projete um registro de uso isolado por cliente com dimensionamento verificável, reprocessamento idempotente, ajustes tardios, testes de falha e revisão auditável."
category: interview-practice
difficulty: advanced
updated: 2026-10-11
prerequisites: [capacity-estimation, system-design-process, asynchronous-messaging, database-consistency, data-partitioning-sharding]
sources:
  - {title: "Apache Beam — Programming Guide: Watermarks and Late Data", url: "https://beam.apache.org/documentation/programming-guide/", kind: "official distributed processing documentation"}
  - {title: "AWS Builders' Library — Making Retries Safe with Idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
  - {title: "Google SRE Book — Monitoring Distributed Systems", url: "https://sre.google/sre-book/monitoring-distributed-systems/", kind: "original engineering reference"}
---
Uma avaliação de arquitetura não pode ser resolvida simplesmente enumerando serviços gerenciados. É preciso **deduzir contratos a partir de requisitos incompletos**, dimensionar hipóteses, estabelecer quem tem autoridade para decisões financeiras e explicar o que muda diante de falhas. A [avaliação de processamento de documentos](/pt/topics/adaptive-system-design-assessment/) já aborda filas, justiça entre clientes e armazenamento regional; a [revisão de checkout](/pt/topics/system-design-architecture-review/) discute estoque e pagamento. Este caso é diferente: **medir consumo para produzir faturas auditáveis a partir de eventos atrasados, repetidos e vinculados a clientes distintos**.

O exercício é fictício e foi elaborado para o manual. Não reproduz questões oficiais ou vazadas de seleção. As hipóteses numéricas e os critérios de revisão são públicos; não há corretor secreto, banco real ou entrevista supervisionada. O estudante deve produzir e defender a arquitetura, em vez de copiar um diagrama fornecido.

## Enunciado inicial: requisitos propositalmente incompletos

Uma plataforma SaaS cobra clientes pelo consumo de uma API. Diversos produtores enviam registros de utilização, e cada cliente consulta totais diários num painel antes do fechamento da fatura mensal. Projete o ponto de entrada, o processamento, a consolidação, a entrega para faturamento, a consulta e a observabilidade. A primeira descrição de produto diz apenas: “a soma deve estar correta, aparecer logo no painel e não cobrar duas vezes após uma tentativa repetida”.

Isso **não constitui um contrato técnico**. Antes de escolher SQL, filas, logs distribuídos ou cache, pergunte qual relógio determina o período de cobrança, o que representa uma unidade faturável, se uma fatura fechada aceita ajustes, qual resposta comprova recebimento durável, quantas horas de atraso são permitidas e de onde vem a identidade confiável do cliente. Diferencie também a perda de um evento diagnóstico da perda de uma unidade faturável: os requisitos de durabilidade podem ser distintos, e isso deve aparecer no projeto.

Defina os termos. **Tempo do evento** é o instante em que o consumo supostamente aconteceu. **Tempo de processamento** é quando o servidor recebeu ou tratou o registro. **Fechamento da fatura** é uma transição de estado de negócio. Um evento que chega hoje com timestamp de três dias atrás não pertence automaticamente ao consumo de hoje. Um *watermark* de uma engine de streaming representa uma estimativa de progresso temporal, não a garantia incondicional de que nunca chegarão eventos antigos [1].

## Especificar interfaces e autoridade antes de desenhar componentes

Considere uma estrutura versionada como `(tenant_id, source_id, event_id, event_time, unit_type, quantity, schema_version)`. Ela é apenas um ponto de partida: decida como o servidor obtém a identidade autenticada do cliente e da origem, quais quantidades são válidas, qual diferença temporal do relógio é aceitável e se uma correção deve criar outro evento auditável ou modificar um existente. Determine quais campos identificam uma operação repetida e como lidar com **o mesmo ID acompanhado de conteúdo diferente**.

Uma requisição pode expirar após ser gravada. Repeti-la com **outro ID** pode cobrar duas vezes o mesmo consumo; tratar todo payload idêntico como repetição também pode eliminar dois consumos legítimos e independentes. A intenção do cliente precisa de identificador estável, escopo definido e política de conflitos. A AWS Builders' Library discute por que tentativas repetidas e requisições atrasadas exigem semântica explícita de idempotência [2].

Explique o significado de HTTP `202 Accepted`. Se o serviço responde sucesso antes de uma gravação durável, um crash pode causar perda silenciosa de consumo faturável. Se aguarda a disponibilidade de outra infraestrutura para responder, a ingestão fica acoplada a essa dependência. Nenhuma escolha é automaticamente correta; ambas exigem políticas de falha, reconciliação dos ACKs e registro de decisões.

## Carga inicial: cálculos com unidades explícitas

Use o [arquivo de cenários](https://github.com/christianrss/manual/blob/main/examples/system-design/usage_metering_scenario.json), com valores **hipotéticos**: **2.400.000 eventos novos por dia**, **2.048 bytes lógicos por evento**, pico de **40 vezes a média**, **28 dias** de retenção bruta, processamento medido hipoteticamente em **250 eventos/segundo por worker**, utilização planejada em **60%**, e tolerância à perda de **uma réplica de processamento**.

A média é `2.400.000 / 86.400 ≈ 27,78 eventos/s`. A projeção inteira do pico é `ceil(27,78 × 40) = 1.112 eventos/s`. O volume lógico em retenção é `2.400.000 × 2.048 × 28 = 137.625.600.000 bytes`, aproximadamente `128,17 GiB` com `1 GiB = 1.073.741.824 bytes`. Não inclui réplicas, índices, WAL, backups, compressão, dead letters nem tentativas repetidas; não equivale a uma estimativa de custo em nuvem.

A 60% da vazão supostamente medida de 250 eventos/s, cada worker terá capacidade planejada de 150 eventos/s. `ceil(1112/150)=8` réplicas saudáveis atendem ao pico idealizado. Reservar mais uma, sob a hipótese simplificada de réplicas independentes e equivalentes, dá **9** para tolerar uma indisponibilidade. Não é uma recomendação de autoscaling: um banco compartilhado insuficiente, uma partição quente, bursts muito curtos ou latências extremas podem impedir o escalonamento linear.

O código abaixo utiliza apenas **aritmética de planejamento**, sem implementar ingestão, banco ou geração de faturas:

~~~python
from examples.python.usage_metering_design_math import (
    peak_ingest_rate, raw_retained_bytes, outage_backlog,
    drain_seconds, ideal_worker_replicas, BYTES_PER_GIB,
)
assert peak_ingest_rate(2_400_000, 40) == 1112
assert raw_retained_bytes(2_400_000, 2048, 28) == 137625600000
assert ideal_worker_replicas(1112, 250, 60, 1) == 9
assert outage_backlog(1200, 600) == 720000
assert drain_seconds(720000, 1200, 1800) == 1200
assert 128 < raw_retained_bytes(2_400_000, 2048, 28) / BYTES_PER_GIB < 129
~~~

As divisões com arredondamento para cima são feitas em **aritmética inteira**, evitando perdas de precisão por ponto flutuante em números grandes. Confirmar os resultados matemáticos não comprova que uma infraestrutura real entregue a vazão modelada.

## Falha de processamento: pico e recuperação não são a mesma carga

Outro cenário assume **1.200 eventos/s constantes**, durante **600 segundos sem processamento**. Essa carga é um novo parâmetro do incidente e **não foi derivada** do pico anterior de 1.112 eventos/s; a divergência é deliberada para questionar o dimensionamento inicial. Sem backlog prévio, surgem `1.200 × 600 = 720.000` eventos pendentes.

Após a restauração, suponha que a cadeia completa de processamento sustente **1.800 eventos/s**, enquanto ainda chegam 1.200/s. A margem de drenagem é só 600/s. O tempo idealizado para eliminar a fila acumulada é `720.000/600=1.200 segundos=20 minutos`, pressupondo taxas constantes, ausência de tentativas extras e eventos que não bloqueiem workers. Se a capacidade restaurada for somente **1.000 eventos/s**, a fila cresce; afirmar uma duração finita para esvaziá-la viola a matemática.

Mesmo a existência de margem positiva não prova uma latência máxima por evento. Monitore idade do trabalho mais antigo, tempo desde ACK até consolidação, atraso de consumidores, dead letters e saúde do armazenamento autoritativo. O livro de SRE do Google discute medições ligadas ao funcionamento percebido do serviço, não apenas o consumo de CPU [3].

## Novas restrições: atraso, conflitos, cliente dominante e ajuste financeiro

O avaliador acrescenta quatro restrições: **5% dos eventos podem chegar com 72 horas de atraso**; produtores reenviam IDs, às vezes com payload conflitante; um único cliente concentra **70% da entrada** durante meia hora; e ajustes verificados podem afetar períodos **já faturados**. Cada cenário invalida uma hipótese anterior sobre completude, identidade, justiça na distribuição da carga ou imutabilidade.

Especifique quando a consulta diária é *provisória* e quando a fatura é *final*. Um período de atraso aceito pelo streaming não é necessariamente igual à política financeira de correções depois do fechamento. Se uma fatura puder ser alterada silenciosamente após ser apresentada ao cliente, perde-se rastreabilidade. Se eventos tardios forem descartados automaticamente após o avanço do watermark, consumo legítimo poderá não ser contabilizado. Uma opção justificável é guardar os eventos originais e lançar ajustes vinculados a versões de faturas, mas a avaliação exige comparar alternativas, incluindo quem possui permissão para aprovar essas alterações.

Uma partição compartilhada ou mal dimensionada pode concentrar o cliente de maior volume e degradar os demais. Dividir o mesmo cliente em muitas partições, por outro lado, pode tornar mais difícil manter certas ordenações e consolidar resultados exatamente uma vez na autoridade escolhida. Declare onde são necessárias transações e onde projeções eventualmente consistentes são aceitáveis. Escrever “Kafka, Redis e microsserviços” não responde a esses problemas.

## Dados, segurança e alternativas com consequências

Elabore um modelo que diferencie **registro autoritativo dos eventos aceitos**, controle de deduplicação ou reprocessamento equivalente, agregações provisórias e decisões financeiras imutáveis ou versionadas. Se o broker confirma uma operação antes de ela existir no armazenamento durável, identifique a janela de perda possível e o mecanismo de recuperação. Se dois recursos independentes precisam ser modificados, explique por que o sucesso de um não significa commit atômico dos dois. Outbox transacional, um log único autoritativo ou outra estratégia argumentada são opções, mas cada uma impõe limites específicos [2].

Mostre onde a identidade do cliente é autenticada, onde cada consulta valida autorização e como exportações de dados respeitam a mesma fronteira. Um cache de painel não pode ser a autoridade financeira. Se o mesmo `event_id` for legítimo em dois clientes ou origens, deduplicar apenas por esse ID pode eliminar cobranças independentes. O tempo de retenção dos identificadores deve corresponder à garantia de replay prometida; quando o prazo expira, a reconciliação precisa adotar outra política explícita.

Compare pelo menos duas arquiteturas plausíveis considerando custo operacional, recuperação, reprocessamento, volume de dados, atualização do painel e exatidão financeira. Identifique o que precisa ser medido: distribuição de tempo de CPU por evento, pico real por cliente, tamanhos reais, limite do banco sob carga, distribuição de atrasos e quantidade de correções. Os valores fictícios não permitem declarar um fornecedor ou serviço como universalmente superior.

## Critérios de revisão e evidências verificáveis

Utilize o [modelo de entrega](https://github.com/christianrss/manual/blob/main/examples/system-design/usage_metering_submission_template.md). Sua **rubrica didática de 100 pontos** reserva 10 para esclarecimento de requisitos, 15 para contratos e autoridade, 20 para invariantes e consistência, 15 para dimensionamento, 20 para falhas, 10 para alternativas e 10 para testes e comunicação. Há também condições eliminatórias: acesso entre clientes, fatura baseada apenas em cache, alteração silenciosa de fatura fechada, confusão entre os dois relógios e promessa de drenar filas sem capacidade excedente.

A pontuação depende de revisão humana; o repositório não possui avaliador automático de arquitetura. A entrega precisa conter um registro de decisão, arquitetura escolhida, alternativas descartadas, hipóteses, falhas, medidas operacionais e condições de reversão. Inclua **pelo menos dois testes de corrida**, como ingestão concorrente do mesmo ID e ajuste simultâneo ao fechamento de fatura, cada um com critério observável de aprovação. O diagrama sozinho não é evidência suficiente.

## Exercícios e verificação

1. **Novo dimensionamento:** se cada worker processa 180 eventos/s com a mesma utilização de 60%, quantas réplicas equivalentes são necessárias para atender ao pico e tolerar uma falha? *Verificação:* 108 eventos/s planejados por réplica; `ceil(1112/108)+1=12`.
2. **Incidente:** com chegada de 1.200 eventos/s e capacidade restaurada de 1.000/s, por que não existe um prazo finito para eliminar a fila? *Verificação:* o backlog aumenta 200 eventos por segundo nas hipóteses dadas.
3. **Identidade:** envie o mesmo ID a partir de dois clientes e, depois, reenvie um ID da mesma origem com quantidade alterada. Qual é o resultado correto em cada caso e onde o registro autoritativo da identidade fica persistido?
4. **Atraso:** um consumo verdadeiro chega após o fechamento. O que deve ser ajustado, o que não pode ser sobrescrito e como uma auditoria reconstrói a decisão?
5. **Injeção de falha:** o broker entrega de novo um evento depois do commit no ledger e antes do ACK do consumidor. Qual invariante deve permanecer verdadeira e que evidência no banco ou no log a demonstra?
6. **Limite de deduplicação:** um replay de um dia inteiro chega após a expiração dos registros de IDs. Por que a alegação anterior de processamento único deixa de ser sustentada? Defina uma nova fronteira de recuperação.

O módulo público verifica **apenas as grandezas aritméticas**. A correção de um sistema de faturamento exige autenticação, fronteiras transacionais, decisões duráveis, políticas financeiras definidas e testes empíricos que não são fornecidos por essas simulações.
