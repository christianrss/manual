---
id: rabbitmq-quorum-majority-loss
title: "RabbitMQ Quorum: perda de maioria, bloqueio e recuperação"
description: "Teste perda de maioria, ausência de confirmação de publicação e recuperação de escritas num cluster RabbitMQ real."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-quorum-leader-failover]
sources:
  - {title: "RabbitMQ 4.1 — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official broker documentation"}
  - {title: "RabbitMQ — Consumer Acknowledgements and Publisher Confirms", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
  - {title: "RabbitMQ — Network Partitions", url: "https://www.rabbitmq.com/docs/partitions", kind: "official broker documentation"}
---
Uma fila replicada pode continuar disponível após falha de um nó e parar de progredir quando **a maioria dos membros votantes deixa de funcionar**. Não é apenas timeout genérico de rede: é parte do **contrato de consistência** das filas quorum. Esta oficina amplia o laboratório de três nós RabbitMQ para exercitar os dois lados da fronteira: escrita confirmada com dois membros, nenhuma confirmação positiva com apenas um membro e retorno das confirmações após restaurar a maioria. Usa containers Docker e AMQP reais, não filas simuladas [1][2].

## Invariante: um nó não constitui quorum

Numa fila de três membros, a maioria mínima é dois. Depois de parar o primeiro nó, os dois restantes conseguem eleger ou manter líder e aceitar novas publicações confirmadas. Ao parar um segundo nó, resta apenas um dos três membros originais. Uma maioria torna-se impossível. O broker sobrevivente pode **ainda aceitar conexão TCP**; isso não prova que a fila quorum consegue confirmar mensagens com segurança.

![Fila de três membros progride com dois, deixa de confirmar com um e retorna após restauração da maioria.](/diagrams/rabbitmq-majority-loss.svg)

A propriedade de segurança é delimitada: **o produtor não deve receber confirmação positiva de nova escrita numa fila quorum quando há apenas um membro votante disponível**. Exceção ou timeout exatos variam conforme versão do broker e estado da eleição. O aplicativo precisa distinguir falta de confirmação positiva de rejeição definitiva: quando conexão cai, resultado da publicação pode ser **desconhecido** para o produtor.

## Reproduza a sequência de falhas real

A fonte [verify_rabbitmq_quorum.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_quorum.py) cria cluster RabbitMQ isolado de três nós e uma fila com três membros explícitos. Primeiro publica evento persistente com publisher confirm habilitado, para nó inicial, recupera mensagem por sobrevivente e publica outro evento confirmado pela maioria de dois membros.

A nova etapa para **um segundo** broker deixando um em execução. Abre uma conexão AMQP adicional com sucesso no nó sobrevivente, impedindo que falha banal de conexão seja confundida com indisponibilidade específica do quorum. Em seguida tenta publicar outra mensagem confirmada num processo filho com prazo máximo.

## Teste negativo com tempo limitado não paralisa o CI

Durante minoria, o teste inicia novo processo Python publicador, em vez de manter a suíte bloqueada indefinidamente. O filho usa \`confirm_delivery()\`, mensagem persistente e a mesma fila quorum. O processo pai considera **confirmação positiva e saída bem-sucedida uma falha do teste**. Timeout limitado ou erro no canal demonstram que a nova escrita **não recebeu confirmação positiva durante a observação**, não que broker descartou definitivamente a mensagem [2].

O sinal central é o *publisher confirm*. Terminar envio pelo socket ou receber ACK TCP não demonstra commit replicado na fila. A política para publicações ambíguas precisa preservar event ID estável e repetir com idempotência, pois publicação aparentemente incerta pode aparecer depois da recuperação.

## Restaure maioria e confirme progresso

Depois de observar a minoria, o script reinicia o segundo broker parado, espera ele aceitar login AMQP e tenta repetidamente uma **nova publicação identificável** pelo nó sobrevivente até receber confirmação ou esgotar prazo rigoroso.

A confirmação após recuperação importa: sem ela, teste negativo poderia passar mesmo com cluster permanentemente quebrado. O experimento examina **retomada do progresso** além da ausência de confirmações positivas durante perda da maioria.

O escopo ainda é parar e iniciar processos Docker. Não provoca partição de rede real nem perda de pacotes. Para testar partição, seria necessário separar conexões entre os nós mantendo processos em execução e verificar comportamento da maioria e minoria com clientes conectados a segmentos diferentes [3].

## Calcule tolerância antes de iniciar infraestrutura

Com n membros votantes, limiar quorum é floor(n/2)+1. Assim fila de três suporta dois disponíveis; fila de cinco requer três. É regra de interseção de maiorias, não medida de throughput nem cobertura de todas as falhas de armazenamento.

~~~python
def tamanho_maioria(membros):
    if not isinstance(membros, int) or membros < 1:
        raise ValueError("quantidade positiva")
    return membros // 2 + 1

def tem_maioria(total, disponiveis):
    if disponiveis < 0 or disponiveis > total:
        raise ValueError("disponibilidade invalida")
    return disponiveis >= tamanho_maioria(total)

assert tem_maioria(3, 2)
assert not tem_maioria(3, 1)
assert tem_maioria(5, 3)
assert not tem_maioria(5, 2)
~~~

A aritmética é **modelo de membros**, não implementação de broker. Quando réplicas estão atrasadas, desconectadas ou divergentes na visão do grupo, contar containers ligados não basta; estado real da fila e consenso determinam se progredir é seguro.

## O problema da publicação ambígua

Suponha produtor que envia evento E e perde conexão antes do confirm. E pode ter sido confirmado internamente antes da falha ou pode não ter sido aceito. Repetir E com **outro ID** pode criar duas operações lógicas. Preserve identidade nas tentativas e torne o efeito do consumidor idempotente na autoridade transacional [2].

Replicação quorum e deduplicação na inbox são complementares, não alternativas. A primeira protege dados replicados e disponibilidade da fila; a segunda impede efeito de negócio duplicado mesmo com publicação repetida ou redelivery.

## Recuperação de quorum não cria capacidade

Imagine consumidores processando 200 jobs/s e entradas novas de 180/s. Após 20 minutos sem processamento, acumulam-se 216 mil jobs. Mantidas taxas, sobra capacidade de apenas 20 jobs/s, exigindo três horas para drenar. São **hipóteses didáticas constantes**, não benchmark RabbitMQ.

~~~python
def tempo_drenagem(chegada_por_s, processamento_por_s, segundos_pane):
    if chegada_por_s < 0 or segundos_pane < 0 or processamento_por_s <= chegada_por_s:
        raise ValueError("margem positiva de recuperacao obrigatoria")
    return (chegada_por_s * segundos_pane) / (processamento_por_s - chegada_por_s)

assert tempo_drenagem(180, 200, 1200) == 10800
~~~

Quorum restaurado não garante SLO de latência da aplicação. Observe idade do backlog, tempo de confirmação, tentativas de entrega, vazão dos consumidores e duração da recuperação da escrita separadamente.

## Evidências observadas, inferidas e não testadas

| Situação | Verificação executável | Não estabelece |
| --- | --- | --- |
| Um nó parado | Mensagem recuperada e nova escrita confirmada | Failover automático de todo cliente |
| Dois nós parados | Sem confirmação positiva antes do deadline | Perda definitiva da tentativa |
| Dois nós disponíveis novamente | Nova publicação confirmada | Réplicas antigas totalmente sincronizadas |
| Host inteiro indisponível | Nada; brokers compartilham host | Tolerância a datacenter |
| Partição de rede entre nós | Não injetada | Correção em partições arbitrárias |
| Consumidor tenta repetir efeitos | Outro teste verifica inbox | Exactly once no PSP externo |

O teste negativo deve **falhar de modo seguro**, com espera limitada. Alegações publicadas precisam respeitar a sequência de falhas realmente executada, sem transformar laboratório em certificação universal.

## Exercícios e verificação

1. Por que login AMQP bem-sucedido na minoria não comprova que fila quorum consegue confirmar escrita?
2. Por que ausência de publisher confirm deve ser tratada como resultado ambíguo, não rejeição definitiva?
3. Modifique Docker para isolar um nó por rede mantendo processo vivo. Preveja qual partição deve progredir.
4. Amplie a recuperação para verificar sincronização do nó que retornou usando métricas de replicação RabbitMQ.
5. Recalcule drenagem se chegadas atingem 190 jobs/s e processamento permanece em 200 jobs/s.

**Capítulos relacionados:** [Quorum de três nós](/pt/topics/rabbitmq-quorum-leader-failover/), [restart de broker](/pt/topics/rabbitmq-broker-restart-lab/), [inbox transacional](/pt/topics/rabbitmq-durable-consumer-integration/) e [consenso Raft](/pt/topics/raft-consensus/) oferecem fundamentos [1][2][3].
