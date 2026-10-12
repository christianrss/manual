---
id: abstract-data-types-representation-invariants
title: "Tipos abstratos de dados: interfaces, invariantes e custos"
description: "Separe o contrato do TAD da representação e derive uma fila circular limitada com provas de FIFO e complexidade."
category: algorithms
difficulty: foundational
updated: 2026-10-12
prerequisites: [data-types-bytes-and-representation, arrays-and-strings, complexity-analysis]
sources:
  - {title: "Open Data Structures — Interfaces", url: "https://opendatastructures.org/ods-python/1_2_Interfaces.html", kind: "university-level open textbook"}
  - {title: "Open Data Structures — Array-Based Lists", url: "https://opendatastructures.org/ods-python/2_Array_Based_Lists.html", kind: "university-level open textbook"}
  - {title: "Python standard library — collections.deque", url: "https://docs.python.org/3/library/collections.html#collections.deque", kind: "official language documentation"}
---
Uma **estrutura de dados** organiza valores na memória; um **tipo abstrato de dados (TAD)** especifica operações e resultados observáveis pelo consumidor. Uma fila pode utilizar array, nós ligados ou deque da biblioteca sem alterar seu contrato FIFO. Escolher representação antes de especificar operações confunde interface e implementação [1]. A competência fundamental é derivar regras de armazenamento a partir do comportamento pretendido, em vez de decorar uma implementação.

## Contratos antes de classes e coleções

Pilha remove o valor inserido por último (LIFO); fila remove o mais antigo ainda presente (FIFO). Conjunto registra pertinência sem ocorrências duplicadas independentes. Mapa associa chaves a valores. Lista admite acesso por índice e atualizações posicionais. Esses contratos são distintos mesmo que diferentes implementações usem fisicamente arrays semelhantes [1].

Para uma fila limitada, defina capacidade inteira positiva C, inclusão que falha se estiver cheia e remoção que falha se estiver vazia. Consulta ao primeiro item não o remove; tamanho devolve a quantidade de elementos ativos. A fila aceita qualquer objeto Python, inclusive None. Portanto, None isoladamente não serve para indicar fila vazia; o estado vazio precisa estar separado do conteúdo dos elementos.

## Derive a representação por array circular

Aloque C posições e mantenha índice h do elemento mais antigo e tamanho lógico n. O invariante numérico é 0 ≤ n ≤ C e 0 ≤ h < C. O elemento da posição abstrata i, com 0 ≤ i < n, ocupa fisicamente o índice (h+i) mod C. Esse é um **invariante de representação**: estabelece a correspondência entre sequência pública e buffer privado.

Com C=4, h=2 e n=3, os índices ocupados são 2, 3 e 0. A próxima inclusão escreve em (2+3) mod 4 = 1. Nenhum valor precisa ser deslocado. Em contraste, remover a primeira posição de uma lista Python geralmente desloca referências das posições posteriores. Indexação circular implementa operações FIFO constantes sobre array fixo, sem mudar o comportamento abstrato [2].

Posições físicas desocupadas podem conter None, da mesma forma que uma posição ocupada pode guardar None inserido intencionalmente. Cabeça e tamanho determinam ocupação lógica. Essa distinção evita confundir elemento legítimo com sentinela de espaço vazio.

## Construa cada operação a partir do invariante

Na inclusão, rejeite quando n=C; caso contrário escreva na cauda (h+n) mod C e aumente n. As posições lógicas anteriores permanecem iguais e um novo elemento aparece no final. Na remoção, rejeite quando n=0; caso contrário leia h, libere a referência, avance h para (h+1) mod C e diminua n. Somente o primeiro elemento lógico desaparece; os demais preservam sua ordem.

Limpar a referência retirada pode reduzir a retenção desnecessária de objetos num runtime com coletor de lixo. Isso não define a correção FIFO, pois a ocupação é dada pelo contador. Quando C=1, o índice permanece zero, mas o tamanho ainda diferencia cheia e vazia. Essa condição de borda permite detectar erros de aritmética entre cabeça e cauda.

~~~python
class BoundedQueue:
    def __init__(self, capacity):
        if type(capacity) is not int or capacity <= 0:
            raise ValueError("invalid capacity")
        self._slots = [None] * capacity
        self._head = 0
        self._size = 0

    def __len__(self):
        return self._size

    def enqueue(self, value):
        if self._size == len(self._slots):
            raise OverflowError("queue full")
        tail = (self._head + self._size) % len(self._slots)
        self._slots[tail] = value
        self._size += 1

    def dequeue(self):
        if not self._size:
            raise IndexError("queue empty")
        value = self._slots[self._head]
        self._slots[self._head] = None
        self._head = (self._head + 1) % len(self._slots)
        self._size -= 1
        return value

    def peek(self):
        if not self._size:
            raise IndexError("queue empty")
        return self._slots[self._head]

    def snapshot(self):
        capacity = len(self._slots)
        return tuple(self._slots[(self._head + i) % capacity]
                     for i in range(self._size))

