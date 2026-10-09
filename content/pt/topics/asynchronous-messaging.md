---
id: asynchronous-messaging
title: Filas, semântica de entrega e idempotência
description: Projete processamento assíncrono com confirmações, reentregas, filas de erro, consumidores idempotentes e controle explícito de pressão.
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites:
- capacity-estimation
- database-consistency
sources:
- title: RabbitMQ — Reliability Guide
  url: https://www.rabbitmq.com/docs/reliability
  kind: official messaging documentation
- title: AWS Builders Library — Avoiding Insurmountable Queue Backlogs
  url: https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/
  kind: engineering article
---
Filas desacoplam produtores e consumidores no tempo: uma requisição pode aceitar trabalho agora, enquanto o processamento ocorre depois. Isso melhora elasticidade e absorve picos temporários, mas introduz estados intermediários, latência, reentregas e ordens de processamento distintas. A documentação de mensageria deixa claro que confirmação de entrega não é a mesma coisa que aplicação única do efeito [1][2].

## Modelos de entrega e confirmação
Em modelos **at-most-once**, uma mensagem pode ser perdida, mas não é normalmente redespachada pelo protocolo após falha. Em **at-least-once**, o produtor ou broker tenta garantir que a mensagem reapareça até confirmação; como resultado, duplicatas são esperadas. A garantia de *exactly-once* depende da fronteira transacional que está sendo considerada: entregar uma mensagem uma vez não significa que um pagamento externo tenha sido executado uma vez.

Um consumidor deve confirmar a mensagem somente depois de persistir os efeitos exigidos. Se a aplicação confirma antes de gravar e cai, a mensagem pode ser perdida. Se grava e cai antes de confirmar, a mesma mensagem pode ser entregue novamente. A solução prática para muitos fluxos é idempotência junto com persistência transacional [1].

## Exemplo: consumidor idempotente
Considere uma mensagem com `event_id` estável. Dentro da mesma transação do efeito, insira `event_id` em tabela de eventos processados com índice único. Se a inserção falhar por conflito, o evento já foi aplicado ou está sob concorrência controlada, e não deve repetir o débito. A chave deve representar o **evento lógico**, não a tentativa de processamento.

```sql
BEGIN;
INSERT INTO processed_events (event_id) VALUES (:event_id);
UPDATE accounts SET balance = balance - :amount WHERE id = :account_id;
COMMIT;
```

O fragmento é ilustrativo: requer restrição UNIQUE, validação de saldo, tratamento de conflito, segurança de autenticação e definição do destino da mensagem em caso de erro. Se o débito depende de sistema externo, a transação local sozinha não garante atomicidade distribuída; serão necessários coordenação, reconciliação e possivelmente padrão de outbox ou saga.

## Retry, DLQ e ordenação
Retries imediatos e ilimitados geram tempestades quando a causa é indisponibilidade persistente. Use tentativas limitadas, atraso exponencial, jitter e classificação de erros. Mensagens que não podem ser processadas seguem para uma **dead-letter queue** com observabilidade e procedimento de correção; a DLQ não equivale a sucesso comercial.

Mensagens podem chegar fora de ordem. Se o estado depende da sequência, use versão por entidade, particionamento por chave ou um mecanismo que rejeite atualizações antigas. A promessa de ordem global é geralmente cara; muitas aplicações precisam apenas de ordem por agregado.

## Backpressure e estabilidade
Com chegada `λ` e serviço `μ` em mensagens/s, se `λ > μ` de forma sustentada, o backlog cresce, ainda que haja buffer. Monitore idade da mensagem mais antiga, profundidade, throughput real e erros; estabeleça rejeição, limites de fila e escalabilidade. Filas suavizam rajadas, mas não criam capacidade de processamento [2].

## Exercícios e verificação
1. O consumidor grava no banco e cai antes do ACK. Explique por que pode haver duplicata e como `event_id` evita segundo efeito.
2. Duas mensagens sobre a mesma conta chegam fora de ordem. Proponha versão monotônica para rejeitar estado antigo.
3. Se entram 150 eventos/s e saem 100/s continuamente, estime crescimento de backlog de 50 eventos/s e escolha um mecanismo de contenção.

A correção depende de contrato de idempotência, comportamento transacional e tratamento explícito de falhas.
