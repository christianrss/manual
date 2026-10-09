---
id: transactional-indexing-isolation
title: "Índices transacionais: MVCC, unicidade e isolamento serializável"
description: "Explique constraints únicas com concorrência, índices multiversão, locks de predicado, write skew, retries e custos de indexação."
category: system-design
difficulty: advanced
updated: 2026-10-09
prerequisites: [database-consistency, sql-query-planning, database-storage-wal]
sources:
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
  - {title: "PostgreSQL — Indexes and MVCC", url: "https://www.postgresql.org/docs/current/indexes-index-only-scans.html", kind: "official database documentation"}
  - {title: "PostgreSQL — Unique Indexes", url: "https://www.postgresql.org/docs/current/indexes-unique.html", kind: "official database documentation"}
---
Um índice não é apenas atalho para SELECT. Num banco transacional ele participa de inserções, exclusões, visibilidade de versões e imposição de restrições. A **correção sob concorrência** depende do isolamento e das regras do banco, não de executar uma consulta preliminar rápida. PostgreSQL oferece exemplo concreto: MVCC admite snapshots simultâneos, índices únicos coordenam chaves conflitantes e isolamento Serializable pode abortar transações que produziriam história não serializável [1][3].

## Separe três perguntas distintas

O índice pergunta: **onde pode estar a tupla relevante?** A visibilidade pergunta: **a versão é visível para esta transação?** A restrição pergunta: **a mudança lógica pode ser confirmada?** Um index scan não responde automaticamente às três questões. Uma tupla alcançada pela B-tree pode ser invisível no snapshot, e até um index-only scan pode consultar o heap para confirmar visibilidade [2].

Uma restrição de unicidade é invariante durável mantido sob modificações concorrentes, não uma consulta `SELECT NOT EXISTS(...)` antes de um INSERT independente. Dois clientes podem observar chave inexistente e tentar inseri-la. Somente restrição de banco que imponha unicidade, ou outro protocolo correto de serialização, protege o invariante.

## Contraexemplo de tempo entre checar e usar

Suponha T1 e T2 consultando `SELECT 1 FROM reservations WHERE seat_id=7` e ambas não encontrando linhas. Depois tentam reservar assento 7. Sem restrição única na chave de negócio correta, ambas podem confirmar, violando 'no máximo uma reserva ativa por assento'. Colocar o SELECT dentro de uma transação comum **não basta** em qualquer nível de isolamento: a ordem e as anomalias permitidas importam [1].

![Duas transações concorrem pela mesma chave; a unicidade arbitra o conflito.](/diagrams/transaction-unique-race.svg)

Uma constraint única em seat_id, ou índice único parcial para reservas **ativas**, obriga o banco a arbitrar. Um INSERT pode bloquear, falhar ou exigir retry conforme resultado da transação concorrente. A API deve traduzir o erro em resposta de domínio, sem supor qual transação vencerá.

## Unicidade, NULL e índices compostos

Índice único composto cobre uma tupla de chaves; escolher `(tenant_id, external_id)` em lugar de `external_id` define a fronteira da unicidade. Na semântica SQL comum do PostgreSQL, NULLs em chaves únicas podem ser tratados como distintos, salvo escolha explícita de alternativa. Assim `UNIQUE(email)` não significa necessariamente 'existe só uma linha sem email'. Revise nulidade, normalização de caixa, collation e status antes de declarar invariantes [3].

O limite de reservas ativas pode usar índice único parcial PostgreSQL em `seat_id WHERE status IN ('pending','confirmed')`; ele expressa no máximo uma reserva ativa. Não garante saldo positivo, sequência válida de estados ou autorização por tenant. Constraints protegem **invariantes específicos** e complementam validações da aplicação.

## MVCC não elimina write skew

Em isolamento baseado em snapshot, duas transações podem ler o mesmo estado anterior e modificar **linhas diferentes**, cada uma passando no teste local, enquanto juntas violam o invariante. Exemplo: dois médicos de plantão. Cada transação verifica que ao menos um permanecerá e desativa um médico diferente. Se ambas confirmam, não há plantonista. Como alteram chaves distintas, proteger apenas escritas duplicadas numa **mesma** entrada de índice não resolve a anomalia [1].

