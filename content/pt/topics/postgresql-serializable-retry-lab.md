---
id: postgresql-serializable-retry-lab
title: "Laboratório Serializable PostgreSQL: write skew e retries completos"
description: "Reproduza write skew real no PostgreSQL, evite com SERIALIZABLE e repita integralmente a transação abortada."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [postgresql-concurrency-integration, transactional-indexing-isolation]
sources:
  - {title: "PostgreSQL 17 — Transaction Isolation", url: "https://www.postgresql.org/docs/17/transaction-iso.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Serialization Failure Handling", url: "https://www.postgresql.org/docs/17/mvcc-serialization-failure-handling.html", kind: "official database documentation"}
  - {title: "PostgreSQL 17 — Explicit Locking and Deadlocks", url: "https://www.postgresql.org/docs/17/explicit-locking.html", kind: "official database documentation"}
---
Uma transação pode proteger cada linha individualmente e ainda violar **invariante de negócio que envolve várias linhas**. O exemplo clássico é **write skew**: dois médicos estão de plantão e cada um pode sair se pelo menos outro continuar. Ambos leem estado inicial igual e atualizam **linhas diferentes**, permitindo que saiam sem conflito direto de escrita. Esta oficina demonstra a anomalia em PostgreSQL real, depois executa o mesmo cenário em **SERIALIZABLE** e repete integralmente a transação rejeitada [1][2].

## Regra e hipóteses de isolamento

A tabela `oncall(doctor PRIMARY KEY, active BOOLEAN)` começa com A=true e B=true. Uma operação `leave(médico)` precisa preservar **pelo menos um médico ativo**. Cada operação consulta quantidade de ativos, verifica se é maior que um e, em caso positivo, desativa sua própria linha. Resultado bem-sucedido exige **commit**; transação abortada não pode declarar sucesso.

Dois clientes usam conexões independentes. Em READ COMMITTED do PostgreSQL, cada SELECT observa snapshot no início da instrução. Se ambas as leituras ocorrem antes dos UPDATEs, as duas veem dois médicos. Como atualizam linhas diferentes, ambas podem confirmar apesar de quebrar **invariante global** [1].

## Force duas leituras antes de atualizar

