---
id: network-partition-quorum-models
title: "Modelos de partições de rede: verificação exaustiva de quoruns"
description: "Enumere grafos de conectividade de três e cinco nós, demonstre exclusividade de maioria e delimite falhas ainda não testadas."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [raft-consensus, rabbitmq-quorum-majority-loss]
sources:
  - {title: "RabbitMQ — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official broker documentation"}
  - {title: "RabbitMQ — Network Partitions", url: "https://www.rabbitmq.com/docs/partitions", kind: "official broker documentation"}
  - {title: "Patroni — Distributed Coordination Store", url: "https://patroni.readthedocs.io/en/latest/modules/patroni.dcs.html", kind: "official HA project documentation"}
---
Interromper um nó e particionar uma rede são experimentos diferentes. Um servidor pode permanecer ligado, executar PostgreSQL ou RabbitMQ e atender alguns clientes enquanto **não consegue falar com os demais membros**. Por isso “o servidor está executando” não basta para inferir disponibilidade de consenso. Esta oficina constrói um modelo executável de **conectividade não direcionada**, enumera todas as topologias estáticas possíveis para três e cinco membros e valida um invariante: **no máximo um componente desconectado pode conter maioria estrita** [1][2].

## Modelo de falha e limites intencionais

Represente n membros votantes por vértices de grafo não direcionado. Uma aresta entre A e B indica comunicação **bidirecional** no instante modelado. Um componente conexo reúne nós com caminho de comunicação entre si. O componente é *elegível a maioria* quando possui mais de n/2 membros.

![Três partições: maioria sobrevivente, ausência de maioria e conectividade restaurada.](/diagrams/network-partition-quorum.svg)

É abstração **estática e simétrica da rede**. Não simula reordenação de pacotes, firewalls assimétricos, atrasos, timeouts de eleição, alterações dinâmicas de membros, posições diferentes do WAL/log nem bugs de split brain. Um grafo conexo é condição **estrutural necessária** para participar de quorum, não prova de que líder Raft foi eleito ou mensagem confirmada [1].

## Enumere todas as topologias pequenas