O modo Serializable do PostgreSQL usa mecanismos de Serializable Snapshot Isolation, incluindo informações de locks de predicado, para detectar padrões perigosos. Uma transação pode sofrer serialization failure em vez de confirmar história não serializável. Isso exige **repetir a transação inteira**, incluindo leituras e decisões, quando o negócio permite [1].

## SQL concreto e fronteiras

~~~sql
CREATE TABLE reservations (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  seat_id BIGINT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'cancelled'))
);
CREATE UNIQUE INDEX one_active_seat
  ON reservations (tenant_id, seat_id)
  WHERE status IN ('pending', 'confirmed');

BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE;
INSERT INTO reservations (tenant_id, seat_id, status)
VALUES (10, 7, 'pending');
COMMIT;
~~~

É exemplo PostgreSQL, não SQL executado pelo CI Python do manual. Pressupõe que assentos são únicos **dentro de cada tenant**; se um assento físico é compartilhado entre tenants, a chave precisa representar identidade global. Se a aplicação gera evento outbox, persista-o na mesma transação local e use idempotência durável para chamadas repetidas.

## Modelo lógico executável

A função testa a **seleção de chaves**, não locking ou execução transacional SQL. Trata pending e confirmed como ativos. O banco real continua sendo a fonte autoritativa.

~~~python
ATIVOS = {"pending", "confirmed"}

def chaves_ativas(reservas):
    chaves = set()
    for linha in reservas:
        if linha["status"] not in ATIVOS:
            continue
        chave = (linha["tenant"], linha["seat"])
        if chave in chaves:
            return None
        chaves.add(chave)
    return chaves

validas = [
    {"tenant":10, "seat":7, "status":"pending"},
    {"tenant":10, "seat":7, "status":"cancelled"},
    {"tenant":11, "seat":7, "status":"confirmed"},
]
assert chaves_ativas(validas) == {(10, 7), (11, 7)}
assert chaves_ativas(validas + [
    {"tenant":10, "seat":7, "status":"confirmed"}
]) is None
~~~

Para clientes concorrentes reais, execute testes no banco com conexões separadas e barreira que faça ambas tentarem o mesmo invariante simultaneamente. Checks sequenciais de um set Python não reproduzem timing, locks, conflitos de constraint ou serialization failure do servidor.

## Custos e manutenção de índices

Índices usam espaço, banda de WAL e CPU nas escritas. UPDATE pode produzir versão nova e exigir manutenção dos índices conforme valores indexados e condições para HOT update. Index-only scan depende de cobertura dos dados **e** de informações do mapa de visibilidade, não de a consulta simplesmente citar coluna indexada [2]. Um índice seletivo melhora leitura, mas pode concentrar contenção de chave popular.

Escolha índice único para identidades duráveis do domínio e índices comuns segundo planos e carga medidos. Indexar todas as colunas não é solução universal: acompanhe taxa de inserção, vacuum, splits de página e volume de backup.

## Retry, idempotência e opções de isolamento

Falhas de serialização podem ocorrer normalmente em Serializable, especialmente sob disputa. Retry deve repetir toda a lógica num snapshot novo. **Não** faça cobrança externa sem idempotência dentro de transação que pode ser repetida, salvo existência de contrato seguro e reconciliação no provedor. Repetir depois de violação de unicidade pode significar que outro cliente reservou o assento, não falha transitória a tentar indefinidamente.

| Exigência | Mecanismo | Limite |
| --- | --- | --- |
| Sem assento ativo duplicado por tenant | Índice único parcial | Predicado/chave devem refletir negócio |
| Evitar write skew | Serializable ou locks corretos | Retry e contenção |
| Leitura seletiva rápida | B-tree | Visibilidade e custo continuam importando |
| Cobrança externa única | Idempotência durável no provedor e domínio | SQL local isoladamente não resolve |

## Exercícios e verificação

1. Mostre duas transações read-then-insert que observam ausência; explique qual constraint impede commits duplicados.
2. Mude unicidade para assentos globais e identifique chave correta.
3. Explique write skew entre duas linhas sem disputa direta de chave única.
4. Por que serialization failure exige repetir a **transação inteira**, não só o último UPDATE?
5. Desenhe testes concorrentes de integração provando unicidade ativa, rejeição de duplicatas e retry seguro.

**Capítulos relacionados:** [Consistência](/pt/topics/database-consistency/), [Armazenamento/MVCC](/pt/topics/database-storage-wal/) e [Planejamento SQL](/pt/topics/sql-query-planning/) explicam facetas diferentes da transação.
