---
id: mlfq-priority-inheritance
title: "Escalonamento por prioridades: MLFQ, aging e herança de prioridade"
description: "Analise escalonamento MLFQ, boost periódico, starvation e inversão de prioridades com modelos de CPU e locks verificáveis."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [cpu-scheduling-fcfs-round-robin, concurrency-synchronization]
sources:
  - {title: "Operating Systems: Three Easy Pieces — Multi-Level Feedback Queue", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf", kind: "primary university textbook chapter"}
  - {title: "Linux kernel — RT-mutex implementation design", url: "https://docs.kernel.org/locking/rt-mutex-design.html", kind: "official operating system design"}
  - {title: "Linux kernel — EEVDF Scheduler", url: "https://docs.kernel.org/scheduler/sched-eevdf.html", kind: "official current scheduler documentation"}
  - {title: "Python documentation — deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official standard library"}
---
O escalonador escolhe uma tarefa pronta. No capítulo anterior de [FCFS e Round Robin](/pt/topics/cpu-scheduling-fcfs-round-robin/), a seleção depende da ordem de chegada e da rotação por quantum. Em cargas reais, surge outra dificuldade: tarefas interativas precisam de resposta rápida, mas o sistema operacional normalmente **não conhece antecipadamente** a duração do próximo burst de CPU. Uma **fila multinível com realimentação (MLFQ)** ajusta prioridades observando o consumo da CPU. **Herança de prioridade** é outro mecanismo: responde ao bloqueio de tarefa prioritária por um mutex detido por tarefa menos prioritária [1][2].

O capítulo apresenta **dois modelos limitados e separadamente testáveis**: MLFQ com três níveis e tarefas CPU-bound, e propagação de prioridade num grafo finito de dependências de locks. Nenhum equivale a implementação do Linux ou prova requisitos de tempo real. O escalonamento comum do Linux evoluiu para **EEVDF** e não deve ser descrito como MLFQ clássico [3].

## Classes de prioridade e realimentação

Num escalonador de prioridade fixa, executa-se uma tarefa da classe pronta de maior prioridade. Quando várias possuem a mesma classe, outra política—como Round Robin—estabelece a ordem. Prioridade fixa não deduz automaticamente quais tarefas são interativas ou consumidoras intensivas de CPU.

O **MLFQ** modifica o nível conforme o histórico de execução: tarefas novas entram na fila mais alta; quem consome integralmente a concessão de CPU desce de nível; tarefas de níveis inferiores executam quando as filas superiores estão vazias. O tratamento de OSTEP apresenta **promoção global periódica** contra starvation e contabilização acumulada de CPU para que yield voluntário imediatamente antes do fim do quantum não burle o rebaixamento [1].

| Aspecto | Incluído no modelo | Fora do modelo |
| --- | --- | --- |
| Processadores | Uma CPU e uma tarefa por tick | Migração multicore e utilização |
| Carga | Trabalho finito, sem I/O | Bloqueio, wake-up e heurísticas de interatividade |
| Prioridades | Três filas, nível 0 maior | Classes reais do Linux e nice |
| Quantum | Quantidade positiva por nível | Temporizador físico |
| Promoção | Reset global periódico opcional | Justiça garantida do kernel |
| Troca de contexto | Custo zero | Cache/TLB, interrupções e locks |

**Vocabulário:** *prioridade* define precedência; *quantum* delimita concessão; *allotment* contabiliza o serviço antes de rebaixar; *aging* amplia a oportunidade de execução de quem aguarda muito. O **boost global periódico** implementado aqui é uma técnica contra starvation, mas **não** é um algoritmo de aging individual por tempo de espera [1].

## Contrato temporal e regras de desempate

Os instantes discretos começam em zero. Cada tarefa possui nome único não vazio, chegada inteira não negativa e trabalho de CPU inteiro estritamente positivo. Chegadas simultâneas respeitam a ordem de entrada. A fila 0 tem maior prioridade. Quanta padrão: `(1, 2, 4)`; após esgotar a concessão no último nível, a tarefa permanece nele. Uma tarefa preemptada por nova prioridade superior **conserva sua parcela do quantum já consumida**.

Cada tick executa, nesta ordem:

1. Se o instante positivo é múltiplo de `boost_interval`, promova todas as tarefas prontas e a que estava executando à fila 0. Percorra filas existentes da maior para a menor, em ordem FIFO; coloque a antiga tarefa em execução **por último** e zere a contabilização de quantum. Intervalo zero desativa o boost.
2. Admita novas tarefas cujo instante de chegada já foi atingido.
3. Se alguma fila superior tiver trabalho pronto, preempte a tarefa atual, colocando-a **na frente de seu nível original**, conservando a contabilização parcial; caso contrário, continue.
4. Escolha a primeira tarefa da fila de maior prioridade disponível e execute **um tick**.
5. Conclusão retira a tarefa; esgotamento de quantum a rebaixa, no máximo um nível, inserindo-a ao fim e reiniciando o orçamento daquele nível.

Quando boost e chegada coincidem, a **promoção acontece antes da admissão**. Mudar essa ordem ou inserir a tarefa preemptada no fim pode alterar resultados. São convenções explícitas desta implementação didática, não regras universais do kernel.

## MLFQ executável de três níveis

O simulador devolve uma **tupla de proprietários da CPU a cada tick**; `None` indica CPU ociosa. Ao contrário do Round Robin orientado a eventos, aqui inspecionamos filas por instante para tornar visíveis preempção, promoção e rebaixamento. A `deque` fornece operações eficientes nas extremidades da fila [4].

~~~python
from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True)
class Task:
    name: str
    arrival: int
    work: int