O código [network_partition_quorum.py](https://github.com/christianrss/manual/blob/main/examples/python/network_partition_quorum.py) gera pares de nós com \`itertools.combinations\`. Para n membros, há n(n−1)/2 pares de conectividade, criando **2^(n(n−1)/2)** configurações possíveis com arestas presentes ou ausentes.

Com três nós são oito grafos; com cinco, **1.024 grafos**. Em cada um, busca em profundidade identifica componentes e o código conta grupos com tamanho pelo menos floor(n/2)+1. Os testes executam toda a enumeração no CI. Exaustivo aqui significa **todos os grafos desse modelo pequeno**, não toda falha de rede real.

## Demonstre a interseção das maiorias

Uma maioria estrita tem mais de n/2 membros. Dois conjuntos disjuntos contendo maioria somariam mais de n membros, o que é impossível. Portanto, **dois componentes desconectados não podem simultaneamente ser maioria do mesmo conjunto fixo de votantes**. Essa é prova matemática curta; enumerar grafos serve de teste de regressão da implementação do modelo, não substitui a prova.

~~~python
def limiar_maioria(votantes):
    if votantes < 1:
        raise ValueError("total positivo necessario")
    return votantes // 2 + 1

def dois_grupos_disjuntos_podem_ter_maioria(votantes):
    minimo=limiar_maioria(votantes)
    return 2 * minimo <= votantes

assert limiar_maioria(3)==2
assert limiar_maioria(5)==3
assert not dois_grupos_disjuntos_podem_ter_maioria(3)
assert not dois_grupos_disjuntos_podem_ter_maioria(5)
~~~

A demonstração presume **configuração única de membros aceita por todos**. Alterar membership não é só trocar um número no arquivo de configuração; sistemas de consenso exigem transições seguras que preservam interseção entre configurações.

## Analise a partição de três nós

Considere A, B e C. Se A fica isolado, mas B e C se comunicam, B+C constitui maioria. O lado A não pode confirmar uma nova escrita de fila quorum com segurança só porque seu broker responde TCP ou AMQP. No [laboratório real de perda de maioria](/pt/topics/rabbitmq-quorum-majority-loss/), a minoria de um nó é avaliada separadamente com publisher confirms verdadeiros do RabbitMQ.

Se todas as ligações se rompem, restam três grupos de um nó. Nenhum tem maioria. A disponibilidade de escrita pode acabar mesmo com **todos os três processos vivos**. Uptime e conexão TCP bem-sucedida não demonstram capacidade de aceitar gravações com segurança.

## Analise partições de cinco membros

Com cinco votantes, limiar é três. Divisão 2+3 produz **uma maioria elegível**. Divisão 2+2+1 não tem nenhuma. Divisão 4+1 novamente tem uma. O teste de grafo verifica essas diferenças explicitamente, sem presumir que remover igual número de links gera necessariamente mesma disponibilidade.

Mesmo alcançando maioria, o sistema pode precisar eleger líder, recusar operações durante eleição ou enfrentar backpressure e disco lento. Conectividade não garante desempenho. A ausência de progresso da minoria é consequência deliberada do compromisso **segurança versus disponibilidade**, não necessariamente defeito de software.

## Relacione modelo a RabbitMQ e PostgreSQL

Filas quorum RabbitMQ possuem membership de réplicas por fila e eleição de líder derivada de Raft [1]. Um cluster pode ter três brokers ativos enquanto determinada fila tem outra composição ou maioria indisponível. É necessário testar **a composição real da fila**, não contar somente containers RabbitMQ.

Replicação física PostgreSQL **não forma automaticamente um quorum Raft**. Primário assíncrono e standby podem continuar vivos diante de partição; sem coordenação externa e fencing, replicação física não impede que os dois se tornem escritores. Armazenamento distribuído de configuração, lease e fencing podem prover autoridade, mas possuem próprias regras de maioria e expiração [2][3].

## Matriz de injeções de falha para próximos testes

| Injeção | Pergunta a responder | Evidência |
| --- | --- | --- |
| Parar um broker | Maioria continua publicando? | Teste Docker quorum |
| Parar dois brokers | Minoria deixa de confirmar escrita? | Teste Docker de maioria |
| Isolar broker por rede mantendo processo vivo | Que lado possui maioria? | **Ainda não integrado** |
| Cortar todos os links | Escritas param de modo seguro? | Apenas modelo de grafos |
| Particionar primário PostgreSQL do controlador | Primário antigo segue gravando? | Exige fencing externo |
| Restaurar ligações | Réplicas recuperam com segurança? | Novo teste necessário |

Uma experiência de caos séria deve isolar **planos de dados e controle conscientemente**, preservar acesso administrativo independente, operar em cluster descartável e registrar líder, termo, replicação, ACKs, erros e latência. Alterar firewall sem observar estado da fila ou autoridade de escrita não comprova segurança.

## Complexidade dos testes exaustivos

Enumerar cada estado de link custa tempo **exponencial no número de arestas possíveis**: com n=7 seriam 2^21 grafos, mais de dois milhões. Portanto o CI limita busca completa a três e cinco membros. Sistemas maiores exigem amostragem baseada em propriedades, model checking limitado e cenários de falha escolhidos.

O teste valida invariante do grafo e código de enumeração. Não verifica algoritmo interno de consenso RabbitMQ, replicação PostgreSQL, regras reais de firewall nem recuperação completa da aplicação. Esses limites precisam constar no relatório técnico.

## Exercícios e verificação

1. Liste divisões possíveis dos cinco membros em componentes e identifique as que possuem maioria.
2. Por que broker pode aceitar conexão TCP mesmo quando fila quorum não consegue confirmar mensagem nova?
3. Adapte o modelo a links direcionados/assimétricos e explique por que componentes não direcionados deixam de bastar.
4. Planeje partição de rede reproduzível no Docker mantendo brokers vivos e conferindo publisher confirms reais.
5. Por que interseção de quorum não impede split brain no primário/standby PostgreSQL sem fencing?

**Capítulos relacionados:** [Consenso Raft](/pt/topics/raft-consensus/), [perda de maioria RabbitMQ](/pt/topics/rabbitmq-quorum-majority-loss/), [fencing PostgreSQL](/pt/topics/postgresql-failover-fencing-gates/) e [observabilidade distribuída](/pt/topics/distributed-observability/) apresentam abordagens complementares [1][2][3].
