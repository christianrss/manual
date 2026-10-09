---
id: data-partitioning-sharding
title: "Particionamento e sharding: chaves, hotspots e rebalanceamento"
description: "Projete partições e shards por padrões de acesso, dimensione hotspots, modele hashing estável, migração e constraints globais."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [system-design-process, database-consistency, database-replication-failover]
sources:
  - {title: "DynamoDB — Best practices for partition keys", url: "https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html", kind: "official vendor documentation"}
  - {title: "PostgreSQL — Table partitioning", url: "https://www.postgresql.org/docs/current/ddl-partitioning.html", kind: "official database documentation"}
  - {title: "Google SRE Workbook — Implementing SLOs", url: "https://sre.google/workbook/implementing-slos/", kind: "engineering workbook"}
---
**Particionamento** distribui subconjuntos de dados entre unidades de armazenamento; **sharding** geralmente designa essa divisão entre nós ou instâncias independentes de banco. A meta é escalar leituras, escritas, espaço ou administração preservando propriedade e correção dos acessos. Acrescentar shards não torna uma chave quente individual mais rápida, não melhora disponibilidade automaticamente e não resolve transações entre shards. Escolha a topologia a partir das consultas, assimetria de tráfego e consistência exigida [1].

## Partições físicas não são necessariamente shards

Um banco relacional pode separar uma tabela lógica em partições **dentro do mesmo sistema**, por exemplo por mês. PostgreSQL suporta particionamento declarativo por faixa, lista e hash. O **partition pruning** evita consultar partições cujos limites não podem satisfazer um filtro [2]. Isso auxilia algumas consultas e manutenção, mas não equivale a distribuir clientes entre clusters de banco independentes.

Uma camada de sharding distribui cada entidade à autoridade de armazenamento correta. O mapeamento pode existir na aplicação, num roteador ou dentro do próprio banco. Um cliente não pode escolher livremente shard para contornar autorização de tenant. A regra de localidade deve ser estável e reproduzível ou mediada por uma autoridade central de roteamento.

## Escolha pela forma da consulta e cardinalidade

Considere um serviço multitenant de notas que frequentemente (1) consulta nota por ID **dentro do tenant**, (2) lista notas recentes do tenant e (3) grava notas para ele. Sharding por tenant_id agrupa operações do mesmo cliente e pode preservar invariantes transacionais dentro do shard. Mas um tenant grande pode dominar a carga e virar **hot shard**. Distribuir por hash(note_id) tende a espalhar gravações, mas listar notas de um tenant passa a exigir consultas a vários shards e mesclagem.

Sharding por intervalo de criação auxilia poda de arquivos antigos, mas concentra escritas recentes numa faixa: **hotspot móvel**. Hash costuma distribuir chaves quando a demanda não é muito assimétrica; aplicar hash a tenant_id ainda dirige toda a carga do mesmo tenant a um shard. A documentação de bancos distribuídos alerta que chaves pouco variadas e atividade desigual criam partições quentes mesmo quando sobra capacidade global [1].

![O particionamento roteia chaves a autoridades, mas uma chave quente pode continuar concentrada.](/diagrams/sharding-key-distribution.svg)

## Modelo de capacidade com hipóteses falsificáveis

Imagine carga **hipotética** de pico de 6.000 escritas/s. Testes mostram que cada shard independente atende 1.000 escritas/s com tamanho dos registros, índices e latência pretendidos. Com distribuição perfeitamente uniforme, precisamos de pelo menos seis shards ativos; reservar um sétimo só ajuda a tolerar perda de um shard **se houver** mecanismo demonstrado de failover/redistribuição. É aritmética de capacidade agregada, não garantia automática de disponibilidade.

Agora suponha que um tenant gere sozinho 3.000 escritas/s. Particionar por tenant manda as 3.000 ao mesmo shard, superando sua capacidade segura de 1.000. Aumentar de 7 para 14 shards não espalha esse tenant. É preciso alterar a chave, talvez (tenant_id, bucket), isolar o cliente em infraestrutura própria, controlar admissão ou mudar estratégia de armazenamento. A leitura exigirá fanout entre buckets ou índice derivado.

## Estratégias e decisões de chave

| Chave/roteamento | Benefício | Custo e falha |
| --- | --- | --- |
| Hash(tenant_id) | Transações e listagens locais | Tenant grande permanece quente |
| Hash(note_id) | Maior distribuição de notas | Listagem do tenant percorre shards |
| Range(created_at) | Arquivamento e pruning temporal | Hotspot das escritas atuais |
| (tenant_id, bucket) | Divide carga do tenant pesado | Leitura distribuída e merge |
| Diretório tenant→shard | Posicionamento e migração explícitos | Disponibilidade do diretório |

Dimensione quantidade de shards por **I/O de pico e assimetria real das chaves**, não apenas bytes totais. Inclua índices, réplica, backfill, coordenação de transações e domínios de falha. Disco pode se tornar gargalo bem antes de CPU média, ou o contrário.

## Por que mudar módulo pode causar problemas

Um roteamento ingênuo shard=hash(chave)%N é determinístico para N fixo, mas mudar N costuma redistribuir muitas chaves. Dados não se movem automaticamente quando o roteador muda: antes de copiar registros e conciliar escritas, requisições podem alcançar nós sem o valor mais recente. A função hash() embutida em Python também não é adequada em geral como roteamento externo persistente, porque seeds aleatórias e semântica variam entre processos e tipos.