def mlfq(tasks, quanta=(1, 2, 4), boost_interval=0):
    items = tuple(tasks)
    if (not isinstance(quanta, tuple) or len(quanta) != 3
            or any(type(q) is not int or q <= 0 for q in quanta)):
        raise ValueError("three positive integer quanta required")
    if type(boost_interval) is not int or boost_interval < 0:
        raise ValueError("invalid boost interval")
    seen = set()
    for item in items:
        if (not isinstance(item, Task) or not isinstance(item.name, str)
                or not item.name.strip() or item.name != item.name.strip()
                or item.name in seen or type(item.arrival) is not int
                or item.arrival < 0 or type(item.work) is not int
                or item.work <= 0):
            raise ValueError("invalid task")
        seen.add(item.name)

    arrivals = sorted(enumerate(items), key=lambda p: (p[1].arrival, p[0]))
    remaining = {task.name: task.work for task in items}
    levels = {task.name: 0 for task in items}
    used = {task.name: 0 for task in items}
    queues = [deque() for _ in range(3)]
    time = cursor = finished = 0
    current = None
    trace = []

    while finished < len(items):
        if boost_interval and time > 0 and time % boost_interval == 0:
            order = [name for queue in queues for name in queue]
            if current is not None:
                order.append(current)
            queues = [deque(order), deque(), deque()]
            for name in order:
                levels[name] = used[name] = 0
            current = None

        while cursor < len(arrivals) and arrivals[cursor][1].arrival <= time:
            queues[0].append(arrivals[cursor][1].name)
            cursor += 1

        if current is not None and any(
                queues[i] for i in range(levels[current])):
            queues[levels[current]].appendleft(current)
            current = None

        if current is None:
            for queue in queues:
                if queue:
                    current = queue.popleft()
                    break
        if current is None:
            trace.append(None)
            time += 1
            continue

        trace.append(current)
        remaining[current] -= 1
        used[current] += 1
        if remaining[current] == 0:
            finished += 1
            current = None
        elif used[current] == quanta[levels[current]]:
            levels[current] = min(levels[current] + 1, 2)
            used[current] = 0
            queues[levels[current]].append(current)
            current = None
        time += 1
    return tuple(trace)

assert mlfq((Task("A", 0, 6),)) == ("A",) * 6
assert mlfq((Task("A", 0, 7), Task("B", 2, 2))) == (
    "A", "A", "B", "A", "B", "A", "A", "A", "A"
)
assert mlfq((Task("A", 5, 2),)) == (
    None, None, None, None, None, "A", "A"
)
~~~

No exemplo com duas tarefas, A consome a primeira concessão de prioridade máxima no tick 0 e começa a consumir o orçamento do segundo nível. B chega em t=2 e toma a fila mais alta. A retoma o **orçamento restante do nível anterior** quando a fila superior esvazia. A quantidade de trabalho de A não é modificada por B: muda apenas a ordem de CPU. Uma tarefa que chega em t=5 produz cinco entradas `None` antes de executar.

