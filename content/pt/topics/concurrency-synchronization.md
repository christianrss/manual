---
id: concurrency-synchronization
title: "Concorrência: corridas, locks, condições e deadlocks"
description: "Deduza invariantes de sincronização, seções críticas, condições de corrida, variáveis de condição, deadlocks e filas limitadas."
category: foundations
difficulty: advanced
updated: 2026-10-10
prerequisites: [processes-virtual-memory, cpu-scheduling-fcfs-round-robin, testing-maintainability]
sources:
  - {title: "Python documentation — threading", url: "https://docs.python.org/3/library/threading.html", kind: "official documentation"}
  - {title: "Operating Systems: Three Easy Pieces — Concurrency", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
---
**Concorrência** significa que atividades progridem com períodos de vida sobrepostos; **paralelismo** significa executar trabalho no mesmo instante em recursos distintos. Um programa pode ser concorrente com uma CPU por intercalação ou paralelo em vários núcleos. A correção exige definir quais estados compartilhados devem permanecer válidos independentemente da ordem de escalonamento. Criar threads ou usar async não garante segurança [1][2].

O capítulo de [escalonamento](/pt/topics/cpu-scheduling-fcfs-round-robin/) explica como uma tarefa pronta recebe CPU. Este capítulo analisa se os invariantes sobrevivem a diferentes intercalações; justiça de escalonamento não corrige incrementos sem sincronização [1][2].

## Intercalações e condição de corrida

Considere duas threads incrementando contador compartilhado. Conceitualmente, incrementar significa ler valor, somar um e gravar o resultado. Com x=0, escalonamento T1 lê 0, T2 lê 0, T1 grava 1, T2 grava 1: valor final x=1 apesar de duas operações. Ocorreu **lost update**. A possibilidade depende das instruções, modelo de memória e intercalação; inserir sleeps arbitrários não corrige o contrato.

Uma **seção crítica** é uma região que acessa estado compartilhado exigindo atomicidade ou exclusão definida. Um mutex permite apenas um proprietário na região. Locks devem proteger **invariantes**, não variáveis isoladas: consultar saldo e descontá-lo em etapas independentes ainda permite ultrapassar o limite, mesmo que cada leitura e escrita seja atômica isoladamente.

## Data races e ordem de memória

Em linguagens como C/C++, uma data race pode ter consequências graves porque acessos conflitantes não sincronizados podem produzir comportamento indefinido segundo o modelo de memória. Python possui detalhes dependentes de implementação; o GIL em muitas versões de CPython não transforma sequências arbitrárias de leitura-modificação-gravação em transações atomicamente garantidas. Existem ainda variantes de Python sem GIL. Use primitivas documentadas, não o comportamento observado num escalonamento específico [1].

**Happens-before** descreve ordens garantidas por sequência de programa e sincronização em certo modelo de memória. Sem tal relação, threads podem observar escritas em momentos inesperados. Aquisição/liberação de mutex fornece exclusão e mecanismos usuais de visibilidade. Uma flag booleana comum, não sincronizada, pode ser incorreta em linguagens com modelos formais específicos.

## Contador compartilhado correto

~~~python
from threading import Thread, Lock

class Contador:
    def __init__(self):
        self.valor = 0
        self.trava = Lock()

    def somar(self, n):
        for _ in range(n):
            with self.trava:
                self.valor += 1

contador = Contador()
threads = [Thread(target=contador.somar, args=(1000,)) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert contador.valor == 4000
~~~

O ponto de linearização dessa atualização está dentro da seção protegida; todas as threads compartilham o mesmo lock. O teste mostra uma execução, não prova universal contra todos os escalonamentos. O argumento formal exige que todos os acessos relevantes usem a trava; basta um escritor desprotegido para invalidar a garantia. Contenção reduz escalabilidade: mantenha a região crítica tão pequena quanto a correção permite, sem mover checagens para fora da fronteira atômica.

## Variáveis de condição e fila limitada

Uma variável de condição permite que uma thread durma esperando um predicado sobre estado compartilhado. O produtor possui mutex associado ao modificar a fila e **notifica** após tornar uma condição verdadeira. O consumidor espera enquanto o predicado for falso. É essencial que wait libere a trava durante o sono e a readquira antes de retornar, permitindo que produtores executem [1].

![Uma fila limitada transita entre vazia, parcialmente ocupada e cheia.](/diagrams/bounded-queue.svg)

~~~python
from threading import Condition, Thread

class FilaLimitada:
    def __init__(self, capacidade):
        if capacidade <= 0: raise ValueError("capacidade deve ser positiva")
        self.capacidade = capacidade
        self.itens = []
        self.condicao = Condition()

    def colocar(self, item):
        with self.condicao:
            while len(self.itens) == self.capacidade:
                self.condicao.wait()
            self.itens.append(item)
            self.condicao.notify_all()

    def retirar(self):
        with self.condicao:
            while not self.itens:
                self.condicao.wait()
            item = self.itens.pop(0)
            self.condicao.notify_all()
            return item

fila = FilaLimitada(2)
recebidos = []
trabalhador = Thread(target=lambda: recebidos.append(fila.retirar()))
trabalhador.start()
fila.colocar(7)
trabalhador.join(timeout=3)
assert not trabalhador.is_alive() and recebidos == [7]
~~~

Use **while**, não if, ao verificar o predicado: a notificação é convite a conferir novamente, não promessa de que outra thread não retirou o item antes. Notificar não libera imediatamente o lock; a thread despertada precisa readquiri-lo. Uma fila de produção deve oferecer cancelamento, timeout, fechamento e eventualmente condições separadas para cheia/vazia. O exemplo ilustra o protocolo, não pretende otimizar filas.

## Deadlock, livelock e starvation

**Deadlock** ocorre quando tarefas esperam num ciclo por recursos ou condições que as próprias tarefas não liberam. Por exemplo, T1 segura lock A e espera B, enquanto T2 segura B e espera A. Uma regra global de **ordem de aquisição** (sempre A antes de B) impede essa forma de espera circular. Evitar segurar recursos durante espera ou prever abortos pode ser necessário, mas timeouts isolados não consertam protocolos incorretos.

**Livelock** significa continuar tentando ou alterando estado sem progresso útil; **starvation** é espera indefinida de alguma tarefa enquanto outras avançam. Um sistema sem deadlock pode ser injusto. Inversão de prioridade ocorre quando tarefa prioritária aguarda recurso mantido por outra menos prioritária; alguns kernels usam herança de prioridade. Correção e progresso são propriedades distintas: exclusão mútua não assegura conclusão de todos [2].

## Concorrência versus sistemas distribuídos

Lock de processo protege threads daquele processo, não processos em máquinas diferentes. Para pagamentos ou reservas globalmente únicos, imponha invariantes na fonte autoritativa, como restrição única e isolamento transacional apropriado. Locks distribuídos precisam de análise de leases, expiração, fencing tokens e modelo de falhas; trava Redis não se torna automaticamente equivalente a transação durável. Diferencie também E/S assíncrona, que sobrepõe esperas, de paralelismo de CPU em múltiplos núcleos.

## Exercícios e verificação

1. Escreva cronograma explícito de duas threads mostrando duas somas de 1 produzirem resultado 1 em vez de 2.
2. Demonstre por que substituir while por if no buffer é perigoso quando dois consumidores acordam e disputam um item.
3. Desenhe grafo de espera para locks A e B; imponha ordem global e explique por que desaparece a espera circular.
4. Por que um lock único pode serializar todas as operações? Identifique dados particionáveis em travas distintas sem violar invariantes.
5. Amplie a fila com close() e defina o resultado de retirar() quando fechada e vazia; teste se todos os trabalhadores em espera despertam.
