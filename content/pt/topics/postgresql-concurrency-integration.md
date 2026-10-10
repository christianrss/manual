---
id: postgresql-concurrency-integration
title: "Laboratório PostgreSQL: reservas concorrentes e recuperação de falhas"
description: "Teste processos independentes e PostgreSQL real com atualização condicional, idempotência e commits duráveis com outbox."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [sqlite-multiprocess-recovery, transactional-indexing-isolation]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "Amazon Builders Library — Making retries safe with idempotent APIs", url: "https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/", kind: "original engineering guidance"}
---
Concorrência no PostgreSQL depende de **transações e autoridade compartilhada**, não de lock mantido dentro de um processo. Duas instâncias de API podem observar produto aparentemente disponível se a própria escrita não proteger o invariante de estoque. Esta oficina amplia o teste SQLite multiprocessos para um **servidor PostgreSQL 17 real**, iniciado em container no CI. O código executável roda em processos Python independentes e utiliza transação PostgreSQL para reservar estoque e registrar intenção outbox [1][2].

## Contrato e propriedade de segurança

Uma linha possui três unidades disponíveis de SKU `seat`. Dois clientes independentes tentam reservar duas unidades com chaves distintas. Exatamente um pode vencer; o outro recebe `insufficient`, e **available jamais pode ficar negativo** após commit. Pedido aceito grava uma reserva e uma intenção outbox no mesmo commit. Quando o cliente repete chave aceita com quantidade idêntica, recebe `replayed`. Chave repetida com quantidade diferente produz conflito.

Neste exemplo, respostas `insufficient` **não** são salvas como resultados idempotentes. Isso importa quando estoque é reabastecido: a mesma operação antes rejeitada poderia ser aceita depois. Produto real pode persistir rejeição definitiva, vinculando chave a tenant autenticado e fingerprint canônico do pedido.

## O risco do SELECT seguido de UPDATE

Uma implementação ingênua lê `available=3`, conclui que duas unidades cabem e mais tarde atualiza sem condição. Outra transação pode ter feito a mesma leitura antes da primeira confirmar. Se ambas as decisões forem aceitas, quatro unidades seriam prometidas apesar de existirem três. Colocar SELECT e UPDATE numa transação não demonstra segurança automaticamente em qualquer isolamento: é preciso entender o comportamento do banco [1].

A implementação utiliza a instrução condicional abaixo. Sob **READ COMMITTED**, um UPDATE concorrente pode esperar o bloqueio da linha e reavaliar a condição contra a versão atualizada, conforme documentação oficial [1].

~~~sql
UPDATE stock
SET available = available - $1
WHERE sku = 'seat' AND available >= $1
RETURNING available;
~~~

Sem linhas retornadas, a reserva é insuficiente. Essa condição e um CHECK no banco protegem estoque; a transação também inclui reserva e outbox, evitando pedido aceito sem intenção de evento persistida.

## Chaves idempotentes e retries concorrentes

A constraint única `reservations(op_key)` precisa corresponder à identidade lógica contratada na API. O exemplo **insere a chave primeiro** com `ON CONFLICT DO NOTHING RETURNING`. Se outro processo estiver gravando a mesma chave, PostgreSQL resolve a disputa por unicidade; o perdedor consulta a quantidade confirmada e devolve `replayed` ou conflito. Não depende de lookup local seguido de INSERT desprotegido.

Para chaves distintas, UPDATE condicional serializa conflito sobre a linha de estoque. Se falhar, a transação reverte também a chave inserida provisoriamente. Assim reserva, outbox e saldo permanecem consistentes. A autoridade é o banco, não cache, fila ou memória do worker.

![Dois clientes PostgreSQL independentes competem por atualização condicional do mesmo estoque.](/diagrams/postgres-concurrency-integration.svg)

## Execute contra servidor real

