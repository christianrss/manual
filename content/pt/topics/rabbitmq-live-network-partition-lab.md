---
id: rabbitmq-live-network-partition-lab
title: "Partição de rede real RabbitMQ: brokers ativos sem quorum"
description: "Isole um broker em execução da rede Docker, observe confirmação na minoria e restaure quorum sem reiniciar o nó."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [rabbitmq-quorum-majority-loss, network-partition-quorum-models]
sources:
  - {title: "Docker — network disconnect", url: "https://docs.docker.com/reference/cli/docker/network/disconnect/", kind: "official container documentation"}
  - {title: "RabbitMQ — Network Partitions", url: "https://www.rabbitmq.com/docs/partitions", kind: "official broker documentation"}
  - {title: "RabbitMQ — Publisher Confirms and Consumer Acknowledgments", url: "https://www.rabbitmq.com/docs/confirms", kind: "official broker documentation"}
---
Um broker interrompido e um broker isolado são falhas diferentes. Quando o processo para, ele não atende chamadas. Numa partição de rede, o processo pode continuar **executando** sem conseguir falar com outros membros do quorum. Um broker em minoria pode aceitar login AMQP enquanto sua fila quorum não progride. Este laboratório amplia o teste de três membros com **desconexão e reconexão reais de uma rede bridge do Docker**, sem parar o processo RabbitMQ isolado [1][2].

## Contrato: cortar comunicação sem encerrar o processo

Começamos com fila quorum de três membros e evento confirmado real. O laboratório já verifica que dois membros recuperam o evento após parada do nó inicial e que a minoria de um membro não confirma nova publicação. Na nova etapa, segundo e terceiro brokers permanecem ligados, enquanto o primeiro segue parado. Em seguida o terceiro é desconectado da rede bridge. O segundo não consegue mais falar com ele; nenhum forma maioria dos três votantes originais.

A asserção é específica: **não ocorrer confirmação positiva de publicação dentro de prazo limitado**. Erro ou timeout não comprova que mensagem foi rejeitada ou perdida. O produtor pode precisar repetir o mesmo evento lógico depois da recuperação; a ambiguidade integra a semântica de publisher confirms do RabbitMQ [2].

![Um broker RabbitMQ permanece ativo após perder conexão com a bridge Docker, enquanto outro recebe o cliente AMQP.](/diagrams/rabbitmq-live-network-partition.svg)

## Verifique identidade do processo antes da separação

