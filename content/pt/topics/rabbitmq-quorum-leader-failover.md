---
id: rabbitmq-quorum-leader-failover
title: "Failover de líder RabbitMQ Quorum: laboratório de três nós"
description: "Teste replicação RabbitMQ quorum real: publicação confirmada, parada do líder inicial, recuperação e escrita pela maioria sobrevivente."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-broker-restart-lab, raft-consensus]
sources:
  - {title: "RabbitMQ — Clustering Guide", url: "https://www.rabbitmq.com/docs/clustering", kind: "official broker documentation"}
  - {title: "RabbitMQ — Quorum Queues", url: "https://www.rabbitmq.com/docs/4.1/quorum-queues", kind: "official replication documentation"}
  - {title: "RabbitMQ — Consumer Acknowledgements and Publisher Confirms", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
---
Um broker RabbitMQ pode recuperar mensagem durável após reiniciar, mas isso **não comprova que fila quorum replicada continua disponível quando seu líder desaparece**. Este laboratório cria três nós RabbitMQ reais em containers Docker separados, forma cluster, publica mensagem persistente confirmada numa fila quorum de três membros, interrompe intencionalmente o nó inicial e lê a mensagem por outro nó. Também testa publicação nova confirmada pela maioria sobrevivente [1][2].

## Segurança e disponibilidade são propriedades diferentes

A fila quorum utiliza log replicado e consenso no estilo Raft. Com três membros, maioria significa **pelo menos dois** nós disponíveis e capazes de se comunicar. Perder um líder pode exigir eleição, mas os dois restantes devem eleger novo líder e preservar mensagens confirmadas conforme contrato de durabilidade do broker [2]. Se dois membros desaparecem, sobra minoria; indisponibilidade não autoriza o aplicativo a inventar sucesso de escrita.

As garantias dependem da confirmação da mensagem pelo publicador e de réplicas realmente inicializadas. Apenas iniciar três containers não demonstra que determinada fila possui três membros. O teste declara a fila **depois** de todos ingressarem no cluster, definindo `x-queue-type=quorum` e `x-quorum-initial-group-size=3`, conforme documentação [2].

## Topologia e autoridade declaradas

O script cria rede Docker isolada e inicia nós `mq1`, `mq2` e `mq3`. Todos recebem o mesmo cookie Erlang efêmero, usado na autenticação entre brokers, e usuário AMQP exclusivo para o teste. O segundo e o terceiro entram no cluster por `rabbitmqctl join_cluster rabbit@mq1`. A documentação oficial descreve o comando e alerta que associação manual é recurso para testes e desenvolvimento, não estratégia preferencial de produção [1].

![Três membros quorum preservam mensagem confirmada quando nó inicial para e maioria sobrevive.](/diagrams/rabbitmq-quorum-majority.svg)

Cada nó tem processo e filesystem de container próprios. É um cluster RabbitMQ de **três nós reais no mesmo host GitHub Actions**. Portanto verificamos falha de processo/container, não independência de hosts, datacenters, partições de rede ou recuperação geográfica.

## Contrato do produtor e replicação

O publicador conecta ao primeiro nó na porta AMQP mapeada, declara fila quorum **durável** e habilita confirmação. Envia mensagem persistente com `message_id` estável e encerra conexão após publicação confirmada. Não significa que consumidor concluiu processamento; significa que broker aceitou a publicação sob as condições de sua fila [2][3].

O modelo quorum mantém membros em nós distintos e um líder eleito para operações. Réplicas atrasadas podem acompanhar o líder após indisponibilidade temporária. A alegação de durabilidade refere-se a mensagens **confirmadas**: enviar bytes pelo socket sem aguardar confirmação não demonstra que uma maioria recebeu o evento.

## Interrompa o nó inicial e recupere em sobrevivente

O laboratório para `mq1`, local do líder inicial nesta configuração controlada. Abre conexão AMQP nova em `mq2` e busca mensagem até obter corpo e ID exatos ou ultrapassar prazo máximo. **Confirma ACK depois de conferir** o evento, não usa auto-ack que poderia descartar mensagem diferente sem verificá-la.

Depois envia mensagem nova por `mq2` com publisher confirms. Esse segundo passo importa: recuperar mensagem antiga mostra leitura após falha, mas **confirmar nova publicação** exercita disponibilidade de escrita da maioria de dois membros. O script não afirma qual nó se tornou líder; endpoint do cliente e identidade do líder da fila não são a mesma coisa.

## Implementação reproduzível e limpeza

A fonte executável é [scripts/verify_rabbitmq_quorum.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_quorum.py). O GitHub Actions executa em etapa própria **após o teste de restart de nó único**. O código cria três containers efêmeros, verifica nomes no cluster, publica e recupera mensagem verdadeira, depois remove os containers e rede no bloco `finally`. Todos os retries têm prazo máximo.

Para executar localmente, é necessário Docker e recursos para três brokers. **Nunca execute em infraestrutura Docker de produção compartilhada**: interromper nó intencionalmente afeta clientes. O CI usa runner descartável separado dos containers de serviço dos testes habituais.

## Experimento quorum não é prova universal

Um invariante útil estabelece que quorum exige mais da metade dos membros. Com n membros, maioria mínima é floor(n/2)+1. Em fila de três membros, são dois. A aritmética não comprova que determinado broker está saudável ou que suas réplicas receberam o log esperado.

~~~python
def maioria(total_membros):
    if not isinstance(total_membros, int) or total_membros <= 0:
        raise ValueError("quantidade positiva obrigatoria")
    return total_membros // 2 + 1

assert maioria(3) == 2
assert maioria(5) == 3
assert 3 - 1 >= maioria(3)
assert 3 - 2 < maioria(3)
~~~

Sistemas distribuídos também exigem composição correta do grupo, fencing de líder antigo, persistência, reconciliação e política de reconexão. A matemática explica interseção de quoruns; o teste executável cobre uma sequência concreta de falha. Nenhum substitui model checking ou experimentos de partição.

## Limites ainda não exercitados

| Cenário | Resultado ou expectativa | Alcance do teste |
| --- | --- | --- |
| Líder inicial interrompido | Mensagem confirmada recuperada | Três containers reais |
| Publicação pela maioria sobrevivente | Novo envio confirmado | Protocolo AMQP real |
| Dois membros deixam de funcionar | Falta maioria; escrita normal indisponível | **Não injetado** |
| Host Docker inteiro falha | Três containers podem cair juntos | **Não testado** |
| Partição de rede isola membro | Maioria pode continuar; minoria não | **Não testado** |
| Líder antigo retorna | Réplica precisa se atualizar | **Não testado** |

O laboratório não elimina **idempotência de consumidores**. Produtor pode repetir envio depois de confirmação ambígua e duplicar publicação; consumidor pode confirmar efeito no banco e cair antes do ACK, provocando redelivery. Inbox transacional e replicação quorum protegem fronteiras diferentes.

## Exercícios e verificação

1. Por que três brokers no **mesmo host** não demonstram tolerância à falha total desse host?
2. Calcule maioria para três, cinco e sete membros e número de falhas toleradas.
3. Acrescente teste que para segundo membro, com timeout limitado, sem aceitar publicação sem confirmação.
4. Amplie laboratório para reiniciar `mq1` e verificar sincronização sem efeitos lógicos duplicados.
5. Compare endpoint usado pelo cliente e identidade do líder eleito; explique por que um não revela o outro.

**Capítulos relacionados:** [Restart de broker](/pt/topics/rabbitmq-broker-restart-lab/), [redelivery e inbox](/pt/topics/rabbitmq-durable-consumer-integration/), [consenso Raft](/pt/topics/raft-consensus/) e [observabilidade](/pt/topics/distributed-observability/) aprofundam garantias [1][2][3].
