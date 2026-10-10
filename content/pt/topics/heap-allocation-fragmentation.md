---
id: heap-allocation-fragmentation
title: "Alocação de memória: listas livres, fragmentação e coalescência"
description: "Modele alocação first-fit e best-fit, blocos livres, fragmentação interna e externa, divisão e coalescência com testes independentes."
category: operating-systems
difficulty: intermediate
updated: 2026-10-10
prerequisites: [processes-virtual-memory]
sources:
  - {title: "Operating Systems: Three Easy Pieces — Memory and Free-Space Management", url: "https://pages.cs.wisc.edu/~remzi/OSTEP/", kind: "university textbook"}
  - {title: "Linux kernel — Physical Memory", url: "https://www.kernel.org/doc/html/latest/mm/physical_memory.html", kind: "official kernel documentation"}
  - {title: "Linux kernel — Memory Management APIs", url: "https://www.kernel.org/doc/html/latest/core-api/mm-api.html", kind: "official kernel API reference"}
---
A alocação de memória pode designar pelo menos três coisas: o programa solicita espaço para **objetos** ao runtime ou à biblioteca; o processo obtém **regiões de endereços virtuais**; e o kernel escolhe **páginas físicas** para sustentar mapeamentos. Essas camadas se relacionam, mas não são sinônimas. Um alocador de arena contígua não implementa diretamente uma tabela de páginas e tampouco escolhe os quadros físicos de uma página virtual [1][2][3].

Vamos construir um modelo delimitado: uma **arena fixa, endereçada por unidades equivalentes a bytes**. Ele implementa first-fit e best-fit com divisão de blocos; liberação com coalescência de espaços adjacentes; e, separadamente, arredondamento de reservas. O código tem contratos verificáveis, mas não substitui `malloc`, o alocador de páginas do Linux nem um subsistema de memória seguro para concorrência.

## Quais informações um alocador mantém

Considere um espaço lógico `[0,N)`, com `N` positivo. Cada alocação viva é um **intervalo semiaberto** `[inicio,inicio+tamanho)`: inclui o início e exclui o final. Assim, `[4,8)` e `[8,11)` são adjacentes sem sobreposição. Os blocos livres seguem a mesma convenção.

Uma **lista de blocos livres** representa as regiões disponíveis. Uma **tabela de alocações** associa um identificador à região reservada. Aqui usamos labels legíveis; alocadores nativos precisam relacionar metadados a endereços retornados e garantir seus próprios contratos de validade [1].

Seguem três invariantes de conservação:

1. Todo endereço em `[0,N)` pertence **exatamente a um** bloco livre ou a uma alocação viva.
2. Alocações vivas não se sobrepõem; intervalos livres não se sobrepõem.
3. A soma dos comprimentos de blocos livres e vivos é sempre `N`.

A implementação mantém blocos livres **ordenados por endereço inicial** e combina vizinhos livres após cada liberação. Por isso, dois registros livres consecutivos não podem se sobrepor **nem ser adjacentes** na representação final. Essa normalização permite inspecionar fragmentação sem depender de inferência visual.

## Fragmentação externa e interna são problemas diferentes

A **fragmentação externa** aparece quando há espaço livre total suficiente, mas não existe **um único intervalo contíguo** capaz de atender à solicitação. Buracos `[0,4)` e `[8,12)` somam oito unidades, porém uma solicitação de cinco unidades contíguas falha. Buracos distantes não se juntam sem mover objetos vivos, admitir armazenamento não contíguo ou mudar a abstração de endereçamento [1].

Exibiremos a estatística `(livre_total, maior_bloco, fora_do_maior)`, com `fora_do_maior=livre_total-maior_bloco`. O terceiro campo mede unidades livres **fora do maior buraco**, não um indicador universal de fragmentação nem memória inutilizável para qualquer solicitação. Várias requisições pequenas podem aproveitar diferentes buracos.