O teste obtém estado Docker \`RestartCount\` e informação de execução do container que será isolado. Depois desconecta a rede e exige que **o mesmo container permaneça em execução** e sua contagem de restarts seja idêntica. Isso importa porque trocar silenciosamente por \`docker stop\` apenas repetiria experimento de falha de nó, não perda de comunicação.

A sequência didática é:

~~~text
docker inspect --format '{{.State.Running}}' <isolated-node>
docker inspect --format '{{.RestartCount}}' <isolated-node>
docker network disconnect <test-bridge> <isolated-node>
docker inspect --format '{{json .NetworkSettings.Networks}}' <isolated-node>
~~~

Os comandos usam placeholders. A implementação reproduzível preenche os nomes efêmeros reais; veja [verify_rabbitmq_quorum.py](https://github.com/christianrss/manual/blob/main/scripts/verify_rabbitmq_quorum.py). O script só modifica seu próprio cluster de teste, nunca infraestrutura compartilhada de produção.

## Observe quorum com processos ainda vivos

O teste abre conexão AMQP nova no broker acessível. Login bem-sucedido estabelece **acessibilidade do endpoint**, não disponibilidade da fila replicada. Em seguida inicia subprocesso para executar uma publicação obrigatória com publisher confirms. O processo possui limite de tempo: uma fila sem maioria pode manter a operação bloqueada. Resposta positiva confirmada durante a minoria causa falha do teste.

A distinção entre resposta negativa e resultado desconhecido é essencial. A tentativa pode ter chegado ao broker local antes do timeout; sua conclusão não pode ser inferida somente pela exceção. O sistema deve manter event ID estável, consumidor idempotente e estratégia de reconciliação ou retentativa, sem tratar timeout como prova de que nada aconteceu [2].

## Restaure rede sem substituir servidor

A recuperação executa \`docker network connect\` para ligar **o mesmo container ainda em execução** à bridge original. Informa alias DNS do nó para que os brokers resolvam novamente o nome Erlang e compara estado de execução e reinícios com os valores anteriores [1].

Depois tenta publicar um evento novo com identidade própria até o RabbitMQ confirmar ou ultrapassar deadline. A verificação positiva **após reconexão** é tão importante quanto a negativa: um cluster definitivamente quebrado também passaria num teste que só exigisse ausência de confirmações.

## Modele quorum e presença de processos

Para fila de três membros, a maioria mínima é dois. Um grupo isolado com apenas um não alcança maioria estrita, mesmo que o processo esteja vivo. Um modelo puro demonstra a diferença:

~~~python
def pode_formar_maioria(membros, alcançaveis):
    if membros < 1 or not (0 <= alcançaveis <= membros):
        raise ValueError("composicao invalida")
    return alcançaveis >= membros // 2 + 1

assert pode_formar_maioria(3, 3)
assert pode_formar_maioria(3, 2)
assert not pode_formar_maioria(3, 1)
assert not pode_formar_maioria(3, 0)
~~~

A função não implementa Raft. Presume votantes fixos e comunicação mútua adequada. Não verifica termo do líder, posição das réplicas ou entrega de confirmação. Por isso há um teste real de broker complementando o modelo estático [3].

## O que uma partição real acrescenta

O teste anterior com nó parado demonstrava resistência à parada do container inteiro. O novo experimento muda a fronteira: processo em execução enquanto desaparecem conexões com pares. É relevante ao risco de split brain e a monitoramento que confunde uptime ou portas abertas com disponibilidade de escrita.

Desligar a conexão bridge ainda é uma interrupção grosseira. Afeta **todo** tráfego da interface, não apenas portas de distribuição Erlang nem perda assimétrica de pacotes. O script não injeta latência arbitrária, reordena pacotes, replica uma pane de roteamento cloud nem isola hosts independentes. Todos os containers compartilham o mesmo runner.

## Segurança de escrita não garante entrega da aplicação

Publisher confirm significa que broker aceitou mensagem conforme o contrato da fila. **Não** significa que consumidor externo atualizou estoque, cobrou cartão ou concluiu webhook. Fluxo at-least-once continua exigindo IDs lógicos estáveis e deduplicação por inbox na autoridade do negócio. Partição também pode perder resposta de uma publicação já confirmada; retries podem gerar duplicatas.

Cliente de produção precisa lidar com reconexão, DNS antigo, endpoints alterados, canais perdidos e redelivery. O teste abre conexões AMQP novas; pools de uma aplicação real podem reagir de forma diferente.

## Evidências e limites

| Propriedade | Evidência executada | O que não prova |
| --- | --- | --- |
| Conexão com bridge removida | Inspeção do Docker | Toda falha de rede possível |
| Broker isolado permanece ligado | State e RestartCount | Progresso interno do broker |
| Endpoint AMQP de outro nó responde | Login com cliente novo | Commit de quorum disponível |
| Minoria não confirma | Publicação em subprocesso limitado | Perda definitiva de evento incerto |
| Rede restaurada | Mesmo container reconectado | Roteamento automático de aplicação |
| Maioria publica novamente | Novo publisher confirm | Exactly once no efeito externo |

O resultado do CI vale para **a sequência executada**. Teste negativo exige asserções fortes: deve verificar que endpoint alvo é acessível e que o cliente tentou a publicação específica na fila quorum, não só que uma porta TCP qualquer estava indisponível.

## Exercícios e verificação

1. Por que conexão AMQP saudável com nó em partição minoritária não demonstra que a fila é gravável?
2. Meça intervalo entre reconexão da bridge e primeira confirmação positiva. Quais parcelas vêm do cliente?
3. Repita com três brokers executando e isole apenas um, deixando a outra dupla com maioria. Preveja qual lado progride.
4. Compare bridge desconectada, bloqueio das portas de distribuição Erlang e perda assimétrica de pacotes.
5. Explique por que repetir publicação ambígua com event ID novo pode quebrar contrato idempotente.

**Capítulos relacionados:** [Perda de maioria](/pt/topics/rabbitmq-quorum-majority-loss/), [modelo de partições](/pt/topics/network-partition-quorum-models/), [inbox transacional](/pt/topics/rabbitmq-durable-consumer-integration/) e [consenso Raft](/pt/topics/raft-consensus/) fundamentam garantias [1][2][3].