**Invariante:** cada tarefa já admitida e inacabada aparece **uma única vez**—ou como `current`, ou em uma das filas. Seu trabalho restante somado aos ticks já executados é igual ao trabalho inicial. Cada tick de execução reduz a soma dos trabalhos restantes em uma unidade. Níveis e orçamentos permanecem nos limites válidos. Boost, chegada e rebaixamento preservam essas condições; portanto cargas finitas de trabalho positivo terminam sob este simulador.

Com `n` tarefas, `T` ticks transcorridos (incluindo ociosidade) e `B` instantes de boost, ordenar chegadas custa `O(n log n)`. Em um tick comum consultamos até três filas, custo total `O(T)`; em um boost podemos percorrer até `n` tarefas. O limite superior é `O(n log n + T + nB)`, com memória `O(n+T)` incluindo o cronograma. É custo **deste código Python**, não custo do kernel. Chegadas em instantes muito distantes tornam simulação por tick menos eficiente que uma versão orientada a eventos.

## Starvation, promoções e limites de justiça

Sem boosts, tarefa de prioridade inferior pode aguardar repetidamente enquanto chega trabalho de prioridade maior. Elevar individualmente quem espera demais (**aging**) e devolver periodicamente todas as tarefas à fila superior (**boost global**) são estratégias relacionadas, mas distintas. O livro OSTEP utiliza a promoção periódica contra starvation e para adaptar o escalonador a mudanças de comportamento da tarefa [1].

Neste modelo, um conjunto finito de bursts positivos termina até mesmo sem promoção. Isso **não** comprova espera limitada com chegadas potencialmente infinitas. Se tarefas entram indefinidamente ou podem bloquear, garantias de progresso e justiça exigem hipóteses adicionais. O boost aumenta a oportunidade das filas inferiores, mas sua eficácia depende de frequência, regra de desempate e carga. Não deduza deadline de poucos cronogramas favoráveis.

Há ainda o **gaming**: políticas que apagam o orçamento de uma tarefa sempre que ela entrega voluntariamente a CPU pouco antes do limite permitem que ela se mantenha indefinidamente na fila superior. O exemplo **não modela I/O nem yield voluntário**; não podemos afirmar que os testes demonstram resistência a essa estratégia. A contabilização parcial é preservada na **preempção por prioridade**. Suportar yields exigiria estados blocked/ready e conservação dos allotments através dessas transições [1].

## Inversão de prioridades: problema distinto com mutexes

Uma tarefa L de prioridade baixa possui um mutex. A tarefa H, de prioridade elevada, precisa desse mutex e fica **bloqueada**. Uma tarefa M de prioridade intermediária pode preemptar L repetidamente, impedindo L de liberar o recurso necessário a H. H acaba indiretamente atrasada por M, apesar de ser mais prioritária. Trata-se de **inversão de prioridades**. Colocar H na frente da fila de prontos não resolve, pois H **não está pronta** enquanto espera pelo mutex [2].

A **herança de prioridade** eleva temporariamente a prioridade efetiva do detentor à do maior solicitante bloqueado. Com bases L=1, M=2 e H=3 (quanto **maior**, mais prioridade **neste modelo**), L passa temporariamente a 3 ao bloquear H. Se L também espera por um mutex de X, a herança se **propaga transitivamente** a X. Quando a espera deixa de existir, é necessário recalcular as prioridades a partir dos valores base, para evitar promoções permanentes [2].

O Linux rt-mutex utiliza estruturas próprias de waiters, mecanismos de locking e propagação de cadeia; o código abaixo **não implementa esses mecanismos**. Apenas calcula ranks efetivos num grafo de espera estável, finito e **acíclico**.

## Propagação de prioridade executável

`blocked_on` mapeia cada tarefa bloqueada para o detentor do lock aguardado. Nesta representação, cada tarefa pode esperar por um único detentor. Referências inexistentes e ciclos são rejeitados: doação de prioridade não resolve deadlock. Prioridades precisam ser inteiros não negativos; `bool` não é aceito como inteiro válido.