**Rendezvous hashing** calcula pontuação estável por par (chave,nó) e escolhe a maior. Ao acrescentar nó, uma chave permanece no antigo vencedor ou migra ao nó novo. Isso reduz movimento comparado a remapeamento amplo por módulo, embora equilíbrio real de tráfego dependa de frequência das chaves e pesos dos nós.

~~~python
from hashlib import sha256

def destino(chave, nos):
    if not nos:
        raise ValueError("pelo menos um no necessario")
    if len(set(nos)) != len(nos):
        raise ValueError("identificadores duplicados")
    def pontuacao(no):
        dados = (str(chave) + "|" + str(no)).encode("utf-8")
        return int.from_bytes(sha256(dados).digest(), "big")
    return max(nos, key=pontuacao)

antes = ["s0", "s1", "s2", "s3"]
depois = antes + ["s4"]
chaves = [f"nota-{n}" for n in range(1000)]
alteradas = [c for c in chaves if destino(c, antes) != destino(c, depois)]
assert 0 < len(alteradas) < len(chaves)
assert all(destino(c, depois) == "s4" for c in alteradas)
assert all(destino(c, antes) == destino(c, depois)
           for c in chaves if c not in alteradas)
assert destino("fixa", antes) == destino("fixa", antes)
~~~

O código demonstra **somente roteamento**. Concatenar usando barra vertical como separador é ambíguo para identificadores não restringidos: na produção, use serialização canônica estruturada ou prefixos de comprimento. O roteador real também precisa de versão de membresia, pesos, tolerância a falhas e ferramenta de migração. Posicionamento consistente não copia registros nem replica operações.

## Resharding é protocolo de migração

Redistribuir com segurança exige **fonte da verdade explícita** durante a transferência. Um plano possível é: criar capacidade alvo; gerar snapshot das faixas antigas; copiar registros com versões; capturar mutações posteriores via log durável; conferir contagens, checksums e versões; controlar o corte e redirecionamento de escritas; atualizar geração do roteador; manter recuperação/rollback. Dual write sem ordenação ou idempotência pode divergir em crashes.

O corte precisa impedir que cópia antiga sobrescreva mutação confirmada mais recente. Use versões crescentes ou garantias demonstradas de transação/offset do stream. Monitore lag de cópia, conflitos, duplicatas e erros de consulta. Trocar somente o mapa de roteamento sem movimentação verificada dos dados não é migração: é indisponibilidade.

## Unicidade, joins e limites transacionais

O índice UNIQUE normalmente protege chaves **dentro da autoridade que o mantém**. Se o negócio exige usernames globalmente únicos e usuários residem em shards distintos, um UNIQUE(username) local por shard não protege o invariante global sozinho. Alternativas incluem cadastro global autoritativo, roteamento determinado pela chave única ou coordenação distribuída com falhas explicitadas.

PostgreSQL impõe restrições adicionais a UNIQUE e PRIMARY KEY sobre tabelas particionadas: a chave da constraint geralmente deve incluir todas as colunas de particionamento, permitindo que índices locais imponham o escopo correto [2]. Isso não significa unicidade global entre bancos independentes.

Joins entre shards podem exigir fanout, execução distribuída ou modelos de leitura pré-computados. Transações entre shards criam latência e riscos de falha: uma transação ACID local não confirma automaticamente alterações em outras autoridades. Quanto mais invariantes ficarem sob autoridade clara e única, mais simples a prova de correção.

## Replicação é dimensão separada

**Particionamento divide dados distintos**; **replicação copia dados sobrepostos** para disponibilidade e/ou leituras. É possível ter quatro shards, cada um com três réplicas, totalizando doze cópias/nós num modelo simplificado; a implantação real depende de colocação, domínios de falha e eleição de líderes. Réplicas podem melhorar disponibilidade, mas introduzir lag e decisões de consistência. Ler réplica obsoleta pode quebrar read-your-writes após escrita confirmada [3].

Backup não é réplica: uma exclusão acidental pode ser rapidamente replicada. O projeto precisa definir RPO, RTO, testes de restauração e espaço de WAL, snapshots e backfill.

## Validação operacional e contraexemplos

Teste chaves sintéticas uniformes **e** acesso assimétrico realista, pois uniformidade esconde hotspots. Observe pico de escrita por shard, fila, CPU, armazenamento, p99, lag e progresso de migração. Provoque falha de shard durante escrita, backfill e logo após corte de roteamento. Confirme que autorização por tenant continua correta com dados movidos.

Não adote sharding prematuramente: banco relacional único com índices, réplicas ou partições de tabela pode atender com menor coordenação. Por outro lado, limites físicos de escrita ou armazenamento com hotspot comprovado podem justificar distribuição. Documente gatilho mensurável, não apenas topologia desejada.

## Exercícios e verificação

1. Com 6.000 escritas/s e 1.000 escritas/s seguras por shard, calcule o mínimo uniforme e por que N+1 não basta como garantia de failover.
2. Por que um tenant com 3.000 escritas/s segue quente após acrescentar shards sob hash(tenant_id)?
3. Compare a listagem recente de um tenant entre sharding por tenant e por hash(note_id).
4. Demonstre, pelo modelo rendezvous, que uma chave remapeada após acrescentar s4 só pode mover **para s4**, não entre nós antigos.
5. Declare invariante de corte que impeça uma cópia de snapshot antiga de substituir escrita nova já confirmada.

**Capítulos relacionados:** [Método System Design](/pt/topics/system-design-process/) define exigências; [índices transacionais](/pt/topics/transactional-indexing-isolation/) trata unicidade; [replicação e failover](/pt/topics/database-replication-failover/) discute RPO/RTO.