A **fragmentação interna** ocorre quando uma reserva é maior que o payload solicitado, por exigências de alinhamento, classes de tamanhos, páginas ou metadados. Um payload de 13 unidades reservado numa classe de 16 desperdiça três unidades **dentro da reserva**. O modelo de lista livre abaixo reserva exatamente a quantidade pedida, ignora cabeçalhos e alinhamento e, portanto, apresenta **fragmentação interna igual a zero por construção**. Em seguida analisaremos arredondamento em modelo distinto.

## First-fit e best-fit: duas políticas, mesmos invariantes

**First-fit** percorre os buracos por endereço crescente e seleciona o *primeiro* que comporta a solicitação. **Best-fit** percorre todos e escolhe o menor buraco suficiente; em empate, usa o menor endereço. Ambos dividem um bloco grande, entregando o prefixo de menor endereço e conservando o sufixo livre [1].

Com um buraco de sete unidades no endereço zero e outro de cinco no endereço nove, uma solicitação de quatro vai para **0** por first-fit e para **9** por best-fit. Não significa que best-fit seja sempre superior: preservar um buraco grande pode ajudar depois, mas também se podem gerar resíduos muito pequenos, com mais custo de busca. Nenhuma política garante fragmentação mínima em toda sequência de eventos.

O método devolve endereço ou `None` se não há bloco adequado, **sem modificar o estado quando falha por falta de espaço**. Solicitações de tamanho inválido ou identificador ainda alocado geram `ValueError`; liberar identificador desconhecido gera `KeyError`. O nome fica reutilizável depois da liberação. Como `bool` é subtipo de `int` em Python, fazemos verificação estrita para não aceitar `True` como tamanho um.

## Implementação de arena contígua com divisão e coalescência

~~~python
class ArenaAllocator:
    def __init__(self, capacity, policy="first"):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        if policy not in ("first", "best"):
            raise ValueError("policy must be first or best")
        self.capacity = capacity
        self.policy = policy
        self.free_blocks = [(0, capacity)]
        self.allocated = {}

    def allocate(self, label, size):
        if (not isinstance(label, str) or not label.strip()
                or label != label.strip() or label in self.allocated):
            raise ValueError("invalid or duplicate label")
        if type(size) is not int or size <= 0:
            raise ValueError("size must be a positive integer")
        choice = None
        for index, (start, length) in enumerate(self.free_blocks):
            if length < size:
                continue
            if self.policy == "first":
                choice = index
                break
            if choice is None:
                choice = index
            else:
                old_start, old_length = self.free_blocks[choice]
                if (length, start) < (old_length, old_start):
                    choice = index
        if choice is None:
            return None
        start, length = self.free_blocks.pop(choice)
        if length > size:
            self.free_blocks.insert(choice, (start + size, length - size))
        self.allocated[label] = (start, size)
        return start

    def release(self, label):
        if label not in self.allocated:
            raise KeyError(label)
        block = self.allocated.pop(label)
        self.free_blocks.append(block)
        self.free_blocks.sort()
        merged = []
        for start, length in self.free_blocks:
            if merged and merged[-1][0] + merged[-1][1] == start:
                previous_start, previous_length = merged[-1]
                merged[-1] = (previous_start, previous_length + length)
            else:
                merged.append((start, length))
        self.free_blocks = merged

    def stats(self):
        total = sum(length for _, length in self.free_blocks)
        largest = max((length for _, length in self.free_blocks), default=0)
        return (total, largest, total - largest)

arena = ArenaAllocator(16)
assert [arena.allocate(k, 4) for k in "ABCD"] == [0, 4, 8, 12]
arena.release("A")
arena.release("C")
assert arena.free_blocks == [(0, 4), (8, 4)]
assert arena.stats() == (8, 4, 4)
assert arena.allocate("E", 5) is None  # 8 free units; no 5-unit span
arena.release("B")
assert arena.free_blocks == [(0, 12)]
assert arena.allocate("E", 8) == 0
assert arena.stats() == (4, 4, 0)

