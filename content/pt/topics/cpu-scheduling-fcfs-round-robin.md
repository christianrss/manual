---
id: cpu-scheduling-fcfs-round-robin
title: "Escalonamento de CPU: FCFS, Round Robin, métricas e justiça"
description: "Derive políticas FCFS e Round Robin, preempção, tempo de resposta, espera e turnaround com simuladores e testes independentes."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory]
sources:
  - {title: "Operating Systems: Three Easy Pieces — Scheduling", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "MIT xv6 book — Scheduling", url: "https://mit-pdos.github.io/xv6-riscv-book/sched.html", kind: "university teaching OS reference"}
  - {title: "Python collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official library reference"}
---
O processador executa instruções; o sistema operacional decide **qual thread ou processo pronto recebe tempo de CPU**. Essa decisão equilibra responsividade, vazão e justiça. É diferente do pipeline, que sobrepõe fases das *instruções de máquina*. O capítulo de [processos e memória virtual](/pt/topics/processes-virtual-memory/) apresenta estados e privilégios; agora deduziremos a ordem do escalonamento [1][2].

Os exemplos são **modelos didáticos determinísticos com uma CPU**, não código de kernel xv6 ou benchmark real. Excluem I/O, locks, interrupções, custo de troca de contexto, multicore e prioridades. Declarar essas exclusões é indispensável: um modelo sem bloqueio não demonstra o comportamento de tarefa que aguarda disco ou rede.

## Estados pronto, executando, bloqueado e despacho

Uma tarefa pode estar *pronta* para executar, *executando* no núcleo, ou *bloqueada* aguardando algum evento. O escalonador escolhe dentre as prontas. O despachante e o mecanismo de **troca de contexto** salvam e restauram o estado necessário. Selecionar uma tarefa bloqueada não faz sua operação de entrada/saída terminar: é necessário que ela volte a ficar pronta.

**Preempção** interrompe a execução antes de terminar um burst de CPU. Um timer pode produzir vencimento de quantum, mas esse evento não implementa sozinho a troca segura. O xv6 exige coordenação de locks, contexto de execução e pilha do escalonador [2]. Escolher quem recebe CPU de maneira justa não corrige acesso à memória compartilhada sem sincronização.

## Modelo de tempo e contrato da fila