~~~python
def effective_priorities(base, blocked_on):
    if (not isinstance(base, dict) or not base
            or any(not isinstance(name, str) or not name
                   or type(priority) is not int or priority < 0
                   for name, priority in base.items())):
        raise ValueError("invalid base priorities")
    if (not isinstance(blocked_on, dict)
            or any(waiter not in base or owner not in base or waiter == owner
                   for waiter, owner in blocked_on.items())):
        raise ValueError("invalid wait graph")

    for origin in base:
        seen = set()
        node = origin
        while node in blocked_on:
            if node in seen:
                raise ValueError("deadlock cycle is outside this model")
            seen.add(node)
            node = blocked_on[node]

    effective = dict(base)
    for _ in range(len(base)):
        changed = False
        for waiter, owner in blocked_on.items():
            if effective[owner] < effective[waiter]:
                effective[owner] = effective[waiter]
                changed = True
        if not changed:
            break
    return effective

base = {"L": 1, "M": 2, "H": 3, "X": 0}
assert effective_priorities(base, {"H": "L"}) == {
    "L": 3, "M": 2, "H": 3, "X": 0}
assert effective_priorities(base, {"H": "L", "L": "X"}) == {
    "L": 3, "M": 2, "H": 3, "X": 3}
assert effective_priorities(base, {}) == base
assert base["L"] == 1
try:
    effective_priorities(base, {"H": "L", "L": "H"})
except ValueError:
    pass
else:
    raise AssertionError("wait cycle must not be silently accepted")
~~~

**Invariante:** após cada passagem, a prioridade efetiva de um detentor não é inferior às bases dos solicitantes cuja doação já alcançou esse detentor; prioridades só aumentam e nunca superam a maior prioridade base. Como o grafo não tem ciclos, qualquer cadeia possui até `n−1` arestas; `n` passagens de relaxamento bastam. Esta implementação direta custa até `O(n²)` nas verificações de ciclos e `O(n×e)` na propagação, com `e` relações de espera. Transparência didática não justifica executá-la num caminho crítico real de mutex do kernel.

Cada chamada recalcula a herança do zero. Ao retirar H→L, L volta a prioridade 1 se nenhum outro solicitante doar. A função **não** obtém ou libera locks, não seleciona a próxima tarefa, não implementa exclusão mútua, não resolve deadlock nem estabelece deadlines. É um **contrato de propagação**, não um rt-mutex.

## Diferença entre MLFQ, herança e Linux atual

O MLFQ utiliza consumo de CPU como heurística para decidir **qual tarefa pronta executar**. Herança de prioridade tenta permitir que **o detentor de um recurso execute para liberar a tarefa prioritária bloqueada**. Um não substitui o outro.

O Linux suporta classes distintas de escalonamento e mecanismos especializados de locks de tempo real. Sua documentação de EEVDF descreve lag e deadlines virtuais para seleção justa: não corresponde às três filas FIFO implementadas aqui [3]. A herança em mutexes reais também precisa integrar política de escalonamento, propriedade do lock e estados bloqueados, e não apenas atribuir inteiros num dicionário [2].

## Exercícios e verificação

1. Trace A(chegada 0, trabalho 7), B(chegada 2, trabalho 2) com quanta `(1,2,4)`, explicando cada preempção e mudança de nível.
2. Use `boost_interval=3` e determine a fila quando boost e nova chegada coincidem.
3. Substitua boost por **aging individual por tempo de espera**; defina relógio, limite, empates e invariantes antes de programar.
4. Acrescente eventos de bloqueio e mostre como conservar allotments em yields voluntários para impedir gaming.
5. Derive o limite `O(n log n+T+nB)`; construa caso em que um grande intervalo ocioso domina o tempo da simulação.
6. Calcule prioridades efetivas em H→L→X e comprove que retirar H→L elimina doações a L e X.
7. Explique por que ciclos no grafo de espera representam **deadlock**, não uma falha corrigível por doação de prioridades.
8. Compare a seleção por deadline virtual do Linux EEVDF com o MLFQ didático e identifique diferenças de estruturas e hipóteses [3].

**Continuidade:** [Concorrência e sincronização](/pt/topics/concurrency-synchronization/) introduz contratos de locks; [FCFS e Round Robin](/pt/topics/cpu-scheduling-fcfs-round-robin/) estabelece as métricas básicas. Medição real de troca de contexto, escalonamento por deadline e cargas com I/O ficam para estudos separados.