def policy_example(policy):
    a = ArenaAllocator(20, policy)
    for label, size in (("A", 7), ("B", 2), ("C", 5), ("D", 2), ("E", 4)):
        a.allocate(label, size)
    a.release("A")
    a.release("C")
    return a.allocate("F", 4)

assert policy_example("first") == 0
assert policy_example("best") == 9
~~~

Na arena de 16 unidades, quatro blocos inicialmente ocupam todo o espaço. Liberar A e C cria dois buracos desconectados de quatro unidades. A tentativa de reservar cinco falha e **não altera** o estado. Liberar B une os intervalos vizinhos `[0,4)`, `[4,8)` e `[8,12)` em `[0,12)`, permitindo reservar oito unidades. Coalescência **não move** objetos vivos; ela só combina espaço livre que já é adjacente. Um compactador de objetos móveis exigiria outro contrato para ponteiros e referências [1].

A ordem das atualizações é importante: alocar valida parâmetros antes de tocar no estado; localiza buraco suficiente antes de remover; divide e registra a reserva. Liberar verifica o identificador, devolve o intervalo, ordena e combina. Como a liberação recupera uma reserva da tabela de vivos, repetir a liberação gera `KeyError`, não uma segunda região livre. Isso não equivale a defesa contra escrita fora de limites ou ponteiros arbitrários de um alocador nativo.

## Conservação de memória e análise de complexidade

Sejam `h` a quantidade de buracos e `a` a de alocações vivas:

- **First-fit:** busca sequencial até o primeiro bloco adequado; `O(h)` no pior caso. O `insert/pop` de uma lista Python também pode deslocar até `h` posições.
- **Best-fit:** precisa avaliar todos os `h` buracos, com `O(h)` tempo neste modelo de comparações de custo limitado; não há superioridade universal de fragmentação.
- **Liberação:** insere, ordena até `h+1` registros e percorre para coalescer. Custa `O(h log h)` nesta implementação simples.
- **Metadados:** `O(h+a)` de espaço adicional. `capacity` descreve endereços lógicos; a classe **não** aloca um `bytearray` físico de `N` unidades.

São limites da **simulação em Python**, admitindo identificadores de tamanho limitado e buscas médias constantes em dicionários. Alocadores de produção podem empregar árvores, classes de tamanho, slabs, sistema buddy ou estruturas por thread/CPU, com outros compromissos de latência, sincronização, segurança e pressão de memória [2][3]. Não basta medir a busca em uma lista para estimar o desempenho de `malloc` ou do kernel.

## Arredondamento de reserva e fragmentação interna

Com granularidade fixa `g`, um payload `x` requer no modelo a reserva `g × ceil(x/g)`. A diferença é espaço ocioso **interno** da região reservada. Isso pode representar classes de tamanho ou reserva por página, mas **não** descreve completamente alinhamento ou metadados de uma implementação específica de `malloc` [3].