O código [postgres_serializable_lab.py](https://github.com/christianrss/manual/blob/main/examples/python/postgres_serializable_lab.py) aceita `threading.Barrier` opcional. O teste integrado inicia duas threads com **conexões PostgreSQL independentes**, exigindo que cada SELECT finalize antes que qualquer worker inicie UPDATE. É coordenação determinística de um escalonamento problemático, não suposição de que teste aleatório acabará encontrando a corrida.

![Duas transações veem dois médicos ativos e desativam linhas diferentes; Serializable aborta uma.](/diagrams/postgresql-write-skew.svg)

~~~python
def avaliar_snapshot(quantidade_ativa):
    if quantidade_ativa <= 1:
        return "negado"
    return "pode_sair"

assert avaliar_snapshot(2) == "pode_sair"
assert avaliar_snapshot(1) == "negado"
assert avaliar_snapshot(0) == "negado"
~~~

A função pura **não resolve concorrência**: executá-la duas vezes com mesma contagem obsoleta de dois autoriza ambas. O problema é a consistência entre leituras e escritas posteriores de transações concorrentes.

## Observe write skew em READ COMMITTED

O primeiro teste usa READ COMMITTED. Após liberar a barreira, A grava sua linha false e B grava a outra false. Não há conflito direto sobre mesma linha; as duas confirmações podem ocorrer. O teste afirma duas respostas `left` **e zero médicos ativos**, registrando falha esperada do invariante.

Esse resultado mostra limitação do isolamento escolhido, **não defeito do banco**. READ COMMITTED tem comportamento documentado; a aplicação pediu garantia insuficiente para uma regra que depende de múltiplas linhas [1].

## Previna com SERIALIZABLE

SERIALIZABLE no PostgreSQL pretende fazer o efeito equivaler a alguma ordem serial. Numa ordem serial, a primeira saída deixaria um médico ativo e a segunda deveria negar. Diante das duas leituras concorrentes forçadas, o mecanismo serializável identifica dependências problemáticas e aborta uma transação com SQLSTATE **40001**, `serialization_failure` [1][2].

O teste exige uma operação confirmada e outra com 40001, mantendo exatamente um médico em plantão. Não presume **qual** médico vence. PostgreSQL pode escolher vítimas conforme conflitos e não se deve depender da mensagem textual ou da identidade do abortado.

## Repita a decisão completa, não apenas UPDATE

A documentação oficial exige executar **toda a transação novamente**, inclusive decisões que determinam SQL e valores, após serialization failure [2]. Refazer somente UPDATE reutilizaria lógica obsoleta e violaria o invariante. Nova transação consulta médicos ativos e, encontrando um, nega a segunda saída.

~~~python
SQLSTATE_REPETIVEL = {"40001", "40P01"}

def repetir_erro(codigo, tentativas, maximo):
    return codigo in SQLSTATE_REPETIVEL and tentativas < maximo

assert repetir_erro("40001", 1, 3)
assert repetir_erro("40P01", 1, 3)
assert not repetir_erro("23505", 1, 3)
assert not repetir_erro("40001", 3, 3)
~~~

O `retry_off_call` publicado cria conexão e transação novas para cada tentativa, com **limite definido**. Serviço real precisa deadline global, jitter adequado entre tentativas, métrica de exaustão e identidade idempotente para operações externas. O exemplo evita sleeps para manter teste de integração rápido e determinístico.

## Deadlock difere de write skew

SQLSTATE **40P01** indica deadlock. Ele ocorre quando transação A segura lock da linha X e espera Y, enquanto B segura Y e espera X. PostgreSQL detecta ciclo e aborta uma transação [3]. Ordem consistente de locks é uma defesa importante; retries limitados da transação completa podem ser necessários.

O cenário dos médicos, porém, atualiza **linhas diferentes**. Não se corrige só adquirindo lock aleatório na própria linha de cada médico. A regra abrange *conjunto* de médicos, portanto é preciso serializar ou proteger essa regra, por exemplo mediante linha guardiã compartilhada, lock de exclusão definido pela aplicação ou SERIALIZABLE com retries corretos.

## Concorrência, performance e limites operacionais

Isolamento mais forte tem custo operacional. SERIALIZABLE pode abortar e exigir retries sob contenção, afetando vazão e latência de cauda. Manter transação aberta enquanto espera usuário ou serviço de rede é especialmente prejudicial: prolonga locks e dificulta raciocínio sobre repetição.

| Observação | Interpretação | Próxima ação |
| --- | --- | --- |
| Duas saídas no READ COMMITTED | Write skew do schedule forçado | Proteger regra global |
| Uma transação SERIALIZABLE aborta | SSI bloqueou commit anômalo | Refazer decisão completa |
| Muitos 40001 | Conflitos ou carga elevada | Medir e ajustar |
| 40P01 | Deadlock, possível ordem de locks | Inspecionar grafo de locks |
| 23505 | Violação de chave única | Verificar conflito de negócio |

CI verde demonstra escalonamento escolhido num servidor PostgreSQL. **Não** certifica failover de replicação, partições de rede, todas as intercalações nem ausência de starvation. Declarar essa limitação faz parte da engenharia de produção.

## Exercícios e verificação

1. Escreva sequência READ COMMITTED que deixa zero médicos apesar de ambas as chamadas terem sucesso.
2. Explique por que os UPDATEs não disputam a mesma linha.
3. Demonstre por que repetir só UPDATE ignora decisão de elegibilidade agora inválida.
4. Substitua SERIALIZABLE por lock de linha guardiã compartilhada e discuta ponto de contenção.
5. Projete métricas de 40001, 40P01, tentativas por transação, p99 e exaustão de retries.

**Capítulos relacionados:** [Isolamento](/pt/topics/transactional-indexing-isolation/), [oficina de concorrência](/pt/topics/concurrency-interview-workshop/), [laboratório PostgreSQL](/pt/topics/postgresql-concurrency-integration/) e [model checking](/pt/topics/formal-model-checking/) aprofundam conceitos [1][2][3].