q = BoundedQueue(2)
q.enqueue("A")
q.enqueue(None)
assert q.snapshot() == ("A", None)
assert q.dequeue() == "A"
q.enqueue("B")
assert q.snapshot() == (None, "B")
assert q.peek() is None
assert q.dequeue() is None and q.dequeue() == "B"
assert len(q) == 0
try:
    q.dequeue()
except IndexError:
    pass
else:
    raise AssertionError("empty dequeue succeeded")
~~~

## Demonstre a preservação do contrato

Inicialmente n=0 e h=0, logo os limites valem e a sequência abstrata está vazia. Suponha o invariante verdadeiro antes de uma inclusão bem-sucedida. Como n<C, a cauda é a primeira posição após os n elementos lógicos. Gravar ali e aumentar n preserva a sequência anterior e acrescenta o valor novo. Uma remoção exige n>0; avançar a cabeça faz cada posição lógica antiga i+1 virar a nova posição i. Isso prova que somente o elemento mais antigo foi retirado.

Consultar o primeiro elemento ou o tamanho não modifica estado. Numa tentativa inválida, a exceção é lançada **antes** de alterar buffer, cabeça ou tamanho. Indução sobre sequências de operações estabelece equivalência a uma lista FIFO abstrata, desde que não se corrompam diretamente os atributos internos. Sublinhados em Python expressam convenção, não privacidade obrigatória.

## Calcule custos e compare representações

Inclusão, remoção, consulta e tamanho executam número fixo de operações aritméticas e referências, portanto O(1) tempo no modelo RAM. Produzir snapshot de n elementos exige O(n) tempo e O(n) referências adicionais. O buffer reserva O(C) posições mesmo vazio. Essa implementação **não** cresce automaticamente; incluir quando cheia provoca erro.

Um array dinâmico admite append amortizado O(1), mas pode realizar O(n) trabalho em realocação. Uma fila ligada com cabeça e cauda admite operações O(1) nas extremidades, mas aloca um nó para cada elemento. A biblioteca collections.deque oferece operações eficientes nas extremidades e normalmente é preferível em aplicações comuns [3]. A fila circular limitada permanece útil para compreender invariantes e contratos de capacidade rígida.

| Necessidade | Possível estrutura | Custo relevante |
| --- | --- | --- |
| FIFO com capacidade fixa | Buffer circular | O(C) posições reservadas |
| FIFO com capacidade variável | Deque ou lista ligada | Crescimento ou custo dos nós |
| Acesso por posição | Array dinâmico | O(1) índice, deslocamento na inclusão |
| Busca por chave | Tabela hash | Tempo esperado constante sob hipóteses |
| Maior prioridade primeiro | Heap | Atualização logarítmica, não FIFO |

Complexidade caracteriza operações sob hipóteses, não uma classificação universal. Memória real também depende de referências, alocador, localidade de cache e tamanho dos elementos.

## Verificação independente e contraexemplos

Uma lista serve de modelo de referência simples: append insere no final e pop(0) remove o mais antigo. Embora a remoção custe O(n), o modelo é claro para testes curtos. Enumere pequenas sequências de operações nas duas implementações e compare retorno, exceção, tamanho e conteúdo lógico após cada etapa. Inclua retorno ao começo do buffer, None, erros repetidos e capacidade um.

A fila não serve se uma carga sem limite precisar aceitar toda inclusão; a política de capacidade faz parte do TAD. A prova também não estabelece segurança entre threads: operações concorrentes de leitura e atualização podem se intercalar. FIFO não garante persistência, entrega por rede nem prioridade. São contratos separados. Um snapshot raso copia referências dos elementos sem clonar objetos mutáveis, então aliasing continua sendo outra questão.

## Exercícios e verificação

1. Rastreie cabeça, quantidade, posições físicas e sequência lógica após enqueue(A), enqueue(B), dequeue(), enqueue(C) com C=2.
2. Reimplemente a mesma interface usando collections.deque, preservando os erros de capacidade fixa [3].
3. Compare um modelo baseado em lista com a fila circular para todas as sequências de até seis operações e capacidades 1, 2 e 3.
4. Demonstre por que verificar se a posição de cabeça vale None falha quando None é uma entrada permitida.
5. Prove por indução que remover preserva FIFO e os limites numéricos.
6. Modifique a política para sobrescrever o valor mais antigo quando cheia. Explique por que isso muda o contrato público, não apenas o desempenho.

Relacionados: [arrays](/pt/topics/arrays-and-strings/), [listas ligadas](/pt/topics/linked-lists/), [pilhas e filas](/pt/topics/stacks-queues/) e [complexidade](/pt/topics/complexity-analysis/).