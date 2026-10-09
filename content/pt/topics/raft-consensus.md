---
id: raft-consensus
title: "Consenso distribuído: Raft, quóruns e logs replicados"
description: "Deduza interseção de quóruns e termos do Raft, eleições, replicação de logs, regras de commit e limites sob partições."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-consistency, asynchronous-messaging, concurrency-synchronization]
sources:
  - {title: "Ongaro and Ousterhout — In Search of an Understandable Consensus Algorithm", url: "https://raft.github.io/raft.pdf", kind: "peer-reviewed systems paper"}
  - {title: "MIT 6.5840 — Distributed Systems", url: "https://pdos.csail.mit.edu/6.5840/", kind: "university course"}
---
Um banco replicado ou serviço de metadados pode exigir que várias máquinas concordem com uma única sequência de comandos apesar de quedas e mensagens atrasadas. **Consenso distribuído** permite coordenar decisões preservando um modelo de segurança explícito. Não elimina partições de rede nem garante progresso quando poucos nós conseguem conversar. Raft é um algoritmo baseado em líder que separa eleição, replicação de log e restrições de segurança [1].

## Modelo de falhas e máquina de estados

Considere n nós trocando mensagens numa rede que pode atrasar, duplicar ou perder comunicação e sofrer partições. Nós podem cair e reiniciar usando estado persistido. O Raft convencional foi concebido para **falhas por parada**, não comportamento bizantino arbitrário em que participantes mentem ou assinam informações inconsistentes. Uma máquina de estados determinística executa comandos em ordem: estado inicial igual e comandos ordenados iguais produzem resultados iguais. Efeitos externos exigem projeto adicional de idempotência e transações.

Cada entrada de log contém comando e **termo** do líder que a criou. Termos são épocas lógicas crescentes, não relógio sincronizado. Nós assumem papéis de seguidor, candidato ou líder. Conhecer termo mais recente invalida liderança antiga. Persistir termo, voto e log corretamente é necessário para que reinício não desfaça compromissos já relevantes para outros nós [1].

## Por que maiorias se intersectam

Com n=2f+1 votantes, quórum majoritário tem f+1 nós. Duas maiorias necessariamente se intersectam: (f+1)+(f+1)=2f+2>2f+1=n. Logo compartilham ao menos um votante. Para n=5, maioria é 3; dois grupos de três votantes inteiramente distintos exigiriam seis nós, impossível. Mas **interseção sozinha não prova** toda a segurança do log Raft: regras eleitorais e correspondência das entradas também são essenciais.

![Cluster Raft de cinco votantes com maioria igual a três.](/diagrams/raft-majority.svg)

~~~python
from itertools import combinations

def maioria(n):
    if n < 1:
        raise ValueError("quantidade de votantes deve ser positiva")
    return n // 2 + 1

def quoruns(n):
    return [set(c) for c in combinations(range(n), maioria(n))]

grupos = quoruns(5)
assert maioria(5) == 3
assert len(grupos) == 10
assert all(a & b for a in grupos for b in grupos)
assert maioria(3) == 2
~~~

O código enumera apenas **conjuntos de quórum**, com custo combinatório de tempo e memória; comprova uma pequena propriedade, não implementa Raft. Mudanças reais de membros exigem protocolo de reconfiguração cuidadoso: mudar n ingenuamente pode criar quóruns antigos e novos sem interseção apropriada.

## Eleições e completude do líder

Se um seguidor deixa de receber comunicação do líder no prazo, pode se tornar candidato, elevar termo e solicitar votos. Cada nó concede no máximo um voto por termo, e o candidato precisa apresentar log pelo menos tão atualizado quanto o do votante, conforme regra de último termo/índice. Isso reduz a chance de escolher nó desatualizado sem entradas confirmadas obrigatórias. Timeouts eleitorais aleatórios diminuem candidaturas simultâneas, mas não garantem eleição imediata [1].

Com candidatos concorrentes, ninguém pode alcançar maioria até mudança de timeout ou conectividade. Segurança eleitoral significa no máximo um líder eleito **por termo**, respeitadas persistência e regras de votação. Em uma partição, líder antigo pode continuar acreditando que manda, mas não confirma novas entradas sem quórum nas regras do Raft. A convicção local do antigo líder não constitui autoridade.