O código completo é [examples/python/postgres_checkout.py](https://github.com/christianrss/manual/blob/main/examples/python/postgres_checkout.py). O teste [tests/test_postgres_integration.py](https://github.com/christianrss/manual/blob/main/tests/test_postgres_integration.py) cria um schema isolado por teste, inicializa estoque e inicia dois processos do sistema operacional com `subprocess`. Verifica uma resposta `accepted`, outra `insufficient`, saldo final um, uma reserva e uma linha outbox.

Ao contrário de repositório falso, o teste emite SQL por conexões independentes para servidor PostgreSQL ativo. Porém cobre uma quantidade finita de escalonamentos, não todos os schedules possíveis. A correção também depende da atomicidade de UPDATE, inserções transacionais e constraints únicas. O teste funciona como proteção de regressão dessa implementação.

## Crash depois do commit

Outro teste inicia worker que confirma reserva e executa `os._exit(23)` antes de devolver resposta. Um processo diferente repete mesma chave e recebe `replayed`; nova conexão comprova linhas duráveis de estoque, reserva e outbox. Demonstra **recuperação após saída de processo e commit** no ambiente do CI, não resistência a corrupção física, falha de host, partições de rede ou replicação mal configurada.

Isso explica por que timeout do cliente não comprova falha. Enviar nova chave após timeout pode gerar nova operação lógica. Mesmo transação PostgreSQL não confirma efeitos de um provedor financeiro independente; aí continuam necessários idempotência do PSP e conciliação [2].

## Estime contenção e gargalo

Considere **hipotéticas** 600 reservas/s de um SKU quente, com região crítica de atualização da linha medindo 2 ms em média. Um recurso serial cujo tempo permaneça realmente 2 ms tem limite nominal próximo de 500 atualizações/s; chegadas sustentadas de 600/s tenderiam a aumentar a fila, ignorando overhead e variação de serviço.

~~~python
def capacidade_nominal_por_segundo(milisegundos_criticos):
    if milisegundos_criticos <= 0:
        raise ValueError("tempo positivo necessario")
    return 1000.0 / milisegundos_criticos

assert capacidade_nominal_por_segundo(2) == 500.0
assert capacidade_nominal_por_segundo(4) == 250.0
~~~

É **aproximação de recurso serial**, não benchmark PostgreSQL. Espera por lock, IO, transação e custo variável alteram vazão. Dividir usuários entre processos não paraleliza a atualização da **mesma linha quente** sem mudar modelo de alocação. Alternativas incluem quotas por depósito, pools de reserva ou aceitar encomenda sem estoque, todas com novas regras explícitas.

## CI, limites e tabela de falhas

O GitHub Actions provisiona PostgreSQL em container Linux, instala driver e executa testes editoriais, exemplos Python e integrações. No CI o banco é obrigatório: problema de conexão falha o job. Na máquina local, configure `POSTGRES_DSN` para banco descartável; sem variável, a classe de integração é ignorada fora do CI.

| Situação | Propriedade protegida | O que não se comprova |
| --- | --- | --- |
| Dois processos disputam duas de três | Sem sobrevenda no banco testado | Failover distribuído |
| Chave aceita repetida | Uma reserva e um outbox | Escopo de tenant |
| Chave repetida com outra quantidade | Conflito explícito | Payload complexo |
| Processo encerra após commit | Retry encontra estado gravado | Queda de energia |
| SKU popular sob carga | Atomicidade da linha | Latência aceitável universal |

Não trate CI verde como garantia de entrega exactly once em fila ou PSP. Esse experimento cobre uma fronteira real de banco; demais componentes precisam de evidências próprias.

## Exercícios e verificação

1. Por que conferir estoque no próprio UPDATE protege melhor que SELECT preliminar?
2. Trace duas chamadas com mesma chave e identifique onde a constraint única resolve corrida.
3. Altere a quantidade para um e explique quantas de três solicitações distintas vencem.
4. Cite falha real que `os._exit(23)` não simula e a infraestrutura para testá-la.
5. Projete benchmark de SKU quente medindo contenção, p95 de espera por lock e erros, além de throughput.

**Capítulos relacionados:** [Isolamento transacional](/pt/topics/transactional-indexing-isolation/), [SQLite multiprocessos](/pt/topics/sqlite-multiprocess-recovery/), [projeto de pedidos](/pt/topics/system-design-order-service/) e [injeção de falhas](/pt/topics/failure-recovery-workshop/) dão suporte.
