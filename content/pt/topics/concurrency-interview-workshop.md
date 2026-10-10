---
id: concurrency-interview-workshop
title: "Oficina de concorrência: corridas, CAS e intercalações"
description: "Derive uma corrida de duas reservas, corrija com CAS versionado, enumere sequências e teste sincronização entre threads."
category: engineering
difficulty: advanced
updated: 2026-10-09
prerequisites: [concurrency-synchronization, testing-strategies]
sources:
  - {title: "Python threading — Lock, Barrier and synchronization", url: "https://docs.python.org/3/library/threading.html", kind: "official Python documentation"}
  - {title: "PostgreSQL — Transaction Isolation", url: "https://www.postgresql.org/docs/current/transaction-iso.html", kind: "official database documentation"}
---
**Exercícios de concorrência** verificam invariantes sob diferentes ordens de execução, não a capacidade de decorar nomes de locks. Uma solução correta declara qual operação é atômica, o que os outros workers observam e qual modelo de falha suporta. Esta oficina estuda **reserva de um único assento**, começando com protocolo defeituoso de leitura e escrita, depois com versão otimista e operações locais protegidas. Threads do Python não dispensam sincronização em mudanças compostas de estado [1].

## Contrato e operações concorrentes

Existe um assento inicialmente `livre` e dois compradores, A e B. Uma chamada reserve(cliente) bem-sucedida retorna sucesso e registra o cliente como proprietário. Após reservado, outro comprador não consegue reservar. O invariante é **no máximo um vencedor**. Defina falhas: todas as tentativas após a primeira reserva retornam falso, inclusive repetição pelo mesmo cliente; permitir retry idempotente do titular exigiria outro contrato.

Diferencie *segurança* (nunca dois vencedores), *progresso* (uma operação em espera pode eventualmente concluir sob hipóteses de escalonamento) e *durabilidade* (decisão confirmada sobrevive a determinadas falhas). Mutex Python protege segurança entre threads no mesmo processo, mas não durabilidade nem réplicas independentes. Uma autoridade de banco exige atualização condicional atômica [2].

## Reproduza uma corrida sem depender do relógio

Uma rotina errada executa `ler dono`, confere livre e `gravar cliente`. Leituras e escritas individualmente corretas não tornam o conjunto atômico. Se A lê livre, B lê livre, A grava A e anuncia sucesso e B grava B e anuncia sucesso, ambos receberam confirmação. O valor final B não revela que A também foi informado de que venceu.

![Dois workers leem estado livre antes de gravar; um commit condicional permite só um vencedor.](/diagrams/concurrency-interview-schedule.svg)

Represente essa ordem diretamente, sem apostar no escalonador. Um cenário determinístico comprova que há uma corrida no modelo; não é teste estatístico de stress.

~~~python
def sequencia_defeituosa(passos):
    dono = None
    observado = {}
    vitorias = []
    for worker, fase in passos:
        if fase == "read":
            observado[worker] = dono
        elif fase == "commit":
            if observado[worker] is None:
                dono = worker
                vitorias.append(worker)
        else:
            raise ValueError("fase desconhecida")
    return dono, vitorias

corrida = [("A", "read"), ("B", "read"), ("A", "commit"), ("B", "commit")]
dono_final, sucessos = sequencia_defeituosa(corrida)
assert dono_final == "B" and sucessos == ["A", "B"]
~~~

O modelo dá a cada worker sua leitura capturada e não afirma que todo banco permite essa sobrescrita em qualquer nível de isolamento. O propósito é expor a ausência da operação atômica **verificar e escrever**.

## Corrija com comparação de versão

Uma escrita condicional compara versão antiga e muda proprietário **num único passo atômico**. Numa autoridade com compare-and-swap (CAS), só um escritor concorrente altera versão zero para um. O outro não pode anunciar sucesso. Demonstração Python local serializa essa operação com Lock, que só coordena threads compartilhando o mesmo objeto.

~~~python
from threading import Lock

class Assento:
    def __init__(self):
        self._dono = None
        self._versao = 0
        self._lock = Lock()

    def ler(self):
        with self._lock:
            return self._dono, self._versao

    def reservar_se_versao(self, cliente, esperada):
        if not cliente:
            raise ValueError("cliente obrigatorio")
        with self._lock:
            if self._versao != esperada or self._dono is not None:
                return False
            self._dono = cliente
            self._versao += 1
            return True

assento = Assento()
assert assento.ler() == (None, 0)
assert assento.reservar_se_versao("A", 0)
assert not assento.reservar_se_versao("B", 0)
assert not assento.reservar_se_versao("A", 1)
assert assento.ler() == ("A", 1)
~~~

O ponto de linearização é a transição protegida em `reservar_se_versao`. Enquanto o lock permanece adquirido, versão e proprietário mudam como operação sincronizada local. Verificar `dono is None` importa porque outra versão poderia resultar de liberação num modelo maior, sem autorizar nova reserva indevida. Em banco, equivalente é UPDATE condicional ou constraint única protegida por transação adequada.

## Enumere as intercalações legais