Aceitamos sequência finita de \`Job(name, arrival, burst)\`. Chegada é inteiro não negativo; burst é inteiro estritamente positivo. Nomes não podem ser vazios, repetidos nem conter espaços nas extremidades. O Python \`bool\` não é aceito como parâmetro de tempo. Há exatamente **um processador**, sem bloqueios ou bursts adicionais.

O contrato de desempate é determinístico: chegadas simultâneas respeitam a **ordem de entrada**. **FCFS** executa a tarefa mais antiga até terminar, sem preempção. **Round Robin** remove a primeira tarefa da fila, executa \`min(quantum, remaining)\` e devolve as incompletas ao final. Quando uma tarefa chega **no mesmo instante** do fim de quantum, ela entra na fila **antes** de reencaminhar a tarefa antiga. Outras convenções válidas produziriam cronogramas diferentes; a escolha deve ser documentada [1].

Não registramos intervalo ocioso como fatia executada. O custo de troca de contexto é **zero no modelo**, inclusive em fatias consecutivas da mesma tarefa. Portanto os tempos representam unidades abstratas e não milissegundos efetivamente medidos.

## FCFS e Round Robin com invariantes verificáveis

FCFS ordena \`(chegada, índice_original)\`, avança o relógio quando não há trabalho e executa cada job uma vez. Round Robin mantém \`remaining\`, uma \`deque\` de identificadores prontos e o cursor de chegada. A \`deque\` permite retirar da frente e inserir no fim da fila FIFO de maneira eficiente [3].

~~~python
from collections import deque
from dataclasses import dataclass

@dataclass(frozen=True)
class Job:
    name: str
    arrival: int
    burst: int

@dataclass(frozen=True)
class Slice:
    name: str
    start: int
    end: int

def validate_jobs(jobs):
    items = tuple(jobs)
    seen = set()
    for j in items:
        if not isinstance(j, Job):
            raise ValueError("expected Job")
        if not isinstance(j.name, str) or not j.name.strip() or j.name != j.name.strip() or j.name in seen:
            raise ValueError("duplicate or invalid name")
        if type(j.arrival) is not int or j.arrival < 0 or type(j.burst) is not int or j.burst <= 0:
            raise ValueError("arrival >= 0 and burst > 0 must be integers")
        seen.add(j.name)
    return items

def fcfs(jobs):
    items = validate_jobs(jobs)
    order = sorted(enumerate(items), key=lambda pair: (pair[1].arrival, pair[0]))
    time = 0
    trace = []
    for _, job in order:
        time = max(time, job.arrival)
        trace.append(Slice(job.name, time, time + job.burst))
        time += job.burst
    return tuple(trace)

def round_robin(jobs, quantum):
    items = validate_jobs(jobs)
    if type(quantum) is not int or quantum <= 0:
        raise ValueError("positive integer quantum required")
    order = sorted(enumerate(items), key=lambda pair: (pair[1].arrival, pair[0]))
    remaining = {j.name: j.burst for j in items}
    ready = deque()
    result = []
    time = cursor = finished = 0
    while finished < len(items):
        if not ready:
            time = max(time, order[cursor][1].arrival)
            while cursor < len(order) and order[cursor][1].arrival <= time:
                ready.append(order[cursor][1].name)
                cursor += 1
        name = ready.popleft()
        duration = min(quantum, remaining[name])
        result.append(Slice(name, time, time + duration))
        time += duration
        remaining[name] -= duration
        # Arrivals at a quantum boundary precede requeue of the old task.
        while cursor < len(order) and order[cursor][1].arrival <= time:
            ready.append(order[cursor][1].name)
            cursor += 1
        if remaining[name]:
            ready.append(name)
        else:
            finished += 1
    return tuple(result)

jobs = (Job("A", 0, 5), Job("B", 1, 2), Job("C", 3, 1))
assert fcfs(jobs) == (Slice("A", 0, 5), Slice("B", 5, 7), Slice("C", 7, 8))
assert round_robin(jobs, 2) == (
    Slice("A", 0, 2), Slice("B", 2, 4), Slice("A", 4, 6),
    Slice("C", 6, 7), Slice("A", 7, 8))
assert fcfs(()) == round_robin((), 1) == ()
assert round_robin((Job("late", 5, 2),), 1) == (
    Slice("late", 5, 6), Slice("late", 6, 7))
~~~

**Invariante de Round Robin:** antes de selecionar a próxima tarefa, a fila contém todas as tarefas chegadas, ainda não concluídas e fora da CPU, cada uma uma única vez, na ordem de entrada na fila. Para cada tarefa, \`remaining + soma(duração das fatias já executadas) = burst_original\`. Toda fatia positiva reduz a soma do trabalho restante; um conjunto finito de bursts finitos termina. O cursor de chegadas avança monotonicamente e não processa a mesma entrada duas vezes.

No exemplo FCFS, A executa 0–5, B 5–7 e C 7–8. Em RR com quantum 2 temos A(0–2), B(2–4), A(4–6), C(6–7), A(7–8). C já espera no instante 4, mas A estava na fila antes dela; no instante 6, C está à frente da última fatia de A. Uma tarefa isolada pode possuir fatias consecutivas no traço sem produzir troca de contexto real.

Para \`n\` jobs, ordenar chegadas custa \`O(n log n)\`; cada chegada é lida uma vez. Definindo \`s=soma(ceil(burst_i/quantum))\` como limite de fatias, RR executa em \`O(n log n+s)\` e usa \`O(n+s)\` de memória incluindo o traço, admitindo identificadores limitados e dicionários com custo médio constante. Esse é o custo do **simulador**; o trabalho de CPU representado é \`soma(burst_i)\`, outra medida.

## Resposta, espera e turnaround não são sinônimos

Para tarefa \`i\`, sejam \`a_i\` a chegada, \`f_i\` a primeira execução, \`c_i\` a conclusão e \`b_i\` seu burst total:

- **Resposta** \`= f_i - a_i\`: demora até receber CPU pela primeira vez.
- **Turnaround** \`= c_i - a_i\`: tempo decorrido até concluir.
- **Espera** \`= turnaround - b_i\`: tempo sem CPU **neste modelo sem I/O**.

Quando uma tarefa real bloqueia aguardando I/O, \`turnaround - CPU\` inclui bloqueios e não mede apenas a espera na fila de prontos. A primeira concessão de CPU também não equivale à latência para entregar uma resposta HTTP. Toda métrica precisa declarar o fenômeno medido [1].

~~~python
def scheduling_metrics(jobs, trace):
    items = validate_jobs(jobs)
    first, finish = {}, {}
    used = {job.name: 0 for job in items}
    for segment in trace:
        if segment.name not in used or segment.end <= segment.start:
            raise ValueError("invalid slice")
        first.setdefault(segment.name, segment.start)
        finish[segment.name] = segment.end
        used[segment.name] += segment.end - segment.start
    if any(used[j.name] != j.burst for j in items):
        raise ValueError("trace lacks requested CPU service")
    return {
        j.name: (first[j.name] - j.arrival,
                 finish[j.name] - j.arrival - j.burst,
                 finish[j.name] - j.arrival)
        for j in items
    }

assert scheduling_metrics(jobs, fcfs(jobs)) == {
    "A": (0, 0, 5), "B": (4, 4, 6), "C": (4, 4, 5)}
assert scheduling_metrics(jobs, round_robin(jobs, 2)) == {
    "A": (0, 3, 8), "B": (1, 1, 3), "C": (3, 3, 4)}
~~~

Os resultados mostram que melhorar a primeira resposta não garante melhora no turnaround. Sob RR, B recebe CPU uma unidade após chegar, mas A termina depois do que em FCFS. A função de métricas valida o total de serviço executado, mas sozinha **não prova** que o cronograma respeita chegadas nem ausência de sobreposição. Os testes independentes conferem ambos os pontos.

## Efeito comboio e políticas de trabalhos curtos

Considere três tarefas chegando juntas: A=6, B=1, C=1 unidades. FCFS em ordem A–B–C conclui nos instantes 6, 7 e 8, produzindo turnaround médio \`(6+7+8)/3 = 7\`; os tempos de primeira resposta são 0, 6 e 7. RR com quantum 1 executa inicialmente A, B e C e permite resposta antecipada para B e C. A tarefa longa A, em compensação, termina mais tarde. Trata-se do **efeito comboio** sob FCFS [1].

**Shortest Job First** (SJF) escolhe o menor burst conhecido dentre as tarefas disponíveis; **Shortest Remaining Time First** (SRTF) é a variante preemptiva. Podem melhorar o turnaround médio em cargas específicas, mas exigem informação ou estimativa sobre o tamanho das tarefas. Chegadas contínuas de trabalho pequeno podem postergar indefinidamente uma tarefa longa. Média baixa não significa justiça universal.

## Starvation, quantum e custo da troca

Para conjunto finito de tarefas CPU-bound prontas, bursts positivos finitos, quantum positivo finito e fila circulando corretamente, todas recebem serviço sob o RR **deste modelo**. Essa propriedade não promete limite universal em caso de chegadas ilimitadas, prioridades superiores permanentes, bloqueios ou defeitos no escalonador. A análise de starvation requer hipóteses explícitas de carga e admissão.

Quanta muito curtos ampliam oportunidades de resposta, mas geram mais trocas de contexto com custo de CPU e perturbação de caches ou traduções. Quanta grandes se aproximam de FCFS quando os bursts cabem em uma fatia, economizando trocas mas prejudicando interatividade. Não contabilizamos esses custos. **Não existe quantum universalmente ideal** independentemente da carga e do hardware [1][2].

## Limitações do simulador

Não existem controladores de interrupção, timer de kernel, salvamento de registradores, troca de memória virtual, locks de escalonamento, fila por CPU, herança de prioridade, deadlines ou migração multicore. O programa testado **não é um escalonador de sistema operacional**. Tampouco comprova ausência de starvation sob qualquer sequência futura de chegadas.

O teste compara o simulador com **oráculo independente por unidade de tempo**, em vez de repetir sua lógica orientada a eventos. A verificação cobre intervalos ociosos, empates, chegadas no fim do quantum, conservação de CPU e métricas por tarefa. São domínios finitos exaustivos, não provas formais de todos os casos nem medição em hardware real.

## Exercícios e verificação

1. Calcule manualmente as cinco fatias de RR e as métricas de A(0,5), B(1,2), C(3,1), comparando com o código somente depois.
2. Alterne o quantum para 1 e 10. Quais tarefas chegam antes de outras? Quando RR coincide com FCFS?
3. Adicione tarefas exatamente no fim de quantum. Inverta a convenção de desempate e registre as diferenças de cronograma.
4. Calcule as primeiras respostas do exemplo A=6, B=1, C=1 em FCFS e RR com quantum 1.
5. Introduza período ocioso antes da primeira chegada e diferencie tempo transcorrido de CPU efetivamente usada.
6. Adicione estados bloqueados e demonstre por que a fórmula anterior não representa mais exclusivamente a espera na fila de prontos.
7. Introduza custo de troca de contexto e decida quando fatias adjacentes da mesma tarefa necessitam troca.
8. Construa fluxo adversarial de chegadas para SJF e proponha invariante de aging ou serviço mínimo que reduza starvation.

**Continuação:** [concorrência e sincronização](/pt/topics/concurrency-synchronization/) mostra a correção necessária sob intercalações, e [processos e memória virtual](/pt/topics/processes-virtual-memory/) descreve isolamento e limites do kernel. Sistemas de arquivos, I/O, escalonadores de deadlines e balanceamento multicore exigem aprofundamentos separados [1][2][3].