## Correspondência e replicação dos logs

O líder acrescenta comandos ao log e envia AppendEntries aos seguidores com índice e termo precedentes. O seguidor só aceita extensão se o histórico coincidir na posição indicada; sufixos conflitantes ainda não confirmados são ajustados conforme o líder repara o histórico do seguidor. Daí surge a **propriedade de correspondência**: se dois logs contêm entradas com mesmo índice e termo, os registros anteriores também concordam conforme as regras do protocolo [1].

Um cliente pode repetir comando após timeout. Raft oferece ordenação e replicação do log, **não necessariamente efeito de negócio exactly-once** para retries. A máquina de estados deve lembrar identificadores de cliente/operação e resultados, ou usar outro protocolo correto de deduplicação, para que repetir comando financeiro não repita cobrança.

## Regra sutil de confirmação

Entrada criada no **termo atual do líder** pode ser considerada confirmada quando replicada em maioria, respeitando procedimento Raft. Entradas de **termos anteriores não devem ser confirmadas apenas pela contagem de cópias**; elas são confirmadas indiretamente quando uma entrada de termo atual é confirmada. A distinção evita afirmações incorretas em histórias com divergência complexa de logs [1].

Considere cinco nós: um líder com entrada replicada em três, seguido de partição que isola dois. O trio conectado ainda pode formar maioria e progredir se regras de eleição, termos e logs permitirem. Um fragmento com apenas dois votantes não confirma novas entradas, mesmo que ambos funcionem perfeitamente. **Disponibilidade** depende de quórum alcançável, não apenas de máquinas ligadas.

## Leituras consistentes e linearizabilidade

Um líder lendo somente sua memória pode estar **obsoleto** se perdeu contato e outro foi eleito. Leituras linearizáveis exigem verificações adicionais de liderança atual e aplicação de entradas confirmadas; implementações podem usar protocolo ReadIndex com quórum ou estratégia de leases sob hipóteses bem justificadas. Possuir log Raft replicado **não** torna toda leitura local do suposto líder automaticamente linearizável.

Concluir operação para o cliente também depende de persistência, aplicação de comandos e associação entre resultado e identidade da requisição. O log replicado protege ordem segundo hipóteses; não define sozinho transação de negócio, autenticação, criptografia do transporte ou recuperação de desastre.

## Falhas, métricas e decisões operacionais

| Falha | Exigência de segurança | Efeito na disponibilidade |
| --- | --- | --- |
| Seguidor cai | Preservar histórico confirmado | Maioria pode continuar |
| Líder cai | Eleger substituto atualizado | Interrupção de eleição |
| Partição minoritária | Não confirmar sem quórum | Minoria não faz escrita linearizável |
| Mensagens de antigo líder | Rejeitar termos e conflitos obsoletos | Repetições temporárias |
| Perda de votos/log persistido | Hipóteses Raft violadas | Segurança pode falhar |

Acompanhe trocas de líder, termos, erros de AppendEntries, atraso do índice de commit, atraso de aplicação, fsync e latência de rede. Timeouts curtos para a latência normal geram trocas frequentes; longos retardam detecção. Reconfiguração de membros e restauração de backups exigem procedimentos testados.

O curso de Sistemas Distribuídos do MIT aborda máquinas de estados replicadas, falhas e testes de forma integrada [2]. **Capítulos relacionados:** [Consistência em bancos](/pt/topics/database-consistency/) diferencia serializabilidade de linearizabilidade; [mensageria assíncrona](/pt/topics/asynchronous-messaging/) discute duplicatas e confirmação durável.

## Exercícios e verificação

1. Com cinco votantes, liste duas maiorias e mostre sua interseção. Com seis, por que maioria é quatro e não três?
2. Entrada de termo anterior aparece na maioria dos logs: por que não basta contar réplicas para confirmar segundo Raft?
3. Divida cinco votantes em grupos de 2 e 3. Qual pode eleger e confirmar, supondo logs e votos corretos?
4. Por que um antigo líder pode devolver leitura obsoleta mesmo com log local internamente consistente?
5. Modele deduplicação com cliente C, requisição R e resultado X. Explique por que executar a mesma operação repetida não pode duplicar o efeito de negócio.
