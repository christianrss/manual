---
id: rabbitmq-durable-consumer-integration
title: "Laboratório RabbitMQ: redelivery e inbox transacional"
description: "Teste desconexão de consumidor RabbitMQ real, mensagens reenviadas e deduplicação em inbox PostgreSQL com ACK manual."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [failure-recovery-workshop, postgresql-concurrency-integration, asynchronous-messaging]
sources:
  - {title: "RabbitMQ — Consumer Acknowledgements and Publisher Confirms", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
  - {title: "RabbitMQ — Work Queues", url: "https://www.rabbitmq.com/tutorials/tutorial-two-python", kind: "official broker tutorial"}
  - {title: "PostgreSQL — INSERT ON CONFLICT", url: "https://www.postgresql.org/docs/current/sql-insert.html", kind: "official database documentation"}
---
Um evento pode chegar **mais de uma vez** mesmo quando produtor e broker estão corretos. Consumidor confirma efeito no banco, perde a conexão e desaparece antes de enviar ACK. RabbitMQ pode então reenfileirar a mensagem não confirmada e entregá-la a outro consumidor. A pergunta correta não é “Como tornar fila exactly once?”, mas “Onde tornar o efeito de negócio idempotente?”. Esta oficina testa **RabbitMQ real com inbox PostgreSQL** no GitHub Actions [1][2].

## Separe aceite, entrega e processamento

A requisição do produtor, o aceite pelo broker, o recebimento pelo consumidor, o commit no banco e o acknowledgment do consumidor são cinco acontecimentos distintos. RabbitMQ diferencia **publisher confirms**, que indicam aceite da publicação no broker, e **consumer acknowledgments**, que indicam que a entrega pode ser removida. Um mecanismo não substitui o outro [1].

No exercício, cada mensagem carrega event ID estável e um efeito lógico: registrar um evento processado. Exigimos **no máximo um efeito confirmado por event ID** na autoridade de banco. Permitimos repetição de entregas quando consumidor falha antes de confirmar recebimento. Não afirmamos exatamente uma execução num PSP externo independente.

## O que o teste integrado realmente executa

O workflow inicia RabbitMQ 4 management e PostgreSQL 17 em containers Linux. O teste Python conecta via `pika` ao AMQP porta 5672, declara fila durável com nome único, habilita publisher confirms e publica uma mensagem persistente com `message_id` estável. Recebe entrega com `basic_get(auto_ack=False)`, grava event ID numa tabela PostgreSQL e fecha conexão **sem enviar ACK**.

![RabbitMQ reenfileira mensagem sem ACK; inbox PostgreSQL bloqueia efeitos duplicados.](/diagrams/rabbitmq-redelivery-inbox.svg)

Uma segunda conexão obtém a mensagem reenfileirada, compara corpo e identidade e observa flag de redelivery do RabbitMQ. Tenta aplicar novamente efeito no PostgreSQL, mas chave primária por event ID impede duplicação. O segundo consumidor confirma ACK e o teste verifica **um efeito, não dois**.

A fonte executável é [tests/test_rabbitmq_postgres_integration.py](https://github.com/christianrss/manual/blob/main/tests/test_rabbitmq_postgres_integration.py), incluída na descoberta de testes comum. É comunicação de rede com broker e constraint real de banco, não stub devolvendo resposta conveniente.

## Inbox atômica e deduplicação

O receptor mantém `inbox(event_id PRIMARY KEY, effects)`. Uma transação tenta `INSERT ... ON CONFLICT(event_id) DO NOTHING RETURNING event_id`. Quando retorna linha, evento ainda não foi gravado e a transação pode confirmar efeito local. Quando existe chave igual, o consumidor reconhece que já confirmou o evento e **não deve repetir efeito** [3].

~~~sql
INSERT INTO inbox(event_id, effects)
VALUES ($1, 1)
ON CONFLICT(event_id) DO NOTHING
RETURNING event_id;
~~~

Neste exemplo restrito, inserir linha **é** o efeito de negócio. Num saldo bancário real, o marcador inbox e alteração de saldo devem confirmar **na mesma transação PostgreSQL**. Persistir marcador antes e transferir depois cria janela na qual marcador diz “concluído”, mas dinheiro não foi movimentado. Inverter escritas separadas abre janela de efeito duplicado.

## Modelo finito de tentativas e efeitos

Modelo Python puro ilustra diferença entre **tentativas** e **efeitos confirmados** sem fingir simular protocolo RabbitMQ. Contador de entregas aumenta em cada observação; conjunto guarda IDs lógicos já processados.

~~~python
def processar_entregas(entregas):
    vistos = set()
    tentativas = 0
    efeitos = 0
    for evento in entregas:
        tentativas += 1
        if evento not in vistos:
            vistos.add(evento)
            efeitos += 1
    return tentativas, efeitos

assert processar_entregas(["e1", "e1", "e2"]) == (3, 2)
assert processar_entregas(["e9"] * 5) == (5, 1)
assert processar_entregas([]) == (0, 0)
~~~

Diferentemente do PostgreSQL, conjunto local não é durável nem sincroniza processos. O teste integrado provê autoridade persistente; o modelo apenas esclarece identidade e pode ser executado sem containers.

## Envie ACK após o efeito durável

ACK do consumidor deve vir **depois** do commit da transação que protege efeito local. Se ACK vier antes do commit e o processo cair, o broker poderá descartar mensagem cujo trabalho nunca foi realizado. Se commit acontecer, mas ACK se perder, haverá redelivery; a inbox durável reconhecerá duplicação. Prioriza evitar perda de trabalho, aceitando tentativas repetidas [1].

Há custo operacional: mensagens sem ACK enquanto a transação executa ocupam capacidade de prefetch e estado do broker. Limite entregas simultâneas sem confirmação, aplique backpressure e monitore latência e unacked. Muitos consumidores não fornecem escala linear quando todos competem por linha quente do banco.

## O que publisher confirm não demonstra

O publicador habilita confirmação de publicação e envia com routing key obrigatória para fila declarada. Confirm recebido significa aceite pelo broker conforme contrato de fila/durabilidade; **não demonstra efeito aplicado pelo consumidor**. Mensagem persistente em fila durável também não substitui teste de reinício do broker, falha de disco ou replicação em cluster.

Um relay de outbox pode cair depois que broker aceita, mas antes de marcar publicação. Ao retornar, publicará mesma identidade; inbox tolera **publicação duplicada e redelivery**. Atomicidade entre banco e broker continua exigindo análise de outbox [2].

## Matriz de falhas e alcance do teste

| Fronteira | Resultado possível | Defesa |
| --- | --- | --- |
| Publicador falha antes do confirm | Aceite desconhecido | Retry com ID estável |
| Broker aceita, relay cai | Publicação duplicada | Inbox durável |
| Consumidor fecha sem ACK | Broker entrega novamente | Ack manual |
| Inbox confirma, ACK se perde | Nova entrega, um efeito local | Chave única transacional |
| Consumidor ACK antes do efeito | Ação pode ser perdida | Commit antes do ACK |
| PSP efetua operação, conexão cai | Resultado financeiro incerto | Idempotência e conciliação |

O CI atual verifica **fechamento do consumidor**, confirmação do publicador e bloqueio de efeito duplicado. Não desliga servidor RabbitMQ durante gravação, não testa quorum cluster, TLS nem partição entre regiões. Isso exige outros experimentos, não é consequência automática do job verde.

## Exercícios e verificação

1. Desenhe ordem dos eventos quando consumidor confirma inbox e cai antes do ACK; explique próxima entrega.
2. Por que inbox única é insuficiente quando atualização de saldo confirma em outra transação?
3. Diferencie publisher confirm, ACK do consumidor e resposta HTTP 202 da API de origem.
4. Proponha teste que publica **duas vezes** mesmo event ID e mantém um efeito local.
5. Descreva o que falha de nó RabbitMQ ou quorum queue testariam além do redelivery num broker isolado.

**Capítulos relacionados:** [Mensageria](/pt/topics/asynchronous-messaging/), [injeção de falhas](/pt/topics/failure-recovery-workshop/), [concorrência PostgreSQL](/pt/topics/postgresql-concurrency-integration/) e [System Design de webhooks](/pt/topics/system-design-interview-workshop/) completam as fronteiras.