Para dois workers com `read` seguido de `commit`, só são legais schedules que mantêm **ordem local** de cada worker. Existem seis intercalações distintas de duas sequências de dois passos. O modelo corrigido verifica segurança em todas, não apenas na ordem que causou o defeito. Aqui o commit condicional é um único passo atômico.

~~~python
from itertools import combinations

def todas_sequencias():
    for pos_a in combinations(range(4), 2):
        a = iter(("read", "commit"))
        b = iter(("read", "commit"))
        yield [(("A", next(a)) if i in pos_a
                else ("B", next(b))) for i in range(4)]

def modelo_protegido(passos):
    dono = None
    versao = 0
    leituras = {}
    sucessos = []
    for worker, operacao in passos:
        if operacao == "read":
            leituras[worker] = versao
        elif operacao == "commit":
            if dono is None and leituras[worker] == versao:
                dono = worker
                versao += 1
                sucessos.append(worker)
    return dono, sucessos

sequencias = list(todas_sequencias())
assert len(sequencias) == 6
assert all(len(modelo_protegido(s)[1]) == 1 for s in sequencias)
assert any(len(sequencia_defeituosa(s)[1]) == 2 for s in sequencias)
~~~

É **teste de estados finitos** num modelo restrito a dois trabalhadores e duas operações. Não prova liveness nem segurança de qualquer programa concorrente. Em um sistema maior, adicione retries, liberações, crashes e partições de rede ao espaço de estados. O crescimento combinatório exige abstrações e limites cuidadosos ao usar model checking.

## Exercite threads reais sem depender de corrida aleatória

Teste de stress pode ajudar, mas passar não prova ausência de race. Use Barrier para iniciar vários workers juntos, execute o método sincronizado e confira o resultado. A barreira aproxima os começos, mas **não força todas as intercalações**; a exploração explícita acima cobre de modo determinístico o cenário escolhido [1].

~~~python
from threading import Barrier, Thread

compartilhado = Assento()
barreira = Barrier(4)
resultados = []

def tentar(nome):
    _, versao = compartilhado.ler()
    barreira.wait()
    resultado = compartilhado.reservar_se_versao(nome, versao)
    resultados.append(resultado)

threads = [Thread(target=tentar, args=(nome,))
           for nome in ("A", "B", "C", "D")]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join(timeout=5)
assert not any(thread.is_alive() for thread in threads)
assert resultados.count(True) == 1
assert compartilhado.ler()[0] in ("A", "B", "C", "D")
~~~

A lista `resultados` reúne retornos após chamadas; a garantia central está na alteração protegida do objeto. Para estoque ou pagamentos, teste deve usar conexões/processos distintos e autoridade real. Threads Python e um Lock não reproduzem conflito distribuído nem validam isolamento do banco.

## Deadlocks, progresso e justiça

Exclusão mútua resolve a perda de atualização, mas pode gerar deadlock se recursos são adquiridos em ordens diferentes. Worker A segura lock de conta esperando estoque; B segura estoque esperando conta; forma-se ciclo. Quebre-o por ordem global de aquisição, redução de regiões críticas ou aquisição limitada com recuperação. Timeout de lock sozinho não reverte efeitos já executados.

Um lock também não garante **justiça**. A documentação Python informa que a escolha da thread bloqueada que adquire um lock liberado é indefinida [1]. Sob contenção, uma thread pode esperar excessivamente mesmo com segurança preservada. Não confunda starvation com deadlock; acompanhe espera separadamente do tempo em serviço.

## Quando lock local é a ferramenta errada

| Cenário | Fronteira de correção | O que mutex não fornece |
| --- | --- | --- |
| Threads no mesmo processo | Objeto Assento compartilhado | Durabilidade após crash |
| Várias instâncias de API | Banco transacional | Coordenação entre processos |
| Várias regiões | Líder/quorum ou autoridade definida | Partição e failover |
| PSP externo | Idempotência do provedor e reconciliação | Commit atômico entre sistemas |
| Consumidores de fila | Claim/lease e deduplicação duráveis | Replay e recuperação |

Exatamente uma reserva local pode ser garantida por autoridade única, mas efeitos externos **exatamente uma vez** precisam de hipóteses mais fortes. Identidades idempotentes e estado durável distinguem retentativas quando a resposta se perde.

## Exercícios e verificação

1. Desenhe as seis intercalações legais e encontre aquelas em que o modelo defeituoso devolve dois sucessos.
2. Explique qual instrução representa o ponto de linearização no Assento corrigido.
3. Acrescente `release` e identifique por que uma versão antiga não pode vencer após liberação e nova reserva (problema ABA).
4. Compare Lock de processo com UPDATE condicional para três réplicas sem estado da API.
5. Desenhe deadlock de dois locks e proponha ordem global que elimina o ciclo.

**Capítulos relacionados:** [Concorrência](/pt/topics/concurrency-synchronization/), [ordem de memória](/pt/topics/memory-ordering-atomics/), [verificação formal](/pt/topics/formal-model-checking/) e [isolamento transacional](/pt/topics/transactional-indexing-isolation/) aprofundam garantias [1][2].