~~~python
def rounded_reservation(payload, granularity):
    if (type(payload) is not int or payload <= 0
            or type(granularity) is not int or granularity <= 0):
        raise ValueError("positive integer sizes required")
    reserved = ((payload + granularity - 1) // granularity) * granularity
    return (reserved, reserved - payload)

assert rounded_reservation(13, 8) == (16, 3)
assert rounded_reservation(4096, 4096) == (4096, 0)
assert rounded_reservation(4097, 4096) == (8192, 4095)
~~~

Com payload 4097 e unidades de 4096, a reserva é 8192, gerando 4095 unidades de slack interno. Duas páginas virtuais **não precisam estar em quadros físicos adjacentes**; reservar duas páginas não pressupõe um bloco físico contíguo de 8192 bytes. O capítulo de [memória virtual](/pt/topics/processes-virtual-memory/) explica tradução e permissões independentemente da política de reserva.

## Buddy, slab e as fronteiras do Linux real

O alocador de páginas físicas do Linux organiza blocos por **ordens em potências de dois**, dividindo ordens maiores quando necessário. Blocos buddy correspondentes podem ser recombinados quando livres. Escolhas reais dependem também de zonas, migratetypes, reclaim e outras condições do kernel [2]. Informações como `/proc/buddyinfo` permitem investigar escassez de blocos de ordem elevada; a arena aqui implementada tem comprimentos arbitrários e **não é um alocador buddy**.

Para objetos de kernel, APIs como `kmalloc`, `vmalloc` e `kvmalloc` assumem contratos diferentes de continuidade de memória e contexto de alocação. `vmalloc` pode devolver intervalo **virtualmente contíguo** sem quadros físicos adjacentes; `kvmalloc` permite caminhos alternativos de alocação [3]. Fragmentação de páginas físicas, fragmentação de heap e slack de reservas paginadas são conceitos relacionados, não a mesma métrica.

Também há a questão do **ciclo de vida**: usar memória depois de liberar, liberar duas vezes, calcular tamanhos incorretos e corromper ponteiros são falhas de correção ou segurança, não somente fragmentação. Coleta de lixo e compactação móvel tratam outros aspectos, com custos e pressupostos próprios.

## Testes independentes e limites do experimento

Os testes associados usam um **oráculo por bitmap** no qual cada endereço possui um proprietário ou está livre, em vez de reutilizar a lista de intervalos do exemplo. Enumeram históricos curtos para as duas políticas, verificam endereços escolhidos, reconstroem os intervalos livres após cada operação e asseguram conservação de espaço. Incluem solicitações inválidas, falta legítima de espaço, reutilização do identificador liberado, coalescência e estados cheios/vazios.

A concordância no domínio finito fornece evidência do contrato, não prova de segurança sob entradas arbitrárias, corrida de threads, heaps infinitos, corrupção de metadados ou ordenação de memória física. O simulador não guarda bytes de payload, não expõe ponteiros reais, não limpa conteúdo liberado e não é thread-safe. Seus testes não substituem medições reais de alocadores.

## Exercícios e verificação

1. A partir de 16 unidades, reserve quatro blocos de quatro. Libere A e C. Deduza a lista livre e prove por que solicitar cinco falha apesar de haver oito unidades livres.
2. Libere B na sequência anterior. Mostre cada etapa da coalescência, calcule `livre_total`, `maior_bloco` e `fora_do_maior`, e comprove que D não se deslocou.
3. Construa histórico com buracos de sete e cinco unidades. Preveja endereços de first-fit e best-fit para solicitação de quatro; explique por que isso não prova superioridade geral.
4. Demonstre a igualdade de conservação após toda reserva ou liberação. Qual outro invariante seria necessário para gerenciar ponteiros reais?
5. Calcule reserva e slack para payloads 1, 8, 9 e 16, com granularidade oito. Explique por que não devemos somar indiscriminadamente esse slack à fragmentação externa.
6. Altere a implementação para garantir endereços alinhados a oito unidades **sem mover blocos já vivos**. Que alterações surgem na divisão de prefixos e sufixos?
7. Explique diferenças de política e tamanho entre alocador buddy e first-fit; indique quando `vmalloc` elimina a necessidade de contiguidade física.
8. Proponha teste que injete labels e tamanhos inválidos, provando que qualquer operação rejeitada não modifica listas livres nem reservas vivas.

**Continuação:** o próximo tópico de sistemas operacionais deverá cobrir **descritores de arquivos e I/O**, incluindo diferenças entre buffering, offsets e persistência. O capítulo de [processos](/pt/topics/processes-virtual-memory/) dá os conceitos de kernel, e [WAL](/pt/topics/database-storage-wal/) analisa durabilidade em outra camada [1][2][3].
