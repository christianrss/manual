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

## Ciclo de vida exato da mensagem

Separe os estados **aceita pelo produtor**, **persistida no broker**, **entregue ao consumidor**, **efeito de negócio confirmado** e **reconhecida (ACK)**. Uma resposta HTTP de sucesso ao produtor não comprova execução futura durável sem garantia de persistência na aceitação. Entrega também não equivale a ACK. Um trabalhador pode cair entre quaisquer desses estados e gerar obrigações de recuperação diferentes [1].

Num sistema *at-least-once*, o broker pode reenviar mensagem cujo ACK foi perdido, mesmo que o efeito tenha sido confirmado. O consumidor precisa de chave durável de deduplicação e restrição de unicidade na mesma transação de mudança local. Conjunto 'IDs vistos' em memória desaparece após reinício; leitura seguida de gravação sem constraint sofre corrida. Se o efeito é cobrança externa, o contrato de idempotência da API remota ou reconciliação é necessário além da deduplicação local.

## Ordem e repetição têm escopo definido

Muitos brokers preservam ordem apenas dentro de fila ou partição, não entre múltiplos consumidores ou partições. Se `Criado(v1)` e `Cancelado(v2)` chegam invertidos, aplicá-los sem proteção pode ressuscitar entidade cancelada. Use versão por entidade ou sequência monotônica e defina tratamento de lacunas. Atrasos de retry podem alterar a ordem de efeitos mesmo se a rota habitual for ordenada.

Para repetição, diferencie erro permanente de validação de falha transitória. Utilize backoff exponencial limitado com jitter, tentativas ou idade máximas, limite de concorrência por dependência e regra de DLQ. Timeout significa que o **resultado remoto pode ser desconhecido**; repetir comando não idempotente pode duplicar efeitos [1].

## Dimensionamento da recuperação da fila

Se chegam `λ=80` trabalhos/s enquanto os consumidores concluem `μ=100` trabalhos/s, a drenagem líquida é `μ−λ=20` trabalhos/s. Um backlog de 12.000 tarefas exige ao menos `12.000/20=600` segundos para zerar, **desde que as taxas permaneçam estáveis e erros não gerem novas tentativas**. Quando `λ≥μ`, a fila não drena em regime. Repetições aumentam a carga efetiva e podem desencadear realimentação instável [2].

Seja `A` a idade da mensagem pronta mais antiga. Duas filas de 10.000 elementos podem ter impacto completamente distinto conforme o tempo por tarefa e os prazos; contagem sozinha é insuficiente. Acompanhe tempo fim-a-fim, isolamento de mensagens problemáticas, contagens por tentativa, idade da DLQ e da mensagem mais antiga.

## Pseudotransação de consumidor idempotente

```text
ao_receber(mensagem com id, entidade, versao):
    BEGIN
      INSERT inbox(id) VALUES (mensagem.id)
      SE conflito de unicidade:
          ROLLBACK/COMMIT SEM EFEITO; ACK; RETORNA
      VERIFICA versao e invariantes da entidade
      APLICA mudanca de negocio
    COMMIT
    ACK da mensagem no broker
```

O esquema supõe inbox e dados de negócio no mesmo banco transacional. Não promete efeito *exactly once* em sistemas externos à transação. Se o processo cai após COMMIT e antes do ACK, a inbox impede duplicação local no reenvio. Se cai antes do COMMIT, o broker tenta novamente conforme sua política de visibilidade ou reconhecimento. Considere isolamento transacional e reconexões.

## Testes com injeção de falhas

Teste queda antes do efeito, queda após confirmação mas antes do ACK, mensagens duplicadas com mesmo ID, dois consumidores concorrentes do mesmo ID, versões invertidas, mensagem venenosa, broker desconectado e API lenta. Verifique não só estado final, mas quantidade de efeitos observáveis externamente. Trata-se de uma matriz de falhas: cada interrupção possível exige recuperação definida e sinal de observabilidade.

## Exercícios e verificação
1. O consumidor grava no banco e cai antes do ACK. Explique por que pode haver duplicata e como `event_id` evita segundo efeito.
2. Duas mensagens sobre a mesma conta chegam fora de ordem. Proponha versão monotônica para rejeitar estado antigo.
3. Se entram 150 eventos/s e saem 100/s continuamente, estime crescimento de backlog de 50 eventos/s e escolha um mecanismo de contenção.

A correção depende de contrato de idempotência, comportamento transacional e tratamento explícito de falhas.
